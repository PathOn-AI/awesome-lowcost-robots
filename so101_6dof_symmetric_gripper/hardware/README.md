# Hardware -- Assembly Guide

## 3D Printed Parts

All parts can be printed with standard PLA/PETG filament. STL files are for slicing, STEP files are provided for modification.

### 6DoF Wrist Upgrade

| Part | STL | STEP |
|------|-----|------|
| Wrist Pitch Link | [link_pitch.stl](3d_printed_parts/6dof/stl/link_pitch.stl) | [link_pitch.step](3d_printed_parts/6dof/step/link_pitch.step) |
| Wrist Yaw Link | [link_yaw.stl](3d_printed_parts/6dof/stl/link_yaw.stl) | [link_yaw.step](3d_printed_parts/6dof/step/link_yaw.step) |

### Symmetric Gripper

| Part | STL | STEP |
|------|-----|------|
| Frame | [frame.stl](3d_printed_parts/symmetric_gripper/stl/frame.stl) | -- |
| Cam | [cam.stl](3d_printed_parts/symmetric_gripper/stl/cam.stl) | -- |
| Rack (upper) | [rack_up.stl](3d_printed_parts/symmetric_gripper/stl/rack_up.stl) | -- |
| Rack (lower) | [rack_down.stl](3d_printed_parts/symmetric_gripper/stl/rack_down.stl) | -- |
| Left Finger | [l_gripper.stl](3d_printed_parts/symmetric_gripper/stl/l_gripper.stl) | -- |
| Right Finger | [r_gripper.stl](3d_printed_parts/symmetric_gripper/stl/r_gripper.stl) | -- |
| Full Assembly | -- | [Parallel_gripper_assembly.step](3d_printed_parts/symmetric_gripper/step/Parallel_gripper_assembly.step) |

## Assembly

### Wrist Upgrade

1. Remove the original SO-101 wrist assembly
2. Attach the wrist pitch link with a servo
3. Attach the wrist yaw link on top of the pitch link with a servo

### Symmetric Gripper

1. Insert the cam into the frame
2. Slide rack_up and rack_down into the frame channels
3. Attach l_gripper and r_gripper to the respective racks
4. Mount the assembled gripper onto the wrist yaw link

> Assembly video coming soon.
