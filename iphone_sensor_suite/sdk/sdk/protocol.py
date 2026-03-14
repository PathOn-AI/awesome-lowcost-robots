"""
Binary protocol parser for iPhone sensor streaming.

Supports Protocol v1 (32-byte header) and v2 (48-byte header).

Protocol v2 format (little-endian):
┌──────────────────────────────────────────────────────────────┐
│ Header (48 bytes)                                            │
│   [0:5]   magic: "REC3D" (5 bytes)                          │
│   [5]     version: uint8                                     │
│   [6:10]  frame_id: uint32                                   │
│   [10:18] timestamp: float64                                 │
│   [18:20] depth_width: uint16                                │
│   [20:22] depth_height: uint16                               │
│   [22:26] depth_size: uint32                                 │
│   [26:30] rgb_size: uint32                                   │
│   [30:32] rgb_width: uint16               (v2 only)          │
│   [32:34] rgb_height: uint16              (v2 only)          │
│   [34:38] confidence_size: uint32         (v2 only)          │
│   [38:42] imu_size: uint32               (v2 only)          │
│   [42:48] reserved: 6 bytes               (v2 only)          │
├──────────────────────────────────────────────────────────────┤
│ Intrinsics (36 bytes) - 3x3 float32 row-major               │
├──────────────────────────────────────────────────────────────┤
│ Transform (64 bytes) - 4x4 float32 row-major                │
├──────────────────────────────────────────────────────────────┤
│ Depth Data (depth_size bytes) - float32 array               │
├──────────────────────────────────────────────────────────────┤
│ RGB Data (rgb_size bytes) - JPEG compressed                  │
├──────────────────────────────────────────────────────────────┤
│ Confidence Data (confidence_size bytes) - uint8 (v2 only)    │
├──────────────────────────────────────────────────────────────┤
│ IMU Data (imu_size bytes) - 7x float64 (v2 only)            │
└──────────────────────────────────────────────────────────────┘
"""

import struct
import numpy as np
import cv2
from typing import Optional, Tuple

from .frame import Frame, Intrinsics, IMUData


MAGIC = b"REC3D"
HEADER_SIZE_V1 = 32
HEADER_SIZE_V2 = 48
HEADER_SIZE = HEADER_SIZE_V1  # minimum header size for initial read
INTRINSICS_SIZE = 36  # 9 floats
TRANSFORM_SIZE = 64   # 16 floats
IMU_DATA_SIZE = 56    # 7 x float64


def _get_version(data: bytes) -> Optional[int]:
    """Get protocol version from header data."""
    if len(data) < 6:
        return None
    if data[0:5] != MAGIC:
        return None
    return data[5]


def parse_header(data: bytes) -> Optional[dict]:
    """Parse packet header (v1 or v2).

    Returns:
        Dict with header fields, or None if invalid.
    """
    if len(data) < HEADER_SIZE_V1:
        return None

    magic = data[0:5]
    if magic != MAGIC:
        return None

    version = data[5]
    frame_id = struct.unpack("<I", data[6:10])[0]
    timestamp = struct.unpack("<d", data[10:18])[0]
    depth_width = struct.unpack("<H", data[18:20])[0]
    depth_height = struct.unpack("<H", data[20:22])[0]
    depth_size = struct.unpack("<I", data[22:26])[0]
    rgb_size = struct.unpack("<I", data[26:30])[0]

    result = {
        "version": version,
        "frame_id": frame_id,
        "timestamp": timestamp,
        "depth_width": depth_width,
        "depth_height": depth_height,
        "depth_size": depth_size,
        "rgb_size": rgb_size,
        "rgb_width": 0,
        "rgb_height": 0,
        "confidence_size": 0,
        "imu_size": 0,
    }

    if version >= 2 and len(data) >= HEADER_SIZE_V2:
        result["rgb_width"] = struct.unpack("<H", data[30:32])[0]
        result["rgb_height"] = struct.unpack("<H", data[32:34])[0]
        result["confidence_size"] = struct.unpack("<I", data[34:38])[0]
        result["imu_size"] = struct.unpack("<I", data[38:42])[0]

    return result


