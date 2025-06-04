#!/usr/bin/env python
"""
Simple usage example for LeRobot WebSocket Client.
Copy this pattern for your own projects.
"""

import asyncio
import numpy as np
from collections import OrderedDict
from lerobot_client import LeRobotClient
from lerobot_client import SyncLeRobotClient


def create_sample_observation_aloha():
    """Create sample observation (replace with your actual observation)"""
    observation = OrderedDict()
    observation['agent_pos'] = np.random.randn(1, 14).astype(np.float32)
    observation['pixels'] = {
        'top': np.random.randint(0, 256, (1, 480, 640, 3), dtype=np.uint8)
    }
    return observation

def create_sample_observation_soarm100():
    """Create sample observation (replace with your actual observation)"""
    observation = OrderedDict()
    
    # State with shape [1, 6] instead of [1, 14]
    observation['state'] = np.random.randn(1, 6).astype(np.float32)
    
    # Images nested structure with on_robot and phone cameras
    # Shape is [1, 3, 480, 640] (batch, channels, height, width)
    observation['images'] = {
        'on_robot': np.random.randint(0, 256, (1, 3, 480, 640), dtype=np.uint8),
        'phone': np.random.randint(0, 256, (1, 3, 480, 640), dtype=np.uint8)
    }
    
    return observation

def print_observation_shape(observation):
    for key, value in observation.items():
        if isinstance(value, dict):
            print(f"{key}:")
            print_observation_shape(value)
            print(type(value))
        else:
            print(f"   {key}: shape={value.shape}")
            print(type(value))

def main_sync():
    """SYNCHRONOUS example - no async/await needed!"""
    print("🔄 Synchronous Usage (Recommended)")
    print("-" * 35)
    
    # Use the sync client (automatically connects and disconnects)
    with SyncLeRobotClient() as client:
        
        # Reset environment
        client.reset()
        print("✅ Environment reset")
        
        # Get action from observation
        #observation = create_sample_observation_aloha()
        observation = create_sample_observation_soarm100()
        print_observation_shape(observation)
        # import pdb; pdb.set_trace()
        action = client.select_action(observation)
        print(f"✅ Received action: shape={action.shape}")
        print(f"   Action range: [{action.min():.3f}, {action.max():.3f}]")
        print(f"   Action: {action}")
        
        # You can call select_action multiple times
        for i in range(3):
            # Update your observation here...
            #observation = create_sample_observation_aloha()  # Replace with real observation
            observation = create_sample_observation_soarm100()
            print_observation_shape(observation)
            action = client.select_action(observation)
            print(f"   Step {i+1}: action shape {action.shape}")
            print(f"   Action: {action}")

if __name__ == "__main__":
    main_sync()