# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Containerized 3D chess application: a Three.js frontend where users play against Stockfish via a FastAPI REST backend. Everything runs in a single Docker container.

## Build & Run

```bash
# Pull from Docker Hub
docker run -d -p 8000:8000 helmutqualtinger/chess3d

# Or build from source (detached)
docker compose up --build -d

# Rebuild after code changes
docker compose up --build -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

The app is available at **http://localhost:8000/**. Health check: `GET /health`.

## Architecture

```
index.html (single-file frontend)
  ├── Three.js 0.162.0  → 3D board, pieces (LatheGeometry), lighting, shadows
  ├── Chess.js 0.10.3   → move validation, FEN, game state
  ├── Web Audio API      → procedural sound effects (no audio files)
  └── Fetch → POST /move, POST /analyze

server.py (FastAPI backend)
  ├── GET /          → serves index.html via FileResponse
  ├── GET /health    → health check
  ├── POST /analyze  → FEN → best move + eval + top 3 lines
  ├── POST /move     → FEN → best response move + eval
  └── POST /uci      → raw UCI command passthrough
  └── Stockfish Python wrapper → /usr/games/stockfish binary
```

**Single container**: Python 3.12-slim base installs Stockfish from apt. Uvicorn serves both the API and the static HTML.

## Key Files

- **server.py** — FastAPI app with Stockfish subprocess managed via lifespan. Pydantic models for request/response. Engine configured via env vars.
- **index.html** — Self-contained ~1300-line HTML/CSS/JS module. Includes 3D scene setup, piece geometry definitions (LatheGeometry profiles + composite knight), raycasting click interaction, move animation, chess clocks, captured pieces display, and procedural audio.
- **Dockerfile** — Installs stockfish from apt, pip installs requirements, copies source, runs uvicorn.
- **docker-compose.yml** — Single `stockfish-server` service on port 8000 with configurable env vars.

## Environment Variables

Configurable in `docker-compose.yml` or via shell:

| Variable | Default | Purpose |
|---|---|---|
| `STOCKFISH_DEPTH` | 20 | Engine search depth |
| `STOCKFISH_THREADS` | 2 | CPU threads for engine |
| `STOCKFISH_HASH` | 256 | Hash table size (MB) |
| `STOCKFISH_PATH` | /usr/games/stockfish | Path to binary |

## Frontend Structure (index.html)

The frontend is a single ES module (`<script type="module">`) using import maps for Three.js. Key sections in order:

1. **Game state** — `playerColor`, `moveHistory`, clock state, piece/square mesh maps
2. **Chess clock** — `initClocks()`, `startClock()`, `stopClockAndIncrement()`, `tickClock()`, `flagged()`
3. **Three.js scene** — Renderer, camera, OrbitControls, lighting (directional + fill + rim + ambient)
4. **Board** — Procedural coarse-weave cloth texture (canvas + normal map), wooden frame, 8×8 square meshes
5. **Piece geometry** — `PIECE_PROFILES` dict with LatheGeometry points per piece type; knight is a composite Group (base + extruded neck/head + cone ears + sphere eyes)
6. **Interaction** — Raycaster click → select piece → show move indicators → click target → `makePlayerMove()`
7. **Sound** — `playSound(type)` synthesizes audio buffers for: move, capture, check, castle, gameover, select
8. **Engine integration** — `askStockfish()` POSTs to `/move`, animates response, manages clocks

## Stockfish Evaluation Convention

The Python `stockfish` library returns evaluation from the **side-to-move's perspective**. The server evaluates the position AFTER making the engine's move (so it's from the player's perspective). The frontend displays the value directly — positive always means good for the player, no sign flip needed.

## Captured Pieces

`getCapturedPieces()` diffs current board material against starting counts. `placeCapturedPieces()` renders scaled-down (0.6) piece meshes on the tablecloth beside the board at table surface height.
