#!/usr/bin/env python3
"""
Open3D point cloud viewer for iPhone sensor streaming.

Usage:
    python point_cloud.py <iphone_ip>          # WiFi mode
    python point_cloud.py 192.168.1.100        # WiFi mode
    python point_cloud.py --usb                # USB mode

Controls:
    Q: Quit
    Mouse: Rotate/zoom view
"""

import sys
import os
import argparse
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import open3d as o3d
except ImportError:
    print("Open3D not installed. Install with: pip install open3d")
    sys.exit(1)

from sdk import IPhoneSensorClient, Frame


def frame_to_point_cloud(frame: Frame) -> o3d.geometry.PointCloud:
    """Convert a frame to Open3D point cloud."""
    depth = frame.depth
    color = frame.color
    intr = frame.get_depth_intrinsics()

    # Create mesh grid of pixel coordinates
    height, width = depth.shape
    u = np.arange(width)
    v = np.arange(height)
    u, v = np.meshgrid(u, v)

    # Unproject to 3D
    z = depth
    x = (u - intr.ppx) * z / intr.fx
    y = (v - intr.ppy) * z / intr.fy

    # Stack into points array
    points = np.stack([x, y, z], axis=-1).reshape(-1, 3)

    # Get colors (resize color to depth size and convert BGR to RGB)
    import cv2
    color_resized = cv2.resize(color, (width, height))
    colors = cv2.cvtColor(color_resized, cv2.COLOR_BGR2RGB).reshape(-1, 3) / 255.0

    # Filter out invalid points (depth = 0 or inf)
    valid = (z.flatten() > 0.1) & (z.flatten() < 5.0) & np.isfinite(z.flatten())
    points = points[valid]
    colors = colors[valid]

    # Create point cloud
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)

    return pcd


def main():
    parser = argparse.ArgumentParser(description="iPhone Sensor Point Cloud Viewer")
    parser.add_argument("host", nargs="?", default="localhost",
                        help="iPhone IP address (default: localhost for USB)")
    parser.add_argument("--port", "-p", type=int, default=8888,
                        help="Server port (default: 8888)")
    parser.add_argument("--usb", action="store_true",
                        help="Use USB mode (auto-manages iproxy)")
    args = parser.parse_args()

    mode_str = "USB" if args.usb else f"{args.host}:{args.port}"
    print(f"Connecting via {mode_str}...")
    client = IPhoneSensorClient(args.host, args.port, usb=args.usb)

    if not client.start():
        print("Failed to connect!")
        sys.exit(1)

    print("Connected! Waiting for first frame...")

    # Wait for first frame
    frame = None
    while frame is None:
        frame = client.wait_for_frame(timeout=1.0)
        if not client.is_connected:
            print("Disconnected!")
            sys.exit(1)

    print(f"Got first frame: depth={frame.depth.shape}, color={frame.color.shape}")

    # Create visualizer
    vis = o3d.visualization.Visualizer()
    vis.create_window("iPhone Sensor Point Cloud", width=1280, height=720)

    # Add initial point cloud
    pcd = frame_to_point_cloud(frame)
    vis.add_geometry(pcd)

    # Set view
    ctr = vis.get_view_control()
    ctr.set_zoom(0.5)

    print("Streaming point cloud. Close window to exit.")

    try:
        while vis.poll_events():
            vis.update_renderer()

            # Get new frame
            new_frame = client.get_frame()
            if new_frame is not None:
                # Update point cloud
                new_pcd = frame_to_point_cloud(new_frame)
                pcd.points = new_pcd.points
                pcd.colors = new_pcd.colors
                vis.update_geometry(pcd)

    except KeyboardInterrupt:
        pass

    client.stop()
    vis.destroy_window()


if __name__ == "__main__":
    main()
