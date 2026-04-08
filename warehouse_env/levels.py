from typing import Dict, Any, List
from .env import WarehouseEnv

class LevelConfig:
    LEVEL_1 = {
        "num_workers": 1,
        "grid_size": [10, 10],
        "dynamic_orders": False,
        "congestion_penalty": 0.0
    }
    LEVEL_2 = {
        "num_workers": 2,
        "grid_size": [15, 15],
        "dynamic_orders": True,
        "congestion_penalty": 1.0
    }
    LEVEL_3 = {
        "num_workers": 5,
        "grid_size": [20, 20],
        "dynamic_orders": True,
        "congestion_penalty": 2.0,
        "fatigue_enabled": True
    }

class WarehouseGrader:
    @staticmethod
    def grade(level: int, metrics: Dict[str, Any]) -> float:
        """
        Returns a score from 0.0 to 1.0 based on metrics.
        """
        completed = int(metrics.get("completed", 0) or 0)
        points = float(metrics.get("points", 0.0) or 0.0)
        
        # Simple grading logic
        if level == 1:
            # Level 1 expects at least 3 orders completed for full score
            score = min(1.0, completed / 5.0)
        elif level == 2:
            score = min(1.0, (completed / 10.0) * (1.0 if points > 0 else 0.5))
        elif level == 3:
            # Scale points loosely; clamp to [0,1]
            score = min(1.0, (completed / 15.0) * (points / 500.0 if points > 0 else 0.1))
        else:
            score = 0.0
            
        return float(max(0.0, score))

def get_env_for_level(level: int) -> WarehouseEnv:
    config = getattr(LevelConfig, f"LEVEL_{level}", LevelConfig.LEVEL_1)
    return WarehouseEnv(
        grid_size=tuple(config["grid_size"]),
        num_workers=config["num_workers"],
        dynamic_orders=bool(config.get("dynamic_orders", True)),
        congestion_penalty=float(config.get("congestion_penalty", 1.0)),
    )
