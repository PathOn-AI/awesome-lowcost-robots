#!/usr/bin/env python

"""
WebSocket server for serving LeRobot policies with large data handling.
"""

import asyncio
import json
import logging
import pickle
import base64
import gzip
from typing import Dict, Any
import websockets
import torch
import numpy as np
from websockets.server import WebSocketServerProtocol
from lerobot.common.utils.random_utils import set_seed

from lerobot.common.policies.pretrained import PreTrainedPolicy
from lerobot.common.utils.utils import get_safe_torch_device
from lerobot.common.envs.factory import make_env
from lerobot.common.envs.utils import add_envs_task, check_env_attributes_and_types, preprocess_observation
from lerobot.common.policies.factory import make_policy
from lerobot.configs.eval import EvalPipelineConfig
from lerobot.configs import parser
from lerobot.common.policies.act.modeling_act import ACTPolicy
from lerobot.common.robot_devices.utils import busy_wait
from lerobot.common.robot_devices.robots.utils import make_robot

import torch



# def convert_nested_to_flat_observation(nested_observation, device):
#     flat_observation = {}
    
#     for key, value in nested_observation.items():    
#         print(f"key: {key}")
#         if isinstance(value, dict):
#             # Handle nested dictionaries
#             for subkey, subvalue in value.items():
#                 flat_key = f'observation.{key}.{subkey}'
#                 subvalue = torch.from_numpy(subvalue)
#                 flat_observation[flat_key] = subvalue
#                 flat_observation[flat_key] = flat_observation[flat_key].to(device)
#         else:
#             # Handle simple values
#             flat_key = f'observation.{key}'
#             print(f"flat_key: {flat_key}")
            
#             # for key, value in flat_observation.items():
#             value = torch.from_numpy(value)
#             flat_observation[flat_key] = value
#             flat_observation[flat_key] = flat_observation[flat_key].to(device)
    
#     return flat_observation

def convert_observation(observation, device):
    flat_observation = {}
    for key, value in observation.items():
        value = torch.from_numpy(value)
        flat_observation[key] = value
    return flat_observation

