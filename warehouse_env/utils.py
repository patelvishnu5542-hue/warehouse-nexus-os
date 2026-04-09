from typing import Dict, Any, List
from .models import State

class WarehouseVisualizer:
    @staticmethod
    def render_console(state: State):
        grid = [["." for _ in range(state.grid_size[0])] for _ in range(state.grid_size[1])]
        
        # Plot inventory
        for item_id, pos in state.inventory.items():
            x, y = pos
            if 0 <= x < state.grid_size[0] and 0 <= y < state.grid_size[1]:
                grid[y][x] = "I"
        
        # Plot workers
        for worker in state.workers:
            x, y = worker.position
            if 0 <= x < state.grid_size[0] and 0 <= y < state.grid_size[1]:
                grid[y][x] = str(worker.id)
                
        print(f"\nTime Step: {state.time_step}")
        for row in reversed(grid):
            print(" ".join(row))
        print("-" * (state.grid_size[0] * 2))

    @staticmethod
    def plot_metrics(metrics: Dict[str, Any]):
        # This can be used for final summary
        print("\n--- Final Metrics ---")
        for k, v in metrics.items():
            print(f"{k}: {v}")

class MetricsTracker:
    def __init__(self):
        self.history = []

    def log(self, state: State, reward: float, info: Dict[str, Any]):
        self.history.append({
            "time_step": state.time_step,
            "reward": reward,
            "completed": sum(1 for o in state.orders if o.status == "completed")
        })
