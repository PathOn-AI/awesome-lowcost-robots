#!/usr/bin/env python3
"""
Fuse multiple iPhone 3D scanner captures into a single point cloud.

Two modes:
  --mode ply   (default) Load pre-computed pointcloud.ply files
  --mode depth           Deproject from depth.png + camera_info.json

Usage:
    python3 fuse_pointclouds.py --data-dir ../scan/2026-03-20--17-33-52
    python3 fuse_pointclouds.py --data-dir ../scan/2026-03-20--17-33-52 --mode depth
    python3 fuse_pointclouds.py --data-dir ../scan/2026-03-20--17-33-52 --icp
"""

import argparse
import json
import os
import glob

import cv2
import numpy as np
import open3d as o3d


# ---------- Shared ----------

def get_optical_to_body_transform():
    """Optical frame (X-right, Y-down, Z-forward) -> ARKit body (X-right, Y-up, Z-backward)."""
    return np.array([
        [1,  0,  0, 0],
        [0, -1,  0, 0],
        [0,  0, -1, 0],
        [0,  0,  0, 1],
    ], dtype=np.float64)


def transform_to_world(points, T_world_body):
    """Transform points from optical frame to world frame."""
    T_world_optical = T_world_body @ get_optical_to_body_transform()
    pts_h = np.hstack([points, np.ones((len(points), 1))])
    return (T_world_optical @ pts_h.T).T[:, :3]


def make_pcd(points, colors):
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))
    pcd.colors = o3d.utility.Vector3dVector(colors.astype(np.float64))
    return pcd


# ---------- Mode: PLY ----------

def load_snapshot_ply(snapshot_dir):
    """Load pre-computed PLY + ARKit transform."""
    pcd = o3d.io.read_point_cloud(os.path.join(snapshot_dir, 'pointcloud.ply'))
    transform = np.loadtxt(os.path.join(snapshot_dir, 'T_world_camera.txt'))

    points = np.asarray(pcd.points)
    colors = np.asarray(pcd.colors)

    pts_world = transform_to_world(points, transform)
    return pts_world, colors, os.path.basename(snapshot_dir)


# ---------- Mode: Depth ----------

def load_snapshot_depth(snapshot_dir):
    """Deproject depth.png to 3D points, transform to world frame."""
    # RGB
    rgb = cv2.cvtColor(cv2.imread(os.path.join(snapshot_dir, 'rgb.png')), cv2.COLOR_BGR2RGB)

    # Depth: 16-bit PNG in millimeters
    depth_mm = cv2.imread(os.path.join(snapshot_dir, 'depth.png'), cv2.IMREAD_UNCHANGED).astype(np.float32)
    depth_m = depth_mm / 1000.0

    # Intrinsics (at RGB resolution)
    with open(os.path.join(snapshot_dir, 'camera_info.json')) as f:
        cam_info = json.load(f)
    K = np.array(cam_info['k']).reshape(3, 3)

    # Meta
    with open(os.path.join(snapshot_dir, 'meta.json')) as f:
        meta = json.load(f)

    # Transform
    transform = np.loadtxt(os.path.join(snapshot_dir, 'T_world_camera.txt'))

    # Scale intrinsics to depth resolution
    depth_h, depth_w = depth_m.shape
    rgb_w, rgb_h = meta.get('rgb_width', rgb.shape[1]), meta.get('rgb_height', rgb.shape[0])
    K_depth = K.copy()
    K_depth[0, 0] *= depth_w / rgb_w
    K_depth[0, 2] *= depth_w / rgb_w
    K_depth[1, 1] *= depth_h / rgb_h
    K_depth[1, 2] *= depth_h / rgb_h

    # Deproject
    fx, fy = K_depth[0, 0], K_depth[1, 1]
    cx, cy = K_depth[0, 2], K_depth[1, 2]
    u, v = np.meshgrid(np.arange(depth_w), np.arange(depth_h))
    z = depth_m
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    points = np.stack([x, y, z], axis=-1).reshape(-1, 3).astype(np.float32)

    # Resize RGB to depth resolution for colors
    rgb_resized = cv2.resize(rgb, (depth_w, depth_h))
    colors = rgb_resized.reshape(-1, 3).astype(np.float64) / 255.0

    # Filter invalid depth
    depth_flat = depth_m.reshape(-1)
    valid = (depth_flat > 0.1) & (depth_flat < 5.0) & np.isfinite(depth_flat)
    points = points[valid]
    colors = colors[valid]

    # Transform to world
    pts_world = transform_to_world(points, transform)
    return pts_world, colors, os.path.basename(snapshot_dir)


# ---------- Mode: TSDF ----------