class PolicyWebSocketServer:
    """WebSocket server that serves a policy for inference."""
    
    def __init__(self, policy: PreTrainedPolicy, device: str = "cuda", 
                 max_size: int = 100 * 1024 * 1024,  # 100MB limit
                 compression_level: int = 6):
        self.policy = policy
        self.device = device
        self.max_size = max_size
        self.compression_level = compression_level
        self.policy.to(self.device)
        self.policy.eval()
        
    async def handle_client(self, websocket: WebSocketServerProtocol):
        """Handle incoming WebSocket connections."""
        logging.info(f"Client connected from {websocket.remote_address}")
        
        async for message in websocket:
            # Parse the incoming message
            data = json.loads(message)
                
            if data.get("type") == "select_action":
                # Deserialize observation data

                # Deserialize observation data to numpy arrays
                observation = self._deserialize_observation(data["observation"])
                observation = convert_observation(observation, device=self.device)
                observation = self._move_observation_to_device(observation)

                with torch.inference_mode():
                    action = self.policy.select_action(observation)

                # Serialize and send response (convert to numpy first)
                response = {
                    "type": "action_response",
                    "action": self._serialize_array(action.cpu().numpy())
                }
                
                await websocket.send(json.dumps(response))
                
            elif data.get("type") == "reset":
                # Reset the policy
                self.policy.reset()
                response = {"type": "reset_response", "status": "success"}
                await websocket.send(json.dumps(response))
                
            elif data.get("type") == "ping":
                # Health check
                response = {"type": "pong"}
                await websocket.send(json.dumps(response))
                    
    
    def _move_observation_to_device(self, observation):
        """Recursively move observation tensors to device."""
        if isinstance(observation, torch.Tensor):
            return observation.to(self.device, non_blocking=self.device == "cuda")
        elif isinstance(observation, dict):
            return {
                key: self._move_observation_to_device(value) 
                for key, value in observation.items()
            }
        else:
            return observation
            
    def _serialize_tensor(self, tensor: torch.Tensor) -> str:
        """Serialize a tensor to compressed base64 string."""
        # Use pickle to serialize
        pickled_data = pickle.dumps(tensor)
        
        # Compress the data
        compressed_data = gzip.compress(pickled_data, compresslevel=self.compression_level)
        
        # Base64 encode
        return base64.b64encode(compressed_data).decode('utf-8')
    
    def _deserialize_tensor(self, data: str) -> torch.Tensor:
        """Deserialize a tensor from compressed base64 string."""
        # Base64 decode
        compressed_data = base64.b64decode(data.encode('utf-8'))
        
        # Decompress
        pickled_data = gzip.decompress(compressed_data)
        
        # Unpickle
        return pickle.loads(pickled_data)
    
    def _serialize_array(self, array: np.ndarray) -> str:
        """Serialize a numpy array to compressed base64 string."""
        # Use pickle to serialize
        pickled_data = pickle.dumps(array)
        
        # Compress the data
        compressed_data = gzip.compress(pickled_data, compresslevel=self.compression_level)
        
        # Base64 encode
        return base64.b64encode(compressed_data).decode('utf-8')
    
    def _deserialize_array(self, data: str) -> np.ndarray:
        """Deserialize a numpy array from compressed base64 string."""
        # Base64 decode
        compressed_data = base64.b64decode(data.encode('utf-8'))
        
        # Decompress
        pickled_data = gzip.decompress(compressed_data)
        
        # Unpickle
        return pickle.loads(pickled_data)
    
    def _serialize_observation(self, observation: Dict) -> Dict:
        """Serialize observation dictionary recursively."""
        result = {}
        for key, value in observation.items():
            if isinstance(value, (torch.Tensor, np.ndarray)):
                # Convert tensor to numpy if needed, then serialize
                if isinstance(value, torch.Tensor):
                    value = value.cpu().numpy()
                result[key] = self._serialize_array(value)
            elif isinstance(value, dict):
                result[key] = self._serialize_observation(value)
            else:
                result[key] = value
        return result
    
    def _deserialize_observation(self, data: Dict) -> Dict:
        """Deserialize observation dictionary recursively."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                # Assume it's a serialized numpy array
                result[key] = self._deserialize_array(value)
            elif isinstance(value, dict):
                result[key] = self._deserialize_observation(value)
            else:
                result[key] = value
        return result
    
    async def start_server(self, host: str = "localhost", port: int = 8765):
        """Start the WebSocket server with increased message size limit."""
        logging.info(f"Starting policy server on {host}:{port}")
        logging.info(f"Max message size: {self.max_size / (1024*1024):.1f}MB")
        
        async with websockets.serve(
            self.handle_client, 
            host, 
            port,
            max_size=self.max_size,  # Increase size limit
            compression=None  # We handle compression ourselves
        ):
            logging.info("Policy server is running...")
            await asyncio.Future()  # Run forever

# @parser.wrap()
def create_policy_server() -> PolicyWebSocketServer:
    """Create and configure the policy server."""
    device = "cuda"

    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    # set_seed(cfg.seed)

    # logging.info("Making environment.")
    # env = make_env(cfg.env, n_envs=cfg.eval.batch_size, use_async_envs=cfg.eval.use_async_envs)

    # logging.info("Making policy.")
    # policy = make_policy(cfg=cfg.policy, env_cfg=cfg.env)
    # policy.eval()
    policy = ACTPolicy.from_pretrained("DanqingZ/act_so100_filtered_yellow_cuboid")
    policy.to(device)
    
    return PolicyWebSocketServer(
        policy, 
        device,
        max_size=100 * 1024 * 1024,  # 100MB limit
        compression_level=6  # Good balance of speed vs compression
    )

async def main():
    """Run the server."""
    server = create_policy_server()
    await server.start_server('0.0.0.0', 8765)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())