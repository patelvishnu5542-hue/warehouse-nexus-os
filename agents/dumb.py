import random

from warehouse_env.models import State, Status


class DumbAgent:
    """
    Intentionally weak baseline:
    - Mostly noop
    - Occasionally random moves
    """

    def __init__(self, move_prob: float = 0.35):
        self.move_prob = move_prob

    def get_action(self, state: State, worker_id: int) -> str:
        worker = next((w for w in state.workers if w.id == worker_id), None)
        if not worker:
            return "noop()"

        if random.random() > self.move_prob:
            return "noop()"

        direction = random.choice(["up", "down", "left", "right"])
        return f"move({worker.id}, '{direction}')"

