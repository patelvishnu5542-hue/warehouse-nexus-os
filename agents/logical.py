from __future__ import annotations

from typing import List, Optional, Set

from warehouse_env.models import State, Status


class LogicalAgent:
    """
    More "intelligent" heuristic:
    - Assign idle workers to different pending orders (greedy)
    - Navigate to next required item
    - Deliver when ready
    - Light congestion avoidance: if adjacent, prefer stepping away
    """

    def get_action(self, state: State, worker_id: int) -> str:
        worker = next((w for w in state.workers if w.id == worker_id), None)
        if not worker:
            return "noop()"

        if worker.status == Status.IDLE:
            order = self._choose_order_for_worker(state, worker.id)
            if order is None:
                return "noop()"
            return f"assign_order({worker.id}, {order.id})"

        order = next((o for o in state.orders if o.id == worker.assigned_order_id), None)
        if not order:
            return "noop()"

        remaining = [item_id for item_id in order.items if item_id not in worker.items_held]
        if remaining:
            item_id = remaining[0]
            item_pos = state.inventory.get(item_id)
            if item_pos is None:
                return "noop()"

            if worker.position == item_pos:
                return f"pick_item({worker.id}, '{item_id}')"

            direction = self._get_direction(worker.position, item_pos)
            direction = self._avoid_congestion_direction(state, worker.id) or direction
            return f"move({worker.id}, '{direction}')"

        delivery_pos = [0, 0]
        if worker.position == delivery_pos:
            return f"deliver_order({worker.id}, {order.id})"

        direction = self._get_direction(worker.position, delivery_pos)
        direction = self._avoid_congestion_direction(state, worker.id) or direction
        return f"move({worker.id}, '{direction}')"

    def _choose_order_for_worker(self, state: State, worker_id: int):
        worker = next((w for w in state.workers if w.id == worker_id), None)
        if not worker:
            return None

        assigned_ids: Set[int] = set()
        for w in state.workers:
            if w.assigned_order_id is not None:
                assigned_ids.add(w.assigned_order_id)

        pending = [o for o in state.orders if o.status == "pending" and o.id not in assigned_ids]
        if not pending:
            pending = [o for o in state.orders if o.status == "pending"]
        if not pending:
            return None

        def dist_to_first_item(order) -> int:
            if not order.items:
                return 10**9
            pos = state.inventory.get(order.items[0])
            if pos is None:
                return 10**9
            return abs(worker.position[0] - pos[0]) + abs(worker.position[1] - pos[1])

        return min(pending, key=dist_to_first_item)

    def _avoid_congestion_direction(self, state: State, worker_id: int) -> Optional[str]:
        worker = next((w for w in state.workers if w.id == worker_id), None)
        if not worker:
            return None

        neighbors = [
            w
            for w in state.workers
            if w.id != worker.id
            and (abs(w.position[0] - worker.position[0]) + abs(w.position[1] - worker.position[1]) <= 1)
        ]
        if not neighbors:
            return None

        closest = min(
            neighbors,
            key=lambda w: abs(w.position[0] - worker.position[0]) + abs(w.position[1] - worker.position[1]),
        )

        dx = worker.position[0] - closest.position[0]
        dy = worker.position[1] - closest.position[1]

        if abs(dx) >= abs(dy):
            return "right" if dx >= 0 else "left"
        return "up" if dy >= 0 else "down"

    def _get_direction(self, current: List[int], target: List[int]) -> str:
        cx, cy = current
        tx, ty = target

        if cx < tx:
            return "right"
        if cx > tx:
            return "left"
        if cy < ty:
            return "up"
        if cy > ty:
            return "down"
        return "up"

