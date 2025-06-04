import time

import torch
import cv2
import numpy as np

from lerobot.common.policies.act.modeling_act import ACTPolicy
from lerobot.common.robot_devices.utils import busy_wait
from lerobot.common.robot_devices.robots.utils import make_robot
from lerobot_client import SyncLeRobotClient


inference_time_s = 30
fps = 25
device = "mps" 

# ckpt_path = "/home/alexis/Documents/python/robotics/so100_ball_cup_act"
policy = ACTPolicy.from_pretrained("DanqingZ/act_so100_filtered_yellow_cuboid")
policy.to(device)


robot = make_robot("so100")
robot.connect()


for step in range(inference_time_s * fps):
    start_time = time.perf_counter()
    observation = robot.capture_observation()
    print(step)
    # observation = convert_flat_to_nested_observation(observation)
    for name in observation:
        if "image" in name:
            observation[name] = observation[name].type(torch.float32) / 255
            observation[name] = observation[name].permute(2, 0, 1).contiguous()
        observation[name] = observation[name].unsqueeze(0)
        observation[name] = observation[name].numpy()
        #.to(device)
        print(name, observation[name].shape)

    with SyncLeRobotClient() as client:
        action = client.select_action(observation)

    action = torch.from_numpy(action)
    action = action.squeeze(0)
    robot.send_action(action)

    dt_s = time.perf_counter() - start_time
    busy_wait(1 / fps - dt_s)