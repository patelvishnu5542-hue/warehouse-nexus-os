---
title: Warehouse Nexus OS
sdk: docker
app_port: 7860
base_path: /web
---

# Warehouse Nexus OS

Warehouse order-fulfillment simulation that demonstrates **progression across 3 difficulty levels** and **3 controller modes** (from dumb → logical → real LLM), with a points-based reward system to explain how you can train/optimize agents.

## What to demo (hackathon story)

### Difficulty Levels (environment)
- **Level 1**: 1 worker, static orders, no congestion penalty (easy sandbox)
- **Level 2**: 2 workers, dynamic orders, congestion penalty enabled
- **Level 3**: 5 workers, dynamic orders, higher congestion penalty (coordination is hard)

Levels are configured in `warehouse_env/levels.py`.

### Agent Modes (controllers)
- **Dumb**: mostly `noop()` / random moves (baseline to beat)
- **Logical**: heuristic decision-making (greedy assignment + routing + light de-congestion)
- **Real AI**: LLM via Hugging Face Serverless Inference (requires `HF_TOKEN`)

## Quick start (local)

### 1) Backend (FastAPI)

```bash
cd <repo-root>
PORT=7860 ./venv/bin/python -m server
```

Backend runs on `http://localhost:7860`.

Optional environment variables:
- `API_BASE_URL`: LLM endpoint (default: Hugging Face Serverless Inference)
- `MODEL_NAME`: model identifier (default: `Qwen/Qwen2.5-72B-Instruct`)
- `HF_TOKEN`: Hugging Face / API key (required for AI calls)
- `DEFAULT_LEVEL`: 1/2/3 (default: 2)
- `AGENT_MODE`: dumb/logic/ai (default: logic)

### Run with Docker (what judges use)

Build:

```bash
docker build -t warehouse-openenv .
```

Run:

```bash
docker run --rm -p 7860:7860 -e PORT=7860 warehouse-openenv
```

Open:
- UI: `http://localhost:7860/ui`
- Health: `http://localhost:7860/health`

### 2) Frontend (React + Vite)

```bash
cd <repo-root>/ui
npm install
VITE_API_URL=http://localhost:7860 npm run dev
```

UI runs on `http://localhost:5174`.

## How “points” works (reward shaping)

The backend produces a reward stream (shown in the UI) like:
- `+100` Delivery bonus
- `+20` Pick bonus
- `+0.5 * distance improvement` goal shaping
- `-congestion_penalty * adjacent_workers` congestion penalty

This is implemented in `warehouse_env/logic.py` and exposed in `/reward_logs`.
For OpenEnv compliance, the `/step` endpoint also returns a normalized `reward.value` in `[0, 1]` and includes raw points in `info.raw_points`.

## CLI simulation (no UI)

```bash
cd <repo-root>
ENV_URL=http://localhost:7860 API_BASE_URL=... MODEL_NAME=... HF_TOKEN=... ./venv/bin/python inference.py
```

## Built-in comparison

From the UI:
- Use the **Level** + **Mode** dropdowns to switch scenarios.
- Click **BENCHMARK** to compare Dumb vs Logical vs AI (AI is skipped unless `HF_TOKEN` is set).

From the backend:
- `GET /benchmark?level=3&steps=80&ai_steps=10`
- `POST /config` with `{"level": 2, "mode": "logic"}`

## Notes for submission

- `ui/src/App.jsx` reads the backend URL from `VITE_API_URL`. In production builds it defaults to the same origin (so HF Spaces works without hardcoding localhost).
- Exclude large local artifacts (`venv/`, `ui/node_modules/`, `*.log`) when zipping; `.dockerignore` is included.
- If `ui/dist` exists, the backend serves it at `GET /ui`.

## Run on Hugging Face Spaces

- Space page (human): `https://huggingface.co/spaces/<namespace>/warehouse-nexus-os`
- Runtime URL (validator/inference): `https://<namespace>-warehouse-nexus-os.hf.space`
- Our UI: `https://<namespace>-warehouse-nexus-os.hf.space/ui`

Set these Space variables/secrets (required by the hackathon rules):
- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

## Local pre-validation

With the backend running:

```bash
ENV_URL=http://localhost:7860 python3 prevalidate_local.py
```

## Submission validator (what the judges run)

Your Space must:
- Return HTTP 200 for `POST /reset`
- Build via `docker build .`
- Pass `openenv validate` (from `openenv-core`)

Quick manual checks:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{}'
python3 -m pip install openenv-core
openenv validate
```
