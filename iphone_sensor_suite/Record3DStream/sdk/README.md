# iPhone Sensor SDK - Python Client

Python client for receiving real-time RGBD data from the iPhone sensor iOS app.

## Installation

```bash
cd sdk
python3 -m venv venv
source venv/bin/activate

# Core SDK only
pip install -e .

# With Open3D for the point cloud example
pip install -e ".[visualization]"
```

## Quick Start

Make sure the iOS streaming app is running on your iPhone — the app screen shows the IP you'll pass below.

```python
from sdk import IPhoneSensorClient

# Connect to iPhone (use IP shown in iOS app)
client = IPhoneSensorClient('192.168.1.100', port=8888)
client.start()

while True:
    frame = client.wait_for_frame()
    if frame:
        print(f"Frame {frame.frame_id}")
        print(f"  Depth: {frame.depth.shape}")   # (192, 256) float32 meters
        print(f"  Color: {frame.color.shape}")   # (H, W, 3) uint8 BGR
        print(f"  Pose: {frame.transform.shape}") # (4, 4) camera transform

client.stop()
```

## Examples

```bash
# RGB + depth side-by-side (OpenCV)
python examples/simple_viewer.py <IPHONE_IP>

# Same viewer rotated for landscape orientation
python examples/landscape_viewer.py <IPHONE_IP>

# Live colored point cloud (requires the [visualization] extra)
python examples/point_cloud.py <IPHONE_IP>

# Protocol v2 fields: confidence map + IMU
python examples/test_v2.py <IPHONE_IP>
```

## API Reference

### IPhoneSensorClient

```python
client = IPhoneSensorClient(host, port=8888, timeout=5.0)
client.start()           # Connect to server
client.stop()            # Disconnect
client.wait_for_frame()  # Block until frame received
client.get_frame()       # Non-blocking, get latest frame
client.is_connected      # Check connection status
```

### Frame

```python
frame.frame_id      # int: Sequential frame number
frame.timestamp     # float: Seconds since stream start
frame.depth         # np.ndarray: (H, W) float32 depth in meters
frame.color         # np.ndarray: (H, W, 3) uint8 BGR image
frame.intrinsics    # Intrinsics: Camera parameters
frame.transform     # np.ndarray: (4, 4) camera pose matrix
```

### Intrinsics

```python
intr = frame.intrinsics
intr.fx, intr.fy    # Focal length
intr.ppx, intr.ppy  # Principal point
intr.width, intr.height  # Depth image dimensions
```

## Protocol

The streaming protocol uses TCP with binary packets:
- Header (32 bytes): magic, version, frame_id, timestamp, dimensions, sizes
- Intrinsics (36 bytes): 3x3 float32 camera matrix
- Transform (64 bytes): 4x4 float32 pose matrix
- Depth data: float32 array (meters)
- RGB data: JPEG compressed
