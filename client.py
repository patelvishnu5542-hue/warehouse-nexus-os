"""
Root client required by the OpenEnv CLI (`openenv push`).

This is a simple HTTP client for the FastAPI server (POST /reset, POST /step).
It is intentionally lightweight and does not depend on the OpenEnv WebSocket client.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from models import WarehouseAction, WarehouseStepResult


class WarehouseEnvClient:
    def __init__(self, base_url: str, timeout_s: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(timeout=timeout_s)

    def reset(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if task_id:
            payload["task_id"] = task_id
        r = self._http.post(f"{self.base_url}/reset", json=payload)
        r.raise_for_status()
        return r.json()

    def step(self, action: WarehouseAction) -> WarehouseStepResult:
        r = self._http.post(f"{self.base_url}/step", json={"actions": action.actions})
        r.raise_for_status()
        data = r.json()
        return WarehouseStepResult(
            observation=data.get("observation"),
            reward=float((data.get("reward") or {}).get("value", 0.0)),
            done=bool(data.get("done", False)),
            error=(data.get("info") or {}).get("step_error"),
        )

    def state(self) -> Dict[str, Any]:
        r = self._http.get(f"{self.base_url}/state")
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._http.close()

