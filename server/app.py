import asyncio
import os
import json
from pathlib import Path
from openai import OpenAI
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any, Callable, Dict, List, Optional, Tuple

from warehouse_env.env import WarehouseEnv
from warehouse_env.levels import get_env_for_level, WarehouseGrader
from warehouse_env.models import State, Action
from warehouse_env.api_models import (
    ResetRequest,
    ResetResponse,
    StepRequest,
    StepResponse,
    TaskListResponse,
    TaskSpec,
    ValidateResponse,
    RuntimeInfo,
)
from agents.baseline import BaselineAgent
from agents.dumb import DumbAgent
from agents.logical import LogicalAgent

app = FastAPI()

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# If a production UI build exists, serve it at `/ui`.
_UI_DIST = Path(__file__).resolve().parents[1] / "ui" / "dist"
if _UI_DIST.is_dir():
    app.mount("/ui", StaticFiles(directory=str(_UI_DIST), html=True), name="ui")
    # Vite build uses absolute `/assets/...` paths by default. Mount assets at the root
    # so `/ui` works without requiring a custom Vite base path.
    _UI_ASSETS = _UI_DIST / "assets"
    if _UI_ASSETS.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_UI_ASSETS)), name="assets")

# Initialize environment
# Simulation state
is_running = False
simulation_task = None
is_thinking = False
reward_logs = [] # Global storage for point logs
current_level = int(os.getenv("DEFAULT_LEVEL", "2"))
agent_mode = (os.getenv("AGENT_MODE") or "").lower().strip()  # dumb | logic | ai
env = get_env_for_level(current_level)
env_lock = asyncio.Lock()

# OpenEnv task selection / episode tracking
BENCHMARK_NAME = "warehouse_fulfillment"
ENV_VERSION = "1.0.0"
TASKS: Dict[str, Dict[str, Any]] = {
    "task_easy_level1": {
        "level": 1,
        "name": "Easy Level 1",
        "difficulty": "easy",
        "description": "1 worker, static orders, no congestion penalty.",
        "max_steps": 30,
        "success_threshold": 0.30,
    },
    "task_medium_level2": {
        "level": 2,
        "name": "Medium Level 2",
        "difficulty": "medium",
        "description": "2 workers, dynamic orders, congestion penalty enabled.",
        "max_steps": 50,
        "success_threshold": 0.35,
    },
    "task_hard_level3": {
        "level": 3,
        "name": "Hard Level 3",
        "difficulty": "hard",
        "description": "5 workers, dynamic orders, higher congestion penalty.",
        "max_steps": 80,
        "success_threshold": 0.40,
    },
}
current_task_id = "task_medium_level2"
episode_max_steps = TASKS[current_task_id]["max_steps"]
episode_steps_taken = 0

heuristic_agent = BaselineAgent()  # kept as fallback
dumb_agent = DumbAgent()
logical_agent = LogicalAgent()
last_performance = {"action": "None", "reward": 0.0, "status": "Idle"}
logs = []

