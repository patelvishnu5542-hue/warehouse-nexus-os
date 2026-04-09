import time
from warehouse_env.levels import get_env_for_level
from warehouse_env.utils import WarehouseVisualizer
from agents.baseline import BaselineAgent

def test_run(level: int = 1, max_steps: int = 30):
    env = get_env_for_level(level)
    agent = BaselineAgent()
    state = env.state()
    
    print(f"--- Starting Baseline Simulation (Level {level}) ---")
    
    for step in range(max_steps):
        # 1. Visualize
        WarehouseVisualizer.render_console(state)
        
        # 2. Get Actions (one per worker)
        actions = [agent.get_action(state, w.id) for w in state.workers]
        print(f"Step {step} | Actions: {actions}")

        # 3. Step
        if len(actions) == 1:
            state, reward, done, info = env.step(actions[0])
        else:
            state, reward, done, info = env.step_multi(actions)
        
        if done:
            print("Environment finished.")
            break
            
        time.sleep(0.1)
        
    print("\n--- Final Metrics ---")
    for k, v in env.metrics.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    test_run(level=1)
