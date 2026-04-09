"""
Root models required by the OpenEnv CLI (`openenv push`).

The environment's canonical simulation types live in `warehouse_env/models.py`.
This module provides thin re-exports and minimal action/observation wrappers.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from warehouse_env.models import State


class WarehouseAction(BaseModel):
    """
    One step consists of one action string per worker.

    Example:
      ["assign_order(0, 1)", "move(1, 'right')"]
    """

    actions: List[str] = Field(default_factory=list)


class WarehouseObservation(BaseModel):
    """
    Observation is the full environment state.
    """

    state: State


class WarehouseStepResult(BaseModel):
    observation: State
    reward: float = 0.0
    done: bool = False
    error: Optional[str] = None

