#!/usr/bin/env python

from lerobot.common.datasets.lerobot_dataset import (
    LeRobotDataset,
    LeRobotDatasetMetadata,
)
import json
import os
import shutil
from collections import Counter, defaultdict
from pathlib import Path
import torch
import numpy as np
import datasets
import pyarrow.compute as pc
import pyarrow.parquet as pq
from lerobot.common.datasets.utils import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_PARQUET_PATH,
    DEFAULT_VIDEO_PATH,
    EPISODES_PATH,
    INFO_PATH,
    STATS_PATH,
    TASKS_PATH,
    write_json,
    write_jsonlines,
)
from huggingface_hub import HfApi

global repo_ids
repo_ids = ["DanqingZ/so100_test_pick_green_4", "DanqingZ/so100_test_pick_green_5", "DanqingZ/so100_test_pick_green_6"]

# Add missing constant for episodes_stats.jsonl
EPISODES_STATS_PATH = "meta/episodes_stats.jsonl"


def repo_meta(repo_id: str):
    ds_meta = LeRobotDatasetMetadata(repo_id)
    total_episodes: int = ds_meta.total_episodes
    print(repo_id)
    print(f"Total number of episodes: {total_episodes}")
    dataset = LeRobotDataset(repo_id)
    print(dataset)
    for i in range(total_episodes):
        task = dataset[i]['task']
        print(task)


def validate_dataset_structure(dataset_root: Path, expected_episodes: int, video_keys: list[str]) -> bool:
    """Validate that all required dataset files exist without loading through LeRobotDataset"""
    
    # Check required metadata files
    required_meta_files = [
        ("info.json", dataset_root / "meta" / "info.json"),
        ("episodes.jsonl", dataset_root / "meta" / "episodes.jsonl"),
        ("tasks.jsonl", dataset_root / "meta" / "tasks.jsonl"),
        ("stats.json", dataset_root / "meta" / "stats.json"),
        ("episodes_stats.jsonl", dataset_root / "meta" / "episodes_stats.jsonl")  # Added missing file
    ]
    
    for filename, filepath in required_meta_files:
        if not filepath.exists():
            print(f"✗ Missing required file: {filepath}")
            return False
        print(f"✓ Found: {filename}")
    
    # Check data directory exists
    data_dir = dataset_root / "data"
    if not data_dir.exists():
        print(f"✗ Missing data directory: {data_dir}")
        return False
    
    # Check parquet files
    parquet_files = list(data_dir.glob("**/*.parquet"))
    print(f"✓ Found {len(parquet_files)} parquet files")
    
    if len(parquet_files) != expected_episodes:
        print(f"⚠ Expected {expected_episodes} parquet files, found {len(parquet_files)}")
    
    # Check video files if expected
    if video_keys:
        videos_dir = dataset_root / "videos"
        if not videos_dir.exists():
            print(f"✗ Missing videos directory: {videos_dir}")
            return False
        
        video_files = list(videos_dir.glob("**/*.mp4"))
        expected_video_count = expected_episodes * len(video_keys)
        print(f"✓ Found {len(video_files)} video files (expected: {expected_video_count})")
        
        if len(video_files) != expected_video_count:
            print(f"⚠ Video count mismatch - expected {expected_video_count}, found {len(video_files)}")
            return False
    
    return True


