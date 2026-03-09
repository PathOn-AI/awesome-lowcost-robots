# iPhone Sensor Suite

Use an iPhone as a full sensor suite for low-cost robot manipulation and autonomous navigation.

Repository: https://github.com/PathOn-AI/opensource_record3d

## Overview

The iPhone LiDAR (dToF flash sensor) + RGB camera + IMU replaces multiple traditional robot sensors:

| iPhone Sensor | Replaces | Output |
|---|---|---|
| LiDAR + RGB + ML | Depth camera (RealSense) | PointCloud2, depth image |
| LiDAR (middle row) | 2D LiDAR (RPLIDAR, Hokuyo) | LaserScan |
| RGB camera | USB camera | Color image |
| IMU (accelerometer + gyroscope) | External IMU | IMU data |

## Architecture

```
iPhone (iOS App)                          PC / Robot (ROS2)
┌────────────────────┐                   ┌──────────────────────────┐
│ ARKit captures:    │   WiFi / USB      │ Python/C++ SDK           │
│  - RGB image       │ ──────────────→   │  - Decode stream         │
│  - LiDAR depth     │   TCP stream      │                          │
│  - IMU data        │                   │ ROS2 Driver              │
│  - Camera params   │                   │  - PointCloud2           │
│  - Camera pose     │                   │  - LaserScan             │
│  - Confidence map  │                   │  - RGB + Depth images    │
└────────────────────┘                   │  - CameraInfo            │
                                         │  - IMU                   │
                                         │  - TF tree               │
                                         │                          │
                                         │ Calibration              │
                                         │  - ArUco marker pose     │
                                         │  - base → camera_link TF │
                                         └──────────────────────────┘
```

## Components

| Component | Description | Path |
|---|---|---|
| **iOS App** | Swift/ARKit app, captures RGBD + IMU + camera params, streams over WiFi/USB | `ios-app/` |
| **SDK** | Python/C++ client to receive and decode the stream (standalone, no ROS2 needed) | `sdk/` |
| **ROS2 Driver** | ROS2 node publishing topics, TF tree, point cloud, LaserScan | `ros2-driver/` |
| **Calibration** | ArUco marker-based camera-to-robot calibration (`base → camera_link`) | `calibration/` |

## How iPhone LiDAR Works

The iPhone LiDAR is a 3D dToF (direct Time-of-Flight) flash sensor. ARKit processes the raw data through three internal pipelines:

| Pipeline | Input | Output | Persistence | We Use It |
|---|---|---|---|---|
| **Depth** | LiDAR + RGB + ML | `sceneDepth` (256x192 depth image) | Per-frame | Yes |
| **Scene Mesh** | Many LiDAR frames accumulated | `ARMeshAnchor` (triangle mesh + classification) | Persistent | Not yet |
| **Body Tracking** | RGB + Neural Engine ML | `ARBodyAnchor` (91 skeleton joints) | Per-frame | Not yet |

Currently we only use Pipeline 1 (depth). The depth image is unprojected to a point cloud (all pixels) and sliced into a LaserScan (middle row).

## Frame Conventions

| Frame | X | Y | Z | Convention |
|---|---|---|---|---|
| `base` | forward | left | up | body |
| `camera_link` | forward | left | up | body |
| `camera_laser_frame` | forward | left | up | body (identity from camera_link) |
| `aruco_tag_frame` | forward | left | up | body (if marker placed correctly) |
| `camera_color_optical_frame` | right | down | forward | optical |

### Static transforms from camera_link

| Transform | Rotation | Translation |
|---|---|---|
| `camera_link → optical frames` | `q = (x=0.5, y=-0.5, z=0.5, w=-0.5)` | none |
| `camera_link → laser_frame` | identity | none |

## Quick Start

### Prerequisites

- iPhone with LiDAR (iPhone 12 Pro or later)
- Python 3.8+
- ROS2 Humble (for ROS2 driver)

### 1. Install the iOS App

Build and install the iOS app on your iPhone via Xcode.

### 2. Stream with Python SDK

```bash
# WiFi mode
python -m sdk.examples.simple_viewer <iphone_ip>

# USB mode (requires libimobiledevice)
python -m sdk.examples.simple_viewer --usb
```

### 3. Run ROS2 Driver

```bash
# WiFi
ros2 run ros2_driver record3d_node --ros-args -p host:=<iphone_ip>

# USB
ros2 run ros2_driver record3d_node --ros-args -p usb:=true
```

### 4. Calibrate with ArUco Marker

Print ArUco marker (DICT_6X6_250, ID 3, 3.8cm) and place it with axes aligned to robot base frame.

```bash
python -m calibration.camera_calibration --usb
```
