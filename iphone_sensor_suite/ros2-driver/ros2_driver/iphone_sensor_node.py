#!/usr/bin/env python3
"""ROS2 node for iPhone RGBD streaming.

Publishes RGB, depth, aligned depth, confidence, point cloud, IMU,
and camera info topics. Broadcasts TF frames.
"""

import sys
import struct
import math

import numpy as np
import cv2

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from rclpy.time import Time

from sensor_msgs.msg import Image, CameraInfo, PointCloud2, PointField, Imu, LaserScan
from geometry_msgs.msg import TransformStamped
from std_msgs.msg import Header
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster
from cv_bridge import CvBridge

from sdk import IPhoneSensorClient
from sdk.frame import Intrinsics


class IPhoneSensorNode(Node):
    def __init__(self):
        super().__init__("iphone_sensor_node")

        # Parameters
        self.declare_parameter("host", "192.168.1.100")
        self.declare_parameter("port", 8888)
        self.declare_parameter("camera_name", "camera")
        self.declare_parameter("publish_pointcloud", True)
        self.declare_parameter("publish_aligned_depth", True)
        self.declare_parameter("publish_confidence", True)
        self.declare_parameter("publish_imu", True)
        self.declare_parameter("publish_scan", True)
        self.declare_parameter("usb", False)
        self.declare_parameter("depth_range_min", 0.1)
        self.declare_parameter("depth_range_max", 5.0)
        self.declare_parameter("min_confidence", 1)


        self.host = self.get_parameter("host").value
        self.port = self.get_parameter("port").value
        self.usb_mode = self.get_parameter("usb").value
        self.camera_name = self.get_parameter("camera_name").value
        self.pub_pc_enabled = self.get_parameter("publish_pointcloud").value
        self.pub_aligned_enabled = self.get_parameter("publish_aligned_depth").value
        self.pub_conf_enabled = self.get_parameter("publish_confidence").value
        self.pub_imu_enabled = self.get_parameter("publish_imu").value
        self.pub_scan_enabled = self.get_parameter("publish_scan").value
        self.depth_min = self.get_parameter("depth_range_min").value
        self.depth_max = self.get_parameter("depth_range_max").value
        self.min_confidence = self.get_parameter("min_confidence").value

        # Frame IDs
        self.color_optical_frame = f"{self.camera_name}_color_optical_frame"
        self.depth_optical_frame = f"{self.camera_name}_depth_optical_frame"
        self.laser_frame = f"{self.camera_name}_laser_frame"
        self.camera_link_frame = f"{self.camera_name}_link"
        self.world_frame = "world"

        # QoS: best effort, volatile, keep last 1 — matches RViz2 sensor expectations
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        # Publishers
        self.pub_color = self.create_publisher(Image, "color/image_raw", sensor_qos)
        self.pub_color_info = self.create_publisher(CameraInfo, "color/camera_info", sensor_qos)
        self.pub_depth = self.create_publisher(Image, "depth/image_rect_raw", sensor_qos)
        self.pub_depth_info = self.create_publisher(CameraInfo, "depth/camera_info", sensor_qos)

        if self.pub_aligned_enabled:
            self.pub_aligned = self.create_publisher(Image, "aligned_depth_to_color/image_raw", sensor_qos)
            self.pub_aligned_info = self.create_publisher(CameraInfo, "aligned_depth_to_color/camera_info", sensor_qos)

        if self.pub_pc_enabled:
            self.pub_pointcloud = self.create_publisher(PointCloud2, "depth/color/points", sensor_qos)

        if self.pub_conf_enabled:
            self.pub_confidence = self.create_publisher(Image, "confidence/image_raw", sensor_qos)

        if self.pub_imu_enabled:
            self.pub_imu = self.create_publisher(Imu, "imu", sensor_qos)

        if self.pub_scan_enabled:
            self.pub_scan = self.create_publisher(LaserScan, "scan", sensor_qos)

        # TF broadcasters
        self.tf_broadcaster = TransformBroadcaster(self)
        self.static_tf_broadcaster = StaticTransformBroadcaster(self)

        # CV bridge
        self.bridge = CvBridge()

        # Publish static TFs (camera_link -> optical frames)
        self._publish_static_tfs()

        # Connect to iPhone (supports both WiFi and USB modes)
        self.client = IPhoneSensorClient(self.host, self.port, usb=self.usb_mode)
        if self.usb_mode:
            self.get_logger().info("Connecting via USB (iproxy)...")
        else:
            self.get_logger().info(f"Connecting via WiFi to {self.host}:{self.port}...")

        if not self.client.start():
            self.get_logger().error("Failed to connect to iPhone!")
            sys.exit(1)

        self.get_logger().info("Connected! Starting frame loop.")

        self._frame_count = 0
        self._log_interval = 30  # Log every N frames
        self._heavy_interval = 5  # Point cloud + aligned depth every N frames

        # Temporal depth filter state (tune these to trade stability vs responsiveness)
        # TODO: consider exposing as ROS parameters for runtime tuning
        self._prev_depth = None
        self._temporal_alpha = 0.4   # EMA weight of current frame (lower = smoother, try 0.2-0.6)
        self._temporal_delta = 0.04  # Reset threshold in meters (lower = more smoothing, higher = preserves fast motion)

        # Timer at ~30Hz
        self.timer = self.create_timer(1.0 / 30.0, self._timer_callback)

    def _publish_static_tfs(self):
        """Publish static TFs: camera_link -> optical frames + laser frame.

        Optical frame convention: X-right, Y-down, Z-forward.
        From camera_link (X-forward, Y-left, Z-up): roll=-90, yaw=-90.
        Laser frame: identity transform from camera_link (X-forward, Z-up).
        """
        now = self.get_clock().now().to_msg()
        transforms = []

        # Rotation: camera_link -> optical frame
        # roll=-90 deg, pitch=0, yaw=-90 deg
        # q = quaternion for this rotation
        # Using ZYX euler: yaw=-pi/2, pitch=0, roll=-pi/2
        # q = (w, x, y, z) = (0.5, -0.5, 0.5, -0.5)
        q_optical = (0.5, -0.5, 0.5, -0.5)  # (x, y, z, w) in ROS

        for child_frame in [self.color_optical_frame, self.depth_optical_frame]:
            parent = self.camera_link_frame
            t = TransformStamped()
            t.header.stamp = now
            t.header.frame_id = parent
            t.child_frame_id = child_frame
            t.transform.rotation.x = q_optical[0]
            t.transform.rotation.y = q_optical[1]
            t.transform.rotation.z = q_optical[2]
            t.transform.rotation.w = q_optical[3]
            transforms.append(t)

        # Laser frame: identity transform from camera_link
        # Same position and orientation (both X-forward, Z-up body convention)
        # ARKit aligns LiDAR depth to RGB camera, so no offset needed
        t = TransformStamped()
        t.header.stamp = now
        t.header.frame_id = self.camera_link_frame
        t.child_frame_id = self.laser_frame
        t.transform.rotation.w = 1.0
        transforms.append(t)

        self.static_tf_broadcaster.sendTransform(transforms)

    def _timer_callback(self):
        frame = self.client.get_frame()
        if frame is None:
            if not self.client.is_connected:
                self.get_logger().error("Disconnected from iPhone!")
                self.timer.cancel()
            return

        self._frame_count += 1
        if self._frame_count == 1:
            self.get_logger().info(
                f"First frame: depth={frame.depth.shape}, color={frame.color.shape}, "
                f"conf={'yes' if frame.confidence is not None else 'no'}, "
                f"imu={'yes' if frame.imu is not None else 'no'}"
            )
        elif self._frame_count % self._log_interval == 0:
            self.get_logger().info(f"Published {self._frame_count} frames")

        now = self.get_clock().now().to_msg()

        # Build headers
        color_header = Header(stamp=now, frame_id=self.color_optical_frame)
        depth_header = Header(stamp=now, frame_id=self.depth_optical_frame)

        # Intrinsics
        rgb_intr = frame.intrinsics
        depth_intr = frame.get_depth_intrinsics()

        # Rotate 90° CW to correct landscape (top-left) → portrait orientation
        frame.color = cv2.rotate(frame.color, cv2.ROTATE_90_CLOCKWISE)
        frame.depth = cv2.rotate(frame.depth, cv2.ROTATE_90_CLOCKWISE)
        if frame.confidence is not None:
            frame.confidence = cv2.rotate(frame.confidence, cv2.ROTATE_90_CLOCKWISE)

        # Rotate intrinsics: 90° CW means (u,v) → (H-1-v, u) in new image
        # new_fx=old_fy, new_fy=old_fx, new_ppx=old_H-1-old_ppy, new_ppy=old_ppx
        old_rgb = rgb_intr
        rgb_intr = Intrinsics(
            width=old_rgb.height, height=old_rgb.width,
            fx=old_rgb.fy, fy=old_rgb.fx,
            ppx=old_rgb.height - 1 - old_rgb.ppy, ppy=old_rgb.ppx,
        )
        old_dep = depth_intr
        depth_intr = Intrinsics(
            width=old_dep.height, height=old_dep.width,
            fx=old_dep.fy, fy=old_dep.fx,
            ppx=old_dep.height - 1 - old_dep.ppy, ppy=old_dep.ppx,
        )

        # --- Publish color image ---
        color_msg = self.bridge.cv2_to_imgmsg(frame.color, encoding="bgr8")
        color_msg.header = color_header
        self.pub_color.publish(color_msg)

        # --- Publish color camera info ---
        color_info = self._make_camera_info(color_header, rgb_intr)
        self.pub_color_info.publish(color_info)

        # --- Publish depth image (32FC1 meters) ---
        depth_msg = self.bridge.cv2_to_imgmsg(frame.depth, encoding="32FC1")
        depth_msg.header = depth_header
        self.pub_depth.publish(depth_msg)

        # --- Publish depth camera info ---
        depth_info = self._make_camera_info(depth_header, depth_intr)
        self.pub_depth_info.publish(depth_info)

        # --- Publish confidence ---
        if self.pub_conf_enabled and frame.confidence is not None:
            conf_msg = self.bridge.cv2_to_imgmsg(frame.confidence, encoding="mono8")
            conf_msg.header = depth_header
            self.pub_confidence.publish(conf_msg)

        # --- Publish IMU ---
        if self.pub_imu_enabled and frame.imu is not None:
            imu_msg = Imu()
            imu_msg.header = Header(stamp=now, frame_id=f"{self.camera_name}_imu_frame")
            # ARKit -> ROS coordinate transform
            imu_msg.linear_acceleration.x = float(frame.imu.accel[0])
            imu_msg.linear_acceleration.y = float(-frame.imu.accel[2])
            imu_msg.linear_acceleration.z = float(frame.imu.accel[1])
            imu_msg.angular_velocity.x = float(frame.imu.gyro[0])
            imu_msg.angular_velocity.y = float(-frame.imu.gyro[2])
            imu_msg.angular_velocity.z = float(frame.imu.gyro[1])
            # Mark orientation as unknown
            imu_msg.orientation_covariance[0] = -1.0
            self.pub_imu.publish(imu_msg)

        # --- Publish LaserScan (middle row of depth) ---
        if self.pub_scan_enabled:
            laser_header = Header(stamp=now, frame_id=self.laser_frame)
            scan_msg = self._make_laserscan(frame.depth, depth_intr, laser_header)
            if scan_msg is not None:
                self.pub_scan.publish(scan_msg)

        # --- Heavy operations: run at reduced rate to avoid blocking ---
        do_heavy = (self._frame_count % self._heavy_interval == 0)

        # --- Publish aligned depth to color ---
        if do_heavy and self.pub_aligned_enabled:
            aligned = frame.get_aligned_depth()
            aligned_msg = self.bridge.cv2_to_imgmsg(aligned, encoding="32FC1")
            aligned_msg.header = color_header
            self.pub_aligned.publish(aligned_msg)

            aligned_info = self._make_camera_info(color_header, rgb_intr)
            self.pub_aligned_info.publish(aligned_info)

        # --- Publish point cloud ---
        if do_heavy and self.pub_pc_enabled:
            pc_msg = self._make_pointcloud(frame, depth_intr, depth_header)
            if pc_msg is not None:
                self.pub_pointcloud.publish(pc_msg)

        # --- Broadcast dynamic TF: world -> camera_link ---
        # Disabled: world -> camera_link TF is provided by an external launch file
        # self._broadcast_pose(frame.transform, now)

    def _make_camera_info(self, header, intr):
        """Build CameraInfo from Intrinsics."""
        msg = CameraInfo()
        msg.header = header
        msg.width = intr.width
        msg.height = intr.height
        msg.distortion_model = "plumb_bob"
        msg.d = [0.0, 0.0, 0.0, 0.0, 0.0]
        msg.k = [
            intr.fx, 0.0, intr.ppx,
            0.0, intr.fy, intr.ppy,
            0.0, 0.0, 1.0,
        ]
        msg.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        msg.p = [
            intr.fx, 0.0, intr.ppx, 0.0,
            0.0, intr.fy, intr.ppy, 0.0,
            0.0, 0.0, 1.0, 0.0,
        ]
        return msg

    def _make_laserscan(self, depth, depth_intr, header):
        """Convert middle row of depth image to LaserScan.

        Depth is in optical frame (Z-forward, X-right).
        LaserScan is in body frame (X-forward, Y-left).
        Mapping: x_body = z_opt, y_body = -x_opt
        Body angle = -atan2(x_opt, z_opt)  (negated from optical)
        """
        height, width = depth.shape
        mid_row = depth[height // 2, :]

        u = np.arange(width, dtype=np.float32)

        # Optical angle: atan2(x_opt, z_opt) per pixel column
        # Body angle: negate (rightward in optical = -Y in body = negative angle)
        angles = -np.arctan2(u - depth_intr.ppx, depth_intr.fx)

        # angles go positive→negative (left-to-right in image)
        # LaserScan needs min_angle < max_angle, so reverse both angles and ranges
        angles = angles[::-1]
        mid_row = mid_row[::-1]

        angle_min = float(angles[0])
        angle_max = float(angles[-1])
        angle_increment = float((angle_max - angle_min) / (width - 1))

        # Convert depth (Z along optical axis) to range (radial distance)
        cos_angles = np.cos(angles)
        ranges = np.where(cos_angles > 0, mid_row / cos_angles, float('inf'))

        # Clamp invalid values
        ranges = np.where(
            (ranges >= self.depth_min) & (ranges <= self.depth_max) & np.isfinite(ranges),
            ranges, float('inf')
        ).astype(np.float32)

        msg = LaserScan()
        msg.header = header
        msg.angle_min = angle_min
        msg.angle_max = angle_max
        msg.angle_increment = angle_increment
        msg.time_increment = 0.0
        msg.scan_time = 1.0 / 30.0
        msg.range_min = float(self.depth_min)
        msg.range_max = float(self.depth_max)
        msg.ranges = ranges.tolist()
        return msg

    def _make_pointcloud(self, frame, depth_intr, header):
        """Generate PointCloud2 from depth + color.

        Three-stage stabilization pipeline to reduce LiDAR point cloud jitter:
          1) Bilateral filter — spatial smoothing (tune d, sigmaColor, sigmaSpace)
          2) Temporal EMA — frame-to-frame smoothing (tune _temporal_alpha, _temporal_delta)
          3) Erosion — removes noisy flying pixels at depth edges (tune kernel size)
        Disable or tune individual stages if the cloud feels over-smoothed or laggy.
        """
        depth = frame.depth.copy()
        height, width = depth.shape

        # 1) Bilateral filter: smooth spatial noise while preserving real edges.
        #    d=5: neighborhood size, sigmaColor=0.04: depth similarity, sigmaSpace=4.5: spatial proximity
        depth = cv2.bilateralFilter(depth, d=5, sigmaColor=0.04, sigmaSpace=4.5)

        # 2) Temporal EMA filter: blend with previous frame to reduce per-frame
        #    LiDAR jitter (~5-20mm). Resets at depth discontinuities (delta
        #    threshold) so real edges and moving objects respond instantly.
        if self._prev_depth is not None and self._prev_depth.shape == depth.shape:
            diff = np.abs(depth - self._prev_depth)
            blend = (diff < self._temporal_delta) & (depth > 0) & (self._prev_depth > 0)
            depth = np.where(blend,
                             self._temporal_alpha * depth + (1 - self._temporal_alpha) * self._prev_depth,
                             depth)
        self._prev_depth = depth.copy()

        # 3) Build valid mask and erode to remove flying pixels at boundaries.
        valid_mask = (depth > self.depth_min) & (depth < self.depth_max) & np.isfinite(depth)
        if frame.confidence is not None and self.min_confidence > 0:
            valid_mask &= (frame.confidence >= self.min_confidence)
        kernel = np.ones((3, 3), np.uint8)
        valid_mask = cv2.erode(valid_mask.astype(np.uint8), kernel, iterations=1).astype(bool)

        # Create pixel coordinate grids
        u = np.arange(width, dtype=np.float32)
        v = np.arange(height, dtype=np.float32)
        u, v = np.meshgrid(u, v)

        # Unproject to 3D
        z = depth
        x = (u - depth_intr.ppx) * z / depth_intr.fx
        y = (v - depth_intr.ppy) * z / depth_intr.fy

        # Resize color to depth resolution for per-point coloring
        color_resized = cv2.resize(frame.color, (width, height))

        # BGR -> pack as float32 for PointCloud2
        b = color_resized[:, :, 0].astype(np.uint32)
        g = color_resized[:, :, 1].astype(np.uint32)
        r = color_resized[:, :, 2].astype(np.uint32)
        rgb_packed = (r << 16) | (g << 8) | b
        rgb_float = rgb_packed.view(np.float32)

        # Apply combined mask
        valid = valid_mask
        x = x[valid]
        y = y[valid]
        z = z[valid]
        rgb_float = rgb_float[valid]

        n_points = x.shape[0]
        if n_points == 0:
            return None

        # Pack into structured array: x, y, z, rgb
        points = np.zeros(n_points, dtype=[
            ("x", np.float32),
            ("y", np.float32),
            ("z", np.float32),
            ("rgb", np.float32),
        ])
        points["x"] = x
        points["y"] = y
        points["z"] = z
        points["rgb"] = rgb_float

        msg = PointCloud2()
        msg.header = header
        msg.height = 1
        msg.width = n_points
        msg.fields = [
            PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name="rgb", offset=12, datatype=PointField.FLOAT32, count=1),
        ]
        msg.is_bigendian = False
        msg.point_step = 16
        msg.row_step = 16 * n_points
        msg.data = points.tobytes()
        msg.is_dense = True

        return msg

    def _broadcast_pose(self, transform, stamp):
        """Broadcast ARKit pose as TF: world -> camera_link.

        ARKit: X-right, Y-up, Z-toward-user
        ROS:   X-forward, Y-left, Z-up

        Position: ros = (arkit.x, -arkit.z, arkit.y)
        Orientation: pre-multiply by correction quaternion
        """
        t = TransformStamped()
        t.header.stamp = stamp
        t.header.frame_id = self.world_frame
        t.child_frame_id = self.camera_link_frame

        # Position: ARKit Y-up -> ROS Z-up
        t.transform.translation.x = float(transform[0, 3])
        t.transform.translation.y = float(-transform[2, 3])
        t.transform.translation.z = float(transform[1, 3])

        # Extract rotation matrix (3x3) from ARKit transform
        R = transform[:3, :3].copy()

        # Apply coordinate swap to rotation: ARKit Y-up -> ROS Z-up
        # New R_ros maps ARKit axes to ROS axes
        # ROS_x = ARKit_x, ROS_y = -ARKit_z, ROS_z = ARKit_y
        R_ros = np.array([
            [R[0, 0], -R[2, 0], R[1, 0]],
            [-R[0, 2], R[2, 2], -R[1, 2]],
            [R[0, 1], -R[2, 1], R[1, 1]],
        ])

        # Convert rotation matrix to quaternion
        qw, qx, qy, qz = self._rotation_matrix_to_quaternion(R_ros)
        t.transform.rotation.x = qx
        t.transform.rotation.y = qy
        t.transform.rotation.z = qz
        t.transform.rotation.w = qw

        self.tf_broadcaster.sendTransform(t)

    @staticmethod
    def _rotation_matrix_to_quaternion(R):
        """Convert 3x3 rotation matrix to quaternion (w, x, y, z)."""
        trace = R[0, 0] + R[1, 1] + R[2, 2]
        if trace > 0:
            s = 0.5 / math.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (R[2, 1] - R[1, 2]) * s
            y = (R[0, 2] - R[2, 0]) * s
            z = (R[1, 0] - R[0, 1]) * s
        elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = 2.0 * math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
            w = (R[2, 1] - R[1, 2]) / s
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = 2.0 * math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
            w = (R[0, 2] - R[2, 0]) / s
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
        else:
            s = 2.0 * math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
            w = (R[1, 0] - R[0, 1]) / s
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s
        return w, x, y, z

    def destroy_node(self):
        self.client.stop()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = IPhoneSensorNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
