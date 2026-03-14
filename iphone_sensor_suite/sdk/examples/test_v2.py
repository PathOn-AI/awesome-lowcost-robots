#!/usr/bin/env python3
"""Test Protocol v2 features: confidence map, IMU data, and helper methods."""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk import IPhoneSensorClient


def main():
    parser = argparse.ArgumentParser(description="Test Protocol v2 data")
    parser.add_argument("host", nargs="?", default="localhost", help="iPhone IP address")
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--usb", action="store_true", help="Use USB mode via iproxy")
    args = parser.parse_args()

    client = IPhoneSensorClient(args.host, args.port, usb=args.usb)
    if not client.start():
        print("Failed to connect")
        return

    try:
        print("Waiting for frames (Ctrl+C to stop)...\n")
        for i in range(10):
            frame = client.wait_for_frame(timeout=3.0)
            if frame is None:
                print("Timeout waiting for frame")
                continue

            print(f"--- Frame {frame.frame_id} (t={frame.timestamp:.3f}s) ---")
            print(f"  Depth:  {frame.depth.shape} {frame.depth.dtype}, range=[{frame.depth.min():.3f}, {frame.depth.max():.3f}]m")
            print(f"  Color:  {frame.color.shape} {frame.color.dtype}")

            # Intrinsics
            intr = frame.intrinsics
            print(f"  Intrinsics (RGB): {intr.width}x{intr.height}, fx={intr.fx:.1f}, fy={intr.fy:.1f}, ppx={intr.ppx:.1f}, ppy={intr.ppy:.1f}")

            depth_intr = frame.get_depth_intrinsics()
            print(f"  Intrinsics (depth): {depth_intr.width}x{depth_intr.height}, fx={depth_intr.fx:.1f}, fy={depth_intr.fy:.1f}")

            # Transform
            pos = frame.transform[:3, 3]
            print(f"  Pose: x={pos[0]:.3f}, y={pos[1]:.3f}, z={pos[2]:.3f}")

            # Confidence (v2)
            if frame.confidence is not None:
                c = frame.confidence
                print(f"  Confidence: {c.shape} {c.dtype}, values={{low={int((c==0).sum())}, med={int((c==1).sum())}, high={int((c==2).sum())}}}")
            else:
                print("  Confidence: None (v1 protocol)")

            # IMU (v2)
            if frame.imu is not None:
                a = frame.imu.accel
                g = frame.imu.gyro
                print(f"  IMU accel: [{a[0]:.3f}, {a[1]:.3f}, {a[2]:.3f}] m/s²")
                print(f"  IMU gyro:  [{g[0]:.3f}, {g[1]:.3f}, {g[2]:.3f}] rad/s")
                print(f"  IMU time:  {frame.imu.timestamp:.6f}s")
            else:
                print("  IMU: None (v1 protocol)")

            # Helper methods
            depth_mm = frame.get_depth_mm()
            print(f"  Depth (mm): {depth_mm.shape} {depth_mm.dtype}, range=[{depth_mm.min()}, {depth_mm.max()}]")

            aligned = frame.get_aligned_depth()
            print(f"  Aligned depth: {aligned.shape} (upscaled to RGB res)")

            print()

    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        client.stop()


if __name__ == "__main__":
    main()
