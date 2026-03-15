# ros2_driver - ROS2 Driver for iPhone LiDAR Streaming

ROS2 Jazzy package that receives RGBD data from the iPhone sensor iOS app and publishes standard ROS2 topics. Drop-in compatible with robotics pipelines expecting RealSense-style topics.

## Prerequisites

- ROS2 Jazzy
- iPhone sensor iOS app running on an iPhone Pro (12 Pro or newer)
- iPhone and host machine on the same WiFi network

## Setup

```bash
# 1. Create virtual environment (inherits ROS2 system packages)
cd ros2-driver
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install "numpy<2" -e ../sdk

# 2. Build with colcon
source /opt/ros/jazzy/setup.bash
cd <project_root>  # parent directory containing ros2-driver/
colcon build --packages-select ros2_driver --symlink-install
```

Note: `numpy<2` is required for compatibility with ROS2 Jazzy's cv_bridge.

## Running

```bash
cd ros2-driver
pip install -e .
```

```bash
# Terminal 1: Start the node
export ROS_DOMAIN_ID=50
source /opt/ros/jazzy/setup.bash
source ros2-driver/venv/bin/activate
python3 -m ros2_driver.iphone_sensor_node --ros-args -p host:=<IPHONE_IP>

# Terminal 2: Verify topics
export ROS_DOMAIN_ID=50
source /opt/ros/jazzy/setup.bash
ros2 topic list

# Terminal 3: Visualize in RViz2
export ROS_DOMAIN_ID=50
export DISPLAY=:5
source /opt/ros/jazzy/setup.bash
rviz2 -d ros2-driver/rviz/iphone_sensor.rviz
```

Replace `<IPHONE_IP>` with the IP shown on the iPhone sensor app.

### Using the launch file

```bash
export ROS_DOMAIN_ID=50
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch ros2_driver iphone_sensor.launch.py host:=<IPHONE_IP>
```

## Published Topics

| Topic | Type | Rate | Description |
|-------|------|------|-------------|
| `color/image_raw` | `sensor_msgs/Image` | 30fps | RGB image (bgr8, 1920x1440) |
| `color/camera_info` | `sensor_msgs/CameraInfo` | 30fps | RGB intrinsics from ARKit |
| `depth/image_rect_raw` | `sensor_msgs/Image` | 30fps | Depth (32FC1 meters, 256x192) |
| `depth/camera_info` | `sensor_msgs/CameraInfo` | 30fps | Depth intrinsics (scaled from RGB) |
| `aligned_depth_to_color/image_raw` | `sensor_msgs/Image` | ~6fps | Depth upscaled to RGB resolution |
| `aligned_depth_to_color/camera_info` | `sensor_msgs/CameraInfo` | ~6fps | Same as RGB intrinsics |
| `depth/color/points` | `sensor_msgs/PointCloud2` | ~6fps | Colored point cloud |
| `confidence/image_raw` | `sensor_msgs/Image` | 30fps | Confidence map (mono8: 0=low, 1=med, 2=high) |
| `imu` | `sensor_msgs/Imu` | 30fps | Accelerometer + gyroscope |
| `scan` | `sensor_msgs/LaserScan` | 30fps | 2D laser scan from middle row of depth |

Point cloud and aligned depth publish at ~6fps (every 5th frame) to avoid blocking the stream.

QoS: All topics use **BEST_EFFORT** reliability, **VOLATILE** durability, **KEEP_LAST(1)**. When subscribing (e.g., in RViz2), set reliability to "Best Effort" to match.

## Depth-RGB Alignment

Unlike RealSense cameras (which have physically separate depth and RGB sensors requiring extrinsic calibration), **ARKit delivers depth already aligned to the RGB camera frame**. The LiDAR depth map shares the same optical center and viewpoint as the RGB image — there is no extrinsic offset between them.

This means:

- **Single intrinsics matrix**: ARKit provides one set of intrinsics at RGB resolution (1920x1440). Depth intrinsics are the same values scaled to 256x192.
- **Single camera pose**: The 4x4 transform from ARKit is one camera-to-world matrix — no separate depth vs. RGB poses.
- **Aligned depth is just upscaling**: The `aligned_depth_to_color` topic resizes 256x192 depth to 1920x1440 with nearest-neighbor interpolation. No reprojection or registration is needed.
- **Zero-translation optical frames**: Both `camera_color_optical_frame` and `camera_depth_optical_frame` are at the same position relative to `camera_link` (rotation-only static TF to convert to optical convention).

## TF Frames

```
world
  └── camera_link                          (dynamic, from ARKit pose)
        ├── camera_color_optical_frame     (static)
        └── camera_depth_optical_frame     (static)
```

- `world`: The iPhone's position when ARKit initialized (i.e. when streaming started). This is an arbitrary origin — it could be your desk, your hand, etc. Restarting the app resets it. At the first frame, `world` and `camera_link` are essentially at the same position.
- `camera_link`: The iPhone's current position/orientation, updated every frame (~30Hz) via ARKit's visual-inertial odometry. As you move the phone, `camera_link` moves relative to `world`.
- `world -> camera_link`: ARKit Y-up converted to ROS Z-up.
- `camera_link -> *_optical_frame`: Standard ROS optical convention (X-right, Y-down, Z-forward).

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | `192.168.1.100` | iPhone IP address |
| `port` | `8888` | TCP port |
| `camera_name` | `camera` | Prefix for topics and TF frames |
| `publish_pointcloud` | `true` | Enable PointCloud2 topic |
| `publish_aligned_depth` | `true` | Enable aligned depth to color topic |
| `publish_confidence` | `true` | Enable confidence map topic |
| `publish_imu` | `true` | Enable IMU topic |
| `publish_scan` | `true` | Enable LaserScan topic |
| `depth_range_min` | `0.1` | Min depth for point cloud (meters) |
| `depth_range_max` | `5.0` | Max depth for point cloud (meters) |
| `min_confidence` | `1` | Min ARKit confidence for point cloud (0=low, 1=medium, 2=high) |

## Troubleshooting

**"Connection refused"**: The iPhone sensor app isn't running or the IP has changed. Check the app screen for the current IP.

**Connection drops after ~20s**: If you have `publish_pointcloud` and `publish_aligned_depth` both enabled, the processing overhead can cause TCP buffer overflows. They are throttled to ~6fps by default, but you can disable them:
```bash
python3 -m ros2_driver.iphone_sensor_node --ros-args \
  -p host:=<IP> -p publish_pointcloud:=false -p publish_aligned_depth:=false
```

**"No Image" in RViz2**: Change the display's Reliability Policy to "Best Effort" in the RViz2 properties panel.

**numpy version error with cv_bridge**: Make sure you installed `numpy<2` in the venv. ROS2 Jazzy's cv_bridge is compiled against numpy 1.x.
