"""
Frame and Intrinsics dataclasses for RGBD data.

Compatible with RealSense-style API.
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import cv2


@dataclass
class Intrinsics:
    """Camera intrinsics (RealSense-compatible)."""
    width: int
    height: int
    fx: float
    fy: float
    ppx: float  # principal point x (cx)
    ppy: float  # principal point y (cy)

    @classmethod
    def from_matrix(cls, matrix: np.ndarray, width: int, height: int) -> "Intrinsics":
        """Create from 3x3 intrinsics matrix."""
        return cls(
            width=width,
            height=height,
            fx=matrix[0, 0],
            fy=matrix[1, 1],
            ppx=matrix[0, 2],
            ppy=matrix[1, 2]
        )


@dataclass
class IMUData:
    """IMU reading (accelerometer + gyroscope)."""
    accel: np.ndarray       # (3,) float64 [x, y, z] m/s²
    gyro: np.ndarray        # (3,) float64 [x, y, z] rad/s
    timestamp: float        # IMU timestamp (seconds)


@dataclass
class Frame:
    """Single RGBD frame from iPhone.

    Attributes:
        frame_id: Sequential frame number
        timestamp: Time since streaming started (seconds)
        depth: Depth image as (H, W) float32 array in meters
        color: Color image as (H, W, 3) uint8 BGR array
        intrinsics: Camera intrinsics (at RGB resolution)
        transform: 4x4 camera pose matrix (camera-to-world)
        confidence: Depth confidence map (H, W) uint8 [0=low, 1=medium, 2=high]
        imu: IMU reading (accelerometer + gyroscope)
    """
    frame_id: int
    timestamp: float
    depth: np.ndarray                       # (H, W) float32 in meters
    color: np.ndarray                       # (H, W, 3) uint8 BGR
    intrinsics: Intrinsics
    transform: np.ndarray                   # 4x4 camera pose matrix
    confidence: Optional[np.ndarray] = None # (H, W) uint8
    imu: Optional[IMUData] = None

    @property
    def depth_width(self) -> int:
        return self.depth.shape[1]

    @property
    def depth_height(self) -> int:
        return self.depth.shape[0]

    @property
    def color_width(self) -> int:
        return self.color.shape[1]

    @property
    def color_height(self) -> int:
        return self.color.shape[0]

    def get_depth_intrinsics(self) -> "Intrinsics":
        """Get intrinsics scaled to depth resolution.

        ARKit intrinsics are for RGB resolution (e.g. 1920x1440).
        This scales them to depth resolution (e.g. 256x192).
        """
        scale_x = self.depth_width / self.intrinsics.width
        scale_y = self.depth_height / self.intrinsics.height
        return Intrinsics(
            width=self.depth_width,
            height=self.depth_height,
            fx=self.intrinsics.fx * scale_x,
            fy=self.intrinsics.fy * scale_y,
            ppx=self.intrinsics.ppx * scale_x,
            ppy=self.intrinsics.ppy * scale_y,
        )

    def get_aligned_depth(self) -> np.ndarray:
        """Get depth upscaled to RGB resolution.

        ARKit depth is already aligned to RGB camera frame.
        This just resizes 256x192 -> 1920x1440 for pixel-level correspondence.
        """
        return cv2.resize(
            self.depth,
            (self.color_width, self.color_height),
            interpolation=cv2.INTER_NEAREST
        )

    def get_depth_mm(self) -> np.ndarray:
        """Get depth as uint16 millimeters (RealSense format)."""
        return (self.depth * 1000).clip(0, 65535).astype(np.uint16)
