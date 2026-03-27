---
name: "AgileX PiPER"
category: "Robotic Arm"
description: "Lightweight 6-DOF arm weighing ~4 kg with 1.5 kg payload and ±0.1 mm repeatability. Native ROS/ROS2 support and Python API."
link: "https://global.agilex.ai/products/piper"
image: "/robots/piper.jpg"
specs:
  dof: "6"
  weight: "~4 kg"
  payload: "1.5 kg"
  reach: "~500 mm"
  price: "~$1,500"
  controller: "External PC"
  interfaces: "ROS, ROS2, Python API"
  power: "DC 24V"
  repeatability: "±0.1 mm"
  status: "Commercial"
purpose:
  - "Research"
components:
  - name: "Brushless DC Motors"
    type: "Actuators (x6)"
  - name: "Harmonic Reducers"
    type: "Transmission"
  - name: "CAN Bus Interface"
    type: "Communication"
  - name: "Optional Gripper"
    type: "End Effector"
---

## Overview

The AgileX PiPER is a lightweight 6-DOF robotic arm built for research and education. At approximately 4 kg, it offers high precision in a compact form factor.

## Use Cases

- Precision manipulation research
- Mobile manipulation (mountable on mobile bases)
- LeRobot integration for policy learning
