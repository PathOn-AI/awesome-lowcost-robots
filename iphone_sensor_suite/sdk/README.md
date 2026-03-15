# iPhone Sensor SDK - Python Client

Python client for receiving real-time RGBD data from the iPhone sensor iOS app.

## Installation

```bash
cd sdk
pip install -r requirements.txt
```

Or install as package:
```bash
pip install -e .
```

## Quick Start

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

### OpenCV Viewer
```bash
python examples/simple_viewer.py <IPHONE_IP>
```

### Open3D Point Cloud
```bash
python examples/point_cloud.py <IPHONE_IP>
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
