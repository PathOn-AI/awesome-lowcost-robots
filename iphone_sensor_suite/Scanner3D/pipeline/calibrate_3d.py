#!/usr/bin/env python3
"""
Fix T_world_marker.txt using OpenCV ArUco detection + LiDAR depth.

Instead of solvePnP (monocular depth, noisy), this script uses the LiDAR depth
image to get accurate 3D positions of the marker corners, then constructs the
marker frame purely from geometry.

Usage:
    python3 calibrate_3d.py --scan-dir ../scan/2026-03-23--16-27-27
    python3 calibrate_3d.py --scan-dir ../scan/2026-03-23--16-27-27 --dict 4x4_50 --id 1 --size 85

How it works:
    1. Detects ArUco marker corners in rgb.png with OpenCV (sub-pixel accurate)
    2. Projects corner pixels into depth.png (LiDAR, sub-cm accurate)
    3. Constructs marker frame from 4 LiDAR 3D corners:
       - Center = mean of 4 corners
       - X = right edge direction (corner0 -> corner1)
       - Y = top edge direction (corner3 -> corner0)
       - Z = cross(X, Y), points out of paper (= up for table-mounted marker)
    4. Averages T_world_marker across all captures
    5. Overwrites T_world_marker.txt
"""

import argparse
import json
import os
import glob

import cv2
import numpy as np


DICT_MAP = {
    "4x4_50": cv2.aruco.DICT_4X4_50,
    "4x4_100": cv2.aruco.DICT_4X4_100,
    "4x4_250": cv2.aruco.DICT_4X4_250,
    "4x4_1000": cv2.aruco.DICT_4X4_1000,
    "5x5_50": cv2.aruco.DICT_5X5_50,
    "5x5_100": cv2.aruco.DICT_5X5_100,
    "5x5_250": cv2.aruco.DICT_5X5_250,
    "5x5_1000": cv2.aruco.DICT_5X5_1000,
    "6x6_50": cv2.aruco.DICT_6X6_50,
    "6x6_100": cv2.aruco.DICT_6X6_100,
    "6x6_250": cv2.aruco.DICT_6X6_250,
    "6x6_1000": cv2.aruco.DICT_6X6_1000,
    "7x7_50": cv2.aruco.DICT_7X7_50,
    "7x7_100": cv2.aruco.DICT_7X7_100,
    "7x7_250": cv2.aruco.DICT_7X7_250,
    "7x7_1000": cv2.aruco.DICT_7X7_1000,
    "original": cv2.aruco.DICT_ARUCO_ORIGINAL,
}


def get_optical_to_body():
    """Optical frame (X-right, Y-down, Z-forward) -> ARKit body (X-right, Y-up, Z-backward)."""
    return np.array([
        [1,  0,  0, 0],
        [0, -1,  0, 0],
        [0,  0, -1, 0],
        [0,  0,  0, 1],
    ], dtype=np.float64)


def detect_marker_corners(image_path, dict_name, marker_id):
    """Detect ArUco marker and return 4 corner pixel coordinates.

    Returns:
        corners: (4, 2) array of pixel coordinates, or None.
        OpenCV corner order: [top-left, top-right, bottom-right, bottom-left]
    """
    rgb = cv2.imread(image_path)
    if rgb is None:
        return None

    gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)

    aruco_dict = cv2.aruco.getPredefinedDictionary(DICT_MAP[dict_name])
    params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, params)
    corners, ids, _ = detector.detectMarkers(gray)

    if ids is None or marker_id not in ids.flatten():
        return None

    idx = list(ids.flatten()).index(marker_id)
    return corners[idx].reshape(4, 2)


def corners_to_3d(corners_px, depth_path, camera_info_path, meta_path):
    """Project 2D corner pixels into 3D using LiDAR depth.

    Args:
        corners_px: (4, 2) pixel coordinates in RGB image space
        depth_path: path to depth.png (16-bit, mm)
        camera_info_path: path to camera_info.json
        meta_path: path to meta.json

    Returns:
        corners_3d: (4, 3) 3D points in optical frame, or None if depth invalid.
    """
    depth_mm = cv2.imread(depth_path, cv2.IMREAD_UNCHANGED)
    if depth_mm is None:
        return None
    depth_m = depth_mm.astype(np.float32) / 1000.0
    depth_h, depth_w = depth_m.shape

    with open(camera_info_path) as f:
        cam_info = json.load(f)
    K = np.array(cam_info['k']).reshape(3, 3)

    with open(meta_path) as f:
        meta = json.load(f)
    rgb_w = meta.get('rgb_width', cam_info.get('width', 1920))
    rgb_h = meta.get('rgb_height', cam_info.get('height', 1440))

    # Scale intrinsics from RGB to depth resolution
    K_depth = K.copy()
    K_depth[0, 0] *= depth_w / rgb_w
    K_depth[0, 2] *= depth_w / rgb_w
    K_depth[1, 1] *= depth_h / rgb_h
    K_depth[1, 2] *= depth_h / rgb_h

    fx, fy = K_depth[0, 0], K_depth[1, 1]
    cx, cy = K_depth[0, 2], K_depth[1, 2]

    # Scale corner pixels from RGB to depth resolution
    corners_depth = corners_px.copy()
    corners_depth[:, 0] *= depth_w / rgb_w
    corners_depth[:, 1] *= depth_h / rgb_h

    corners_3d = []
    for u, v in corners_depth:
        # Sample depth with bilinear interpolation in a small neighborhood
        u_int, v_int = int(round(u)), int(round(v))

        # Collect valid depths in a 5x5 patch around the corner
        half = 2
        depths = []
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                vi, ui = v_int + dy, u_int + dx
                if 0 <= vi < depth_h and 0 <= ui < depth_w:
                    d = depth_m[vi, ui]
                    if 0.05 < d < 5.0:
                        depths.append(d)

        if not depths:
            return None  # no valid depth at this corner

        z = np.median(depths)
        x = (u - cx) * z / fx
        y = (v - cy) * z / fy
        corners_3d.append([x, y, z])

    return np.array(corners_3d, dtype=np.float64)