def _header_size(version: int) -> int:
    """Get header size for protocol version."""
    return HEADER_SIZE_V2 if version >= 2 else HEADER_SIZE_V1


def parse_frame(data: bytes) -> Optional[Frame]:
    """Parse a complete frame packet (v1 or v2).

    Args:
        data: Raw packet bytes

    Returns:
        Frame object or None if parsing fails.
    """
    header = parse_header(data)
    if header is None:
        return None

    version = header["version"]
    hdr_size = _header_size(version)
    depth_width = header["depth_width"]
    depth_height = header["depth_height"]
    depth_size = header["depth_size"]
    rgb_size = header["rgb_size"]
    confidence_size = header["confidence_size"]
    imu_size = header["imu_size"]

    # Calculate offsets
    intrinsics_start = hdr_size
    transform_start = intrinsics_start + INTRINSICS_SIZE
    depth_start = transform_start + TRANSFORM_SIZE
    rgb_start = depth_start + depth_size
    confidence_start = rgb_start + rgb_size
    imu_start = confidence_start + confidence_size

    expected_size = imu_start + imu_size
    if len(data) < expected_size:
        return None

    # Parse intrinsics (3x3 float32 row-major)
    intrinsics_data = data[intrinsics_start:transform_start]
    intrinsics_array = np.frombuffer(intrinsics_data, dtype=np.float32).reshape(3, 3)

    # Parse transform (4x4 float32 row-major)
    transform_data = data[transform_start:depth_start]
    transform = np.frombuffer(transform_data, dtype=np.float32).reshape(4, 4).copy()

    # Parse depth (float32 array)
    depth_data = data[depth_start:rgb_start]
    depth = np.frombuffer(depth_data, dtype=np.float32).reshape(depth_height, depth_width).copy()

    # Parse RGB (JPEG)
    rgb_data = data[rgb_start:rgb_start + rgb_size]
    color = cv2.imdecode(np.frombuffer(rgb_data, dtype=np.uint8), cv2.IMREAD_COLOR)

    if color is None:
        return None

    # Determine RGB dimensions
    if version >= 2 and header["rgb_width"] > 0:
        rgb_width = header["rgb_width"]
        rgb_height = header["rgb_height"]
    else:
        rgb_height, rgb_width = color.shape[:2]

    # Create intrinsics at RGB resolution
    intrinsics = Intrinsics.from_matrix(intrinsics_array, rgb_width, rgb_height)

    # Parse confidence (v2 only)
    confidence = None
    if confidence_size > 0:
        conf_data = data[confidence_start:confidence_start + confidence_size]
        confidence = np.frombuffer(conf_data, dtype=np.uint8).reshape(depth_height, depth_width).copy()

    # Parse IMU (v2 only)
    imu = None
    if imu_size >= IMU_DATA_SIZE:
        imu_raw = data[imu_start:imu_start + IMU_DATA_SIZE]
        values = struct.unpack("<7d", imu_raw)
        imu = IMUData(
            accel=np.array(values[0:3], dtype=np.float64),
            gyro=np.array(values[3:6], dtype=np.float64),
            timestamp=values[6]
        )

    return Frame(
        frame_id=header["frame_id"],
        timestamp=header["timestamp"],
        depth=depth,
        color=color,
        intrinsics=intrinsics,
        transform=transform,
        confidence=confidence,
        imu=imu
    )


def get_packet_size(data: bytes) -> Optional[int]:
    """Get the total size of a packet from its header.

    Args:
        data: At least HEADER_SIZE_V1 bytes

    Returns:
        Total packet size or None if invalid.
    """
    header = parse_header(data)
    if header is None:
        return None

    version = header["version"]
    hdr_size = _header_size(version)

    return (hdr_size + INTRINSICS_SIZE + TRANSFORM_SIZE
            + header["depth_size"] + header["rgb_size"]
            + header["confidence_size"] + header["imu_size"])
