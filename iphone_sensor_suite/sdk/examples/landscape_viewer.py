#!/usr/bin/env python3
"""
Simple OpenCV viewer for iPhone sensor streaming (landscape mode).

Hold the iPhone in landscape-right orientation (home button on the left).
No rotation is applied — the raw ARKit frames are displayed as-is.

Usage:
    python landscape_viewer.py <iphone_ip>          # WiFi mode
    python landscape_viewer.py 192.168.1.100        # WiFi mode
    python landscape_viewer.py --usb                # USB mode

Controls:
    Q: Quit
    S: Save current frame
"""

import sys
import os
import argparse
import cv2
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdk import IPhoneSensorClient


def colorize_depth(depth: np.ndarray, max_depth: float = 5.0) -> np.ndarray:
    """Convert depth to colorized image."""
    depth_normalized = np.clip(depth / max_depth, 0, 1)
    depth_colorized = cv2.applyColorMap(
        (depth_normalized * 255).astype(np.uint8),
        cv2.COLORMAP_JET
    )
    return depth_colorized


def main():
    parser = argparse.ArgumentParser(description="iPhone Sensor Viewer (Landscape)")
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

    print("Connected! Press Q to quit, S to save frame.")

    frame_count = 0
    while True:
        frame = client.wait_for_frame(timeout=1.0)

        if frame is None:
            if not client.is_connected:
                print("Disconnected!")
                break
            continue

        frame_count += 1

        # Colorize depth
        depth_vis = colorize_depth(frame.depth)

        # Resize color to match depth for side-by-side view
        color_resized = cv2.resize(frame.color, (depth_vis.shape[1], depth_vis.shape[0]))

        # Create side-by-side view
        combined = np.hstack([color_resized, depth_vis])

        # Add info text
        info = f"Frame: {frame.frame_id} | FPS: {frame_count} | Depth: {frame.depth.shape}"
        cv2.putText(combined, info, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow("iPhone Sensor Stream (Landscape)", combined)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            # Save frame
            filename = f"frame_{frame.frame_id:06d}"
            cv2.imwrite(f"{filename}_color.jpg", frame.color)
            cv2.imwrite(f"{filename}_depth.png", (frame.depth * 1000).astype(np.uint16))
            np.save(f"{filename}_transform.npy", frame.transform)
            print(f"Saved {filename}_*")

    client.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
