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

### 5.1 Get started with pi0 finetuning

To start training your Pi0 model:

```bash
modal run lerobot_pi0.py
```

By the end of training, you can access the Weights & Biases training log and have the final model saved to your Hugging Face account.

Please note that this script:
- **Training Duration**: The script runs for 20 steps by default.
- **Timeout**: The training timeout is set to 1 hour (default is 5 minutes). You can change the timeout in the code.
- **Cost**: Expect to spend less than $1 for a complete run.
- **Data**: Uses LeRobot example data for fine-tuning.

### 5.2 Complete Pi0 run

For a long-running training job, try running in detached mode and change the timeout. Run the script below to finetune pi0 on one of the datasets collected from so-arm100:

```bash
modal run -d lerobot_pi0.py
```
