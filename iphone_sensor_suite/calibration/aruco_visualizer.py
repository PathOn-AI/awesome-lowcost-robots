#!/usr/bin/env python3
"""
ArUco marker detector and visualizer using ROS2 RealSense topics.
Subscribes to the RealSense color image and camera_info via ROS2,
detects the ArUco marker, and draws the 3D coordinate axes on the image.

Usage:
    source /opt/ros/jazzy/setup.bash
    python3 aruco_visualizer.py

Press 'q' to quit.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import cv2
import numpy as np
from scipy.spatial.transform import Rotation as R

# Marker config (must match your marker)
ARUCO_DICT = cv2.aruco.DICT_6X6_250
MARKER_ID = 3
MARKER_SIZE = 0.038  # meters (3.8 cm)


class ArucoVisualizer(Node):
    def __init__(self):
        super().__init__('aruco_visualizer')
        self.bridge = CvBridge()
        self.camera_matrix = None
        self.dist_coeffs = None

        self.aruco_dict = cv2.aruco.Dictionary_get(ARUCO_DICT)
        self.aruco_params = cv2.aruco.DetectorParameters_create()

        # QoS to match iPhone sensor node (BEST_EFFORT)
        from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        self.create_subscription(
            CameraInfo,
            'color/camera_info',
            self.camera_info_cb, qos
        )
        self.create_subscription(
            Image,
            'color/image_raw',
            self.image_cb, qos
        )

        self.get_logger().info(
            f'ArUco Visualizer running. Looking for DICT_6X6_250, '
            f'ID {MARKER_ID}, size {MARKER_SIZE*100:.1f}cm. Press q to quit.'
        )

    def camera_info_cb(self, msg):
        if self.camera_matrix is None:
            self.camera_matrix = np.array(msg.k).reshape(3, 3)
            self.dist_coeffs = np.array(msg.d)
            self.get_logger().info(
                f'Got intrinsics: fx={self.camera_matrix[0,0]:.1f}, '
                f'fy={self.camera_matrix[1,1]:.1f}'
            )

    def image_cb(self, msg):
        self.get_logger().info('Got image', throttle_duration_sec=2.0)
        if self.camera_matrix is None:
            return

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.aruco_params
        )

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

            if MARKER_ID in ids.flatten():
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

                if success:
                    # --- Transform optical → camera_link ---
                    rot_mat_optical, _ = cv2.Rodrigues(rvec)
                    t_optical = tvec.flatten()

                    # optical: X→right, Y→down, Z→forward
                    # camera_link: X→forward, Y→left, Z→up
                    R_optical_from_link = R.from_euler('ZX', [-90, -90], degrees=True)

                    # Build 4x4: optical → aruco
                    T_optical_to_aruco = np.eye(4)
                    T_optical_to_aruco[:3, :3] = rot_mat_optical
                    T_optical_to_aruco[:3, 3] = t_optical

                    # Build 4x4: camera_link → optical
                    T_link_to_optical = np.eye(4)
                    T_link_to_optical[:3, :3] = R_optical_from_link.as_matrix()

                    # Chain: camera_link → aruco
                    T_link_to_aruco = T_link_to_optical @ T_optical_to_aruco

                    t_link = T_link_to_aruco[:3, 3]
                    rot_link = R.from_matrix(T_link_to_aruco[:3, :3])
                    rpy_link = rot_link.as_euler('xyz', degrees=True)

                    # Convert camera_link pose back to optical frame for drawing
                    rvec_link, _ = cv2.Rodrigues(T_link_to_aruco[:3, :3].astype(np.float64))
                    tvec_link = T_link_to_aruco[:3, 3].reshape(3, 1).astype(np.float64)

                    # To draw in the image, we need to go back through optical frame
                    # Project camera_link axes through: optical = inv(link→optical) * link
                    T_optical_from_link = np.linalg.inv(T_link_to_optical)
                    T_optical_aruco_via_link = T_optical_from_link @ T_link_to_aruco
                    rvec_draw, _ = cv2.Rodrigues(T_optical_aruco_via_link[:3, :3].astype(np.float64))
                    tvec_draw = T_optical_aruco_via_link[:3, 3].reshape(3, 1).astype(np.float64)

                    # Draw 3D axes in camera_link convention (R=X fwd, G=Y left, B=Z up)
                    axis_length = MARKER_SIZE * 1.5
                    cv2.drawFrameAxes(frame, self.camera_matrix, self.dist_coeffs,
                                      rvec_draw, tvec_draw, axis_length)

                    # Invert: aruco → camera_link
                    T_aruco_to_link = np.linalg.inv(T_link_to_aruco)
                    t_inv = T_aruco_to_link[:3, 3]
                    quat_inv = R.from_matrix(T_aruco_to_link[:3, :3]).as_quat()  # [qx, qy, qz, qw]
                    rpy_inv = R.from_matrix(T_aruco_to_link[:3, :3]).as_euler('xyz', degrees=True)

                    print(
                        f"[cam_link→aruco] pos: x={t_link[0]:.4f} y={t_link[1]:.4f} z={t_link[2]:.4f}m | "
                        f"[aruco→cam_link] pos: x={t_inv[0]:.4f} y={t_inv[1]:.4f} z={t_inv[2]:.4f}m | "
                        f"quat: [{quat_inv[0]:.4f}, {quat_inv[1]:.4f}, {quat_inv[2]:.4f}, {quat_inv[3]:.4f}]"
                    )

                    # Display both on screen
                    cv2.putText(frame, "camera_link -> aruco (X:fwd Y:left Z:up)", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    info = f"pos: x={t_link[0]:.3f} y={t_link[1]:.3f} z={t_link[2]:.3f}m"
                    cv2.putText(frame, info, (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                    cv2.putText(frame, "aruco -> camera_link (inverted)", (10, 100),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    info_inv = f"pos: x={t_inv[0]:.3f} y={t_inv[1]:.3f} z={t_inv[2]:.3f}m"
                    cv2.putText(frame, info_inv, (10, 130),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    quat_info = f"quat: [{quat_inv[0]:.3f}, {quat_inv[1]:.3f}, {quat_inv[2]:.3f}, {quat_inv[3]:.3f}]"
                    cv2.putText(frame, quat_info, (10, 160),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        else:
            cv2.putText(frame, "No marker detected", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        display = cv2.resize(frame, (frame.shape[1] // 2, frame.shape[0] // 2))
        cv2.imshow("ArUco Visualizer", display)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.get_logger().info('Quitting...')
            raise SystemExit


def main():
    rclpy.init()
    node = ArucoVisualizer()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
