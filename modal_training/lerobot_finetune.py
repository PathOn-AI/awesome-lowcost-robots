import modal
import os

app = modal.App("lerobot-finetune-app")

# Create image with Python 3.10, ffmpeg, and LeRobot
image = (
    modal.Image.debian_slim(python_version="3.10")
    # Install system dependencies including ffmpeg
    .apt_install("git", "ffmpeg")
    # Clone and install LeRobot with pi0 extras, then fix transformers version
    .run_commands(
        "git clone https://github.com/huggingface/lerobot.git /lerobot",
        'cd /lerobot && pip install -e ".[pi0]"',
        'cd /lerobot && pip install -e ".[smolvla]"',
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

@app.function(gpu="H100", image=image, secrets=[modal.Secret.from_name("wandb-secret"), modal.Secret.from_name("hf-secret"), modal.Secret.from_name("hf-name-secret")], timeout=86400)
def run_lerobot_h100(dataset_repo_id, model_id, policy_name=None, save_freq=200000, log_freq=100, steps=None, policy_type=False, batch_size=None):
    """Run LeRobot training on H100"""
    return _run_lerobot_training("H100", dataset_repo_id, model_id, policy_name, save_freq, log_freq, steps, policy_type, batch_size)

@app.function(gpu="A100", image=image, secrets=[modal.Secret.from_name("wandb-secret"), modal.Secret.from_name("hf-secret"), modal.Secret.from_name("hf-name-secret")], timeout=86400)
def run_lerobot_a100(dataset_repo_id, model_id, policy_name=None, save_freq=200000, log_freq=100, steps=None, policy_type=False, batch_size=None):
    """Run LeRobot training on A100"""
    return _run_lerobot_training("A100", dataset_repo_id, model_id, policy_name, save_freq, log_freq, steps, policy_type, batch_size)


def _run_lerobot_training(gpu_type, dataset_repo_id, model_id, policy_name=None, save_freq=200000, log_freq=100, steps=None, policy_type=False, batch_size=None):
    """Shared training logic"""
    import torch
    import subprocess
    import os
    import wandb
    from datetime import datetime
    
    print("Running LeRobot training with Wandb and HF authentication...")
    print(f"Device: {torch.cuda.get_device_name() if torch.cuda.is_available() else 'CPU'}")
    print(f"Dataset: {dataset_repo_id}")
    print(f"Model: {model_id}")
    print(f"GPU Type: {gpu_type}")
    print(f"Policy Name: {policy_name if policy_name else 'auto-generated'}")
    print(f"Steps: {steps if steps else 'default (from config)'}")
    print(f"Batch Size: {batch_size if batch_size else 'default (from config)'}")
    
    # Set up Hugging Face authentication
    try:
        from huggingface_hub import login
        login(token=os.environ.get("HF_TOKEN"))
        print("✅ Hugging Face authentication successful")
    except Exception as e:
        print(f"⚠️ Hugging Face authentication failed: {e}")
    
    # Set up wandb authentication
    try:
        wandb.login()
        print("✅ Wandb authentication successful")
    except Exception as e:
        print(f"⚠️ Wandb authentication failed: {e}")
        print("Training will continue without wandb logging")
    
    # Change to lerobot directory
    os.chdir("/lerobot")
    hf_username = os.environ["HF_NAME"]
    policy_path = model_id
    output_dir = "./output"
    
    # Run the training script
    if policy_type:
        cmd = [
            "python", "lerobot/scripts/train.py",
            f"--policy.type={policy_path}",
            f"--dataset.repo_id={dataset_repo_id}",
            "--wandb.enable=true",
            f"--save_freq={save_freq}",
            f"--log_freq={log_freq}",
            f"--output_dir={output_dir}"
        ]
        
        # Generate job name if policy_name is provided
        if policy_name:
            cmd.append(f"--job_name={policy_name}")
        else:
            # Auto-generate job name
            dataset_name = dataset_repo_id.split('/')[-1] if '/' in dataset_repo_id else dataset_repo_id
            auto_job_name = f"{policy_path}_{datetime.now().strftime('%m%d')}_{dataset_name}"
            cmd.append(f"--job_name={auto_job_name}")
    else:
        cmd = [
            "python", "lerobot/scripts/train.py",
            f"--policy.path={policy_path}",
            f"--dataset.repo_id={dataset_repo_id}",
            "--wandb.enable=true",
            f"--save_freq={save_freq}",
            f"--log_freq={log_freq}",
            f"--output_dir={output_dir}"
        ]
    
    # Add batch size if specified
    if batch_size:
        cmd.append(f"--batch_size={batch_size}")
    
    # Add steps if specified
    if steps:
        cmd.append(f"--steps={steps}")
    
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
    model_name = model_id.split('/')[-1] if '/' in model_id else model_id
    dataset_name = dataset_repo_id.split('/')[-1] if '/' in dataset_repo_id else dataset_repo_id

    # Generate repo_id
    if policy_name:
        repo_id = f"{hf_username}/{policy_name}"
    else:
        auto_policy_name = f"{model_name}_{dataset_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        repo_id = f"{hf_username}/{auto_policy_name}"

    from huggingface_hub import HfApi, upload_folder
    
    checkpoint_path = os.path.join(output_dir, "checkpoints", "last", "pretrained_model")
    api = HfApi()

    # Create and upload to repository
    try:
        api.create_repo(repo_id=repo_id, repo_type="model", exist_ok=True)
        print(f"Repository {repo_id} created or already exists")
        
        upload_folder(
            folder_path=checkpoint_path,
            repo_id=repo_id,
            repo_type="model",
            commit_message="Upload training checkpoint"
        )
        print(f"Checkpoint uploaded to https://huggingface.co/{repo_id}")
    except Exception as e:
        print(f"Error uploading to repository: {e}")

    # Cleanup
    import time
    print("Cleaning up...")
    time.sleep(5)
    return repo_id

@app.local_entrypoint()
def main(
    dataset_repo_id: str = "DanqingZ/so100_test_yellow_cuboid_2",
    model_id: str = "lerobot/pi0",
    gpu_type: str = "H100",
    policy_name: str = None,
    save_freq: int = 200000,
    log_freq: int = 100,
    steps: int = None,
    skip_test: bool = False,
    policy_type: bool = False,
    batch_size: int = None
):
    """
    Run LeRobot training with configurable parameters.
    
    Args:
        dataset_repo_id: HuggingFace dataset repository ID
        model_id: Model to use for training (policy path) or policy type (if policy_type=True)
        gpu_type: GPU instance type (H100, A100)
        policy_name: Custom name for output repository/job name (optional)
        save_freq: Save frequency for checkpoints
        log_freq: Logging frequency
        steps: Number of training steps (optional, uses config default if not specified)
        skip_test: Skip the setup test
        policy_type: If True, uses model_id as policy.type; if False, uses model_id as policy.path
        batch_size: Training batch size (optional, uses config default if not specified)
    """
    
    print(f"Configuration:")
    print(f"  Dataset: {dataset_repo_id}")
    print(f"  Model: {model_id}")
    print(f"  GPU: {gpu_type}")
    print(f"  Steps: {steps if steps else 'default'}")
    print(f"  Policy Name: {policy_name if policy_name else 'auto-generated'}")
    print(f"  Policy Type: {policy_type}")
    print(f"  Batch Size: {batch_size if batch_size else 'default'}")
    
    if not skip_test:
        print("\nTesting setup...")
        test_lerobot_setup.remote()
    
    # Select training function based on GPU type
    training_functions = {
        "H100": run_lerobot_h100,
        "A100": run_lerobot_a100
    }
    
    if gpu_type not in training_functions:
        raise ValueError(f"Unsupported GPU type: {gpu_type}. Supported types: {list(training_functions.keys())}")
    
    training_func = training_functions[gpu_type]
    
    print("\nStarting training...")
    result = training_func.remote(
        dataset_repo_id=dataset_repo_id,
        model_id=model_id,
        policy_name=policy_name,
        save_freq=save_freq,
        log_freq=log_freq,
        steps=steps,
        policy_type=policy_type,
        batch_size=batch_size
    )
    
    print(f"\n✅ Training completed! Model uploaded to: {result}")