def copy_video_files(original_episode_mappings, video_keys, dataset_root):
    """Copy video files from source datasets to filtered dataset"""
    print("Copying video files...")
    
    successful_copies = 0
    total_expected = len(original_episode_mappings) * len(video_keys)
    
    # Copy videos for each episode
    for mapping in original_episode_mappings:
        new_ep_idx = mapping["new_episode_idx"]
        original_repo_id = mapping["original_repo_id"]
        original_ep_idx = mapping["original_episode_idx"]
        
        if not original_repo_id:
            continue
            
        try:
            source_dataset = LeRobotDataset(original_repo_id)
            new_ep_chunk = new_ep_idx // DEFAULT_CHUNK_SIZE
            
            for vid_key in video_keys:
                try:
                    # Source video path
                    source_video_path = source_dataset.root / source_dataset.meta.get_video_file_path(original_ep_idx, vid_key)
                    
                    # Destination video path
                    dest_video_dir = dataset_root / f"videos/chunk-{new_ep_chunk:03d}/{vid_key}"
                    dest_video_dir.mkdir(parents=True, exist_ok=True)
                    dest_video_path = dest_video_dir / f"episode_{new_ep_idx:06d}.mp4"
                    
                    # Copy video file if it exists
                    if source_video_path.exists():
                        shutil.copy2(source_video_path, dest_video_path)
                        successful_copies += 1
                        if new_ep_idx % 10 == 0:  # Log every 10th episode to avoid spam
                            print(f"Copied video: {vid_key} episode {new_ep_idx}")
                    else:
                        print(f"Warning: Source video not found: {source_video_path}")
                        
                except Exception as e:
                    print(f"Error copying video {vid_key} for episode {new_ep_idx}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error loading source dataset {original_repo_id}: {e}")
            continue
    
    print(f"Video copy complete: {successful_copies}/{total_expected} videos copied successfully")


def generate_judge_jsonl(repo_ids, output_file):
    """Generate JSONL file with repo_id, episode_id, and judge fields"""
    with open(output_file, 'w') as f:
        for repo_id in repo_ids:
            try:
                print(f"Processing {repo_id}...")
                ds_meta = LeRobotDatasetMetadata(repo_id)
                dataset = LeRobotDataset(repo_id)
                
                total_episodes = ds_meta.total_episodes
                print(f"  Total episodes: {total_episodes}")
                
                for i in range(total_episodes):
                    json_obj = {
                        "repo_id": repo_id,
                        "episode_id": i,
                        "judge": 2
                    }
                    f.write(json.dumps(json_obj) + '\n')
                    
                    if (i + 1) % 10 == 0 or i == total_episodes - 1:
                        print(f"  Processed {i + 1}/{total_episodes} episodes")
                
                print(f"✓ Completed {repo_id}")
                
            except Exception as e:
                print(f"✗ Error processing {repo_id}: {e}")
                continue


def calculate_feature_stats(data_values):
    """Calculate statistics for a feature, handling different data types and shapes"""
    if len(data_values) == 0:
        return {"min": [], "max": [], "mean": [], "std": [], "count": [0]}
    
    data_array = np.array(data_values)
    
    if data_array.ndim == 1:
        # 1D data
        return {
            "min": [float(data_array.min())],
            "max": [float(data_array.max())],
            "mean": [float(data_array.mean())],
            "std": [float(data_array.std())],
            "count": [len(data_array)]
        }
    elif data_array.ndim == 2:
        # 2D data (like action, observation.state)
        return {
            "min": data_array.min(axis=0).tolist(),
            "max": data_array.max(axis=0).tolist(),
            "mean": data_array.mean(axis=0).tolist(),
            "std": data_array.std(axis=0).tolist(),
            "count": [len(data_array)]
        }
    else:
        # Multi-dimensional data (like images)
        # Calculate stats along the first axis (batch dimension)
        min_vals = data_array.min(axis=0)
        max_vals = data_array.max(axis=0)
        mean_vals = data_array.mean(axis=0)
        std_vals = data_array.std(axis=0)
        
        return {
            "min": min_vals.tolist(),
            "max": max_vals.tolist(),
            "mean": mean_vals.tolist(),
            "std": std_vals.tolist(),
            "count": [len(data_array)]
        }


