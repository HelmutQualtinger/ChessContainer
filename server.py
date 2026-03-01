import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from stockfish import Stockfish, StockfishException

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")
STOCKFISH_DEPTH = int(os.getenv("STOCKFISH_DEPTH", "20"))
STOCKFISH_THREADS = int(os.getenv("STOCKFISH_THREADS", "2"))
STOCKFISH_HASH = int(os.getenv("STOCKFISH_HASH", "256"))

sf: Stockfish | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sf
    sf = Stockfish(
        path=STOCKFISH_PATH,
        depth=STOCKFISH_DEPTH,
        parameters={"Threads": STOCKFISH_THREADS, "Hash": STOCKFISH_HASH},
    )
    yield
    if sf:
        del sf


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


class UCIRequest(BaseModel):
    commands: list[str]


class UCIResponse(BaseModel):
    output: str


# ── Endpoints ───────────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse("index.html", media_type="text/html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
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
def get_move(req: MoveRequest):
    try:
        sf.set_fen_position(req.fen)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid FEN position")

    if req.moves:
        try:
            sf.make_moves_from_current_position(req.moves)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid move list")

    depth = req.depth or STOCKFISH_DEPTH
    sf.set_depth(depth)

    best_move = sf.get_best_move()
    evaluation = sf.get_evaluation()

    return MoveResponse(best_move=best_move, evaluation=evaluation)


@app.post("/uci", response_model=UCIResponse)
def uci_passthrough(req: UCIRequest):
    try:
        lines: list[str] = []
        for cmd in req.commands:
            raw = sf._put(cmd)
            if raw:
                lines.append(str(raw))
        return UCIResponse(output="\n".join(lines))
    except StockfishException as e:
        raise HTTPException(status_code=400, detail=str(e))
