from functions import *


def main():
    """Main execution function"""
    # Step 1: Show original dataset info
    print("=== Original Datasets Info ===")
    for repo_id in repo_ids:
        repo_meta(repo_id)

    # Step 2: Generate or load judge file
    judge_jsonl = "judge.jsonl"
    if not os.path.exists(judge_jsonl):
        generate_judge_jsonl(repo_ids, judge_jsonl)
        print("Generated judge.jsonl")
    else:
        print("judge file already exists, skipping generation")


if __name__ == "__main__":
    main()