def load_tsdf_snapshot(snap_dir):
    """Load all data needed for TSDF integration from a capture directory."""
    name = os.path.basename(snap_dir)

    depth_mm = cv2.imread(os.path.join(snap_dir, 'depth.png'), cv2.IMREAD_UNCHANGED)
    if depth_mm is None:
        return None
    depth_m = depth_mm.astype(np.float32) / 1000.0

    rgb = cv2.cvtColor(cv2.imread(os.path.join(snap_dir, 'rgb.png')), cv2.COLOR_BGR2RGB)
    depth_h, depth_w = depth_m.shape
    rgb_resized = cv2.resize(rgb, (depth_w, depth_h))

    with open(os.path.join(snap_dir, 'camera_info.json')) as f:
        cam_info = json.load(f)
    K = np.array(cam_info['k']).reshape(3, 3)

    with open(os.path.join(snap_dir, 'meta.json')) as f:
        meta = json.load(f)
    rgb_w = meta.get('rgb_width', rgb.shape[1])
    rgb_h = meta.get('rgb_height', rgb.shape[0])

    K_depth = K.copy()
    K_depth[0, 0] *= depth_w / rgb_w
    K_depth[0, 2] *= depth_w / rgb_w
    K_depth[1, 1] *= depth_h / rgb_h
    K_depth[1, 2] *= depth_h / rgb_h

    T_world_body = np.loadtxt(os.path.join(snap_dir, 'T_world_camera.txt'))

    return {
        'name': name,
        'depth_m': depth_m,
        'rgb_resized': rgb_resized,
        'K_depth': K_depth,
        'depth_w': depth_w,
        'depth_h': depth_h,
        'T_world_body': T_world_body,
    }


