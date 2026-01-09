# awesome-lerobot

> 🚀 **Note:** Major modifications to this repository are planned for January 2026, developed by the PathOnAI open source team. 🛠️

Step-by-step tutorial at https://learn-robotics.pathon.ai/

## Tutorials:
* **General Introduction to SO-ARM100 and LeRobot**: https://learn-robotics.pathon.ai/blog/soarm100
* **Using LeRobot in Simulation Environment**: https://learn-robotics.pathon.ai/blog/simulation
* **Control the Open-Source Robot Arm with ACT (Action Chunking with Transformers) Using LeRobot**: https://learn-robotics.pathon.ai/blog/lerobot_act
* **Control the Open-Source Robot Arm with Pi0 Using LeRobot**: https://learn-robotics.pathon.ai/blog/lerobot_pi0

## 1. Open-Source Hardware

| **Platform** | **Type** | **Description** | **Repository** |
|--------------|----------|-----------------|----------------|
| **SO-100 & SO-101** | Robotic Arms | Standard Open robotic arms | https://github.com/TheRobotStudio/SO-ARM100 |
| **LeKiwi** | Mobile Manipulator | Low-Cost Mobile Manipulator for so-100/101 arm | https://github.com/SIGRobotics-UIUC/LeKiwi |
| **XLeRobot** | Mobile Manipulator | Built on top of LeKiwi | https://github.com/Vector-Wangel/XLeRobot |
| **Bambot** | Mobile Manipulator | Built on top of LeKiwi | https://github.com/timqian/bambot |

## 2. Policy Networks

### 2.1 Supported model types in LeRobot

| **Policy** | **Full Name** | **Description** | **Paper** |
|------------|---------------|-----------------|-----------|
| **ACT** | Action Chunking with Transformers | Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware | https://arxiv.org/abs/2304.13705 |
| **Diffusion Policy** | Diffusion Policy | Visuomotor Policy Learning via Action Diffusion | https://arxiv.org/abs/2303.04137 |
| **TD-MPC** | Temporal Difference Learning for Model Predictive Control | Model Predictive Control with Temporal Difference Learning | https://arxiv.org/abs/2203.04955 |
| **FOWM** | Finetuning Offline World Models | Finetuning Offline World Models in the Real World | https://arxiv.org/abs/2310.16029 |
| **VQ-BeT** | Vector-Quantized Behavior Transformer | Behavior Generation with Latent Actions | https://arxiv.org/abs/2403.03181 |
| **π0** | Pi-Zero | A Vision-Language-Action Flow Model for General Robot Control | https://www.physicalintelligence.company/download/pi0.pdf |

### 2.2 VLA
https://github.com/DelinQu/awesome-vision-language-action-model

## 3. Data Collection & Teleoperation
### 3.1 Teleoperation
There are different ways to teleoperate the follower arm
* in lerobot package, the official way is to use a leader arm to control the follower arm
* there are other ways to control the follower arm, like
    * using joycon: https://github.com/box2ai-robotics/joycon-robotics
    * using VR like meta quest 3: https://github.com/DipFlip/telegrip


### 3.2 Dataset
* data conversion: https://github.com/Tavish9/any4lerobot
* data explorer
* data operation
    * data set cleaning
    * data manipulation
    * delete episode, combine dataset

## 4. Simulation
* sim2real: https://github.com/StoneT2000/lerobot-sim2real
* digital twin: https://github.com/LiZhYun/BiLerobot
* isaac lab
    * https://www.youtube.com/live/z7KdHGkUTNE
    * https://medium.com/@kabilankb2003/setting-up-lerobot-using-api-standalone-method-in-nvidia-isaac-sim-f2b57164b0f2
    * https://medium.com/@kabilankb2003/training-so-100-robot-for-cube-lifting-in-isaac-lab-from-simulation-to-intelligent-control-with-9e81f94c6d6e
