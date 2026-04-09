from typing import List, Tuple, Optional
from .models import Action, Worker, Order, State, Status, Direction, Priority

class WarehouseLogic:
    def __init__(self, grid_size: List[int], congestion_penalty: float = 1.0):
        self.grid_size = grid_size
        self.congestion_penalty = float(congestion_penalty)

    def calculate_reward(self, worker: Worker, action: Action, result: str, state: State, 
                         order_completed: bool = False, deadline_missed: bool = False,
                         item_picked: bool = False) -> Tuple[float, List[dict]]:
        """
        High-Performance RL Reward System with Metadata tracking:
        - returns (total_reward, events_list)
        """
        total_reward = -0.01  # Base step cost
        events = []
        
        # 1. Goal-Directed Reward Shaping
        if worker.target:
            curr_dist = abs(worker.position[0] - worker.target[0]) + abs(worker.position[1] - worker.target[1])
            shaping = (worker.previous_dist - curr_dist) * 0.5
            total_reward += shaping
            if shaping != 0:
                events.append({"reason": "Goal Step", "points": shaping, "worker_id": worker.id})
        
        # 2. Outcome Bonuses
        if order_completed:
            total_reward += 100.0
            events.append({"reason": "Delivery Bonus", "points": 100.0, "worker_id": worker.id})
        if item_picked:
            total_reward += 20.0
            events.append({"reason": "Pick Bonus", "points": 20.0, "worker_id": worker.id})
        if deadline_missed:
            total_reward -= 50.0
            events.append({"reason": "Deadline Penalty", "points": -50.0, "worker_id": worker.id})
            
        # 3. Penalties
        if result == "invalid_action":
            total_reward -= 5.0
            events.append({"reason": "Invalid Action", "points": -5.0, "worker_id": worker.id})
        if action.type == "noop" and worker.status == Status.BUSY:
            total_reward -= 2.0
            events.append({"reason": "Idling when Busy", "points": -2.0, "worker_id": worker.id})
            
        # 4. Multi-Agent Congestion Handling
        density = sum(1 for w in state.workers if w.id != worker.id and 
                      abs(w.position[0] - worker.position[0]) + abs(w.position[1] - worker.position[1]) <= 1)
        if density > 0:
            penalty = -self.congestion_penalty * density
            total_reward += penalty
            events.append({"reason": "Congestion Penalty", "points": penalty, "worker_id": worker.id})
            
        return float(total_reward), events

    @staticmethod
    def get_new_position(current_pos: List[int], direction: Direction, grid_size: List[int]) -> List[int]:
        x, y = current_pos
        if direction == Direction.UP and y < grid_size[1] - 1:
            y += 1
        elif direction == Direction.DOWN and y > 0:
            y -= 1
        elif direction == Direction.LEFT and x > 0:
            x -= 1
        elif direction == Direction.RIGHT and x < grid_size[0] - 1:
            x += 1
        return [x, y]

    @staticmethod
    def is_valid_pick(worker: Worker, item_id: str, inventory: dict) -> bool:
        if item_id not in inventory:
            return False
        item_pos = inventory[item_id]
        if worker.position != item_pos:
            return False
        if worker.load >= worker.capacity:
            return False
        return True

    @staticmethod
    def is_valid_delivery(worker: Worker, order_id: int, orders: List[Order], delivery_zone: List[int]) -> bool:
        order = next((o for o in orders if o.id == order_id), None)
        if not order:
            return False
        if worker.position != delivery_zone:
            return False
        # Check if worker has all items for this order
        for item in order.items:
            if item not in worker.items_held:
                return False
        return True
