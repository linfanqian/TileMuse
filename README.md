# TileMuse
An AI-assisted 2D map design tool that turns vague ideas into editable, validated maps.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Node.js 20+.

```sh
# Terminal 1: backend on :8000
cd backend
uv sync
uv run fastapi dev

# Terminal 2: frontend on :5173 (proxies /api to the backend)
cd frontend
npm install
npm run dev
```

Copy `backend/.env.example` to `backend/.env` and set `ANTHROPIC_API_KEY` once the LLM stage is implemented.
