---
name: "LeKiwi"
category: "Mobile Manipulator"
description: "Low-cost holonomic drive robot with manipulation capabilities for embodied AI experiments."
link: "https://github.com/SIGRobotics-UIUC/LeKiwi"
image: "/robots/lekiwi.jpg"
specs:
  dof: "3 (base) + 6 (arm)"
  weight: "~1.5 kg"
  payload: "~100 g (arm)"
  price: "~$500"
  controller: "Raspberry Pi"
  interfaces: "Python, LeRobot"
  power: "Li-Ion Battery"
  status: "Open Source / DIY"
purpose:
  - "Research"
  - "Hobby"
components:
  - name: "STS3215 Servos"
    type: "Bus Servos (x9)"
  - name: "3D-Printed Frame"
    type: "PLA / PETG"
  - name: "Kiwi Drive Wheels"
    type: "Omnidirectional (x3)"
  - name: "Raspberry Pi"
    type: "Onboard Compute"
  - name: "USB Camera"
    type: "Vision"
---

## Overview

LeKiwi is a low-cost mobile manipulator with a holonomic (kiwi) drive base, developed for embodied AI experiments. It combines omnidirectional movement with a mounted SO-ARM100 style arm for manipulation.

## Use Cases

- Embodied AI and reinforcement learning
- Mobile manipulation with imitation learning
- Navigation + manipulation combined tasks
- Low-cost research platform for labs and universities
