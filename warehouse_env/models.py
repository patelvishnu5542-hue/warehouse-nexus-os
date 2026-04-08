from enum import Enum
from typing import List, Dict, Optional, Tuple, Union
from pydantic import BaseModel, Field

class Status(str, Enum):
    IDLE = "idle"
    BUSY = "busy"

class Priority(str, Enum):
    NORMAL = "normal"
    URGENT = "urgent"

class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

class TaskType(str, Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"
    IDLE = "idle"

class Worker(BaseModel):
    id: int
    position: List[int] = Field(..., min_items=2, max_items=2)
    status: Status = Status.IDLE
    load: int = 0
    capacity: int = 5
    assigned_order_id: Optional[int] = None
    items_held: List[str] = []
    fatigue: float = 1.0
    # RL Enhancements
    target: Optional[List[int]] = None
    task_type: TaskType = TaskType.IDLE
    previous_dist: float = 0.0

class Order(BaseModel):
    id: int
    items: List[str]
    priority: Priority = Priority.NORMAL
    deadline: int
    created_at: int
    status: str = "pending"  # pending, assigned, completed
    penalty_paid: bool = False

class InventoryItem(BaseModel):
    id: str
    position: List[int] = Field(..., min_items=2, max_items=2)
    quantity: int = 1

class State(BaseModel):
    workers: List[Worker]
    orders: List[Order]
    inventory: Dict[str, List[int]]
    grid_size: List[int] = Field(..., min_items=2, max_items=2)
    time_step: int

class Reward(BaseModel):
    value: float = Field(..., ge=0.0, le=1.0)

class Action(BaseModel):
    type: str  # assign_order, move, pick_item, deliver_order, noop
    worker_id: Optional[int] = None
    order_id: Optional[int] = None
    item_id: Optional[str] = None
    direction: Optional[Direction] = None

    @classmethod
    def parse(cls, action_str: str) -> "Action":
        """
        Parses action strings like:
        - assign_order(worker_id, order_id)
        - move(worker_id, direction)
        - pick_item(worker_id, item_id)
        - deliver_order(worker_id, order_id)
        - noop()
        """
        import re
        
        # Simple regex for function-like strings
        match = re.match(r"(\w+)\((.*)\)", action_str.strip())
        if not match:
            return cls(type="noop")
            
        action_type = match.group(1)
        args = [arg.strip().strip("'\"") for arg in match.group(2).split(",") if arg.strip()]
        
        try:
            if action_type == "assign_order":
                return cls(type=action_type, worker_id=int(args[0]), order_id=int(args[1]))
            elif action_type == "move":
                return cls(type=action_type, worker_id=int(args[0]), direction=Direction(args[1]))
            elif action_type == "pick_item":
                return cls(type=action_type, worker_id=int(args[0]), item_id=args[1])
            elif action_type == "deliver_order":
                return cls(type=action_type, worker_id=int(args[0]), order_id=int(args[1]))
            else:
                return cls(type="noop")
        except (IndexError, ValueError):
            return cls(type="noop")
