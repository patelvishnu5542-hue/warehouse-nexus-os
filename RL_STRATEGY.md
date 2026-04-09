# Reinforcement Learning Strategy: Multi-Agent Warehouse

## 1. State Representation (Observation Space)
For high-performance learning, we use a decentralized approach:
- **Local Ego State**: `[x, y, load, capacity, task_type_id]`
- **Goal Information**: `[target_x, target_y, target_dist, target_angle]`
- **Local Grid View**: 5x5 occupancy map (congestion handling).
- **Global Context**: `[time_step, pending_orders_count]`

## 2. Action Space
- **Discrete Commands**: `NOOP`, `MOVE_{U,D,L,R}`, `PICK_ITEM`, `DELIVER_ORDER`.
- **High-Level Action**: `AUTO_NAVIGATE` (Uses A* heuristic).

## 3. Recommended Algorithm: MAPPO
**Multi-Agent Proximal Policy Optimization (MAPPO)** is recommended for centralized training and decentralized execution, ensuring stability in complex coordination tasks.

## 4. Reward Shaping (Implemented)
Shaped **raw points** are computed per-worker (then summed per step) in `warehouse_env/logic.py`:
- `-0.01` base step cost (per worker, per step)
- `+0.5 * (previous_dist - current_dist)` goal shaping (Manhattan distance to current target)
- `+20` pick bonus
- `+100` delivery bonus
- `-5` invalid action penalty
- `-2` for `noop()` while `BUSY` (idling when busy)
- Congestion penalty: `-(congestion_penalty * adjacent_workers)` where `congestion_penalty` depends on level:
  - Level 1: `0.0`
  - Level 2: `1.0`
  - Level 3: `2.0`
- Deadline penalty: `-50` once per order when the deadline is first missed

For OpenEnv compliance, the HTTP `/step` response returns a **normalized** `reward.value` in `[0,1]` computed as `clamp(total_points / 100, 0, 1)`, and exposes raw points as `info.raw_points`.
