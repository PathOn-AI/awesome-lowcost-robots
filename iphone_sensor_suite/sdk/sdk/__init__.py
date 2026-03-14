"""
iPhone Sensor SDK - Python client for iPhone RGBD streaming

Usage:
    from sdk import IPhoneSensorClient, Frame, Intrinsics

    # WiFi mode
    client = IPhoneSensorClient('192.168.1.100')
    client.start()

    # USB mode
    client = IPhoneSensorClient(usb=True)
    client.start()

    while True:
        frame = client.wait_for_frame()
        if frame:
            print(f"Frame {frame.frame_id}: depth={frame.depth.shape}, color={frame.color.shape}")

    client.stop()
"""

from .frame import Frame, Intrinsics, IMUData
from .client import IPhoneSensorClient, connect
from .usb import IProxyManager

__version__ = "0.1.0"
__all__ = ["IPhoneSensorClient", "Frame", "Intrinsics", "IMUData", "IProxyManager", "connect"]
