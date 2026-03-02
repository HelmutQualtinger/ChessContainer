import asyncio
import os
import random
import time
from contextlib import asynccontextmanager
from pathlib import Path

import chess
import chess.polyglot
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from stockfish import Stockfish

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")
BOOK_PATH = Path(__file__).parent / "book.bin"
STOCKFISH_DEPTH = int(os.getenv("STOCKFISH_DEPTH", "20"))
STOCKFISH_THREADS = int(os.getenv("STOCKFISH_THREADS", "2"))
STOCKFISH_HASH = int(os.getenv("STOCKFISH_HASH", "256"))

SESSION_TIMEOUT = 30 * 60  # 30 minutes
CLEANUP_INTERVAL = 60  # seconds


class SessionEntry:
    __slots__ = ("sf", "last_used")

    def __init__(self, sf: Stockfish):
        self.sf = sf
        self.last_used = time.monotonic()


sessions: dict[str, SessionEntry] = {}


def create_engine() -> Stockfish:
    return Stockfish(
        path=STOCKFISH_PATH,
        depth=STOCKFISH_DEPTH,
        parameters={"Threads": STOCKFISH_THREADS, "Hash": STOCKFISH_HASH},
    )


def get_engine(session_id: str) -> Stockfish:
    entry = sessions.get(session_id)
    if entry is None:
        entry = SessionEntry(create_engine())
        sessions[session_id] = entry
    entry.last_used = time.monotonic()
    return entry.sf


def cleanup_stale_sessions() -> None:
    now = time.monotonic()
    stale = [sid for sid, e in sessions.items() if now - e.last_used > SESSION_TIMEOUT]
    for sid in stale:
        entry = sessions.pop(sid, None)
        if entry:
            del entry.sf


def shutdown_all_sessions() -> None:
    for entry in sessions.values():
        del entry.sf
    sessions.clear()


async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        cleanup_stale_sessions()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()
    shutdown_all_sessions()


app = FastAPI(title="Stockfish Chess Server", lifespan=lifespan)


# ── Request / Response models ───────────────────────────────────────

class AnalyzeRequest(BaseModel):
    fen: str
    depth: int | None = None


class AnalyzeResponse(BaseModel):
    fen: str
    depth: int
    best_move: str
    evaluation: dict
    top_lines: list[dict] | None = None


class MoveRequest(BaseModel):
    fen: str
    moves: list[str] = []
    depth: int | None = None


class MoveResponse(BaseModel):
    best_move: str
    evaluation: dict


# ── Opening book ───────────────────────────────────────────────────

def book_move(fen: str) -> str | None:
    """Look up a weighted-random move from the polyglot opening book."""
    if not BOOK_PATH.exists():
        return None
    board = chess.Board(fen)
    try:
        with chess.polyglot.open_reader(BOOK_PATH) as reader:
            entries = list(reader.find_all(board))
        if not entries:
            return None
        # Weighted random pick by the book's own weights
        total = sum(e.weight for e in entries)
        r = random.randint(0, total - 1)
        for e in entries:
            r -= e.weight
            if r < 0:
                return e.move.uci()
        return entries[0].move.uci()
    except Exception:
        return None


# ── Helper ─────────────────────────────────────────────────────────

def _session_id(request: Request) -> str:
    sid = request.headers.get("X-Session-ID")
    if not sid:
        raise HTTPException(status_code=400, detail="Missing X-Session-ID header")
    return sid


# ── Endpoints ───────────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse("index.html", media_type="text/html")


@app.get("/health")
def health():
    return {"status": "ok", "active_sessions": len(sessions)}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, request: Request):
    sf = get_engine(_session_id(request))

    try:
        sf.set_fen_position(req.fen)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid FEN position")

    depth = req.depth or STOCKFISH_DEPTH
    sf.set_depth(depth)

    best_move = sf.get_best_move()
    evaluation = sf.get_evaluation()
    top_lines = sf.get_top_moves(3)

    return AnalyzeResponse(
        fen=req.fen,
        depth=depth,
        best_move=best_move,
        evaluation=evaluation,
        top_lines=top_lines,
    )


@app.post("/move", response_model=MoveResponse)
def get_move(req: MoveRequest, request: Request):
    sf = get_engine(_session_id(request))

    try:
        sf.set_fen_position(req.fen)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid FEN position")

    if req.moves:
        try:
            sf.make_moves_from_current_position(req.moves)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid move list")

    # Try opening book first (instant response)
    fen_for_book = req.fen if not req.moves else None
    if fen_for_book:
        bm = book_move(req.fen)
    else:
        # Build FEN after applying moves for book lookup
        board = chess.Board(req.fen)
        for m in req.moves:
            board.push(chess.Move.from_uci(m))
        bm = book_move(board.fen())

    if bm:
        # Use shallow eval for book moves (instant response)
        sf.set_fen_position(req.fen)
        if req.moves:
            sf.make_moves_from_current_position(req.moves)
        sf.make_moves_from_current_position([bm])
        sf.set_depth(8)
        evaluation = sf.get_evaluation()
        return MoveResponse(best_move=bm, evaluation=evaluation)

    depth = req.depth or STOCKFISH_DEPTH
    sf.set_depth(depth)

    best_move = sf.get_best_move()

    # Evaluate the position AFTER the engine's move so the UI shows
    # the correct assessment of what's on the board.
    if best_move:
        sf.make_moves_from_current_position([best_move])
    evaluation = sf.get_evaluation()

    return MoveResponse(best_move=best_move, evaluation=evaluation)


