#!/usr/bin/env python3
import os
import sys
from typing import Any, Dict, List

import httpx


def main() -> int:
    base_url = os.environ.get("ENV_URL", "http://localhost:7860").rstrip("/")
    client = httpx.Client(timeout=20.0)

    r = client.get(f"{base_url}/health")
    if r.status_code != 200:
        print(f"health failed: {r.status_code} {r.text}", file=sys.stderr)
        return 1

    val = client.get(f"{base_url}/validate").json()
    if not val.get("valid"):
        print(f"validate failed: {val}", file=sys.stderr)
        return 1

    tasks = client.get(f"{base_url}/tasks").json().get("tasks", [])
    if len(tasks) < 3:
        print(f"expected 3+ tasks, got {len(tasks)}", file=sys.stderr)
        return 1

    for task in tasks:
        tid = task["id"]
        reset = client.post(f"{base_url}/reset", json={"task_id": tid}).json()
        obs = reset.get("observation", {})
        workers = obs.get("workers", [])
        actions = ["noop()"] * max(1, len(workers))
        step = client.post(f"{base_url}/step", json={"actions": actions}).json()

        reward = float(step.get("reward", {}).get("value", -1.0))
        if not (0.0 <= reward <= 1.0):
            print(f"{tid}: reward out of range: {reward}", file=sys.stderr)
            return 1

        score = step.get("info", {}).get("final_score")
        if score is not None:
            score_f = float(score)
            if not (0.0 <= score_f <= 1.0):
                print(f"{tid}: final_score out of range: {score_f}", file=sys.stderr)
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
