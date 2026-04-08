#!/usr/bin/env python3
"""
Warehouse Fulfillment OpenEnv - Baseline Inference Script
=========================================================

MANDATORY STDOUT FORMAT:

[START] task=<task_name> env=<benchmark> model=<model_name>
[STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
[END] success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

Required environment variables:
- API_BASE_URL: The API endpoint for the LLM
- MODEL_NAME: The model identifier to use for inference
- HF_TOKEN: API key for authentication

Optional environment variables:
- ENV_URL: Environment server URL (your HF Space). Default: http://localhost:8004
"""

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

import httpx  # noqa: E402
from openai import OpenAI  # noqa: E402


# Configuration from environment (as required by the hackathon validator)
API_BASE_URL = os.environ.get("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.environ.get("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
API_KEY = os.environ.get("HF_TOKEN") or os.environ.get("API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
LOCAL_IMAGE_NAME = os.environ.get("LOCAL_IMAGE_NAME", "")

# Environment URL - should point to your deployed HF Space
_port = os.environ.get("PORT", "8004")
ENV_URL = os.environ.get("ENV_URL") or os.environ.get("PING_URL") or f"http://localhost:{_port}"
BENCHMARK = "warehouse_fulfillment"

# Agent settings
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "96"))
TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.1"))
MAX_STEPS_CAP = int(os.environ.get("INFERENCE_MAX_STEPS", "30"))

# Task configurations (3+ tasks required)
TASKS = [
    {"task_id": "task_easy_level1", "name": "easy_level1"},
    {"task_id": "task_medium_level2", "name": "medium_level2"},
    {"task_id": "task_hard_level3", "name": "hard_level3"},
]


# ============== MANDATORY LOGGING FUNCTIONS ==============
def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    action_clean = action.replace("\n", " ").replace("\r", "")
    print(
        f"[STEP] step={step} action={action_clean} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


def _safe_json_actions(raw_response: str, expected_len: int) -> List[str]:
    raw = (raw_response or "").strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) > 1:
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]

    actions: List[str] = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            actions = [str(x) for x in parsed]
    except Exception:
        # Fallback: extract function-like strings
        actions = re.findall(r"(\w+\(.*?\))", raw)

    if len(actions) < expected_len:
        actions.extend(["noop()"] * (expected_len - len(actions)))
    if len(actions) > expected_len:
        actions = actions[:expected_len]
    return actions


def _state_to_prompt(state_dict: Dict[str, Any]) -> str:
    # Keep prompt compact for latency; model must output JSON list of actions.
    workers = state_dict.get("workers", [])
    worker_ids = [w.get("id") for w in workers]

    prompt = "You are a Warehouse Logistics Strategist.\n"
    prompt += "Goal: maximize reward by picking and delivering orders efficiently.\n"
    prompt += "Rules:\n"
    prompt += "- Avoid invalid actions.\n"
    prompt += "- If a worker has nothing useful to do, use noop().\n\n"
    prompt += f"STATE:\n{json.dumps(state_dict, separators=(',', ':'), ensure_ascii=False)}\n\n"
    prompt += f"Output ONLY a JSON list of EXACTLY {len(worker_ids)} action strings, in worker-id order: {worker_ids}.\n"
    prompt += "Allowed actions: assign_order(worker_id, order_id), move(worker_id, 'up|down|left|right'), pick_item(worker_id, 'item_x'), deliver_order(worker_id, order_id), noop().\n"
    return prompt


def run_episode(
    llm_client: OpenAI,
    http_client: httpx.Client,
    task_id: str,
    task_name: str,
) -> Dict[str, Any]:
    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False
    fatal_error: Optional[str] = None

    try:
        # Reset environment (selects task/level server-side)
        try:
            reset_response = http_client.post(f"{ENV_URL}/reset", json={"task_id": task_id})
            reset_response.raise_for_status()
            reset_data = reset_response.json()
        except Exception as e:
            fatal_error = str(e)
            reset_data = {}

        observation = reset_data.get("observation", {})
        info = reset_data.get("info", {})
        max_steps = min(int(info.get("max_steps", 200)), MAX_STEPS_CAP)

        done = fatal_error is not None
        if fatal_error is not None:
            max_steps = 0
        while not done and steps_taken < max_steps:
            steps_taken += 1
            last_error: Optional[str] = None

            # Build LLM prompt
            prompt = _state_to_prompt(observation)
            messages = [{"role": "user", "content": prompt}]

            # Get model response
            try:
                completion = llm_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                )
                response_text = completion.choices[0].message.content or ""
            except Exception as e:
                response_text = "[]"
                last_error = str(e)

            workers = observation.get("workers", [])
            actions = _safe_json_actions(response_text, expected_len=len(workers) if workers else 1)
            action_str = json.dumps(actions, separators=(",", ":"), ensure_ascii=False)

            # Execute action(s)
            try:
                step_response = http_client.post(f"{ENV_URL}/step", json={"actions": actions})
                step_response.raise_for_status()
                step_data = step_response.json()

                observation = step_data.get("observation", {})
                reward = float(step_data.get("reward", {}).get("value", 0.0))
                done = bool(step_data.get("done", False))
                step_error = step_data.get("info", {}).get("step_error") or last_error

                rewards.append(reward)
                log_step(step=steps_taken, action=action_str, reward=reward, done=done, error=step_error)

                if done:
                    score = float(step_data.get("info", {}).get("final_score") or 0.0)
                    success = score >= 0.5
            except Exception as e:
                rewards.append(0.0)
                log_step(step=steps_taken, action=action_str, reward=0.0, done=False, error=str(e))

        # If the server didn't mark done, fetch final score from metrics endpoint (best-effort)
        if not success:
            try:
                metrics_res = http_client.get(f"{ENV_URL}/metrics")
                if metrics_res.status_code == 200:
                    metrics = metrics_res.json()
                    # If server exposes final_score in metrics (optional), use it; else leave score as-is.
                    if "final_score" in metrics:
                        score = float(metrics.get("final_score") or 0.0)
                        success = score >= 0.5
            except Exception:
                pass
    except Exception as e:
        fatal_error = fatal_error or str(e)
    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return {
        "task_id": task_id,
        "task_name": task_name,
        "final_score": score,
        "steps_used": steps_taken,
        "rewards": rewards,
        "success": success,
    }


def main() -> None:
    llm_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY or "missing-token")
    http_client = httpx.Client(timeout=60.0)

    for task in TASKS:
        run_episode(
            llm_client=llm_client,
            http_client=http_client,
            task_id=task["task_id"],
            task_name=task["name"],
        )


if __name__ == "__main__":
    main()
