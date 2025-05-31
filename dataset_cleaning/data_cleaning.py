#!/usr/bin/env python

from lerobot.common.datasets.lerobot_dataset import (
    LeRobotDataset,
    LeRobotDatasetMetadata,
)
import json
import os
import shutil
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import torch
import numpy as np
import datasets
import pyarrow.compute as pc
import pyarrow.parquet as pq
from tqdm import tqdm
import os
import re
import glob
import pandas as pd
from lerobot.common.datasets.utils import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_PARQUET_PATH,
    DEFAULT_VIDEO_PATH,
    EPISODES_PATH,
    EPISODES_STATS_PATH,
    INFO_PATH,
    TASKS_PATH,
    write_json,
    write_jsonlines,
)
from huggingface_hub import HfApi
from lerobot.common.datasets.utils import write_episode_stats

def validate_dataset_structure(dataset_root: Path, expected_episodes: int, video_keys: list[str]) -> bool:
    """Validate that all required dataset files exist without loading through LeRobotDataset"""
    
    # Check required metadata files
    required_meta_files = [
        ("info.json", dataset_root / "meta" / "info.json"),
        ("episodes.jsonl", dataset_root / "meta" / "episodes.jsonl"),
        ("tasks.jsonl", dataset_root / "meta" / "tasks.jsonl"),
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


def generate_dataset(judge_jsonl_path, repo_ids):
    """Create filtered dataset with proper video handling"""
    
    # Get judge=2 episodes
    judge2_episodes = defaultdict(list)
    with open(judge_jsonl_path, 'r') as f:
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
    
    episodes_stats = []
    for repo_id in repo_ids:
        if repo_id not in judge2_episodes:
            continue
            
        dataset = LeRobotDataset(repo_id)
        
        for ep_id in judge2_episodes[repo_id]:
            print(f"Collecting {repo_id} episode {ep_id}")
            episodes_stats.append(dataset.meta.episodes_stats[ep_id])
            
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
    print(f"Episodes stats: {episodes_stats}")
    
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

    # Remove existing directory if it exists, then create fresh one
    if dataset_root.exists():
        print(f"Removing existing directory: {dataset_root}")
        import shutil
        shutil.rmtree(dataset_root)

    print(f"Creating fresh directory: {dataset_root}")
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

    for ep_idx in tqdm(range(total_episodes)):
        write_episode_stats(ep_idx, episodes_stats[ep_idx], dataset_root)
    
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

def update_task_index(dataset_root):
    # meta/episodes.jsonl, not need to update
    # output_dir = Path("./filtered_dataset")
    # dataset_name = "so100_filtered_pick_green"
    # dataset_root = output_dir / dataset_name
    print(dataset_root)
    episodes_path = dataset_root / "meta" / "episodes.jsonl"
    print(episodes_path)
    all_tasks = []
    with open(episodes_path, 'r') as f:
        for line in f:
            episode = json.loads(line.strip())
            all_tasks.extend(episode['tasks'])

    # Create unique task list
    unique_tasks = list(dict.fromkeys(all_tasks))

    # Create mappings
    task_to_id = {task: i for i, task in enumerate(unique_tasks)}
    id_to_task = {i: task for i, task in enumerate(unique_tasks)}
    print(task_to_id, id_to_task)

    tasks_path = dataset_root / "meta" / "tasks.jsonl"
    with open(tasks_path, 'w') as f:
        for k, v in task_to_id.items():
            f.write(json.dumps({"task_index": v, "task": k}) + '\n')

    episodes_task_mapping = {}
    with open(episodes_path, 'r') as f:
        for line in f:
            episode = json.loads(line.strip())
            episode_id = episode['episode_index']
            task = episode['tasks'][0]
            episodes_task_mapping[episode_id] = task_to_id[task]
    print(episodes_task_mapping)

    updated_episodes = []
    episodes_stats_path = dataset_root / "meta" / "episodes_stats.jsonl"
    with open(episodes_stats_path, 'r') as f:
        for line in f:
            episode_stats = json.loads(line.strip())
            episode_id = episode_stats['episode_index']
            
            print(episode_id)
            print(episodes_task_mapping[episode_id])
            print(episode_stats['stats']['task_index'])
            
            # Update the task_index stats with the mapped task value
            mapped_task = episodes_task_mapping[episode_id]
            episode_stats['stats']['task_index']['min'] = [mapped_task]
            episode_stats['stats']['task_index']['max'] = [mapped_task]
            episode_stats['stats']['task_index']['mean'] = [float(mapped_task)]  # Ensure it's a float for mean
            
            print(episode_stats['stats']['task_index'])
            
            # Add the modified episode to our list
            updated_episodes.append(episode_stats)

    # Write the updated data back to the file
    with open(episodes_stats_path, 'w') as f:
        for episode_stats in updated_episodes:
            json_line = json.dumps(episode_stats)
            f.write(json_line + '\n')

    data_folder = dataset_root / "data"
    parquet_files = glob.glob(os.path.join(data_folder, "**/*.parquet"), recursive=True)

    print("All parquet files:")
    for file in parquet_files:
        print(file)
        episode_match = re.search(r'episode_(\d+)', file)
        if episode_match:
            episode_id = episode_match.group(1)
            episode_id = int(episode_id)
            print(f"Episode ID: {episode_id}")
            print(episodes_task_mapping[episode_id])
            # update the task_index in the parquet file
            df = pd.read_parquet(file)
            df['task_index'] = episodes_task_mapping[episode_id]
            df.to_parquet(file, index=False)

def main():
    """Main execution function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Filter LeRobot datasets based on judge scores")
    parser.add_argument(
        "--repo_ids", 
        type=str, 
        required=True,
        help="Comma-separated list of repository IDs (e.g., 'repo1,repo2,repo3')"
    )
    parser.add_argument(
        "--judge_file",
        type=str,
        default="judge.jsonl",
        help="Path to the judge JSONL file (default: judge.jsonl)"
    )
    parser.add_argument(
        "--hub_repo_id",
        type=str,
        default="DanqingZ/so100_filtered_pick_green",
        help="Hugging Face Hub repository ID for pushing the dataset (default: DanqingZ/so100_filtered_pick_green)"
    )
    
    args = parser.parse_args()
    
    # Parse comma-separated repo_ids into a list
    repo_ids = [repo_id.strip() for repo_id in args.repo_ids.split(',') if repo_id.strip()]
    
    if not repo_ids:
        print("Error: No valid repository IDs provided")
        return
    
    judge_jsonl = args.judge_file
    
    if not os.path.exists(judge_jsonl):
        print(f"Error: Judge file '{judge_jsonl}' not found")
        return
    
    print(f"Processing {len(repo_ids)} repositories: {repo_ids}")
    print(f"Using judge file: {judge_jsonl}")

    judge_counts = Counter()
    with open(judge_jsonl, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data = json.loads(line)
                    judge_value = data.get('judge')
                    judge_counts[judge_value] += 1
                except json.JSONDecodeError as e:
                    print(f"Error parsing line: {line[:50]}... - {e}")
                    continue

    print(f"\nJudge distribution:")
    print(f"Judge = 0: {judge_counts.get(0, 0)}")
    print(f"Judge = 1: {judge_counts.get(1, 0)}")
    print(f"Judge = 2: {judge_counts.get(2, 0)}")

    # Step 4: Create filtered dataset
    success, dataset_root = generate_dataset(judge_jsonl_path=judge_jsonl, repo_ids=repo_ids)
    if not success and dataset_root is None:
        print("Failed to create dataset")
        return

    update_task_index(dataset_root)

    # Automatically push to Hugging Face Hub with default settings
    hub_repo_id = args.hub_repo_id
    print(f"Dataset root: {dataset_root}")  
    dataset = LeRobotDataset(repo_id=hub_repo_id, root=dataset_root)
    dataset.push_to_hub()


if __name__ == "__main__":
    main()