def create_judge2_dataset_with_videos():
    """Create filtered dataset with proper video handling"""
    
    # Get judge=2 episodes
    judge2_episodes = defaultdict(list)
    with open("judge.jsonl", 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                if data.get('judge') == 2:
                    judge2_episodes[data['repo_id']].append(data['episode_id'])
    
    print("\n=== Creating filtered dataset with judge=2 episodes ===")
    
    # Collect all data
    all_data = []
    episode_info = []
    original_episode_mappings = []
    new_episode_index = 0
    
    # Get source dataset info for video handling
    source_dataset = LeRobotDataset(repo_ids[0])
    has_videos = len(source_dataset.meta.video_keys) > 0
    video_keys = source_dataset.meta.video_keys
    
    print(f"Source dataset has videos: {has_videos}")
    if has_videos:
        print(f"Video keys: {video_keys}")
    
    for repo_id in repo_ids:
        if repo_id not in judge2_episodes:
            continue
            
        dataset = LeRobotDataset(repo_id)
        for ep_id in judge2_episodes[repo_id]:
            print(f"Collecting {repo_id} episode {ep_id}")
            
            episode_data = []
            for i in range(len(dataset.hf_dataset)):
                row = dataset.hf_dataset[i]
                if row['episode_index'].item() == ep_id:
                    # Convert all tensors to numpy/python types and update indices
                    row_dict = {}
                    for k, v in row.items():
                        if isinstance(v, torch.Tensor):
                            if v.dim() == 0:  # scalar tensor
                                row_dict[k] = v.item()
                            else:  # multi-dimensional tensor
                                row_dict[k] = v.numpy()
                        else:
                            row_dict[k] = v
                    
                    # Update episode_index and index for new dataset
                    row_dict['episode_index'] = new_episode_index
                    row_dict['index'] = len(all_data) + len(episode_data)
                    episode_data.append(row_dict)
            
            if len(episode_data) == 0:
                print(f"Warning: No data found for {repo_id} episode {ep_id}")
                continue
            
            print(f"  Collected {len(episode_data)} frames from episode {ep_id}")
            if len(episode_data) > 0:
                print(f"  Sample keys: {list(episode_data[0].keys())}")
                
            all_data.extend(episode_data)
            episode_info.append({
                "episode_index": new_episode_index,
                "tasks": [dataset.meta.tasks[episode_data[0]['task_index']]],
                "length": len(episode_data)
            })
            
            # Track original episode mapping for video copying
            original_episode_mappings.append({
                "new_episode_idx": new_episode_index,
                "original_repo_id": repo_id,
                "original_episode_idx": ep_id
            })
            
            new_episode_index += 1
    
    if len(all_data) == 0:
        print("Error: No data collected from any episodes!")
        return None, None
    
    print(f"\n=== Data Collection Summary ===")
    print(f"Total frames collected: {len(all_data)}")
    print(f"Total episodes: {len(episode_info)}")
    print(f"Columns in dataset: {list(all_data[0].keys())}")
    
    # Verify we have all essential columns
    essential_columns = ['action', 'observation.state', 'timestamp', 'frame_index', 'episode_index', 'index', 'task_index']
    missing_columns = [col for col in essential_columns if col not in all_data[0].keys()]
    if missing_columns:
        print(f"WARNING: Missing essential columns: {missing_columns}")
    else:
        print("✓ All essential columns present")
    
    # Create output directory
    output_dir = Path("./filtered_dataset")
    dataset_name = "so100_filtered_pick_green"
    dataset_root = output_dir / dataset_name
    dataset_root.mkdir(parents=True, exist_ok=True)
    
    # Create videos directory if needed
    if has_videos:
        (dataset_root / "videos").mkdir(exist_ok=True)
    
    # Create HF dataset and save as parquet files
    hf_data = {key: [row[key] for row in all_data] for key in all_data[0].keys()}
    hf_dataset = datasets.Dataset.from_dict(hf_data, split="train")
    
    # Save each episode as separate parquet file
    for ep_info in episode_info:
        ep_idx = ep_info["episode_index"]
        ep_chunk = ep_idx // DEFAULT_CHUNK_SIZE
        
        # Create chunk directory
        chunk_dir = f"data/chunk-{ep_chunk:03d}"
        (dataset_root / chunk_dir).mkdir(parents=True, exist_ok=True)
        
        # Filter and save episode data
        ep_table = hf_dataset.data.table.filter(pc.equal(hf_dataset.data.table["episode_index"], ep_idx))
        output_file = dataset_root / f"{chunk_dir}/episode_{ep_idx:06d}.parquet"
        pq.write_table(ep_table, output_file)
    
    # Copy video files if they exist
    if has_videos:
        copy_video_files(original_episode_mappings, video_keys, dataset_root)
    
    # Create metadata files
    total_episodes = len(episode_info)
    total_frames = len(all_data)
    total_chunks = (total_episodes // DEFAULT_CHUNK_SIZE) + (1 if total_episodes % DEFAULT_CHUNK_SIZE else 0)
    
    # tasks.jsonl
    tasks = [{"task_index": 0, "task": "Grasp the green cube and put it in the bin."}]
    write_jsonlines(tasks, dataset_root / TASKS_PATH)
    
    # episodes.jsonl
    write_jsonlines(episode_info, dataset_root / EPISODES_PATH)
    
    # info.json with proper video handling
    metadata = {
        "codebase_version": "v2.1",
        "robot_type": source_dataset.meta.robot_type,
        "total_episodes": total_episodes,
        "total_frames": total_frames,
        "total_tasks": 1,
        "total_videos": total_episodes * len(video_keys) if has_videos else 0,
        "total_chunks": total_chunks,
        "chunks_size": DEFAULT_CHUNK_SIZE,
        "fps": source_dataset.meta.fps,
        "splits": {"train": f"0:{total_episodes}"},
        "data_path": DEFAULT_PARQUET_PATH,
        "video_path": DEFAULT_VIDEO_PATH if has_videos else None,
        "features": source_dataset.meta.features,
    }
    write_json(metadata, dataset_root / INFO_PATH)
    
    # Create proper stats from source dataset
    # Calculate stats from the filtered data
    stats_data = {}
    for key, feature_info in source_dataset.meta.features.items():
        if feature_info["dtype"] not in ["image", "video"]:
            # Get data for this feature from filtered episodes
            if key in hf_data:
                data_values = np.array(hf_data[key])
                if data_values.ndim > 1:
                    # Handle multi-dimensional data
                    stats_data[key] = {
                        "max": data_values.max(axis=0).tolist(),
                        "mean": data_values.mean(axis=0).tolist(),
                        "min": data_values.min(axis=0).tolist(),
                        "std": data_values.std(axis=0).tolist(),
                    }
                else:
                    # Handle 1D data
                    stats_data[key] = {
                        "max": [float(data_values.max())],
                        "mean": [float(data_values.mean())],
                        "min": [float(data_values.min())],
                        "std": [float(data_values.std())],
                    }
    
    write_json(stats_data, dataset_root / STATS_PATH)
    
    # CREATE EPISODES_STATS.JSONL - This was missing!
    print("Creating episodes_stats.jsonl...")
    episodes_stats = []
    
    for ep_info in episode_info:
        ep_idx = ep_info["episode_index"]
        
        # Filter data for this episode
        ep_data = [row for row in all_data if row['episode_index'] == ep_idx]
        
        # Calculate per-episode stats for all features
        ep_stats_obj = {
            "episode_index": ep_idx,
            "stats": {}
        }
        
        # Process each feature
        for key, feature_info in source_dataset.meta.features.items():
            if key in ep_data[0]:  # Make sure the key exists in our data
                # Get data for this feature from this episode
                ep_values = [row[key] for row in ep_data]
                
                # Calculate stats using our helper function
                ep_stats_obj["stats"][key] = calculate_feature_stats(ep_values)
        
        episodes_stats.append(ep_stats_obj)
    
    # Write episodes_stats.jsonl using standard write_jsonlines
    write_jsonlines(episodes_stats, dataset_root / EPISODES_STATS_PATH)
    
    print(f"✓ Created dataset: {total_episodes} episodes, {total_frames} frames")
    print(f"✓ Video support: {has_videos}")
    if has_videos:
        print(f"✓ Videos copied to: {dataset_root}/videos/")
    print(f"✓ Created episodes_stats.jsonl with {len(episodes_stats)} episode statistics")
    
    # Validate dataset structure without loading through LeRobotDataset
    print(f"\nValidating dataset structure...")
    validation_passed = validate_dataset_structure(dataset_root, total_episodes, video_keys)
    
    if validation_passed:
        print("✅ Dataset validation passed - all required files present and structure looks correct")
        return True, dataset_root
    else:
        print("⚠️  Dataset validation found some issues, but files were created")
        return False, dataset_root


def push_to_hub(dataset_root, hub_repo_id="DanqingZ/so100_filtered_pick_green", private=False):
    """Push the filtered dataset to Hugging Face Hub"""
    try:
        print(f"\n=== Pushing dataset to Hugging Face Hub ===")
        print(f"Repository: {hub_repo_id}")
        
        hub_api = HfApi()
        
        # Create repository
        print("Creating repository...")
        hub_api.create_repo(
            repo_id=hub_repo_id,
            repo_type="dataset",
            private=private,
            exist_ok=True
        )
        
        # Create README.md
        readme_content = f"""---
license: apache-2.0
task_categories:
- robotics
tags:
- robotics
- manipulation
- so100
- filtered
- lerobotdataset
size_categories:
- 1K<n<10K
---

# SO100 Filtered Dataset (Judge=2)

This dataset contains filtered episodes from the SO100 pick green cube task, including only episodes that received a judge score of 2 (highest quality).

## Dataset Information

- **Task**: Grasp the green cube and put it in the bin
- **Robot**: SO100
- **Episodes**: High-quality episodes (judge=2) only
- **Format**: LeRobot Dataset v2.1
- **Original datasets**: 
  - DanqingZ/so100_test_pick_green_4
  - DanqingZ/so100_test_pick_green_5  
  - DanqingZ/so100_test_pick_green_6

## Usage

```python
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset

# Load the dataset
dataset = LeRobotDataset("{hub_repo_id}")

# Access episodes
for i in range(len(dataset)):
    data_point = dataset[i]
    # Your training code here
```

## Filtering Criteria

This dataset was created by filtering the original datasets to include only episodes where `judge = 2`, representing the highest quality demonstrations for robot learning.

## Dataset Structure

- **data/**: Episode data in parquet format
- **meta/**: Metadata including episode info, tasks, and statistics
- **videos/**: Video files for visual observations (if applicable)

Generated using LeRobot dataset tools.
"""
        
        # Upload README first
        hub_api.upload_file(
            path_or_fileobj=readme_content.encode(),
            path_in_repo="README.md",
            repo_id=hub_repo_id,
            repo_type="dataset"
        )
        
        # Upload the entire dataset folder
        print("Uploading dataset files...")
        hub_api.upload_folder(
            repo_id=hub_repo_id,
            folder_path=dataset_root,
            repo_type="dataset",
            ignore_patterns=[".git/", "__pycache__/", "*.pyc", ".DS_Store"]
        )
        
        # Create codebase version tag for LeRobot compatibility
        print("Creating codebase version tag...")
        try:
            # Read the codebase version from info.json
            import json
            with open(dataset_root / "meta" / "info.json", 'r') as f:
                info = json.load(f)
            codebase_version = info.get("codebase_version", "v2.1")
            
            # Delete existing tag if it exists and create new one
            try:
                hub_api.delete_tag(repo_id=hub_repo_id, tag=codebase_version, repo_type="dataset")
            except:
                pass  # Tag might not exist
            
            hub_api.create_tag(
                repo_id=hub_repo_id, 
                tag=codebase_version, 
                repo_type="dataset"
            )
            print(f"✓ Created tag: {codebase_version}")
            
        except Exception as e:
            print(f"⚠ Warning: Could not create version tag: {e}")
            print("You may need to manually create the tag for full LeRobot compatibility")
        
        print(f"✓ Successfully pushed to https://huggingface.co/datasets/{hub_repo_id}")
        print(f"✓ Others can now load it with: LeRobotDataset('{hub_repo_id}')")
        return True
        
    except Exception as e:
        print(f"✗ Failed to push to hub: {e}")
        return False