# SO-ARM100 Robot Control

Control the SO-ARM100 robotic arm in both physical and simulation environments.

## 🤖 1. Physical Robot Control

**Hardware**: SO-ARM100 by Feetech

**TODO:**
- [ ] Keyboard control implementation
- [ ] Camera integration
- [ ] Save data in LeRobotDataset format

## 🎮 2. Simulation Control

### 2.1 MuJoCo (Ready)

**Quick Start:**
```bash
pip install mujoco
mjpython script.py --control threaded_input
```

**Controls:**
- `q+/q-`: Rotation | `w+/w-`: Pitch | `e+/e-`: Elbow
- `r+/r-`: Wrist Pitch | `t+/t-`: Wrist Roll | `y+/y-`: Jaw
- `reset`: Zero position | `status`: Show positions | `quit`: Exit

**Robot Model Sources:**
- [MJCF Model](https://github.com/google-deepmind/mujoco_menagerie/tree/main/trs_so_arm100) (Google DeepMind)
- [Original URDF](https://github.com/TheRobotStudio/SO-ARM100/blob/main/Simulation/SO100/so100.urdf) (The Robot Studio)

### 2.2 Genesis (In Development)

Integration with LeRobot ecosystem coming soon.


### 2.3 Maniskill (In Development)

## 📚 References

- [XLeRobot Simulation Guide](https://github.com/Vector-Wangel/XLeRobot/blob/main/simulation/sim_guide.md)
- [Simulator Comparison](https://simulately.wiki/docs/comparison/)