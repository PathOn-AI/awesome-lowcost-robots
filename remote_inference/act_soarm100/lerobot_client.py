#!/usr/bin/env python

import asyncio
import numpy as np
import torch
import websockets
import threading
import logging
from typing import Dict, Any, Optional
from msgpack_utils import packb, unpackb
from time import time


class LeRobotClientError(Exception):
    pass


class LeRobotClient:
    def __init__(self, uri: str, max_message_size: int = 100 * 1024 * 1024, timeout: float = 30.0):
        self.uri = "ws://localhost:8765" if uri is None else uri
        self.max_message_size = max_message_size
        self.timeout = timeout
        self._websocket: Optional[websockets.WebSocketServerProtocol] = None
        self._connected = False
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self._websocket is not None
    
    async def connect(self) -> None:
        if self._connected:
            self.logger.warning("Already connected to server")
            return
        
        try:
            self.logger.info(f"Connecting to {self.uri}...")
            self._websocket = await asyncio.wait_for(
                websockets.connect(self.uri, max_size=self.max_message_size),
                timeout=self.timeout
            )
            self._connected = True
            self.logger.info("✅ Connected to LeRobot server")
            
        except asyncio.TimeoutError:
            raise LeRobotClientError(f"Connection timeout after {self.timeout}s")
        except websockets.exceptions.ConnectionRefused:
            raise LeRobotClientError(f"Connection refused. Is server running on {self.uri}?")
        except Exception as e:
            raise LeRobotClientError(f"Failed to connect: {e}")
    
    async def disconnect(self) -> None:
        if self._websocket and self._connected:
            await self._websocket.close()
            self.logger.info("Disconnected from server")
        self._websocket = None
        self._connected = False
    
    async def _send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_connected:
            raise LeRobotClientError("Not connected to server. Call connect() first.")
        
        try:
            message_bytes = packb(message)
            await asyncio.wait_for(self._websocket.send(message_bytes), timeout=self.timeout)
            
            response_bytes = await asyncio.wait_for(self._websocket.recv(), timeout=self.timeout)
            response = unpackb(response_bytes)
            
            if response.get("type") == "error":
                raise LeRobotClientError(f"Server error: {response.get('message', 'Unknown error')}")
            
            return response
            
        except asyncio.TimeoutError:
            raise LeRobotClientError(f"Operation timeout after {self.timeout}s")
        except Exception as e:
            raise LeRobotClientError(f"Communication error: {e}")
    
    async def ping(self) -> bool:
        try:
            response = await self._send_message({"type": "ping"})
            return response.get("type") == "pong"
        except LeRobotClientError:
            return False
    
    async def reset(self) -> bool:
        response = await self._send_message({"type": "reset"})
        
        if response.get("type") == "reset_response":
            self.logger.info("Environment reset successful")
            return True
        else:
            raise LeRobotClientError(f"Reset failed: {response}")
    
    async def select_action(self, observation: Dict[str, Any]) -> np.ndarray:
        if not isinstance(observation, dict):
            raise LeRobotClientError("Observation must be a dictionary")
        
        message = {"type": "select_action", "observation": observation}
        response = await self._send_message(message)

        if response.get("type") == "action_response":
            action = response["action"]
            self.logger.debug(f"Received action with shape: {action.shape}")
            return action
        else:
            raise LeRobotClientError(f"Unexpected response: {response}")
