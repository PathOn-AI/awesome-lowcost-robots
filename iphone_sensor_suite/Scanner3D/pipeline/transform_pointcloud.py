#!/usr/bin/env python3
"""
Transform a PLY point cloud using a 4x4 transformation matrix.

Usage:
    # Transform using a matrix file
    python3 transform_pointcloud.py --input fused.ply --transform T.txt --output transformed.ply

    # Transform scan captures to marker frame using T_world_marker.txt
    python3 transform_pointcloud.py --input fused.ply \
        --world-marker scan/session/T_world_marker.txt \
        --output fused_marker_frame.ply

    # Full pipeline: fuse scan in marker frame
    python3 transform_pointcloud.py --input fused.ply \
        --world-marker scan/session/T_world_marker.txt \
        --marker-workspace T_marker_workspace.txt \
        --output fused_workspace.ply

The transform chain:
    T_world_camera     <- ARKit per-frame pose (already applied in fused.ply)
    T_world_marker     <- ARKit marker detection (saved per session)
    T_marker_workspace <- Hand-measured constant

    points_workspace = T_marker_workspace @ inv(T_world_marker) @ points_world
"""

import argparse
import numpy as np
import open3d as o3d


def load_transform(path):
    """Load a 4x4 transformation matrix from a space-separated text file."""
    return np.loadtxt(path)


def main():
    parser = argparse.ArgumentParser(description='Transform a PLY point cloud')
    parser.add_argument('--input', type=str, required=True,
                        help='Input PLY file')
    parser.add_argument('--output', type=str, required=True,
                        help='Output PLY file')

    # Option 1: Direct transform matrix
    parser.add_argument('--transform', type=str, default=None,
                        help='4x4 transformation matrix file (applied directly)')

    # Option 2: World-to-marker conversion
    parser.add_argument('--world-marker', type=str, default=None,
                        help='T_world_marker.txt — transforms points from ARKit world to marker frame')

    # Option 3: Additional marker-to-workspace
    parser.add_argument('--marker-workspace', type=str, default=None,
                        help='T_marker_workspace.txt — transforms from marker to workspace frame')

    args = parser.parse_args()

    # Load input
    is_mesh = False
    mesh = o3d.io.read_triangle_mesh(args.input)
    if len(mesh.vertices) > 0 and len(mesh.triangles) > 0:
        is_mesh = True
        print(f"Loaded mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
    else:
        is_mesh = False
        mesh = o3d.io.read_point_cloud(args.input)
        print(f"Loaded point cloud: {len(mesh.points)} points")

    # Compute transform
    if args.transform:
        T = load_transform(args.transform)
        print(f"Applying transform from {args.transform}")

    elif args.world_marker:
        T_world_marker = load_transform(args.world_marker)
        # points_marker = inv(T_world_marker) @ points_world
        T = np.linalg.inv(T_world_marker)
        print(f"Converting from ARKit world to marker frame")
        print(f"  T_world_marker from: {args.world_marker}")

        if args.marker_workspace:
            T_marker_workspace = load_transform(args.marker_workspace)
            # points_workspace = T_marker_workspace @ points_marker
            T = T_marker_workspace @ T
            print(f"  Then marker to workspace via: {args.marker_workspace}")

    else:
        print("Error: provide --transform or --world-marker")
        return

    print(f"\nTransform matrix:\n{T}")

    # Apply transform
    mesh.transform(T)

    # Save
    if is_mesh:
        o3d.io.write_triangle_mesh(args.output, mesh)
    else:
        o3d.io.write_point_cloud(args.output, mesh)

    print(f"\nSaved to {args.output}")


if __name__ == '__main__':
    main()
