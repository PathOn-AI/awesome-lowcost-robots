# SO-ARM101 Robot Control Script

## 🛠️ Prerequisites

- Python environment with LeRobot installed
- SO-ARM101 robotic arm hardware

```bash
conda activate lerobot
```

## 🚀 Quick Start

### 1. Physical Robot Control

**Follower Arm Control** - Moves the robot through a sequence of positions:
```bash
python control_robot.py
```

**Leader Arm Control** - Control the leader arm for teleoperation:
```bash
python control_teleoperator.py
```

### 2. Real-time Position Monitoring

Monitor live position data from the leader arm:
```bash
python use_teleoperator.py
```
