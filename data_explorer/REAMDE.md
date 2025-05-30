# Clean and Combine LeRobot Datasets

```bash
export HUGGINGFACE_HUB_TOKEN=your_huggingface_token_here
```

## Step 1: Generate judge.jsonl file and add your judgments

Create a judgment file where each episode is scored based on data quality:

- **0**: The episode cannot be used for training
- **1**: Might be useful for training
- **2**: Good imitation learning data

```bash
python generate_judge.py
```

## Step 2: Select high-quality episodes and combine datasets

Based on the judge.jsonl file, select episodes with a score of 2 and combine them into a single dataset:

```bash
python data_cleaning.py
```