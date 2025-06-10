# LeRobot Training on Modal

A solution for robotics enthusiasts who need more computing power for LeRobot model training, particularly for finetuning large models like Pi0.

## 1. Background

Many robotics enthusiasts like those in the LeRobot discord channel lack access to sufficient computing resources for training large models. While a local RTX 3090 GPU works well for smaller models like ACT and diffusion models (with hundreds of millions of parameters), it struggles with Pi0 finetuning due to:

- Frequent out-of-memory (OOM) errors
- Forced batch size of 1, leading to very slow training
- Insufficient VRAM for larger model architectures

This repository provides a Modal-based solution that leverages serverless H100 GPUs for efficient and cost-effective training.

## 2. Choosing the Right Setup for Your Hardware

Different computing setups require different approaches. Use this table to find the best option for your situation:

| **Your Setup**      | **Model Size**                 | **Recommended Platform**  | **Cost**    | **Debugging**            | **Best For**                |
| ------------------- | ------------------------------ | ------------------------- | ----------- | ------------------------ | --------------------------- |
| **RTX 3090 / 4090** | ACT, Diffusion (<100M params)  | Local machine             | Free        | Easy (local / SSH)       | Learning, small experiments |
| **RTX 3090 / 4090** | Pi0, large models (1B+ params) | Modal (H100)              | \~\$1/run   | Hard (serverless)        | Production training         |
| **No GPU**          | Small and large models         | Colab / Lambda Labs / AWS | Free / Paid | Medium (notebooks / SSH) | Getting started             |

## 3. Prerequisites

**Important**: Ensure your LeRobot code is already debugged and working locally before using Modal. Since Modal is a serverless platform without SSH access, debugging is challenging.

**Debugging Recommendations by Setup:**
- **Have local GPU**: Debug locally first, then move to Modal for larger models
- **No local GPU**: Use Google Colab A100 for debugging, then Modal for production
- **Mac users**: Use CPU debugging locally, then cloud training
- **Beginners**: Start with Google Colab free tier before investing in cloud resources

## 4. Setup

### 4.1. Install Modal

```bash
pip install modal
```

### 4.2. Authenticate with Modal

```bash
modal setup
```

If the above command doesn't work, try:
```bash
python -m modal setup
```

### 4.3. Configure Secrets

Set up your API keys and tokens as Modal secrets:

```bash
# Weights & Biases API key
modal secret create wandb-secret WANDB_API_KEY=your_wandb_api_key_here

# HuggingFace token
modal secret create hf-secret HF_TOKEN=your_huggingface_token_here

# HuggingFace username
modal secret create hf-name-secret HF_NAME=your_huggingface_user_name_here
```

## 5. Usage

### 5.1 Fine-tuning Pre-trained Models

To fine-tune an existing pre-trained model (like Pi0):

```bash
modal run -d lerobot_finetune.py --dataset-repo-id="danaaubakirova/koch_test" --model-id="lerobot/pi0" --gpu-type="A100" --policy-name="modal_pi0_test" --save-freq=100000 --steps=20 --log-freq=5
```

This uses `--policy.path` under the hood:
```bash
python lerobot/scripts/train.py \
--policy.path=lerobot/pi0 \
--dataset.repo_id=danaaubakirova/koch_test
```

**Quick Test Notes:**
- **Training Duration**: 20 steps for testing
- **Timeout**: 1 hour default
- **Cost**: < $1 for a test run
- **Data**: Uses LeRobot example data

### 5.2 Production Fine-tuning

For a complete fine-tuning of pi0 on So-Arm100 data:

```bash
modal run -d lerobot_finetune.py --dataset-repo-id="DanqingZ/filtered_pick_yellow_pink" --model-id="lerobot/pi0" --gpu-type="H100" --policy-name="pi0_pick_yellow_pink" --save-freq=200000 --log-freq=100
```
**Cost estimate:** ~$50 for 100k steps on H100

For a complete fine-tuning of smolvla on So-Arm100 data:
```bash
modal run -d lerobot_finetune.py --dataset-repo-id="DanqingZ/filtered_pick_yellow_pink" --model-id="lerobot/smolvla_base" --gpu-type="H100" --policy-name="pi0_pick_yellow_pink" --save-freq=200000 --log-freq=100 --batch-size=64 --steps=20000
```



### 5.3 Training from Scratch

To train a model from scratch (e.g., ACT), use the `--policy-type` flag:

```bash
modal run -d lerobot_finetune.py --dataset-repo-id="DanqingZ/filtered_pick_pink" --model-id="act" --gpu-type="A100" --policy-name="act_pick_pink" --save-freq=200000 --log-freq=100 --policy-type
```

This uses `--policy.type` under the hood:
```bash
python lerobot/scripts/train.py \
--policy.type=act \
--dataset.repo_id=DanqingZ/filtered_pick_pink \
--job_name=act_pick_pink
```

### 5.4 Parameter Explanation

| Parameter | Description | Fine-tuning | From Scratch |
|-----------|-------------|-------------|--------------|
| `--policy-type` | Training mode flag | Not used | Required |
| `--model-id` | Model identifier | Pre-trained path (e.g., `lerobot/pi0`) | Policy type (e.g., `act`) |
| `--policy-name` | Output model name | Repository name | Job name |

**Key Differences:**
- **Fine-tuning** (default): Uses existing weights from a pre-trained model
- **From scratch** (`--policy-type`): Trains a new model with random initialization