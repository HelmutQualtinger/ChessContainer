# 3D Chess vs Stockfish

A fully interactive 3D chess game running in a Docker container. Play against the Stockfish engine through a beautiful Three.js board with realistic lighting, shadows, and procedural sound effects.

## Quick Start

```bash
docker run -d -p 8000:8000 helmutqualtinger/chess3d
```

Open **http://localhost:8000** in your browser.

## Features

- **True 3D board** — Three.js scene with orbit controls (drag to rotate, scroll to zoom), shadow-casting directional lighting, procedural marble textures (cream and green), and a linen tablecloth
- **Glass chess pieces** — Transparent crystal-glass white pieces and dark red glass pieces with physically-based rendering
- **Cognac glasses** — Decorative snifter glasses with visible cognac liquid rendered through physically transparent glass
- **Captured pieces** — Taken pieces are displayed on the tablecloth beside the board
- **Chess clocks** — Bullet (1+0, 2+1), Blitz (3+2, 5+3), Rapid (10+5, 15+10), or Unlimited; defaults to Rapid 10+5
- **Configurable engine strength** — Depth 10 (fast) to 20 (strong)
- **Sound effects** — Procedurally synthesized glass-on-stone sounds via Web Audio API: move, capture, check, castle, game over
- **Play either side** — Swap Sides rotates the camera and lets Stockfish open as white
- **Live evaluation** — Eval bar updates after each move, always oriented from the player's perspective
- **Move indicators** — Green dots for valid moves, red rings for captures
- **Animated moves** — Pieces arc through the air with eased motion
- **Resign and Undo** — Full game controls in the sidebar

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `STOCKFISH_DEPTH` | `20` | Engine search depth |
| `STOCKFISH_THREADS` | `2` | CPU threads |
| `STOCKFISH_HASH` | `256` | Hash table size in MB |

```bash
docker run -d -p 8000:8000 -e STOCKFISH_DEPTH=15 -e STOCKFISH_THREADS=4 helmutqualtinger/chess3d
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves the 3D chess UI |
| `GET` | `/health` | Health check |
| `POST` | `/analyze` | Analyze a FEN position (best move + eval + top 3 lines) |
| `POST` | `/move` | Get Stockfish's best response to a position |
| `POST` | `/uci` | Raw UCI command passthrough |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Engine | Stockfish 17 (via apt) |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | Three.js, Chess.js, Web Audio API |
| Container | Docker |

## Source

[GitHub Repository](https://github.com/HelmutQualtinger/ChessContainer)
