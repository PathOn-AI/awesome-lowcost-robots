from time import sleep
from lerobot.common.robot_devices.motors.configs import FeetechMotorsBusConfig
from lerobot.common.robot_devices.motors.feetech import FeetechMotorsBus
from lerobot.common.robot_devices.robots.utils import make_robot_config
import json
import numpy as np
import time

## inspired and modified from https://github.com/alexis779/slobot

class Configuration:
    # 16:9 aspect ratio
    LD = (426, 240)
    SD = (854, 480)
    HD = (1280, 720)
    FHD = (1920, 1080)

    QPOS_MAP = {
        "zero": [0, 0, 0, 0, 0, 0],
        "rotated": [-np.pi/2, -np.pi/2, np.pi/2, np.pi/2, -np.pi/2, np.pi/2],
        "rest": [0.049, -3.62, 3.19, 1.26, -0.17, -0.67]
    }

    POS_MAP = {
        "zero": [2035, 3081, 1001, 1966, 1988, 2125],
        "rotated": [3052, 2021, 2040, 3062, 905, 3179],
        "rest": [2068, 819, 3051, 2830, 2026, 2049],
    }

    DOFS = 6
    JOINT_NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]



class Feetech():
    ROBOT_TYPE = 'so100'
    ARM_NAME = 'main'
    ARM_TYPE = 'follower'

    MODEL_RESOLUTION = 4096
    RADIAN_PER_STEP = (2 * np.pi) / MODEL_RESOLUTION
    MOTOR_DIRECTION = [-1, 1, 1, 1, 1, 1]
    JOINT_IDS = [0, 1, 2, 3, 4, 5]
    PORT = '/dev/tty.usbmodem59700741371'
    REFERENCE_FRAME = 'rotated'

    def move_to_pos(self, pos):
        self.move(pos)

    def __init__(self, **kwargs):
        self.qpos_handler = kwargs.get('qpos_handler', None)
        connect = kwargs.get('connect', True)
        if connect:
            self.connect()

    def connect(self):
        self.motors_bus = self._create_motors_bus()

    def disconnect(self):
        self.motors_bus.disconnect()


    def get_pos(self):
        return self.motors_bus.read('Present_Position')

    def move(self, target_pos):
        self.control_position(target_pos)
        position = self.get_pos()
        print(position)
        print(target_pos)
        error = np.linalg.norm(target_pos - position) / Feetech.MODEL_RESOLUTION
        print("pos error=", error)

    def go_to_rest(self):
        self.go_to_preset('rest')

    def go_to_preset(self, preset):
        pos = Configuration.POS_MAP[preset]
        self.move(pos)
        time.sleep(1)
        self.disconnect()

    def _create_motors_bus(self):
        robot_config = make_robot_config(Feetech.ROBOT_TYPE)
        motors = robot_config.follower_arms[Feetech.ARM_NAME].motors
        config = FeetechMotorsBusConfig(port=self.PORT, motors=motors)
        motors_bus = FeetechMotorsBus(config)
        motors_bus.connect()
        return motors_bus

    def _motor_names(self, ids):
        return [
            self._motor_name(id)
            for id in ids
        ]

    def _motor_name(self, id):
        return Configuration.JOINT_NAMES[id]
    
    def control_position(self, pos):
        self.motors_bus.write('Goal_Position', pos)


feetech = Feetech()

print(Configuration.POS_MAP['zero'])
feetech.move(Configuration.POS_MAP['zero'])
sleep(2)
feetech.move(Configuration.POS_MAP['rest'])
sleep(2)
feetech.move_to_pos([2035, 3081, 3001, 1966, 1988, 2125])
sleep(2)
feetech.move_to_pos([2035, 3081, 2001, 1966, 1988, 2125])
sleep(2)
feetech.move_to_pos([2035, 3081, 1001, 1966, 1988, 2125])
sleep(2)
feetech.go_to_rest()
sleep(1)
