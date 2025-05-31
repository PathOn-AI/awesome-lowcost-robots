# Clean and Combine LeRobot Datasets

```bash
export HUGGINGFACE_HUB_TOKEN=your_huggingface_token_here
```

Here we assume the episode duration is the same across all episodes from different datasets. If you want to filter and merge datasets with different episode durations, please submit a PR to change the script.

## Step 1: Generate judge.jsonl file and add your judgments

Create a judgment file where each episode is scored based on data quality:

- **0**: The episode cannot be used for training
- **1**: Might be useful for training
- **2**: Good imitation learning data

```bash
python generate_judge.py --repo_ids "DanqingZ/so100_test_pick_green_4,DanqingZ/so100_test_pick_green_5,DanqingZ/so100_test_pick_green_6,DanqingZ/so100_test_pick_grey_1,DanqingZ/so100_test_pick_grey_2" --output_file "judge.jsonl"
```

## Step 2: Select high-quality episodes and combine datasets

Based on the judge.jsonl file, select episodes with a score of 2 and combine them into a single dataset:

```bash
python data_cleaning.py --repo_ids "DanqingZ/so100_test_pick_green_4,DanqingZ/so100_test_pick_green_5,DanqingZ/so100_test_pick_green_6,DanqingZ/so100_test_pick_grey_1,DanqingZ/so100_test_pick_grey_2" --judge_file "judge.jsonl" --hub_repo_id "DanqingZ/so100_filtered_pick_green_grey"
```
Visualization of the consolidated dataset: https://huggingface.co/spaces/lerobot/visualize_dataset?path=%2FDanqingZ%2Fso100_filtered_pick_green_grey%2Fepisode_1