def fuse_tsdf(snapshot_dirs, voxel_size=0.005, sdf_trunc=None, depth_trunc=3.0,
              use_icp=False, min_fitness=0.1, max_correction_mm=500.0):
    """Fuse captures into a mesh using TSDF volumetric integration.

    Args:
        snapshot_dirs: list of capture directories
        voxel_size: TSDF voxel size in meters (smaller = finer detail)
        sdf_trunc: SDF truncation distance (default: 3 * voxel_size)
        depth_trunc: max depth to integrate in meters
        use_icp: refine poses with ICP before TSDF integration
        min_fitness: skip frames with ICP fitness below this (default: 0.1)
        max_correction_mm: skip frames needing correction larger than this in mm (default: 500)
    """
    if sdf_trunc is None:
        sdf_trunc = voxel_size * 3

    T_body_optical = get_optical_to_body_transform()

    # Load all snapshots
    snapshots = []
    for snap_dir in sorted(snapshot_dirs):
        snap = load_tsdf_snapshot(snap_dir)
        if snap is None:
            print(f"  {snap['name']}: no depth.png, skipped")
            continue
        snapshots.append(snap)

    if not snapshots:
        print("No valid snapshots!")
        return o3d.geometry.TriangleMesh()

    # ICP pose refinement: correct ARKit poses using point cloud alignment
    if use_icp and len(snapshots) > 1:
        print("\nICP pose refinement for TSDF:")

        # Build world-frame point clouds for ICP
        ref_snap = snapshots[0]
        ref_pts, _, _ = load_snapshot_ply(os.path.join(
            os.path.dirname(snapshot_dirs[0]), ref_snap['name']))
        accumulated_pcd = make_pcd(ref_pts, np.ones_like(ref_pts) * 0.5)
        print(f"  Reference: {ref_snap['name']}")

        # icp_corrections[i] = correction transform for snapshot i (identity for reference)
        icp_corrections = [np.eye(4)]

        for i, snap in enumerate(snapshots[1:], 1):
            snap_dir = os.path.join(os.path.dirname(snapshot_dirs[0]), snap['name'])
            pts, _, _ = load_snapshot_ply(snap_dir)
            source_pcd = make_pcd(pts, np.ones_like(pts) * 0.5)

            correction, fitness, rmse = icp_refine(source_pcd, accumulated_pcd)

            translation = np.linalg.norm(correction[:3, 3]) * 1000
            angle = np.arccos(np.clip((np.trace(correction[:3, :3]) - 1) / 2, -1, 1))
            angle_deg = np.degrees(angle)

            # Check if frame should be skipped
            skip = False
            reasons = []
            if fitness < min_fitness:
                reasons.append(f"fitness {fitness:.4f} < {min_fitness}")
                skip = True
            if translation > max_correction_mm:
                reasons.append(f"correction {translation:.0f}mm > {max_correction_mm:.0f}mm")
                skip = True

            if skip:
                print(f"  {snap['name']}: SKIPPED ({', '.join(reasons)})")
                icp_corrections.append(None)  # mark as skipped
            else:
                print(f"  {snap['name']}: fitness={fitness:.4f}, RMSE={rmse*1000:.2f}mm, "
                      f"correction: {translation:.2f}mm / {angle_deg:.3f}deg")
                icp_corrections.append(correction)

                # Update accumulated cloud with corrected points
                source_pcd.transform(correction)
                accumulated_pcd = accumulated_pcd + source_pcd
    else:
        icp_corrections = [np.eye(4)] * len(snapshots)

    # TSDF integration with (optionally corrected) poses
    skipped = sum(1 for c in icp_corrections if c is None)
    if skipped > 0:
        print(f"\nSkipped {skipped} frame(s) due to poor alignment")
    print("\nTSDF integration:")
    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel_size,
        sdf_trunc=sdf_trunc,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8,
    )

    for i, snap in enumerate(snapshots):
        # Skip frames marked as poorly aligned
        if icp_corrections[i] is None:
            print(f"  {snap['name']}: skipped (poor alignment)")
            continue

        intrinsic = o3d.camera.PinholeCameraIntrinsic(
            snap['depth_w'], snap['depth_h'],
            snap['K_depth'][0, 0], snap['K_depth'][1, 1],
            snap['K_depth'][0, 2], snap['K_depth'][1, 2])

        # Compute world-to-optical extrinsic
        T_world_body = snap['T_world_body']
        T_world_optical = T_world_body @ np.linalg.inv(T_body_optical)

        # Apply ICP correction: corrected_world = correction @ original_world
        T_world_optical_corrected = icp_corrections[i] @ T_world_optical
        extrinsic = np.linalg.inv(T_world_optical_corrected)

        depth_o3d = o3d.geometry.Image(snap['depth_m'])
        color_o3d = o3d.geometry.Image(snap['rgb_resized'].astype(np.uint8))
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_o3d, depth_o3d,
            depth_scale=1.0,
            depth_trunc=depth_trunc,
            convert_rgb_to_intensity=False)

        volume.integrate(rgbd, intrinsic, extrinsic)
        print(f"  {snap['name']}: integrated ({snap['depth_w']}x{snap['depth_h']})")

    print("\nExtracting mesh from TSDF volume...")
    mesh = volume.extract_triangle_mesh()
    mesh.compute_vertex_normals()

    print(f"Mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
    return mesh


# ---------- ICP ----------

def icp_refine(source_pcd, target_pcd, icp_voxel_size=0.005, max_distance=0.02):
    source_down = source_pcd.voxel_down_sample(icp_voxel_size)
    target_down = target_pcd.voxel_down_sample(icp_voxel_size)

    source_down.estimate_normals(
        o3d.geometry.KDTreeSearchParamHybrid(radius=icp_voxel_size * 4, max_nn=30))
    target_down.estimate_normals(
        o3d.geometry.KDTreeSearchParamHybrid(radius=icp_voxel_size * 4, max_nn=30))

    result = o3d.pipelines.registration.registration_icp(
        source_down, target_down, max_distance, np.eye(4),
        o3d.pipelines.registration.TransformationEstimationPointToPlane(),
        o3d.pipelines.registration.ICPConvergenceCriteria(
            max_iteration=100, relative_fitness=1e-6, relative_rmse=1e-6))

    return result.transformation, result.fitness, result.inlier_rmse


# ---------- Fusion ----------

def fuse_snapshots(snapshot_dirs, mode='ply', bounds=None, voxel_size=None,
                   use_statistical_filter=True, use_icp=False):
    load_fn = load_snapshot_ply if mode == 'ply' else load_snapshot_depth
    per_capture = []

    for snap_dir in sorted(snapshot_dirs):
        points, colors, name = load_fn(snap_dir)

        if len(points) == 0:
            print(f"  {name}: 0 points (skipped)")
            continue

        if bounds is not None:
            mask = (
                (points[:, 0] >= bounds[0, 0]) & (points[:, 0] <= bounds[0, 1]) &
                (points[:, 1] >= bounds[1, 0]) & (points[:, 1] <= bounds[1, 1]) &
                (points[:, 2] >= bounds[2, 0]) & (points[:, 2] <= bounds[2, 1])
            )
            points, colors = points[mask], colors[mask]

        print(f"  {name}: {len(points)} points")
        per_capture.append((points, colors, name))

    if not per_capture:
        print("No valid points found!")
        return o3d.geometry.PointCloud()

    if use_icp and len(per_capture) > 1:
        print("\nICP refinement:")
        ref_points, ref_colors, ref_name = per_capture[0]
        accumulated_pcd = make_pcd(ref_points, ref_colors)
        all_points = [ref_points]
        all_colors = [ref_colors]
        print(f"  Reference: {ref_name}")

        for points, colors, name in per_capture[1:]:
            source_pcd = make_pcd(points, colors)
            transform, fitness, rmse = icp_refine(source_pcd, accumulated_pcd)

            source_pcd.transform(transform)
            refined_points = np.asarray(source_pcd.points)
            refined_colors = np.asarray(source_pcd.colors)

            translation = np.linalg.norm(transform[:3, 3]) * 1000
            angle = np.arccos(np.clip((np.trace(transform[:3, :3]) - 1) / 2, -1, 1))
            print(f"  {name}: fitness={fitness:.4f}, RMSE={rmse*1000:.2f}mm, "
                  f"correction: {translation:.2f}mm / {np.degrees(angle):.3f}deg")

            all_points.append(refined_points)
            all_colors.append(refined_colors)

            accumulated_pcd = make_pcd(np.vstack(all_points), np.vstack(all_colors))
    else:
        all_points = [p for p, c, n in per_capture]
        all_colors = [c for p, c, n in per_capture]

    merged_points = np.vstack(all_points)
    merged_colors = np.vstack(all_colors)
    print(f"\nTotal merged: {len(merged_points)} points")

    pcd = make_pcd(merged_points, merged_colors)

    if voxel_size is not None and voxel_size > 0:
        pcd = pcd.voxel_down_sample(voxel_size)
        print(f"After voxel downsampling ({voxel_size}m): {len(pcd.points)} points")

    if use_statistical_filter and len(pcd.points) > 100:
        pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=50, std_ratio=2.0)
        print(f"After outlier removal: {len(pcd.points)} points")

    return pcd


