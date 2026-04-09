---
title: Warehouse Nexus OS
sdk: docker
app_port: 7860
---

# Warehouse Nexus OS (OpenEnv Submission)

Warehouse order-fulfillment simulation with **3 levels** (difficulty) and **3 controller modes**:
- `dumb`: weak baseline
- `logic`: heuristic controller
- `ai`: LLM controller (OpenAI client via OpenAI-compatible endpoint)

## Links
- GitHub: `https://github.com/patelvishnu5542-hue/warehouse-nexus-os`
- HF Space: `https://huggingface.co/spaces/Vishnupatel/warehouse-nexus-os`
- Runtime URL: `https://vishnupatel-warehouse-nexus-os.hf.space`

## Required Space Variables/Secrets
- `API_BASE_URL` (recommended): `https://router.huggingface.co/v1`
- `MODEL_NAME` (example): `Qwen/Qwen2.5-72B-Instruct`
- `HF_TOKEN` (secret)

## How it works (high level)
- The env is a multi-agent warehouse grid. Each step you send **one action string per worker**.
- The server applies actions, updates the `State`, and returns:
  - `reward.value` (normalized in `[0,1]`)
  - `info.final_score` (episode score, strictly in `(0,1)`)
- Level affects worker count + difficulty:
  - Level 1: 1 worker
  - Level 2: 2 workers
  - Level 3: 5 workers

## Local (Docker)
```bash
docker build -t warehouse-openenv .
docker run --rm -p 7860:7860 -e PORT=7860 warehouse-openenv
```

Open:
- UI: `http://localhost:7860/ui`
- Health: `http://localhost:7860/health`

## Using the UI
- Open `/ui`
- Use the dropdowns to switch `level` and `mode`
- Click **START** to run the simulation loop
- Click **RESET** to restart the episode

## Runtime Endpoints
- UI: `GET /ui`
- Health: `GET /health` (expects `{"status":"healthy"}`)
- Reset: `POST /reset` (expects HTTP 200)
- Step: `POST /step` (OpenEnv step; actions for all workers)
- State: `GET /state`
- Tasks: `GET /tasks` (3 tasks; one per level)
- Config: `POST /config` (switch level/mode)
- Status: `GET /status`
- Metadata: `GET /metadata` (OpenEnv runtime validation)
- Schema: `GET /schema` (OpenEnv runtime validation)
- MCP: `POST /mcp` (OpenEnv runtime validation)

## Validation (same as judges)
```bash
bash scripts/validate-submission.sh https://vishnupatel-warehouse-nexus-os.hf.space .
```

## Inference script (judge runner)
- `inference.py` is at repo root and emits stdout lines in the required `[START] / [STEP] / [END]` format.
- It uses the OpenAI Python client (`from openai import OpenAI`) with:
  - `API_BASE_URL` (OpenAI-compatible endpoint)
  - `MODEL_NAME`
  - `HF_TOKEN`
