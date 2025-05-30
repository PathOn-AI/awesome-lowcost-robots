from lerobot.common.datasets.lerobot_dataset import (
    LeRobotDataset,
    LeRobotDatasetMetadata,
)
import os
import json
import argparse

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

def main():
    """Main execution function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Process LeRobot datasets")
    parser.add_argument(
        "--repo_ids", 
        type=str, 
        required=True,
        help="Comma-separated list of repository IDs (e.g., 'repo1,repo2,repo3')"
    )
    parser.add_argument(
        "--output_file",
        type=str,
        default="judge.jsonl",
        help="Output JSONL file name (default: judge.jsonl)"
    )
    
    args = parser.parse_args()
    
    # Parse comma-separated repo_ids into a list
    repo_ids = [repo_id.strip() for repo_id in args.repo_ids.split(',') if repo_id.strip()]
    
    if not repo_ids:
        print("Error: No valid repository IDs provided")
        return
    
    print(f"Processing {len(repo_ids)} repositories: {repo_ids}")
    
    # Step 1: Show original dataset info
    print("=== Original Datasets Info ===")
    for repo_id in repo_ids:
        repo_meta(repo_id)
    
    # Step 2: Generate or load judge file
    judge_jsonl = args.output_file
    if not os.path.exists(judge_jsonl):
        generate_judge_jsonl(repo_ids, judge_jsonl)
        print(f"Generated {judge_jsonl}")
    else:
        print(f"Judge file {judge_jsonl} already exists, skipping generation")

if __name__ == "__main__":
    main()