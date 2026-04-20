# iPhone Sensor Suite

[![discord-badge](https://dcbadge.limes.pink/api/server/xukJ3nh9wC)](https://discord.gg/xukJ3nh9wC)
[![followers](https://custom-icon-badges.demolab.com/github/followers/PathOn-AI?color=236ad3&labelColor=1155ba&style=for-the-badge&logo=person-add&label=Follow&logoColor=white)](https://github.com/PathOn-AI?tab=followers)
[![stars](https://custom-icon-badges.demolab.com/github/stars/PathOn-AI/pathon_opensource?color=55960c&style=for-the-badge&labelColor=488207&logo=star)](https://github.com/PathOn-AI/pathon_opensource/stargazers)

Open-source iPhone LiDAR tools for robotics. Two iOS apps with Python tooling for real-time streaming and offline 3D scanning.

## Apps

| App | Description | App Store |
|-----|-------------|-----------|
| [Record3DStream](Record3DStream/) | Real-time LiDAR RGBD streaming to Python/ROS2 over WiFi or USB | [![Download](https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg)](https://apps.apple.com/app/id6761314229) |
| [Scanner3D](Scanner3D/) | Offline 3D scanning with point cloud capture and fusion | [![Download](https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg)](https://apps.apple.com/app/id6762235906) |

## Project Structure

```
iphone_sensor_suite/
├── Record3DStream/             # Real-time LiDAR RGBD streaming
│   ├── sdk/                    # Python client library
│   ├── ros2-driver/            # ROS2 Jazzy package
│   └── calibration/            # ArUco-based camera-to-robot calibration
├── Scanner3D/                  # Offline 3D scanning & point cloud fusion
└── images/                     # Demo images
```

## Prerequisites

- **iPhone**: iPhone 12 Pro or newer (with LiDAR)
- **Python**: 3.10+ (for Python tools)
- **ROS2**: Jazzy on Ubuntu (for ROS2 streaming, Record3DStream only)

## Overview

The iPhone LiDAR (dToF flash sensor) + RGB camera + IMU replaces multiple traditional robot sensors:

| iPhone Sensor | Replaces | Output |
|---|---|---|
| LiDAR + RGB + ML | Depth camera (RealSense) | PointCloud2, depth image |
| LiDAR (middle row) | 2D LiDAR (RPLIDAR, Hokuyo) | LaserScan |
| RGB camera | USB camera | Color image |
| IMU (accelerometer + gyroscope) | External IMU | IMU data |

See each app's README for detailed setup and usage instructions.
