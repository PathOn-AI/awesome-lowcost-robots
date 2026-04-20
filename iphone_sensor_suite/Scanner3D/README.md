# Scanner3D

Offline 3D scanning app for iPhone. Capture depth, RGB, camera pose, and confidence maps using the LiDAR sensor, then export scans and fuse them into 3D point clouds in marker frame.

## Demo

https://www.loom.com/share/b4a0ab5e65ce4debafca076c697b67ae

*Visualization of the fused point cloud in marker frame.*

## iOS App

Download the free iOS scanning app:

[![Download on the App Store](https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg)](https://apps.apple.com/app/id6762235906)

## Features

- Real-time depth heatmap preview at 60fps
- Capture depth (256x192), RGB (1920x1440), intrinsics, camera pose, and confidence maps
- Save and manage multiple scan sessions in the Library
- Export scans as zip files via the iOS Files app
- ArUco marker generation for camera-to-robot calibration
- Mesh scanning mode with ARKit scene reconstruction

## Requirements

- iPhone 12 Pro or newer (with LiDAR sensor)
- iOS 17.5+
- Python 3.11 (for the processing pipeline)

## How It Works

1. **Scan** -- Point your iPhone at an object with an ArUco marker visible, tap "Start Scan", then tap "Capture" for each frame
2. **Save** -- Save the scan session to the Library
3. **Export** -- Export as a zip file and transfer to your computer via Files app
4. **Process** -- Run the 3-step pipeline below to get a fused point cloud in marker frame

## Exported Data Format

Each scan session is exported as a zip containing `capture_NNNNNN/` folders. Each capture folder contains:

| File | Description |
|------|-------------|
| `pointcloud.ply` | Point cloud in camera optical frame (confidence-filtered) |
| `depth.png` | 16-bit grayscale depth in millimeters |
| `rgb.png` | Color image |
| `camera_info.json` | Camera intrinsics (ROS CameraInfo format) |
| `T_world_camera.txt` | 4x4 ARKit camera-to-world transform |
| `meta.json` | Capture metadata (timestamps, resolutions) |
| `depth_vis.png` | Depth visualization (red=close, blue=far) |

## Pipeline

3-step processing pipeline to go from raw captures to a fused point cloud in marker frame.

### Setup

Requires Python 3.11 (Open3D does not support 3.13 yet).

```bash
cd pipeline
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
cd pipeline
source venv/bin/activate

# Step 1: Calibrate — find ArUco marker pose from the best capture
python3 calibrate_3d.py --scan-dir ../example_scan/2026-03-23--19-45-00 --best

# Step 2: TSDF fusion — fuse all captures into a single mesh
python3 fuse_pointclouds.py --data-dir ../example_scan/2026-03-23--19-45-00 --mode tsdf --voxel-size 0.002 --icp

# Step 3: Transform — convert fused mesh from world frame to marker frame
python3 transform_pointcloud.py \
    --input ../example_scan/2026-03-23--19-45-00/fused.ply \
    --world-marker ../example_scan/2026-03-23--19-45-00/T_world_marker_3d.txt \
    --output ../example_scan/2026-03-23--19-45-00/fused_marker.ply
```

### Output

```
example_scan/2026-03-23--19-45-00/
├── capture_000000/              # Raw captures (input)
├── capture_000001/
├── ...
├── T_world_marker_3d.txt        # Step 1: marker pose (from best capture)
├── fused.ply                    # Step 2: fused mesh in ARKit world frame
└── fused_marker.ply             # Step 3: fused mesh in marker frame
```

### Pipeline Details

| Step | Script | What it does |
|------|--------|-------------|
| 1 | `calibrate_3d.py --best` | Detects ArUco marker in RGB, looks up LiDAR depth at corners, selects the capture with the largest marker (closest to camera = most accurate depth) |
| 2 | `fuse_pointclouds.py --mode tsdf` | TSDF volumetric fusion using ARKit camera poses. ICP refines pose alignment between captures. Outputs a clean triangle mesh |
| 3 | `transform_pointcloud.py` | Transforms the fused mesh from ARKit world frame to marker frame via `inv(T_world_marker)` |

### Key Options

| Option | Description |
|--------|-------------|
| `--scan-dir` / `--data-dir` | Directory containing `capture_*` folders (required) |
| `--best` | Use the single best capture for calibration (recommended) |
| `--mode` | `ply`, `depth`, or `tsdf` (default: `ply`) |
| `--voxel-size` | Voxel size in meters for TSDF (default: 0.005, use 0.002 for fine detail) |
| `--icp` | Enable ICP pose refinement before TSDF integration |
| `--bounds` | Workspace bounds filter: `x_min,x_max,y_min,y_max,z_min,z_max` |
| `--output` | Output PLY path |
