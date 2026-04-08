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
- `+100` for Order Delivery.
- `+0.5` per unit Manhattan distance decreased.
- `-1.0` per adjacent agent (congestion).
- `-2.0` for idling when busy.
