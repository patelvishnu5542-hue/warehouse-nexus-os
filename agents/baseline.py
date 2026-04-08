import math
from typing import List, Optional
from warehouse_env.models import State, Action, Status, Worker, Direction

class BaselineAgent:
    def __init__(self):
        pass

    def get_action(self, state: State, worker_id: int) -> str:
        # Simple heuristic:
        # 1. If idle, find closest pending order and assign it.
        # 2. If busy and has items to pick, move to closest item.
        # 3. If busy and has all items, move to delivery zone (0,0).
        
        worker = next((w for w in state.workers if w.id == worker_id), None)
        if not worker: return "noop()"
        
        if worker.status == Status.IDLE:
            pending_orders = [o for o in state.orders if o.status == "pending"]
            if not pending_orders:
                return "noop()"
            
            # Assign closest order
            closest_order = pending_orders[0]
            return f"assign_order({worker.id}, {closest_order.id})"
        
        if worker.status == Status.BUSY:
            order = next((o for o in state.orders if o.id == worker.assigned_order_id), None)
            if not order:
                return f"noop()"
            
            # Check for items to pick
            items_to_pick = [item_id for item_id in order.items if item_id not in worker.items_held]
            if items_to_pick:
                item_id = items_to_pick[0]
                item_pos = state.inventory[item_id]
                
                if worker.position == item_pos:
                    return f"pick_item({worker.id}, '{item_id}')"
                else:
                    return f"move({worker.id}, '{self._get_direction(worker.position, item_pos)}')"
            
            # Deliver if all items picked
            delivery_pos = [0, 0]
            if worker.position == delivery_pos:
                return f"deliver_order({worker.id}, {order.id})"
            else:
                return f"move({worker.id}, '{self._get_direction(worker.position, delivery_pos)}')"
        
        return "noop()"

    def _get_direction(self, current: List[int], target: List[int]) -> str:
        cx, cy = current
        tx, ty = target
        
        if cx < tx: return "right"
        if cx > tx: return "left"
        if cy < ty: return "up"
        if cy > ty: return "down"
        return "up"
