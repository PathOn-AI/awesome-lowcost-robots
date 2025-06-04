# Remote Inference Server Setup Guide

This guide walks you through setting up a remote inference server on high-end GPUs (3090/4090/5090) and connecting to it from your MacBook Pro. 
Similar Implementations 
* from Isaac-GR00T: https://github.com/NVIDIA/Isaac-GR00T/blob/main/scripts/inference_service.py#:20, https://github.com/NVIDIA/Isaac-GR00T/blob/main/gr00t/eval/robot.py
* from OpenPi: https://github.com/Physical-Intelligence/openpi/tree/main/src/openpi

## 1. Eval model in simulation environment
### 1.1. Set Up the WebSocket Server on GPU Machine

**Option A: Direct Setup on 3090/4090/5090**
```bash
python lerobot/inference/websocket_server.py \
    --policy.path=DanqingZ/act_aloha_insertion \
    --output_dir=outputs/eval/act_aloha_insertion/last \
    --env.type=aloha \
    --env.task=AlohaInsertion-v0 \
    --eval.n_episodes=10 \
    --eval.batch_size=10 \
    --policy.device=cuda \
    --policy.use_amp=false
```

**Option B: Alternative Remote Server Setup**
You can alternatively set up the remote server using your preferred configuration.

### 1.2. Set Up Client-Side Code on MacBook Pro

#### Expose Server with ngrok
```bash
ngrok tcp 8765
```

This will provide output similar to:
```
Web Interface: http://127.0.0.1:4040
Forwarding: tcp://6.tcp.us-cal-1.ngrok.io:16363 -> localhost:8765
```

#### Configure Client Connection
Copy and paste the ngrok forwarding URL into your `lerobot_client.py` file to enable the LeRobot client to connect to the remote server.

### 1.3. Use Remote Server Response Instead of Direct Policy Output

Run the evaluation script configured to use the remote server:

```bash
python eval_simulation.py \
    --policy.path=DanqingZ/act_aloha_insertion \
    --output_dir=outputs/eval/act_aloha_insertion/test_local_server_5 \
    --env.type=aloha \
    --env.task=AlohaInsertion-v0 \
    --eval.n_episodes=10 \
    --eval.batch_size=10 \
    --policy.device=cuda \
    --policy.use_amp=false
```

### Notes

- Ensure your GPU machine has the necessary CUDA drivers and PyTorch installation
- Verify that port 8765 is accessible on your GPU machine
- Update the ngrok URL in your client code each time you restart ngrok (URLs change on restart)
- Monitor GPU memory usage during inference to ensure optimal performance


## 2. Eval Model on Robot (so-arm100)

First, copy the config files:
```
cp -r /Users/danqingzhang/lerobot/.cache /Users/danqingzhang/Desktop/learning/awesome-lerobot/inference/
```

### Local Test
```
python adhoc_eval_robot.py
```

## Run Inference on the Server

On the server, run:
```
python websocket_server_robot.py
```

On MacBook, run:
```
python adhoc_eval_robot_server.py
```

TODO: Need to speed up the inference. Use MessagePack instead of JSON + Pickle.