---
name: "SO-ARM101"
category: "Robotic Arm"
description: "Standard Open Arm 101 — enhanced version with improved capabilities for robotic manipulation research."
link: "https://github.com/TheRobotStudio/SO-ARM100"
image: "/robots/soarm101.jpg"
specs:
  dof: "6"
  weight: "~0.5 kg"
  payload: "~100 g"
  reach: "~300 mm"
  price: "~$200"
  controller: "Raspberry Pi / PC"
  interfaces: "Python, LeRobot"
  power: "DC 7.4V"
  status: "Open Source / DIY"
purpose:
  - "Research"
  - "Education"
components:
  - name: "STS3215 Servos"
    type: "Bus Servos (x6)"
  - name: "3D-Printed Frame"
    type: "PLA / PETG"
  - name: "Raspberry Pi 4/5"
    type: "Compute (optional)"
  - name: "USB Camera"
    type: "Vision"
---

## Overview

The SO-ARM101 is an enhanced version of the Standard Open Arm 100, an open-source robotic arm designed for accessible manipulation research and education. It is one of the most popular platforms in the LeRobot ecosystem.

## Use Cases

- Imitation learning and teleoperation research
- Tabletop manipulation tasks
- Education and prototyping
- Policy training with LeRobot