def build_marker_frame(corners_3d_optical, T_world_body):
    """Build T_world_marker from 4 LiDAR 3D corners.

    Args:
        corners_3d_optical: (4, 3) in optical frame
            [0]=top-left, [1]=top-right, [2]=bottom-right, [3]=bottom-left
        T_world_body: 4x4 ARKit camera pose

    Returns:
        T_world_marker: 4x4 transform
    """
    T_optical_to_body = get_optical_to_body()
    T_world_optical = T_world_body @ T_optical_to_body

    # Transform corners to world frame
    ones = np.ones((4, 1))
    corners_h = np.hstack([corners_3d_optical, ones])  # (4, 4)
    corners_world = (T_world_optical @ corners_h.T).T[:, :3]  # (4, 3)

    # Marker frame from corners
    # X axis: left to right (corner0 -> corner1)
    x_raw = corners_world[1] - corners_world[0]
    # Y axis: bottom to top (corner3 -> corner0) — but OpenCV order is
    # [top-left, top-right, bottom-right, bottom-left], so corner3=bottom-left
    y_raw = corners_world[0] - corners_world[3]
    # Z axis: out of paper
    z_raw = np.cross(x_raw, y_raw)

    # Normalize
    x_axis = x_raw / np.linalg.norm(x_raw)
    z_axis = z_raw / np.linalg.norm(z_raw)
    # Recompute Y for orthogonality
    y_axis = np.cross(z_axis, x_axis)
    y_axis = y_axis / np.linalg.norm(y_axis)

    # Center = mean of 4 corners
    center = corners_world.mean(axis=0)

    T_world_marker = np.eye(4)
    T_world_marker[:3, 0] = x_axis
    T_world_marker[:3, 1] = y_axis
    T_world_marker[:3, 2] = z_axis
    T_world_marker[:3, 3] = center

    return T_world_marker


def average_transforms(transforms):
    """Average multiple 4x4 transforms: SVD for rotation, mean for translation."""
    if len(transforms) == 1:
        return transforms[0].copy()

    translations = np.array([T[:3, 3] for T in transforms])
    avg_t = translations.mean(axis=0)

    R_sum = sum(T[:3, :3] for T in transforms)
    U, _, Vt = np.linalg.svd(R_sum)
    det = np.linalg.det(U @ Vt)
    D = np.diag([1, 1, det])
    avg_R = U @ D @ Vt

    T_avg = np.eye(4)
    T_avg[:3, :3] = avg_R
    T_avg[:3, 3] = avg_t
    return T_avg


