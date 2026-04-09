---
title: Warehouse Nexus OS
sdk: docker
app_port: 7860
---

# Warehouse Nexus OS (OpenEnv Submission)

Warehouse Nexus OS is a **multi-agent warehouse order-fulfillment simulator**. It demonstrates:
- A clear progression from **baseline → logical planning → LLM-driven control**
- A **points-based reward** that can be used to **train / optimize** policies
- A deployment-ready **OpenEnv-compatible** HTTP environment + web UI demo
## 🌐 have a look at live training of AI 🔥
https://vishnupatel-warehouse-nexus-os.hf.space/ui/

---
## Links (submission)
- GitHub: `https://github.com/patelvishnu5542-hue/warehouse-nexus-os`
- HF Space (page): `https://huggingface.co/spaces/Vishnupatel/warehouse-nexus-os`
- HF Space (runtime): `https://vishnupatel-warehouse-nexus-os.hf.space`
- UI (runtime): `https://vishnupatel-warehouse-nexus-os.hf.space/ui`

## Industry relevance (why this matters)
Real warehouses care about:
- **Throughput** (orders/hour), **distance traveled**, and **deadline/SLA** adherence
- **Multi-agent coordination** (avoid congestion, avoid idling, reduce invalid actions)
- Safely evaluating decision policies in a **digital twin** before deploying to operations

This environment can be used to prototype and compare strategies for:
- dispatching/assignment (which worker handles which order)
- navigation and pick routing
- congestion-aware coordination

## Controllers (3 modes)
Switchable via `POST /config` or the UI dropdown:
- `dumb`: intentionally weak baseline (mostly `noop()` and random moves)
- `logic`: heuristic planner (assignment + navigation + light decongestion)
- `ai`: LLM controller (uses OpenAI Python client via an OpenAI-compatible endpoint)

## Levels / tasks (3 tasks required)
We expose 3 tasks (one per level). Level affects the number of workers and congestion penalty.
- Level 1 / `task_easy_level1`: 1 worker, no congestion penalty
- Level 2 / `task_medium_level2`: 2 workers, congestion penalty enabled
- Level 3 / `task_hard_level3`: 5 workers, higher congestion penalty

List tasks:
- `GET /tasks`

## Reward, scoring, and “training by points”

### Raw points (training signal)
The simulator computes dense shaped **raw points** (per worker, summed per step). This is the core signal you would use for RL training or policy improvement.
Implementation:
- `warehouse_env/logic.py` (reward computation)
- `RL_STRATEGY.md` (training notes)

The points encourage:
- Deliver orders (large positive bonus)
- Pick items (positive bonus)
- Move toward the current target (distance shaping)
- Avoid congestion (adjacency penalty)
- Avoid invalid actions and idling while busy (penalties)
- Avoid missing deadlines (penalty when first missed)

### OpenEnv normalized reward
For OpenEnv HTTP compliance, `/step` returns:
- `reward.value` in `[0,1]` (normalized)
- `info.raw_points` with the underlying shaped points for debugging/training

### Task score (validator)
At episode end, `/step` returns:
- `info.final_score` (episode-level score)

Hackathon requirement:
- each task score must be strictly inside `(0, 1)` (not exactly `0.0` or `1.0`).

## LLM usage (OpenAI client is mandatory)
All LLM calls in this project use the **OpenAI Python client**:
- `from openai import OpenAI`
- `client.chat.completions.create(...)`

The endpoint is OpenAI-compatible (we recommend HF router). No Anthropic SDK, no LangChain wrappers, no raw `requests.post(...)` for LLM inference.

### Required Space Variables / Secrets
Set in HF Space Settings → Variables/Secrets:
- `API_BASE_URL` (recommended): `https://router.huggingface.co/v1`
- `MODEL_NAME` (example): `Qwen/Qwen2.5-72B-Instruct`
- `HF_TOKEN` (secret)

## Using the UI
1. Open: `/ui`
2. Select `level` and `mode`
3. Click **START** to run the simulation loop
4. Click **RESET** to restart the episode

## Using the API

### Configure level/mode
```bash
curl -s -X POST https://vishnupatel-warehouse-nexus-os.hf.space/config \
  -H "Content-Type: application/json" \
  -d '{"level":2,"mode":"logic"}'
```

### Reset
```bash
curl -s -X POST https://vishnupatel-warehouse-nexus-os.hf.space/reset \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Step
Send one action string per worker (worker-id order):
```bash
curl -s -X POST https://vishnupatel-warehouse-nexus-os.hf.space/step \
  -H "Content-Type: application/json" \
  -d '{"actions":["noop()","noop()"]}'
```

### Action format
Actions are strings:
- `assign_order(worker_id, order_id)`
- `move(worker_id, 'up'|'down'|'left'|'right')`
- `pick_item(worker_id, 'item_3')`
- `deliver_order(worker_id, order_id)`
- `noop()`

## Run locally (Docker)
```bash
docker build -t warehouse-openenv .
docker run --rm -p 7860:7860 -e PORT=7860 warehouse-openenv
```

Open:
- UI: `http://localhost:7860/ui`
- Health: `http://localhost:7860/health`

## Runtime endpoints (OpenEnv + app)
- `GET /ui` (web demo)
- `GET /health` (returns `{"status":"healthy"}`)
- `POST /reset`
- `POST /step`
- `GET /state`
- `GET /tasks`
- `POST /config` / `GET /status`
- `GET /metadata` / `GET /schema` / `POST /mcp` (OpenEnv runtime validation)

## Inference & evaluation (judge runner)
The required script is:
- `inference.py` (repo root)

It:
- Uses OpenAI client with `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`
- Runs the 3 tasks
- Emits strict stdout lines: `[START]`, `[STEP]`, `[END]`

Example:
```bash
ENV_URL=https://vishnupatel-warehouse-nexus-os.hf.space \
API_BASE_URL=https://router.huggingface.co/v1 \
MODEL_NAME=Qwen/Qwen2.5-72B-Instruct \
HF_TOKEN=... \
python inference.py
```

## How to train/improve the AI (practical roadmap)
This project is designed to make “training by points” practical:
- The reward is dense, so agents get feedback even before the first full delivery.
- You can collect trajectories `(state, action, reward, next_state)` and train:
  - **Imitation**: learn from the `logic` controller trajectories
  - **RL**: optimize a policy that outputs action strings (MAPPO-style multi-agent training works well)
  - **LLM policy improvement**: improve prompts/tools to reduce invalid actions and increase reward

## Validation
```bash
bash scripts/validate-submission.sh https://vishnupatel-warehouse-nexus-os.hf.space .
```

