"""
TCP client for iPhone sensor streaming.

Usage:
    from sdk import IPhoneSensorClient
    client = IPhoneSensorClient('192.168.1.100')
    client.start()

    while True:
        frame = client.wait_for_frame()
        if frame:
            # Process frame
            pass

    client.stop()
"""

import socket
import threading
from typing import Optional

from .frame import Frame
from .protocol import parse_frame, get_packet_size, HEADER_SIZE, HEADER_SIZE_V2
from .usb import IProxyManager


class IPhoneSensorClient:
    """TCP client for receiving RGBD frames from iPhone.

    Args:
        host: iPhone IP address (ignored in USB mode, defaults to localhost)
        port: Server port (default 8888)
        timeout: Socket timeout in seconds (default 5.0)
        usb: If True, use USB mode via iproxy (connects to localhost)
        device_udid: Optional iPhone UDID for USB mode with multiple devices
    """

    def __init__(self, host: str = "localhost", port: int = 8888,
                 timeout: float = 5.0, usb: bool = False,
                 device_udid: Optional[str] = None):
        self.usb = usb
        self.host = "localhost" if usb else host
        self.port = port
        self.timeout = timeout

        self._socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._latest_frame: Optional[Frame] = None
        self._frame_lock = threading.Lock()
        self._frame_event = threading.Event()
        self._buffer = bytearray()

        # USB tunnel manager
        self._iproxy: Optional[IProxyManager] = None
        if usb:
            self._iproxy = IProxyManager(
                local_port=port,
                device_port=port,
                udid=device_udid
            )

    @property
    def is_connected(self) -> bool:
        """Check if connected to server."""
        return self._socket is not None and self._running

    def start(self) -> bool:
        """Connect to server and start receiving frames.

        Returns:
            True if connected successfully.
        """
        if self._running:
            return True

        # Start USB tunnel if needed
        if self._iproxy is not None:
            try:
                self._iproxy.start()
            except (FileNotFoundError, RuntimeError) as e:
                print(f"USB tunnel error: {e}")
                return False

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))
            self._running = True

            self._thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._thread.start()

            mode_str = "USB" if self.usb else "WiFi"
            print(f"Connected to {self.host}:{self.port} ({mode_str})")
            return True

        except socket.error as e:
            print(f"Failed to connect: {e}")
            self._cleanup()
            return False

    def stop(self):
        """Disconnect from server."""
        self._running = False

        if self._socket:
            try:
                self._socket.close()
            except:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        self._cleanup()

        # Stop USB tunnel
        if self._iproxy is not None:
            self._iproxy.stop()

        print("Disconnected")

    def wait_for_frame(self, timeout: float = 1.0) -> Optional[Frame]:
        """Wait for and return the latest frame.

        Always returns the most recent frame, never a stale one.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Frame object or None if timeout/disconnected.
        """
        if not self._running:
            return None

        self._frame_event.wait(timeout=timeout)
        self._frame_event.clear()

        with self._frame_lock:
            frame = self._latest_frame
            self._latest_frame = None
            return frame

    def get_frame(self) -> Optional[Frame]:
        """Get the latest frame without waiting (non-blocking).

        Returns:
            Frame object or None if no frame available.
        """
        with self._frame_lock:
            frame = self._latest_frame
            self._latest_frame = None
            return frame

    def _receive_loop(self):
        """Background thread for receiving data."""
        while self._running:
            try:
                # Receive data
                data = self._socket.recv(524288)
                if not data:
                    print("Connection closed by server")
                    break

                self._buffer.extend(data)

                # Try to parse complete frames
                while True:
                    if len(self._buffer) < HEADER_SIZE:
                        break

                    # Need enough bytes to parse header (v2 needs 48 bytes)
                    hdr_read_size = min(HEADER_SIZE_V2, len(self._buffer))
                    packet_size = get_packet_size(bytes(self._buffer[:hdr_read_size]))
                    if packet_size is None:
                        # Invalid header, try to find magic
                        magic_pos = self._buffer.find(b"REC3D")
                        if magic_pos > 0:
                            self._buffer = self._buffer[magic_pos:]
                        elif magic_pos < 0:
                            self._buffer.clear()
                        break

                    # Check if we have complete packet
                    if len(self._buffer) < packet_size:
                        break

                    # Parse frame
                    packet_data = bytes(self._buffer[:packet_size])
                    self._buffer = self._buffer[packet_size:]

                    frame = parse_frame(packet_data)
                    if frame:
                        # Always keep only the latest frame
                        with self._frame_lock:
                            self._latest_frame = frame
                        self._frame_event.set()

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    print(f"Receive error: {e}")
                break

        self._running = False

    def _cleanup(self):
        """Clean up resources."""
        self._socket = None
        self._buffer.clear()
        with self._frame_lock:
            self._latest_frame = None
        self._frame_event.clear()


# Convenience function
def connect(host: str = "localhost", port: int = 8888,
            usb: bool = False) -> IPhoneSensorClient:
    """Create and connect a client.

    Args:
        host: iPhone IP address (ignored in USB mode)
        port: Server port (default 8888)
        usb: If True, use USB mode via iproxy

    Returns:
        Connected client (raises on failure)
    """
    client = IPhoneSensorClient(host, port, usb=usb)
    if not client.start():
        mode_str = "USB" if usb else f"{host}:{port}"
        raise ConnectionError(f"Failed to connect via {mode_str}")
    return client
