# TileMuse

AI-assisted 2D map design tool: turns a vague idea into an editable, validated Tiled map.
`frontend/` is React + TypeScript (Vite). `backend/` is Python FastAPI. Vite proxies `/api` to the backend.

## Architecture (read before changing the pipeline)

idea → **LLM** → spec → **Pydantic schema** → **deterministic generator** → GameMap → **validator** → Violations → **explainer** → editor. `GameMap` is the internal format every stage shares; Tiled JSON is produced only on export.

- IMPORTANT: The LLM never generates maps or tiles. It only produces the spec. Maps come only from the generator.
- Spec validation (Pydantic, on LLM output) and map validation (gameplay rules) are separate. Don't merge them.
- The validator checks gameplay rules: door reachability (BFS), required objects present, density limits, and spec-specific rules. It runs after generation **and after every edit**, and returns `Violation` objects.
- Tiled JSON format and GID validity are ensured by the export code itself and verified by tests, not checked at runtime by the validator. Exception: imported maps (stretch) are external input and must be format-validated at import.
- The generator is deterministic: same spec + seed gives an identical map. The seed is required. Use no global/unseeded randomness. Pass a seeded RNG explicitly.
- The explainer is template-based (one template per violation code). LLM polish is optional and only rephrases. It must never add, drop, or change violations. Templates are the fallback when the LLM is unavailable.
- Claude API calls happen only in `backend/` (Anthropic Python SDK). Never call the API or expose the key from `frontend/`.

## Module layout

- Backend: one module per pipeline stage in `backend/app/` (`llm`, `generator`, `validator`, `explainer`, `tiled`), each with one public function. Shared contracts live in `models.py` (`GameMap`, `Violation`, `Explanation`) and `spec.py` (`MapSpec`).
- Imports go one way: `api.py` → stages → shared. Stages never import each other; only `api.py` wires them together. If two stages need the same logic, move it into a shared module.
- Frontend: `src/features/*` never import each other. They import only from `src/api/`, and `App.tsx` composes them.
- `frontend/src/api/schema.d.ts` is generated. After changing a backend model or route, run `npm run gen:api` (in `frontend/`, with the backend running) and commit the result.

## Commands

Frontend (run in `frontend/`):
- `npm install` / `npm run dev`
- `npm test` (Vitest). Prefer a single file: `npx vitest run path/to/file.test.ts`
- `npm run lint` (oxlint) and `npx prettier --check .`
- `npm run typecheck` (`tsc -b`; plain `tsc --noEmit` checks nothing with the project references)

Backend (run in `backend/`):
- `uv sync` / `uv run fastapi dev` (serves on :8000)
- `uv run pytest`. Prefer a single test: `uv run pytest tests/test_x.py::test_name`
- `uv run ruff check .` and `uv run ruff format .`
- Use `uv add <pkg>` for dependencies. Never `pip install`.

## Environment

- `ANTHROPIC_API_KEY` goes in `backend/.env` (gitignored). Never commit it or log it.

## Testing

- Generator changes: add or update a fixed-seed test that asserts identical output.
- Validator changes: cover each rule with a passing map and a violating map.
- Before finishing, run lint, typecheck, and tests for whichever side you touched.

## Git

- IMPORTANT: Never commit or push to `main`. Work on a branch and open a PR to `main`.
- Branch names: `<type>/<person>-<issue#>-<short-name>`, e.g. `feat/janedoe-12-tile-editor`
- Types (shared by branches and Conventional Commit messages): `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`