# HuggingFace/OpenAI-compatible Inference Configuration
hf_token = (os.getenv("HF_TOKEN") or "").strip()  # required for real AI mode
api_base_url = (os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1").strip()
MODEL_NAME = (os.getenv("MODEL_NAME") or os.getenv("HF_MODEL") or "Qwen/Qwen2.5-72B-Instruct").strip()

# Default to AI when a token exists (unless AGENT_MODE is explicitly set).
if not agent_mode:
    agent_mode = "ai" if hf_token else "logic"

# Important: HF Spaces UI sometimes stores variables with a trailing newline when copy/pasted.
# The OpenAI client (httpx) rejects base_url values with non-printable characters.
client = OpenAI(
    base_url=api_base_url,
    api_key=hf_token or "dummy-token-to-prevent-crash",
)

def state_to_prompt(state_dict: dict) -> str:
    prompt = "You are a Warehouse Logistics Strategist. Your goal is to EXCEL in efficiency.\n"
    prompt += "Scoring: +100 for Delivery, +20 for Picking. -1.0 for Congestion (being adjacent).\n\n"
    
    prompt += "### Coordination Strategy ###\n"
    prompt += "1. ASSIGN orders to Idle workers first.\n"
    prompt += "2. AVOID clustering. Keep agents separated to prevent congestion penalties.\n"
    prompt += "3. OPTIMIZE pathing. Use 'move' commands to get closer to targets.\n"
    prompt += "4. DO NOT move IDLE workers unnecessarily. If a worker is IDLE and not assigned an order, you MUST output 'noop()'.\n\n"

    # Worker status for better context
    prompt += "### Agent Status ###\n"
    for worker in state_dict['workers']:
        status_info = f"- Worker {worker['id']}: Pos {worker['position']}, Load {worker['load']}/{worker['capacity']}"
        if worker['status'] == 'idle':
            status_info += " [IDLE]"
        else:
            status_info += f" [BUSY] Target: {worker['target']}, Task: {worker['task_type']}"
        prompt += status_info + "\n"
            
    prompt += f"\n### Warehouse Global State ###\n{json.dumps(state_dict, indent=2)}\n"
    worker_ids = [w.get("id") for w in state_dict.get("workers", [])]
    prompt += f"\nOutput ONLY a JSON list of EXACTLY {len(worker_ids)} action strings, in worker-id order: {worker_ids}.\n"
    prompt += "Example: [\"move(0, 'right')\", \"pick_item(1, 'item_5')\"]\n"
    prompt += "Do NOT wrap in markdown blocks like ```json. Do NOT output any words other than the literal JSON brackets and contents.\n"
    return prompt

def add_log(message: str):
    global logs
    logs.append({"timestamp": env.time_step, "message": message})
    if len(logs) > 50:
        logs.pop(0)

class ActionRequest(BaseModel):
    action: str

class ConfigRequest(BaseModel):
    level: int
    mode: str  # dumb | logic | ai

def _get_mode_actions(state: State) -> List[str]:
    global agent_mode
    if agent_mode == "dumb":
        return [dumb_agent.get_action(state, w.id) for w in state.workers]
    if agent_mode == "logic":
        return [logical_agent.get_action(state, w.id) for w in state.workers]
    # ai: handled in simulation loop (needs LLM call); fallback here
    return [logical_agent.get_action(state, w.id) for w in state.workers]

def _safe_json_actions(raw_response: str) -> List[str]:
    raw = raw_response.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) > 1:
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass
    import re
    return re.findall(r"(\w+\(.*\))", raw)

@app.get("/state")
async def get_state():
    async with env_lock:
        return env.state()

@app.get("/")
async def root():
    # Render the UI by default on Hugging Face Spaces (better UX than raw JSON).
    # If the UI isn't built, fall back to a simple JSON response.
    index_html = _UI_DIST / "index.html"
    if index_html.is_file():
        return FileResponse(str(index_html))
    return {"status": "ok", "service": "warehouse-nexus-os"}

@app.get("/health")
async def health():
    # OpenEnv runtime validation expects {"status":"healthy"}.
    return {"status": "healthy"}

@app.get("/metadata")
async def metadata() -> Dict[str, str]:
    return {
        "name": BENCHMARK_NAME,
        "description": "Multi-agent warehouse fulfillment simulation (3 levels, 3 controller modes).",
    }

@app.get("/schema")
async def schema() -> Dict[str, Any]:
    # Minimal schemas for OpenEnv runtime validation.
    return {
        "action": StepRequest.model_json_schema(),
        "observation": State.model_json_schema(),
        "state": State.model_json_schema(),
    }

