# awesome-lerobot

## 1. Open-Source Hardware

| **Platform** | **Type** | **Description** | **Repository** |
|--------------|----------|-----------------|----------------|
| **SO-100 & SO-101** | Robotic Arms | Standard Open robotic arms | https://github.com/TheRobotStudio/SO-ARM100 |
| **LeKiwi** | Mobile Manipulator | Low-Cost Mobile Manipulator for so-100/101 arm | https://github.com/SIGRobotics-UIUC/LeKiwi |
| **XLeRobot** | Mobile Manipulator | Built on top of LeKiwi | https://github.com/Vector-Wangel/XLeRobot |
| **Bambot** | Mobile Manipulator | Built on top of LeKiwi | https://github.com/timqian/bambot |

## 2. Policy Networks

| **Policy** | **Full Name** | **Description** | **Paper** |
|------------|---------------|-----------------|-----------|
| **ACT** | Action Chunking with Transformers | Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware | https://arxiv.org/abs/2304.13705 |
| **Diffusion Policy** | Diffusion Policy | Visuomotor Policy Learning via Action Diffusion | https://arxiv.org/abs/2303.04137 |
| **TD-MPC** | Temporal Difference Learning for Model Predictive Control | Model Predictive Control with Temporal Difference Learning | https://arxiv.org/abs/2203.04955 |
| **FOWM** | Finetuning Offline World Models | Finetuning Offline World Models in the Real World | https://arxiv.org/abs/2310.16029 |
| **VQ-BeT** | Vector-Quantized Behavior Transformer | Behavior Generation with Latent Actions | https://arxiv.org/abs/2403.03181 |
| **π0** | Pi-Zero | A Vision-Language-Action Flow Model for General Robot Control | https://www.physicalintelligence.company/download/pi0.pdf |


## 3. Teleoperation
* https://github.com/box2ai-robotics/joycon-robotics


## 4. Dataset
* data conversion: https://github.com/Tavish9/any4lerobot


## 5. Use LeRobot in simulated environment
### 5.1 pushT environment
Train from scratch a diffusion policy using data from lerobot/pusht
```
python lerobot/scripts/train.py \
    --output_dir=outputs/train/diffusion_pusht \
    --policy.type=diffusion \
    --dataset.repo_id=lerobot/pusht \
    --seed=100000 \
    --env.type=pusht \
    --batch_size=64 \
    --steps=200000 \
    --eval_freq=25000 \
    --save_freq=25000 \
    --wandb.enable=true
```
evaluate train policy https://huggingface.co/lerobot/diffusion_pusht
```
python lerobot/scripts/eval.py \
    --policy.path=lerobot/diffusion_pusht \
    --env.type=pusht \
    --eval.batch_size=10 \
    --eval.n_episodes=10 \
    --policy.use_amp=false \
    --policy.device=mps
```

### 5.2 aloha environment
```
python lerobot/scripts/train.py \
    --output_dir=outputs/train/act_aloha_insertion \
    --policy.type=act \
    --dataset.repo_id=lerobot/aloha_sim_insertion_human \
    --env.type=aloha \
    --env.task=AlohaInsertion-v0 \
    --policy.device=cuda \
    --wandb.enable=true
```
evaluate train policy: https://huggingface.co/lerobot/act_aloha_sim_insertion_human
```
python lerobot/scripts/eval.py \
    --policy.path=lerobot/act_aloha_sim_insertion_human \
    --output_dir=outputs/eval/act_aloha_insertion/last \
    --env.type=aloha \
    --env.task=AlohaInsertion-v0 \
    --eval.n_episodes=500 \
    --eval.batch_size=50 \
    --policy.device=mps \
    --policy.use_amp=false
```

### 5.3 LIBERO