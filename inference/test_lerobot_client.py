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


def create_sample_observation():
    """Create sample observation (replace with your actual observation)"""
    observation = OrderedDict()
    observation['agent_pos'] = np.random.randn(1, 14).astype(np.float32)
    observation['pixels'] = {
        'top': np.random.randint(0, 256, (1, 480, 640, 3), dtype=np.uint8)
    }
    return observation

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
        observation = create_sample_observation()
        action = client.select_action(observation)
        print(f"✅ Received action: shape={action.shape}")
        print(f"   Action range: [{action.min():.3f}, {action.max():.3f}]")
        print(f"   Action: {action}")
        
        # You can call select_action multiple times
        for i in range(3):
            # Update your observation here...
            observation = create_sample_observation()  # Replace with real observation
            action = client.select_action(observation)
            print(f"   Step {i+1}: action shape {action.shape}")
            print(f"   Action: {action}")

if __name__ == "__main__":
    main_sync()