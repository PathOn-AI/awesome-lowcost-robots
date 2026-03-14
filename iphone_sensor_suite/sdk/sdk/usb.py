"""
USB tunneling via iproxy (libimobiledevice).

Manages the iproxy subprocess that tunnels TCP over USB to the iPhone.
Requires:
  macOS:  brew install libimobiledevice
  Linux:  sudo apt install libimobiledevice-utils libusbmuxd-tools
"""

import subprocess
import shutil
import time
import atexit
from typing import Optional


class IProxyManager:
    """Manages an iproxy subprocess for USB TCP tunneling.

    iproxy forwards a local TCP port to a port on a USB-connected iPhone.
    This allows TCP clients to connect to localhost:<local_port> and have
    traffic routed over USB to the iPhone's <device_port>.

    Args:
        local_port: Port on localhost to listen on (default 8888)
        device_port: Port on the iPhone to forward to (default 8888)
        udid: Optional device UDID (for multiple connected devices)
    """

    def __init__(self, local_port: int = 8888, device_port: int = 8888,
                 udid: Optional[str] = None):
        self.local_port = local_port
        self.device_port = device_port
        self.udid = udid
        self._process: Optional[subprocess.Popen] = None

    @staticmethod
    def is_available() -> bool:
        """Check if iproxy is installed."""
        return shutil.which("iproxy") is not None

    @property
    def is_running(self) -> bool:
        """Check if iproxy process is alive."""
        return self._process is not None and self._process.poll() is None

    def start(self, timeout: float = 2.0) -> bool:
        """Start iproxy subprocess.

        Args:
            timeout: Seconds to wait for iproxy to start listening.

        Returns:
            True if iproxy started successfully.

        Raises:
            FileNotFoundError: If iproxy is not installed.
            RuntimeError: If iproxy fails to start.
        """
        if self.is_running:
            return True

        if not self.is_available():
            raise FileNotFoundError(
                "iproxy not found. Install libimobiledevice:\n"
                "  macOS:  brew install libimobiledevice\n"
                "  Linux:  sudo apt install libimobiledevice-utils libusbmuxd-tools"
            )

        cmd = ["iproxy", str(self.local_port), str(self.device_port)]
        if self.udid:
            cmd.extend(["-u", self.udid])

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            atexit.register(self.stop)

            # Wait briefly and verify process didn't immediately exit
            time.sleep(0.5)
            if self._process.poll() is not None:
                stderr = self._process.stderr.read().decode() if self._process.stderr else ""
                raise RuntimeError(f"iproxy exited immediately: {stderr}")

            print(f"iproxy started: localhost:{self.local_port} -> device:{self.device_port}")
            return True

        except OSError as e:
            raise RuntimeError(f"Failed to start iproxy: {e}")

    def stop(self):
        """Stop iproxy subprocess."""
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=1.0)
            except Exception:
                pass
            finally:
                self._process = None
            print("iproxy stopped")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
