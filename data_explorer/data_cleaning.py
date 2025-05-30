from functions import *


def main():
    judge_jsonl = "judge.jsonl"

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
    success, dataset_root = create_judge2_dataset_with_videos()
    
    if not success and dataset_root is None:
        print("Failed to create dataset")
        return
    
    # Step 5: Push to Hugging Face Hub (proceed even if local validation had issues)
    print(f"\nDataset files created at: {dataset_root}")
    
    if success:
        print("✅ Local validation passed!")
    else:
        print("⚠️  Local validation had issues, but files were created. You may still try pushing to Hub.")
    
    push_choice = input("Do you want to push to Hugging Face Hub? (y/n): ").strip().lower()
    
    if push_choice == 'y':
        hub_repo_id = input("Enter hub repo ID (default: DanqingZ/so100_filtered_pick_green): ").strip()
        if not hub_repo_id:
            hub_repo_id = "DanqingZ/so100_filtered_pick_green"
        
        private_choice = input("Make repository private? (y/n): ").strip().lower()
        private = private_choice == 'y'
        
        push_success = push_to_hub(dataset_root, hub_repo_id, private)
        if push_success:
            print(f"\n🎉 Dataset successfully uploaded to Hugging Face!")
            print(f"📁 Repository: https://huggingface.co/datasets/{hub_repo_id}")
            print(f"💻 Load with: LeRobotDataset('{hub_repo_id}')")
            
            # Now try loading from hub to verify
            try:
                print("\nTesting dataset loading from HuggingFace...")
                hub_dataset = LeRobotDataset(hub_repo_id)
                print(f"✓ Hub dataset loads successfully: {hub_dataset}")
                print(f"✓ Episodes: {hub_dataset.num_episodes}")
                print(f"✓ Frames: {hub_dataset.num_frames}")
            except Exception as e:
                print(f"✗ Error loading from hub: {e}")
                print("The dataset was uploaded but there might be an issue with the format.")
    else:
        print(f"Dataset saved locally at: {dataset_root}")
        print(f"Files created:")
        for item in dataset_root.rglob("*"):
            if item.is_file():
                print(f"  {item.relative_to(dataset_root)}")
        print(f"\nTo upload later, run the script again or manually push the folder to HuggingFace.")


if __name__ == "__main__":
    main()