@app.post("/mcp")
async def mcp(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Minimal JSON-RPC response so `openenv validate <url>` can succeed.
    request_id = payload.get("id", 0) if isinstance(payload, dict) else 0
    return {"jsonrpc": "2.0", "id": request_id, "result": {"status": "ok"}}

@app.get("/validate")
async def validate() -> ValidateResponse:
    # Lightweight validator endpoint (useful for pre-submission scripts)
    return ValidateResponse(
        valid=True,
        env_name=BENCHMARK_NAME,
        version=ENV_VERSION,
        benchmark=BENCHMARK_NAME,
        tasks=list(TASKS.keys()),
        endpoints=["/health", "/reset", "/step", "/state", "/tasks", "/validate"],
        runtime=RuntimeInfo(port=int(os.getenv("PORT", "7860")), framework="fastapi"),
    )

@app.get("/tasks")
async def get_tasks() -> TaskListResponse:
    tasks: List[TaskSpec] = []
    for task_id, meta in TASKS.items():
        tasks.append(
            TaskSpec(
                id=task_id,
                level=int(meta["level"]),
                name=str(meta["name"]),
                difficulty=str(meta["difficulty"]),
                description=str(meta["description"]),
                max_steps=int(meta["max_steps"]),
                success_threshold=float(meta["success_threshold"]),
            )
        )
    return TaskListResponse(tasks=tasks)

@app.get("/logs")
async def get_logs():
    return logs

@app.post("/action")
async def take_action(request: ActionRequest):
    async with env_lock:
        state, reward, done, info = env.step(request.action)
    if info.get("result") == "success":
        add_log(f"Action: {request.action}")
    return {"status": "success", "reward": reward, "done": done, "info": info}

@app.post("/reset")
async def reset_env(request: Optional[ResetRequest] = None) -> ResetResponse:
    global env, logs, reward_logs, current_level, current_task_id, episode_max_steps, episode_steps_taken
    logs.clear()
    reward_logs.clear()

    # Select task/level if provided (OpenEnv-style)
    task_id = request.task_id if request and request.task_id else None
    if task_id and task_id in TASKS:
        current_task_id = task_id
        current_level = int(TASKS[current_task_id]["level"])
        episode_max_steps = int(TASKS[current_task_id]["max_steps"])
        env = get_env_for_level(current_level)
    elif request and request.level in (1, 2, 3):
        current_level = int(request.level)
        # keep previous max_steps unless a known task_id is provided
        env = get_env_for_level(current_level)

    async with env_lock:
        env.reset()
        episode_steps_taken = 0

    return ResetResponse(
        observation=env.state(),
        info={
            "task_id": current_task_id,
            "level": current_level,
            "max_steps": int(episode_max_steps),
            "benchmark": BENCHMARK_NAME,
        },
    )

@app.post("/step")
async def step_multi(request: StepRequest) -> StepResponse:
    """
    OpenEnv-style endpoint: apply one environment step for all workers.
    """
    global episode_steps_taken
    async with env_lock:
        state, reward_value, done_env, info_list = env.step_multi(request.actions)
    episode_steps_taken += 1
    done = bool(done_env) or episode_steps_taken >= episode_max_steps

    raw_points = float(getattr(env, "last_step_points", 0.0))

    invalids = [i for i in info_list if i.get("result") == "invalid_action"]
    step_error = "invalid_action" if invalids else None

    final_score = None
    if done:
        final_score = WarehouseGrader.grade(current_level, env.metrics)

    if info_list:
        add_log(f"StepMulti: {len(request.actions)} actions")
    return StepResponse(
        observation=state,
        reward={"value": float(reward_value)},
        done=bool(done),
        info={
            "task_id": current_task_id,
            "level": current_level,
            "steps_taken": int(episode_steps_taken),
            "max_steps": int(episode_max_steps),
            "raw_points": float(raw_points),
            "final_score": final_score,
            "step_error": step_error,
            "metrics": dict(env.metrics),
        },
    )

@app.get("/metrics")
async def get_metrics():
    async with env_lock:
        return {**env.metrics, "final_score": WarehouseGrader.grade(current_level, env.metrics)}

@app.get("/reward_logs")
async def get_reward_logs():
    return {"logs": reward_logs[-50:]} # Return last 50 logs

@app.get("/status")
async def get_status():
    return {
        "is_running": is_running,
        "is_thinking": is_thinking,
        "level": current_level,
        "mode": agent_mode,
        "has_hf_token": bool(hf_token),
        "model": MODEL_NAME,
        "api_base_url": api_base_url,
    }

@app.get("/config")
async def get_config():
    return {
        "level": current_level,
        "mode": agent_mode,
        "has_hf_token": bool(hf_token),
        "model": MODEL_NAME,
        "api_base_url": api_base_url,
    }

@app.post("/config")
async def set_config(request: ConfigRequest):
    global env, logs, reward_logs, current_level, agent_mode, is_thinking, current_task_id, episode_max_steps, episode_steps_taken

    level = int(request.level)
    mode = str(request.mode).lower().strip()
    if level not in (1, 2, 3):
        return {"status": "error", "error": "level must be 1, 2, or 3"}
    if mode not in ("dumb", "logic", "ai"):
        return {"status": "error", "error": "mode must be dumb, logic, or ai"}

    is_thinking = False
    current_level = level
    agent_mode = mode
    logs.clear()
    reward_logs.clear()
    # Reset environment on config changes so mode differences are immediately visible.
    async with env_lock:
        env = get_env_for_level(current_level)
        env.reset()
        episode_steps_taken = 0
        # Keep OpenEnv task metadata aligned with the selected level.
        if current_level == 1:
            current_task_id = "task_easy_level1"
        elif current_level == 2:
            current_task_id = "task_medium_level2"
        else:
            current_task_id = "task_hard_level3"
        episode_max_steps = int(TASKS[current_task_id]["max_steps"])

    return {
        "status": "ok",
        "level": current_level,
        "mode": agent_mode,
        "has_hf_token": bool(hf_token),
        "model": MODEL_NAME,
        "task_id": current_task_id,
        "max_steps": int(episode_max_steps),
    }

@app.get("/benchmark")
async def benchmark(level: Optional[int] = None, steps: int = 80, ai_steps: int = 10, seed: int = 42):
    """
    Quick comparison for demo:
    - Runs dumb + logic for `steps`
    - Runs ai for `ai_steps` if HF_TOKEN exists (else skipped)
    """
    import random as _random

    run_level = int(level) if level is not None else current_level
    if run_level not in (1, 2, 3):
        return {"status": "error", "error": "level must be 1, 2, or 3"}

    def run_episode(mode: str, max_steps: int) -> Dict[str, Any]:
        _random.seed(seed)
        local_env = get_env_for_level(run_level)

        for _ in range(max_steps):
            st = local_env.state()
            if mode == "dumb":
                actions = [dumb_agent.get_action(st, w.id) for w in st.workers]
            elif mode == "logic":
                actions = [logical_agent.get_action(st, w.id) for w in st.workers]
            else:
                # AI mode: single call per step, fallback to logic on errors.
                if not hf_token:
                    break
                prompt = state_to_prompt(st.model_dump())
                try:
                    resp = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=60,
                        temperature=0.1,
                    )
                    raw = resp.choices[0].message.content or ""
                    actions = _safe_json_actions(raw)
                except Exception:
                    actions = [logical_agent.get_action(st, w.id) for w in st.workers]

            _, _, done, _ = local_env.step_multi(actions)
            if done:
                break

        return dict(local_env.metrics)

    results: Dict[str, Any] = {"status": "ok", "level": run_level, "steps": steps, "seed": seed, "results": {}}
    results["results"]["dumb"] = run_episode("dumb", steps)
    results["results"]["logic"] = run_episode("logic", steps)
    if hf_token:
        results["results"]["ai"] = run_episode("ai", max(1, int(ai_steps)))
    else:
        results["results"]["ai"] = {"skipped": True, "reason": "HF_TOKEN not set"}
    return results

