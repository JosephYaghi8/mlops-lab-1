import argparse
import math
import os
from pathlib import Path

from mlflow.exceptions import MlflowException

import mlflow
from mlflow import MlflowClient

MODEL_NAME = "food11"
METRIC_NAME = "test_accuracy"


def count_eval_images(dataset_param: str) -> int:
    dataset_name = "processed_mini" if dataset_param == "mini" else "processed"
    eval_dir = Path(f"./data/food11_{dataset_name}/evaluation")
    if not eval_dir.exists():
        return 0
    return sum(1 for p in eval_dir.rglob("*") if p.is_file())


def get_accuracy_and_n(client: MlflowClient, run_id: str):
    run = client.get_run(run_id)
    acc = run.data.metrics.get(METRIC_NAME)
    if acc is None:
        raise ValueError(f"Run {run_id} has no '{METRIC_NAME}' metric")
    n = count_eval_images(run.data.params.get("dataset", "mini"))
    return acc, n


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, required=True, help="Candidate model version number")
    parser.add_argument("--n", type=int, default=None, help="Override test-split size instead of counting files on disk")
    args = parser.parse_args()

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient()

    candidate_mv = client.get_model_version(MODEL_NAME, str(args.version))
    acc_candidate, n_candidate = get_accuracy_and_n(client, candidate_mv.run_id)

    try:
        champion_mv = client.get_model_version_by_alias(MODEL_NAME, "champion")
    except MlflowException:
        print(f"No existing champion found. Promoting version {args.version} to champion directly.")
        client.set_registered_model_alias(MODEL_NAME, "champion", args.version)
        client.set_model_version_tag(MODEL_NAME, str(args.version), "promotion_decision", "champion (no prior champion)")
        client.set_model_version_tag(MODEL_NAME, str(args.version), "candidate_accuracy", f"{acc_candidate:.4f}")
        return

    acc_champion, n_champion = get_accuracy_and_n(client, champion_mv.run_id)

    n = args.n if args.n is not None else (n_champion or n_candidate)
    if not n:
        raise ValueError("Could not determine test split size; pass --n explicitly")

    p = acc_champion
    se = math.sqrt(p * (1 - p) / n)
    threshold = acc_champion + 2 * se

    print(f"Candidate v{args.version}: test_accuracy = {acc_candidate:.4f}")
    print(f"Champion v{champion_mv.version}: test_accuracy = {acc_champion:.4f}")
    print(f"n (test split size) = {n}, se = {se:.4f}, promotion threshold = {threshold:.4f}")

    if acc_candidate >= threshold:
        decision = "champion"
        client.set_registered_model_alias(MODEL_NAME, "champion", args.version)
        print(f"Decision: PROMOTE v{args.version} to champion")
    else:
        decision = "challenger"
        client.set_registered_model_alias(MODEL_NAME, "challenger", args.version)
        print(f"Decision: set v{args.version} as challenger; champion remains v{champion_mv.version}")

    client.set_model_version_tag(MODEL_NAME, str(args.version), "promotion_decision", decision)
    client.set_model_version_tag(MODEL_NAME, str(args.version), "candidate_accuracy", f"{acc_candidate:.4f}")
    client.set_model_version_tag(MODEL_NAME, str(args.version), "champion_accuracy_at_decision", f"{acc_champion:.4f}")


if __name__ == "__main__":
    main()