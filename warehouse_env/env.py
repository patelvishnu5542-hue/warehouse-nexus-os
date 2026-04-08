import random
import heapq
from typing import List, Dict, Tuple, Optional, Any
from warehouse_env.models import State, Action, Worker, Order, Status, Direction, Priority, InventoryItem, TaskType
from warehouse_env.logic import WarehouseLogic

class WarehouseEnv:
    def __init__(
        self,
        grid_size: Tuple[int, int] = (10, 10),
        num_workers: int = 1,
        delivery_zone: List[int] = [0, 0],
        dynamic_orders: bool = True,
        congestion_penalty: float = 1.0,
    ):
        self.grid_size = list(grid_size)
        self.num_workers = num_workers
        self.delivery_zone = delivery_zone
        self.dynamic_orders = bool(dynamic_orders)
        self.logic = WarehouseLogic(self.grid_size, congestion_penalty=congestion_penalty)
        self.time_step = 0
        self.workers = []
        self.orders = []
        self.inventory = {}
        self.metrics = {}
        self.last_step_points = 0.0
        self.reset()

    def reset(self) -> State:
        self.time_step = 0
        self.workers = [
            Worker(id=i, position=[random.randint(0, self.grid_size[0]-1), random.randint(0, self.grid_size[1]-1)])
            for i in range(self.num_workers)
        ]
        self.orders: List[Order] = []
        self.inventory: Dict[str, List[int]] = self._generate_inventory()
        self.metrics = {"completed": 0, "distance": 0, "rewards": 0.0, "points": 0.0}
        self.last_step_points = 0.0
        
        # Initial orders
        self._add_random_order()
        return self.state()

    def _generate_inventory(self) -> Dict[str, List[int]]:
        # Map item IDs to positions
        items = {}
        for i in range(20):
            item_id = f"item_{i}"
            items[item_id] = [random.randint(0, self.grid_size[0]-1), random.randint(0, self.grid_size[1]-1)]
        return items

    def _add_random_order(self):
        order_id = len(self.orders)
        num_items = random.randint(1, 3)
        order_items = random.sample(list(self.inventory.keys()), num_items)
        deadline = self.time_step + random.randint(20, 50)
        priority = Priority.URGENT if random.random() < 0.2 else Priority.NORMAL
        self.orders.append(Order(
            id=order_id, 
            items=order_items, 
            deadline=deadline, 
            created_at=self.time_step,
            priority=priority
        ))

    def get_astar_path(self, start: List[int], goal: List[int]) -> List[List[int]]:
        """Standard A* pathfinding for obstacles/congestion avoidance."""
        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        neighbors = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        close_set = set()
        came_from = {}
        gscore = {tuple(start): 0}
        fscore = {tuple(start): heuristic(start, goal)}
        oheap = []

        heapq.heappush(oheap, (fscore[tuple(start)], tuple(start)))
        
        while oheap:
            current = heapq.heappop(oheap)[1]
            if list(current) == goal:
                data = []
                while current in came_from:
                    data.append(list(current))
                    current = came_from[current]
                return data[::-1]

            close_set.add(current)
            for i, j in neighbors:
                neighbor = (current[0] + i, current[1] + j)
                if 0 <= neighbor[0] < self.grid_size[0] and 0 <= neighbor[1] < self.grid_size[1]:
                    if neighbor in close_set:
                        continue
                    
                    tentative_g_score = gscore[current] + 1
                    if tentative_g_score < gscore.get(neighbor, float('inf')):
                        came_from[neighbor] = current
                        gscore[neighbor] = tentative_g_score
                        fscore[neighbor] = tentative_g_score + heuristic(neighbor, goal)
                        heapq.heappush(oheap, (fscore[neighbor], neighbor))
        return []

    def state(self) -> State:
        return State(
            workers=self.workers,
            orders=[o for o in self.orders if o.status != "completed"],
            inventory=self.inventory,
            grid_size=self.grid_size,
            time_step=self.time_step
        )

    def step_multi(self, actions_str: List[str]) -> Tuple[State, float, bool, List[Dict[str, Any]]]:
        """Process actions for ALL workers in a single time step."""
        self.time_step += 1
        total_points = 0.0
        all_info = []
        all_events = []
        
        # Step-level metrics
        order_completed_this_step = False
        deadline_missed_this_step = False
        items_picked_this_step = 0

        for action_index, action_str in enumerate(actions_str):
            action = Action.parse(action_str)
            if action.worker_id is None and action_index < len(self.workers):
                action.worker_id = self.workers[action_index].id
            worker = next((w for w in self.workers if w.id == action.worker_id), None)
            
            info = {
                "worker_id": action.worker_id if action.worker_id is not None else -1,
                "action_taken": action.type,
                "result": "success",
            }
            item_picked = False
            order_completed = False

            if worker:
                # Pre-step distance capture
                if worker.target:
                    worker.previous_dist = abs(worker.position[0] - worker.target[0]) + abs(worker.position[1] - worker.target[1])
                
                # Execute Action
                if action.type == "move":
                    new_pos = self.logic.get_new_position(worker.position, action.direction, self.grid_size)
                    worker.position = new_pos
                    self.metrics["distance"] += 1
                
                elif action.type == "assign_order":
                    order = next((o for o in self.orders if o.id == action.order_id and o.status == "pending"), None)
                    if order:
                        order.status = "assigned"
                        worker.assigned_order_id = order.id
                        worker.status = Status.BUSY
                        worker.task_type = TaskType.PICKUP
                        if order.items: worker.target = self.inventory.get(order.items[0])
                    else: info["result"] = "invalid_action"

                elif action.type == "pick_item":
                    if self.logic.is_valid_pick(worker, action.item_id, self.inventory):
                        worker.items_held.append(action.item_id)
                        worker.load += 1
                        item_picked = True
                        items_picked_this_step += 1
                        order = next((o for o in self.orders if o.id == worker.assigned_order_id), None)
                        if order:
                            remaining = [i for i in order.items if i not in worker.items_held]
                            if remaining:
                                worker.target = self.inventory.get(remaining[0])
                                worker.task_type = TaskType.PICKUP
                            else:
                                worker.target = self.delivery_zone
                                worker.task_type = TaskType.DELIVERY
                    else: info["result"] = "invalid_action"

                elif action.type == "deliver_order":
                    if self.logic.is_valid_delivery(worker, action.order_id, self.orders, self.delivery_zone):
                        order = next((o for o in self.orders if o.id == action.order_id))
                        order.status = "completed"
                        worker.status = Status.IDLE
                        worker.assigned_order_id = None
                        worker.target = None
                        worker.task_type = TaskType.IDLE
                        for item in order.items:
                            if item in worker.items_held: worker.items_held.remove(item)
                        worker.load -= len(order.items)
                        order_completed = True
                        order_completed_this_step = True
                        self.metrics["completed"] += 1
                    else: info["result"] = "invalid_action"

                # Calculate Reward for THIS worker
                worker_reward, events = self.logic.calculate_reward(worker, action, info["result"], self.state(), 
                                                           order_completed, False, item_picked)
                total_points += worker_reward
                all_events.extend(events)
                all_info.append({**info, "events": events})

        # Check for missed deadlines (once per step)
        deadline_penalty = 0
        for order in self.orders:
            if order.status != "completed" and self.time_step > order.deadline and not order.penalty_paid:
                deadline_missed_this_step = True
                order.penalty_paid = True
                deadline_penalty -= 50.0

        total_points += deadline_penalty
        self.last_step_points = float(total_points)

        # Normalized reward in [0, 1] for OpenEnv compliance
        total_reward = max(0.0, min(1.0, float(total_points) / 100.0))

        self.metrics["points"] += float(total_points)
        self.metrics["rewards"] += float(total_reward)

        if self.dynamic_orders and random.random() < 0.1:
            self._add_random_order()

        done = self.time_step >= 500 or (len(self.orders) > 0 and all(o.status == "completed" for o in self.orders))
        return self.state(), float(total_reward), done, all_info

    def step(self, action_str: str) -> Tuple[State, float, bool, Dict[str, Any]]:
        # Traditional step wrapper for backward compatibility
        state, reward, done, all_info = self.step_multi([action_str])
        return state, reward, done, all_info[0] if all_info else {}