def main():
    parser = argparse.ArgumentParser(
        description='Fix T_world_marker.txt using ArUco detection + LiDAR depth')
    parser.add_argument('--scan-dir', type=str, required=True,
                        help='Scan session directory')
    parser.add_argument('--dict', type=str, default='4x4_50',
                        choices=list(DICT_MAP.keys()),
                        help='ArUco dictionary (default: 4x4_50)')
    parser.add_argument('--id', type=int, default=1,
                        help='Marker ID (default: 1)')
    parser.add_argument('--size', type=float, default=85,
                        help='Marker size in mm (default: 85, used for reporting only)')
    parser.add_argument('--capture', type=int, default=None,
                        help='Use specific capture index (default: use all)')
    parser.add_argument('--best', action='store_true',
                        help='Use only the single best capture (largest marker in frame)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print result without overwriting T_world_marker.txt')

    args = parser.parse_args()
    scan_dir = os.path.abspath(args.scan_dir)

    # Find capture directories
    if args.capture is not None:
        captures = [os.path.join(scan_dir, f'capture_{args.capture:06d}')]
    else:
        captures = sorted([d for d in glob.glob(os.path.join(scan_dir, 'capture_*'))
                          if os.path.isdir(d)])

    if not captures:
        print(f"No captures found in {scan_dir}")
        return

    # Detect marker in all captures, build frame from LiDAR 3D corners
    all_T_world_marker = []
    used_captures = []
    marker_pixel_sizes = []  # track marker size in pixels for --best selection

    for cap_dir in captures:
        name = os.path.basename(cap_dir)
        image_path = os.path.join(cap_dir, 'rgb.png')
        depth_path = os.path.join(cap_dir, 'depth.png')
        info_path = os.path.join(cap_dir, 'camera_info.json')
        meta_path = os.path.join(cap_dir, 'meta.json')
        pose_path = os.path.join(cap_dir, 'T_world_camera.txt')

        required = [image_path, depth_path, info_path, meta_path, pose_path]
        if not all(os.path.exists(p) for p in required):
            print(f"  {name}: missing files, skipped")
            continue

        # Detect 2D corners
        corners_px = detect_marker_corners(image_path, args.dict, args.id)
        if corners_px is None:
            print(f"  {name}: marker not detected")
            continue

        # Marker size in pixels (perimeter / 4) — larger = closer = better depth
        perimeter = sum(np.linalg.norm(corners_px[(i+1) % 4] - corners_px[i])
                        for i in range(4))
        marker_px_size = perimeter / 4

        # Project to 3D using LiDAR depth
        corners_3d = corners_to_3d(corners_px, depth_path, info_path, meta_path)
        if corners_3d is None:
            print(f"  {name}: invalid depth at marker corners")
            continue

        # Compute marker size from LiDAR corners (sanity check)
        edge_top = np.linalg.norm(corners_3d[1] - corners_3d[0]) * 1000
        edge_right = np.linalg.norm(corners_3d[2] - corners_3d[1]) * 1000
        edge_bottom = np.linalg.norm(corners_3d[3] - corners_3d[2]) * 1000
        edge_left = np.linalg.norm(corners_3d[0] - corners_3d[3]) * 1000
        avg_size = (edge_top + edge_right + edge_bottom + edge_left) / 4

        # Build marker frame
        T_world_body = np.loadtxt(pose_path)
        T_wm = build_marker_frame(corners_3d, T_world_body)

        z_axis = T_wm[:3, 2]
        pos = T_wm[:3, 3]
        print(f"  {name}: Z=[{z_axis[0]:.3f}, {z_axis[1]:.3f}, {z_axis[2]:.3f}]  "
              f"pos=[{pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f}]  "
              f"measured_size={avg_size:.1f}mm (expected {args.size}mm)  "
              f"pixel_size={marker_px_size:.1f}px")

        all_T_world_marker.append(T_wm)
        used_captures.append(name)
        marker_pixel_sizes.append(marker_px_size)

    if not all_T_world_marker:
        print(f"Marker (dict={args.dict}, ID={args.id}) not found in any capture")
        return

    print(f"\nMarker detected in {len(all_T_world_marker)}/{len(captures)} captures")
    print(f"  Dictionary: {args.dict}, ID: {args.id}, Size: {args.size}mm")

    if args.best and len(all_T_world_marker) > 1:
        # Pick the capture with the largest marker in pixels (closest, most accurate depth)
        best_idx = int(np.argmax(marker_pixel_sizes))
        best_name = used_captures[best_idx]
        best_px = marker_pixel_sizes[best_idx]
        print(f"\n  --best: using {best_name} (largest marker: {best_px:.1f}px)")
        T_world_marker = all_T_world_marker[best_idx]
    else:
        # Average T_world_marker across all detections
        T_world_marker = average_transforms(all_T_world_marker)

    if len(all_T_world_marker) > 1:
        for i, (T_wm, name) in enumerate(zip(all_T_world_marker, used_captures)):
            t_diff = np.linalg.norm(T_wm[:3, 3] - T_world_marker[:3, 3]) * 1000
            R_diff = T_world_marker[:3, :3].T @ T_wm[:3, :3]
            angle = np.degrees(np.arccos(np.clip((np.trace(R_diff) - 1) / 2, -1, 1)))
            best_tag = " <-- BEST" if args.best and i == best_idx else ""
            print(f"  {name} deviation: {t_diff:.1f}mm, {angle:.1f}°{best_tag}")

    print(f"\nT_world_marker (LiDAR 3D):")
    for row in range(4):
        vals = " ".join(f"{T_world_marker[row, col]:10.6f}" for col in range(4))
        print(f"  {vals}")

    # Compare with existing
    output_path = os.path.join(scan_dir, 'T_world_marker_3d.txt')
    if os.path.exists(output_path):
        T_old = np.loadtxt(output_path)
        R_diff = T_old[:3, :3].T @ T_world_marker[:3, :3]
        angle = np.degrees(np.arccos(np.clip((np.trace(R_diff) - 1) / 2, -1, 1)))
        t_diff = np.linalg.norm(T_old[:3, 3] - T_world_marker[:3, 3])
        print(f"\nDifference from existing {os.path.basename(output_path)}:")
        print(f"  Rotation: {angle:.1f}°")
        print(f"  Translation: {t_diff*1000:.1f}mm")

    # Save
    if args.dry_run:
        print("\n(dry-run: not saving)")
    else:
        np.savetxt(output_path, T_world_marker, fmt='% .8f')
        print(f"\nSaved to {output_path}")


if __name__ == '__main__':
    main()
