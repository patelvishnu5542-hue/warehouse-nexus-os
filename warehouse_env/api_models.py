from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .models import Reward, State


class ResetRequest(BaseModel):
    task_id: Optional[str] = None
    level: Optional[int] = None


class ResetInfo(BaseModel):
    task_id: str
    level: int
    max_steps: int
    benchmark: str


class ResetResponse(BaseModel):
    observation: State
    info: ResetInfo


class StepRequest(BaseModel):
    actions: List[str] = Field(default_factory=list)


class StepInfo(BaseModel):
    task_id: str
    level: int
    steps_taken: int
    max_steps: int
    raw_points: float
    final_score: Optional[float] = None
    step_error: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class StepResponse(BaseModel):
    observation: State
    reward: Reward
    done: bool
    info: StepInfo


class TaskSpec(BaseModel):
    id: str
    level: int
    name: str
    difficulty: str
    description: str
    max_steps: int
    success_threshold: float


class TaskListResponse(BaseModel):
    tasks: List[TaskSpec]


class RuntimeInfo(BaseModel):
    port: int
    framework: str


class ValidateResponse(BaseModel):
    valid: bool
    env_name: str
    version: str
    benchmark: str
    tasks: List[str]
    endpoints: List[str]
    runtime: RuntimeInfo

