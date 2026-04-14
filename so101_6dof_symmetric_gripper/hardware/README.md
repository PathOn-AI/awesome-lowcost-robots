# Hardware -- Assembly Guide

## Bill of Materials

### 6DoF Wrist Upgrade BOM

| # | Part | Qty | Source |
|---|------|-----|--------|
| 1 | STS3215 servo | 1 | Purchased |
| 2 | link_pitch | 1 | 3D printed |
| 3 | link_yaw | 1 | 3D printed |

### Symmetric Gripper BOM

| # | Part | Qty | Source |
|---|------|-----|--------|
| 1 | STS3215 servo | 1 | Purchased |
| 2 | frame | 1 | 3D printed |
| 3 | cam | 1 | 3D printed |
| 4 | rack_up | 1 | 3D printed |
| 5 | rack_down | 1 | 3D printed |
| 6 | l_gripper | 1 | 3D printed |
| 7 | r_gripper | 1 | 3D printed |

## 3D Printed Parts

All parts can be printed with standard PLA/PETG filament. STL files are for slicing, STEP files are provided for modification.

### Print Orientation

Orient the parts as shown below for optimal layer strength. Parts are positioned so that load-bearing surfaces have layers running perpendicular to the primary stress direction.

**6DoF Wrist Parts**

<p align="center">
  <img src="Documentation/print_orientation_6dof.png" alt="Print orientation for 6DoF wrist parts" width="600">
</p>

**Symmetric Gripper Parts**

<p align="center">
  <img src="Documentation/print_orientation_gripper.png" alt="Print orientation for symmetric gripper parts" width="600">
</p>

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

### Step 1 -- Attach the Pitch Link to the SO-101 Arm

Mount the `link_pitch` onto the last servo of the SO-101 arm using the servo horn.

<p align="center">
  <img src="Documentation/pitch1.png" alt="Pitch link separated from the arm" width="500">
</p>

Secure the pitch link using the servo screws so it rotates freely on the pitch axis.

<p align="center">
  <img src="Documentation/pitch2.png" alt="Pitch link attached to the arm" width="500">
</p>

### Step 2 -- Install the Yaw Servo

Insert an STS3215 servo into the `link_yaw` mount. The servo should sit flush inside the yaw link.

<p align="center">
  <img src="Documentation/yaw1.png" alt="Yaw link with servo, front view" width="400">
</p>

Secure the STS3215 servo by 2 self tapping screws from the servo pack

<p align="center">
  <img src="Documentation/yaw2.png" alt="Yaw link with servo, side view" width="400">
</p>

### Step 3 -- Attach the Roll Servo

Connect the `link_yaw` assembly with the bottom servo.

<p align="center">
  <img src="Documentation/yaw3.png" alt="Yaw link attached to pitch link" width="400">
</p>

Secure the bottom servo with the 4 self tapping screws.

<p align="center">
  <img src="Documentation/yaw_screw.png" alt="Yaw servo secured with screw" width="400">
</p>

### Step 4 -- Fix yaw to pitch

The completed wrist assembly with both pitch and yaw links attached to the SO-101 arm.

<p align="center">
  <img src="Documentation/both1.png" alt="Completed 6DoF wrist, angled view" width="400">
</p>

Attach the Yaw servo horn to the top face of the pitch link and secure it with screws

<p align="center">
  <img src="Documentation/both2.png" alt="Completed 6DoF wrist, front view" width="400">
</p>

### Step 5 -- Prepare the Gripper Frame

Take the gripper `frame` and position it for mounting onto the yaw link.

<p align="center">
  <img src="Documentation/g1.png" alt="Gripper frame approaching the wrist" width="500">
</p>

Place the Frame link onto the bottom servo of the Yaw link servo and secure it with the servo screws.

<p align="center">
  <img src="Documentation/g2.png" alt="Gripper frame with servo mounted, top view" width="400">
</p>

### Step 6 -- Mount the Gripper Servo

***Connect the Servo wire to the STS3215 servo*** and then Insert it into the gripper `frame`. The servo sits in the top cavity of the frame.

<p align="center">
  <img src="Documentation/g4.png" alt="Gripper frame and wrist, exploded view" width="500">
</p>

Secure it with two self tapping screws on the top

<p align="center">
  <img src="Documentation/g5.png" alt="Gripper servo seated in frame, front view" width="400">
</p>

Secure it with two self tapping screws on the back side above the servo flange cavity

<p align="center">
  <img src="Documentation/g6.png" alt="Gripper frame with servo and cam, rear view" width="400">
</p>

### Step 7 -- Install the Cam and Racks

Attach the `cam` gear to the servo output shaft inside the frame. and secure it with screws

<p align="center">
  <img src="Documentation/g7.png" alt="Cam gear visible through the frame" width="400">
</p>

Then slide `rack_up` and `rack_down` into the frame channels so the cam teeth mesh with both racks.

<p align="center">
  <img src="Documentation/g8.png" alt="Racks inserted into the frame channels" width="400">
</p>

### Step 8 -- Attach the Gripper Fingers

Attach `l_gripper` and `r_gripper` to the ends of the upper and lower racks respectively.

<p align="center">
  <img src="Documentation/g9.png" alt="Gripper fingers attached to racks" width="500">
</p>

### Step 9 -- Completed Assembly

The fully assembled SO-101 6DoF arm with symmetric gripper.

<p align="center">
  <img src="Documentation/g10.png" alt="Fully assembled 6DoF arm with symmetric gripper" width="600">
</p>