def main():
    parser = argparse.ArgumentParser(description='Fuse iPhone 3D scanner captures')
    parser.add_argument('--data-dir', type=str, required=True,
                        help='Directory containing capture_* folders')
    parser.add_argument('--mode', choices=['ply', 'depth', 'tsdf'], default='ply',
                        help='ply: point cloud from PLY files, depth: from depth.png, tsdf: volumetric mesh fusion')
    parser.add_argument('--output', type=str, default=None,
                        help='Output PLY path (default: <data-dir>/fused.ply)')
    parser.add_argument('--voxel-size', type=float, default=0.005,
                        help='Voxel size for downsampling in meters (0 to disable)')
    parser.add_argument('--bounds', type=str, default=None,
                        help='Workspace bounds: x_min,x_max,y_min,y_max,z_min,z_max')
    parser.add_argument('--icp', action='store_true',
                        help='Refine alignment with ICP')
    parser.add_argument('--no-filter', action='store_true',
                        help='Disable statistical outlier removal')
    parser.add_argument('--min-fitness', type=float, default=0.1,
                        help='Skip frames with ICP fitness below this (default: 0.1)')
    parser.add_argument('--max-correction', type=float, default=500,
                        help='Skip frames needing ICP correction larger than this in mm (default: 500)')

    args = parser.parse_args()

    data_dir = args.data_dir
    if not os.path.isabs(data_dir):
        data_dir = os.path.abspath(data_dir)

    snapshot_dirs = sorted(glob.glob(os.path.join(data_dir, 'capture_*')))
    if not snapshot_dirs:
        print(f"No capture folders found in {data_dir}")
        return

    print(f"Found {len(snapshot_dirs)} captures in {data_dir}")
    print(f"Mode: {args.mode}")

    bounds = None
    if args.bounds:
        vals = [float(v) for v in args.bounds.split(',')]
        bounds = np.array(vals).reshape(3, 2)
        print(f"Bounds: X=[{bounds[0,0]:.3f}, {bounds[0,1]:.3f}], "
              f"Y=[{bounds[1,0]:.3f}, {bounds[1,1]:.3f}], "
              f"Z=[{bounds[2,0]:.3f}, {bounds[2,1]:.3f}]")

    output_path = args.output or os.path.join(data_dir, 'fused.ply')

    if args.mode == 'tsdf':
        mesh = fuse_tsdf(snapshot_dirs, voxel_size=args.voxel_size, use_icp=args.icp,
                         min_fitness=args.min_fitness, max_correction_mm=args.max_correction)
        o3d.io.write_triangle_mesh(output_path, mesh)
        print(f"\nSaved fused mesh to {output_path}")
    else:
        voxel = args.voxel_size if args.voxel_size > 0 else None
        pcd = fuse_snapshots(snapshot_dirs, mode=args.mode, bounds=bounds, voxel_size=voxel,
                             use_statistical_filter=not args.no_filter,
                             use_icp=args.icp)
        o3d.io.write_point_cloud(output_path, pcd)
        print(f"\nSaved fused point cloud to {output_path}")


if __name__ == '__main__':
    main()
