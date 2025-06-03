#!/usr/bin/env python

import asyncio
import json
import pickle
import base64
import gzip
import numpy as np
import websockets
from typing import Dict, Any, Optional, Union
import logging
from collections import OrderedDict


import asyncio
import numpy as np
import threading
from typing import Dict, Any, Optional
from collections import OrderedDict
import logging



class LeRobotClientError(Exception):
    """Custom exception for LeRobot client errors."""
    pass

class LeRobotClient:
    """
    WebSocket client for LeRobot servers.
    
    Handles serialization of numpy observations, compression, and communication
    with LeRobot WebSocket servers.
    """
    
    def __init__(self, uri: str, 
                 compression_level: int = 6, max_message_size: int = 100 * 1024 * 1024,
                 timeout: float = 30.0):
        """
        Initialize LeRobot client.
        
        Args:
            host: Server hostname (default: localhost)
            port: Server port (default: 8765) 
            compression_level: Gzip compression level 1-9 (default: 6)
            max_message_size: Maximum WebSocket message size in bytes (default: 100MB)
            timeout: Timeout for operations in seconds (default: 30)
        """
        self.uri = "ws://6.tcp.us-cal-1.ngrok.io:16363" if uri is None else uri
        #"wss://49a3-192-184-146-191.ngrok-free.app" if uri is None else uri
        self.compression_level = compression_level
        self.max_message_size = max_message_size
        self.timeout = timeout
        
        self._websocket: Optional[websockets.WebSocketServerProtocol] = None
        self._connected = False
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected to server."""
        return self._connected and self._websocket is not None
    
    def _serialize_array(self, array: np.ndarray) -> str:
        """
        Serialize a numpy array to compressed base64 string.
        
        Args:
            array: NumPy array to serialize
            
        Returns:
            Base64-encoded compressed string
        """
        pickled_data = pickle.dumps(array)
        compressed_data = gzip.compress(pickled_data, compresslevel=self.compression_level)
        return base64.b64encode(compressed_data).decode('utf-8')
    
    def _deserialize_array(self, data: str) -> np.ndarray:
        """
        Deserialize a numpy array from compressed base64 string.
        
        Args:
            data: Base64-encoded compressed string
            
        Returns:
            Deserialized NumPy array
        """
        compressed_data = base64.b64decode(data.encode('utf-8'))
        pickled_data = gzip.decompress(compressed_data)
        return pickle.loads(pickled_data)
    
    def _serialize_observation(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize observation dictionary recursively.
        
        Args:
            obs: Observation dictionary containing numpy arrays
            
        Returns:
            Serialized observation dictionary
        """
        result = {}
        for key, value in obs.items():
            if isinstance(value, np.ndarray):
                result[key] = self._serialize_array(value)
            elif isinstance(value, dict):
                result[key] = {k: self._serialize_array(v) for k, v in value.items()}
            else:
                result[key] = value
        return result
    
    async def connect(self) -> None:
        """
        Connect to the LeRobot WebSocket server.
        
        Raises:
            LeRobotClientError: If connection fails
        """
        if self._connected:
            self.logger.warning("Already connected to server")
            return
        
        try:
            self.logger.info(f"Connecting to {self.uri}...")
            self._websocket = await asyncio.wait_for(
                websockets.connect(
                    self.uri,
                    max_size=self.max_message_size
                ),
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
        """Disconnect from the WebSocket server."""
        if self._websocket and self._connected:
            await self._websocket.close()
            self.logger.info("Disconnected from server")
        
        self._websocket = None
        self._connected = False
    
    async def _send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message and wait for response.
        
        Args:
            message: Message dictionary to send
            
        Returns:
            Response dictionary from server
            
        Raises:
            LeRobotClientError: If not connected or communication fails
        """
        if not self.is_connected:
            raise LeRobotClientError("Not connected to server. Call connect() first.")
        
        try:
            # Send message
            message_str = json.dumps(message)
            await asyncio.wait_for(
                self._websocket.send(message_str),
                timeout=self.timeout
            )
            
            # Wait for response
            response_str = await asyncio.wait_for(
                self._websocket.recv(),
                timeout=self.timeout
            )
            
            response = json.loads(response_str)
            
            # Check for server errors
            if response.get("type") == "error":
                raise LeRobotClientError(f"Server error: {response.get('message', 'Unknown error')}")
            
            return response
            
        except asyncio.TimeoutError:
            raise LeRobotClientError(f"Operation timeout after {self.timeout}s")
        except json.JSONDecodeError as e:
            raise LeRobotClientError(f"Invalid JSON response: {e}")
        except Exception as e:
            raise LeRobotClientError(f"Communication error: {e}")
    
    async def ping(self) -> bool:
        """
        Send a ping to test server connectivity.
        
        Returns:
            True if ping successful, False otherwise
        """
        try:
            response = await self._send_message({"type": "ping"})
            return response.get("type") == "pong"
        except LeRobotClientError:
            return False
    
    async def reset(self) -> bool:
        """
        Reset the environment on the server.
        
        Returns:
            True if reset successful
            
        Raises:
            LeRobotClientError: If reset fails
        """
        response = await self._send_message({"type": "reset"})
        
        if response.get("type") == "reset_response":
            self.logger.info("Environment reset successful")
            return True
        else:
            raise LeRobotClientError(f"Reset failed: {response}")
    
    async def select_action(self, observation: Dict[str, Any]) -> np.ndarray:
        """
        Request action selection from the server given an observation.
        
        Args:
            observation: Observation dictionary containing numpy arrays
                Expected structure:
                - 'agent_pos': numpy array of shape (1, 14)
                - 'pixels': dict with 'top' key containing array of shape (1, 480, 640, 3)
        
        Returns:
            Action numpy array from the server
            
        Raises:
            LeRobotClientError: If action selection fails
        """
        # Validate observation structure
        if not isinstance(observation, dict):
            raise LeRobotClientError("Observation must be a dictionary")
        
        # Serialize observation
        try:
            serialized_obs = self._serialize_observation(observation)
        except Exception as e:
            raise LeRobotClientError(f"Failed to serialize observation: {e}")
        
        # Send action request
        message = {
            "type": "select_action",
            "observation": serialized_obs
        }
        
        # Log data size info
        if self.logger.isEnabledFor(logging.DEBUG):
            message_str = json.dumps(message)
            size_mb = len(message_str.encode('utf-8')) / (1024 * 1024)
            self.logger.debug(f"Sending observation of size: {size_mb:.2f}MB")
        
        response = await self._send_message(message)
        
        if response.get("type") == "action_response":
            try:
                action = self._deserialize_array(response["action"])
                self.logger.debug(f"Received action with shape: {action.shape}")
                return action
            except Exception as e:
                raise LeRobotClientError(f"Failed to deserialize action: {e}")
        else:
            raise LeRobotClientError(f"Unexpected response: {response}")
    
    def get_compression_stats(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get compression statistics for an observation.
        
        Args:
            observation: Observation dictionary
            
        Returns:
            Dictionary with compression statistics
        """
        # Calculate raw size
        raw_size = 0
        for key, value in observation.items():
            if isinstance(value, np.ndarray):
                raw_size += value.nbytes
            elif isinstance(value, dict):
                for v in value.values():
                    if isinstance(v, np.ndarray):
                        raw_size += v.nbytes
        
        # Calculate compressed size
        serialized_obs = self._serialize_observation(observation)
        message = {"type": "select_action", "observation": serialized_obs}
        compressed_size = len(json.dumps(message).encode('utf-8'))
        
        return {
            "raw_size_bytes": raw_size,
            "compressed_size_bytes": compressed_size,
            "raw_size_mb": raw_size / (1024 * 1024),
            "compressed_size_mb": compressed_size / (1024 * 1024),
            "compression_ratio": raw_size / compressed_size,
            "compression_level": self.compression_level
        }

# Convenience function for quick usage
async def create_client_and_connect(uri: str, **kwargs) -> LeRobotClient:
    """
    Create and connect a LeRobot client in one step.
    
    Args:
        host: Server hostname
        port: Server port
        **kwargs: Additional arguments for LeRobotClient constructor
        
    Returns:
        Connected LeRobotClient instance
    """
    client = LeRobotClient(uri, **kwargs)
    await client.connect()
    return client




class SyncLeRobotClient:
    """
    Synchronous wrapper for LeRobotClient.
    
    This class provides a synchronous interface to the async LeRobotClient,
    handling all the asyncio operations internally.
    
    Usage:
        client = SyncLeRobotClient()
        client.connect()
        
        client.reset()
        action = client.select_action(observation)
        
        client.disconnect()
        
    Or use as context manager:
        with SyncLeRobotClient() as client:
            client.reset()
            action = client.select_action(observation)
    """
    
    def __init__(self, uri: str=None,
                 compression_level: int = 6, max_message_size: int = 100 * 1024 * 1024,
                 timeout: float = 30.0):
        """
        Initialize synchronous LeRobot client.
        
        Args:
            host: Server hostname (default: localhost)
            port: Server port (default: 8765) 
            compression_level: Gzip compression level 1-9 (default: 6)
            max_message_size: Maximum WebSocket message size in bytes (default: 100MB)
            timeout: Timeout for operations in seconds (default: 30)
        """
        self._async_client = LeRobotClient(
            uri=uri, compression_level=compression_level,
            max_message_size=max_message_size, timeout=timeout
        )
        self._loop = None
        self._thread = None
        self._connected = False
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def _run_async(self, coro):
        """Run an async coroutine synchronously."""
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, we need to run in a new thread
                return self._run_in_thread(coro)
            else:
                # Loop exists but not running, we can use it
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop, create a new one
            return asyncio.run(coro)
    
    def _run_in_thread(self, coro):
        """Run coroutine in a separate thread with its own event loop."""
        result = None
        exception = None
        
        def run_in_thread():
            nonlocal result, exception
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(coro)
                loop.close()
            except Exception as e:
                exception = e
        
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()
        
        if exception:
            raise exception
        return result
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected to server."""
        return self._connected
    
    def connect(self) -> None:
        """
        Connect to the LeRobot WebSocket server.
        
        Raises:
            LeRobotClientError: If connection fails
        """
        if self._connected:
            self.logger.warning("Already connected to server")
            return
        
        self._run_async(self._async_client.connect())
        self._connected = True
        self.logger.info("✅ Connected to LeRobot server")
    
    def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        if self._connected:
            self._run_async(self._async_client.disconnect())
            self._connected = False
            self.logger.info("Disconnected from server")
    
    def ping(self) -> bool:
        """
        Send a ping to test server connectivity.
        
        Returns:
            True if ping successful, False otherwise
        """
        if not self._connected:
            return False
        return self._run_async(self._async_client.ping())
    
    def reset(self) -> bool:
        """
        Reset the environment on the server.
        
        Returns:
            True if reset successful
            
        Raises:
            LeRobotClientError: If reset fails
        """
        if not self._connected:
            raise LeRobotClientError("Not connected to server. Call connect() first.")
        
        return self._run_async(self._async_client.reset())
    
    def select_action(self, observation: Dict[str, Any]) -> np.ndarray:
        """
        Request action selection from the server given an observation.
        
        Args:
            observation: Observation dictionary containing numpy arrays
                Expected structure:
                - 'agent_pos': numpy array of shape (1, 14)
                - 'pixels': dict with 'top' key containing array of shape (1, 480, 640, 3)
        
        Returns:
            Action numpy array from the server
            
        Raises:
            LeRobotClientError: If action selection fails
        """
        if not self._connected:
            raise LeRobotClientError("Not connected to server. Call connect() first.")
        
        return self._run_async(self._async_client.select_action(observation))
    
    def get_compression_stats(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get compression statistics for an observation.
        
        Args:
            observation: Observation dictionary
            
        Returns:
            Dictionary with compression statistics
        """
        return self._async_client.get_compression_stats(observation)

def create_sync_client_and_connect(host: str = "localhost", port: int = 8765, **kwargs) -> SyncLeRobotClient:
    """
    Create and connect a synchronous LeRobot client in one step.
    
    Args:
        host: Server hostname
        port: Server port
        **kwargs: Additional arguments for SyncLeRobotClient constructor
        
    Returns:
        Connected SyncLeRobotClient instance
    """
    client = SyncLeRobotClient(host=host, port=port, **kwargs)
    client.connect()
    return client

# Example usage
if __name__ == "__main__":
    # Create sample observation
    def create_sample_observation():
        observation = OrderedDict()
        observation['agent_pos'] = np.random.randn(1, 14).astype(np.float32)
        observation['pixels'] = {
            'top': np.random.randint(0, 256, (1, 480, 640, 3), dtype=np.uint8)
        }
        return observation
    
    print("🧪 Testing Synchronous LeRobot Client")
    print("=" * 40)
    
    try:
        # Method 1: Manual connection management
        print("Method 1: Manual connection")
        client = SyncLeRobotClient()
        client.connect()
        
        # Test ping
        if client.ping():
            print("✅ Server is responding")
        
        # Reset and get action
        client.reset()
        print("✅ Environment reset")
        
        observation = create_sample_observation()
        action = client.select_action(observation)
        print(f"✅ Received action: shape={action.shape}")
        
        client.disconnect()
        print("✅ Disconnected")
        
        print("\nMethod 2: Context manager")
        # Method 2: Context manager (recommended)
        with SyncLeRobotClient() as client:
            client.reset()
            
            for i in range(3):
                observation = create_sample_observation()
                action = client.select_action(observation)
                print(f"✅ Step {i+1}: action shape {action.shape}")
        
        print("\n🎉 All tests completed successfully!")
        
    except LeRobotClientError as e:
        print(f"❌ Client error: {e}")
        print("Make sure your LeRobot server is running on localhost:8765")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")