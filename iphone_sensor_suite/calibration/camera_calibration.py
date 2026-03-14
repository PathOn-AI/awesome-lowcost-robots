#!/usr/bin/env python3
"""
Camera calibration via ArUco marker.

Single node that:
1. Publishes static TF: world → aruco_tag_frame (fixed, known position)
2. Detects ArUco marker from iPhone camera stream
3. Collects 100 samples, averages, and publishes static TF: aruco_tag_frame → camera_link
4. After calibration, the full chain world → aruco_tag_frame → camera_link is established
5. Marker can be removed after calibration completes

Usage:
    source /opt/ros/jazzy/setup.bash
    python3 -m calibration.camera_calibration

Requires: iPhone sensor ROS2 node running.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import TransformStamped
from tf2_ros import StaticTransformBroadcaster
from cv_bridge import CvBridge
import cv2
import numpy as np
from scipy.spatial.transform import Rotation as R

# ------------------------------------------------------------------ #
#  CONFIG                                                              #
# ------------------------------------------------------------------ #
# ArUco marker
ARUCO_DICT = cv2.aruco.DICT_6X6_250
MARKER_ID = 3
MARKER_SIZE = 0.038  # meters (3.8 cm)

# Fixed position of marker center relative to world frame
TAG_X = -0.10
TAG_Y = -0.27
TAG_Z = 0.0

# Calibration
CALIBRATION_COUNT = 100


class CameraCalibration(Node):
    def __init__(self):
        super().__init__('camera_calibration')

        self.bridge = CvBridge()
        self.camera_matrix = None
        self.dist_coeffs = None
        self.broadcaster = StaticTransformBroadcaster(self)

        self.aruco_dict = cv2.aruco.Dictionary_get(ARUCO_DICT)
        self.aruco_params = cv2.aruco.DetectorParameters_create()

        self.samples = []
        self.calibration_done = False

        # Step 1: Publish world → aruco_tag_frame
        self._publish_world_to_tag()

        # QoS to match iPhone sensor node (BEST_EFFORT)
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscribe to iPhone camera (iPhone sensor ROS2 node)
        self.create_subscription(
            CameraInfo,
            'color/camera_info',
            self._camera_info_cb, qos
        )
        self.create_subscription(
            Image,
            'color/image_raw',
            self._image_cb, qos
        )

        self.get_logger().info(
            f'Camera calibration started. Place ArUco marker (ID {MARKER_ID}) '
            f'in camera view. Collecting {CALIBRATION_COUNT} samples...'
        )

    def _publish_world_to_tag(self):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'world'
        t.child_frame_id = 'aruco_tag_frame'

        t.transform.translation.x = TAG_X
        t.transform.translation.y = TAG_Y
        t.transform.translation.z = TAG_Z

        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = 0.0
        t.transform.rotation.w = 1.0

        self.broadcaster.sendTransform(t)
        self.get_logger().info(
            f'Published static TF: world → aruco_tag_frame '
            f'(x={TAG_X}, y={TAG_Y}, z={TAG_Z})'
        )

    def _camera_info_cb(self, msg):
        if self.camera_matrix is None:
            self.camera_matrix = np.array(msg.k).reshape(3, 3)
            self.dist_coeffs = np.array(msg.d)
            self.get_logger().info(
                f'Got intrinsics: fx={self.camera_matrix[0,0]:.1f}, '
                f'fy={self.camera_matrix[1,1]:.1f}'
            )

    def _image_cb(self, msg):
        if self.camera_matrix is None or self.calibration_done:
            return

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.aruco_params
        )

        if ids is None or MARKER_ID not in ids.flatten():
            self.get_logger().warn(
                'ArUco marker not detected — make sure it is visible',
                throttle_duration_sec=2.0
            )
            return

        idx = list(ids.flatten()).index(MARKER_ID)
        marker_corners = corners[idx]

        obj_points = np.array([
            [-MARKER_SIZE / 2,  MARKER_SIZE / 2, 0],
            [ MARKER_SIZE / 2,  MARKER_SIZE / 2, 0],
            [ MARKER_SIZE / 2, -MARKER_SIZE / 2, 0],
            [-MARKER_SIZE / 2, -MARKER_SIZE / 2, 0]
        ], dtype=np.float32)

        success, rvec, tvec = cv2.solvePnP(
            obj_points,
            marker_corners.reshape(4, 2),
            self.camera_matrix,
            self.dist_coeffs
        )

        if not success:
            return

        # solvePnP gives: optical_frame → aruco
        # Invert to get: aruco → optical_frame
        rot_mat, _ = cv2.Rodrigues(rvec)
        T = np.eye(4)
        T[:3, :3] = rot_mat
        T[:3, 3] = tvec.flatten()
        T_inv = np.linalg.inv(T)

        inv_trans = T_inv[:3, 3]
        inv_quat = R.from_matrix(T_inv[:3, :3]).as_quat()

        self.samples.append((inv_trans, inv_quat))
        count = len(self.samples)

        self.get_logger().info(
            f'Calibrating... {count}/{CALIBRATION_COUNT}',
            throttle_duration_sec=0.5
        )

        if count >= CALIBRATION_COUNT:
            self._finish_calibration()

    def _finish_calibration(self):
        # Average translation and rotation in optical frame
        # Samples are: aruco → optical_frame (inverted solvePnP)
        all_trans = np.array([s[0] for s in self.samples])
        avg_trans_optical = np.mean(all_trans, axis=0)

        all_quats = np.array([s[1] for s in self.samples])
        avg_rot_optical = R.from_quat(all_quats).mean()

        # Convert: aruco → optical_frame  →  aruco → camera_link
        # iPhone camera_link → optical_frame: pure rotation, no translation offset
        # q = (x=0.5, y=-0.5, z=0.5, w=-0.5) as defined in the ROS2 driver
        T_link_to_optical = np.eye(4)
        T_link_to_optical[:3, :3] = R.from_quat(
            [0.5, -0.5, 0.5, -0.5]
        ).as_matrix()

        # Build 4x4: aruco → optical
        T_tag_to_optical = np.eye(4)
        T_tag_to_optical[:3, :3] = avg_rot_optical.as_matrix()
        T_tag_to_optical[:3, 3] = avg_trans_optical

        # optical → camera_link = inv(camera_link → optical)
        T_optical_to_link = np.linalg.inv(T_link_to_optical)

        # Chain: aruco → camera_link
        T_tag_to_link = T_tag_to_optical @ T_optical_to_link

        avg_trans = T_tag_to_link[:3, 3]
        avg_quat = R.from_matrix(T_tag_to_link[:3, :3]).as_quat()

        # Publish static TF: aruco_tag_frame → camera_link
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'aruco_tag_frame'
        t.child_frame_id = 'camera_link'

        t.transform.translation.x = float(avg_trans[0])
        t.transform.translation.y = float(avg_trans[1])
        t.transform.translation.z = float(avg_trans[2])
        t.transform.rotation.x = float(avg_quat[0])
        t.transform.rotation.y = float(avg_quat[1])
        t.transform.rotation.z = float(avg_quat[2])
        t.transform.rotation.w = float(avg_quat[3])

        self.broadcaster.sendTransform(t)
        self.calibration_done = True

        self.get_logger().info(
            f'\n========================================\n'
            f'  CALIBRATION COMPLETE!\n'
            f'========================================\n'
            f'  aruco_tag_frame → camera_link:\n'
            f'    Translation: x={avg_trans[0]:.4f}, y={avg_trans[1]:.4f}, z={avg_trans[2]:.4f}\n'
            f'    Quaternion:  x={avg_quat[0]:.4f}, y={avg_quat[1]:.4f}, z={avg_quat[2]:.4f}, w={avg_quat[3]:.4f}\n'
            f'\n'
            f'  TF chain: world → aruco_tag_frame → camera_link\n'
            f'  Marker can now be removed.\n'
            f'  Keep this node running to maintain the TF.\n'
            f'========================================'
        )


def main(args=None):
    rclpy.init(args=args)
    node = CameraCalibration()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