async def simulation_loop():
    global is_running
    while is_running:
        try:
            async with env_lock:
                state = env.state()
            state_dict = state.model_dump()
            
            # 1. Get Actions from Gemini (Batch for all agents)
            actions_to_execute = []
            global is_thinking
            is_thinking = False
            try:
                if agent_mode in ("dumb", "logic"):
                    actions_to_execute = _get_mode_actions(state)
                elif agent_mode == "ai" and hf_token:
                    is_thinking = True
                    prompt = state_to_prompt(state_dict)
                    response = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=60,
                        temperature=0.1
                    )
                    raw_response = (response.choices[0].message.content or "").strip()
                    actions_to_execute = _safe_json_actions(raw_response)
                else:
                    # ai mode but no token: fallback to logical heuristic
                    actions_to_execute = _get_mode_actions(state)
            except Exception as e:
                print(f"LLM API Error: {e}")
                for w in state.workers:
                    actions_to_execute.append(heuristic_agent.get_action(state, w.id))
            finally:
                is_thinking = False
                
                # 2. Execute Batch Actions
            if actions_to_execute:
                async with env_lock:
                    new_state, reward, done, info_list = env.step_multi(actions_to_execute)
                
                # Append new reward events to global reward_log
                for info in info_list:
                    if "events" in info:
                        reward_logs.extend(info["events"])
                    
                    # Log significant events
                    action_str = info.get("action_taken", "")
                    w_id = info.get("worker_id", -1)
                    if "pick" in action_str: add_log(f"🧠 AI Pick: W{w_id}")
                    elif "deliver" in action_str: add_log(f"🧠 AI Deliver: W{w_id}")
                    elif "assign" in action_str: add_log(f"🧠 AI Assign: W{w_id}")
                
                # Keep log size manageable
                if len(reward_logs) > 200:
                    reward_logs[:] = reward_logs[-100:]
                
                global last_performance
                last_performance = {
                    "action": str(actions_to_execute),
                    "reward": reward,
                    "status": "Multi-Step Success"
                }
            
            if done:
                is_running = False
                add_log("🏁 Mission Completed!")
        except Exception as e:
            print(f"Simulation Loop Error: {e}")
            add_log(f"⚠️ Sys Error: {str(e)[:50]}")
            
        await asyncio.sleep(5.0) # Rate limited for Free Tier (15-60 RPM)

@app.post("/start")
async def start_sim(background_tasks: BackgroundTasks):
    global is_running
    if not is_running:
        is_running = True
        background_tasks.add_task(simulation_loop)
    return {"status": "started"}

@app.post("/stop")
async def stop_sim():
    global is_running
    is_running = False
    return {"status": "stopped"}

def main() -> None:
    import uvicorn

    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
