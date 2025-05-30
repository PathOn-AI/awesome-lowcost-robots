import modal

app = modal.App("lerobot-example")

# To set up authentication, create Modal secrets:
# modal secret create wandb-secret WANDB_API_KEY=your_wandb_api_key_here
# modal secret create hf-secret HF_TOKEN=your_huggingface_token_here

# Create image with Python 3.10, ffmpeg, and LeRobot
image = (
    modal.Image.debian_slim(python_version="3.10")
    # Install system dependencies including ffmpeg
    .apt_install("git", "ffmpeg")
    # Clone and install LeRobot with pi0 extras, then fix transformers version
    .run_commands(
        "git clone https://github.com/huggingface/lerobot.git /lerobot",
        'cd /lerobot && pip install -e ".[pi0]"',
        "pip uninstall -y transformers",
        "pip install transformers==4.51.3",
        "pip install wandb pytest"
    )
)

@app.function(gpu="H100", image=image, secrets=[modal.Secret.from_name("hf-secret"), modal.Secret.from_name("hf-name-secret")], timeout=600)
def test_lerobot_setup():
    """Test that LeRobot is properly installed and can import"""
    import sys
    import os
    print(f"Python version: {sys.version}")
    
    # Test LeRobot imports
    try:
        import lerobot
        print(f"✅ LeRobot installed successfully, version: {lerobot.__version__}")
    except ImportError as e:
        print(f"❌ LeRobot import failed: {e}")
        return
    
    # Test transformers version
    try:
        import transformers
        print(f"✅ Transformers installed, version: {transformers.__version__}")
        if transformers.__version__ == "4.51.3":
            print("✅ Correct transformers version (4.51.3)")
        else:
            print(f"⚠️ Expected transformers 4.51.3, got {transformers.__version__}")
    except ImportError as e:
        print(f"❌ Transformers import failed: {e}")
    
    # Define training parameters
    try:
        hf_username = os.environ["HF_NAME"]
        print(f"✅ HF_NAME set to: {hf_username}")
    except KeyError:
        raise ValueError("❌ HF_NAME not set. Please run with: HF_NAME=your_username modal run lerobot_pi0.py")
    
    
    # Test wandb
    try:
        import wandb
        print(f"✅ Wandb installed, version: {wandb.__version__}")
    except ImportError as e:
        print(f"❌ Wandb import failed: {e}")
    
    # Test pytest
    try:
        import pytest
        print(f"✅ Pytest installed, version: {pytest.__version__}")
    except ImportError as e:
        print(f"❌ Pytest import failed: {e}")
    
    # Test huggingface_hub
    try:
        import huggingface_hub
        print(f"✅ Huggingface Hub installed, version: {huggingface_hub.__version__}")
    except ImportError as e:
        print(f"❌ Huggingface Hub import failed: {e}")
    
    # Test PyTorch availability
    try:
        import torch
        print(f"✅ PyTorch available, version: {torch.__version__}")
        print(f"✅ CUDA available: {torch.cuda.is_available()}")
    except ImportError:
        print("❌ PyTorch not available")
    
    # Test ffmpeg
    import subprocess
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFmpeg available")
        else:
            print("❌ FFmpeg not working")
    except FileNotFoundError:
        print("❌ FFmpeg not found")

@app.function(gpu="H100", image=image, secrets=[modal.Secret.from_name("wandb-secret"), modal.Secret.from_name("hf-secret"), modal.Secret.from_name("hf-name-secret")], timeout=3600)
def run_lerobot_example():
    """Example function using LeRobot with Wandb logging and HF authentication"""
    import torch
    import subprocess
    import os
    import wandb
    from datetime import datetime
    
    print("Running LeRobot training with Wandb and HF authentication...")
    print(f"Device: {torch.cuda.get_device_name() if torch.cuda.is_available() else 'CPU'}")
    
    # Set up Hugging Face authentication
    try:
        from huggingface_hub import login
        # The HF_TOKEN should be set in your Modal secret
        login(token=os.environ.get("HF_TOKEN"))
        print("✅ Hugging Face authentication successful")
    except Exception as e:
        print(f"⚠️ Hugging Face authentication failed: {e}")
    
    # Set up wandb authentication
    try:
        # The WANDB_API_KEY should be set in your Modal secret
        wandb.login()
        print("✅ Wandb authentication successful")
    except Exception as e:
        print(f"⚠️ Wandb authentication failed: {e}")
        print("Training will continue without wandb logging")
    
    # Change to lerobot directory
    os.chdir("/lerobot")
    # Define training parameters
    hf_username = os.environ["HF_NAME"]
    policy_path = "lerobot/pi0"
    dataset_repo_id = "danaaubakirova/koch_test"
    steps = 20
    save_freq = 30
    log_freq = 5
    output_dir = "./output"
    
    # Run the training script
    cmd = [
        "python", "lerobot/scripts/train.py",
        f"--policy.path={policy_path}",
        f"--dataset.repo_id={dataset_repo_id}",
        "--wandb.enable=true",
        f"--steps={steps}",
        f"--save_freq={save_freq}",
        f"--log_freq={log_freq}",
        f"--output_dir={output_dir}"
    ]
    
    print(f"Executing: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Training completed successfully!")
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"❌ Training failed with return code {e.returncode}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        raise
    
    # Extract model name from policy_path
    model_name = policy_path.split('/')[-1] if '/' in policy_path else policy_path

    # Extract dataset name from dataset_repo
    dataset_name = dataset_repo_id.split('/')[-1] if '/' in dataset_repo_id else dataset_repo_id

    # Combine with timestamp
    policy_name = f"{model_name}_{dataset_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    repo_id = f"{hf_username}/{policy_name}"

    from huggingface_hub import HfApi, upload_folder
    import os

    # Your existing variable
    checkpoint_path = os.path.join(output_dir, "checkpoints", "last", "pretrained_model")

    # Initialize the API
    api = HfApi()

    # Define repository info
    repo_type = "model"

    # Create the repository if it doesn't exist
    try:
        api.create_repo(repo_id=repo_id, repo_type=repo_type, exist_ok=True)
        print(f"Repository {repo_id} created or already exists")
    except Exception as e:
        print(f"Error creating repository: {e}")

    # Upload the checkpoint folder
    upload_folder(
        folder_path=checkpoint_path,
        repo_id=repo_id,
        repo_type=repo_type,
        commit_message="Upload diffusion_pusht last checkpoint"
    )

    print(f"Checkpoint uploaded to https://huggingface.co/{repo_id}")

    # Give wandb time to clean up to avoid shutdown errors
    import time
    print("Cleaning up...")
    time.sleep(5)

@app.local_entrypoint()
def main():
    # Test the setup first
    test_lerobot_setup.remote()
    
    # Run your LeRobot code
    run_lerobot_example.remote()