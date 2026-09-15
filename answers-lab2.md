# Lab 2 Answers

**Q1 - pyproject.toml / uv.lock changes**
mlflow and scikit-learn were added as new dependencies. torch and torchvision lost their version pins (>=2.14.0 / >=0.29.0 became unpinned) - needed because the CUDA index (cu128) only serves up to torch 2.11.0, so a hard minimum of 2.14.0 made resolution impossible. A [[tool.uv.index]] block was added pointing to https://download.pytorch.org/whl/cu128, and a [tool.uv.sources] block was added routing torch/torchvision to that index specifically - this makes uv fetch the CUDA-enabled build instead of the default CPU-only wheels from PyPI. uv.lock reflects this: torch/torchvision entries show source = { registry = "https://download.pytorch.org/whl/cu128" } instead of pypi.org, resolved to torch==2.11.0+cu128 / torchvision==0.26.0+cu128.

**Q2 - backend-store-uri and default-artifact-root**
--backend-store-uri sets where mlflow stores run metadata (params, metrics, tags, run status) - a database (sqlite here). --default-artifact-root sets where mlflow stores artifacts - the actual files like the logged model. Metadata is small, structured and queryable; artifacts are large binary outputs referenced by that metadata.

**Q3 - why mlflow.db and mlruns/ stay out of git/dvc**
They're local run outputs that regenerate every time training runs and are specific to my machine's experiment history, not code or a reusable dataset. Git shouldn't track them because they change constantly and would bloat the repo with meaningless binary/db diffs. DVC shouldn't track them either - DVC is for versioning meaningful reusable data artifacts (datasets), not ephemeral experiment logs; mlflow already handles tracking/versioning of runs itself.

**Q4 - calling set_experiment with a new name**
mlflow auto-creates the experiment. Confirmed by the terminal log: "Experiment with name 'food11' does not exist. Creating a new experiment." and the food11 experiment now shows up in the UI's experiment list alongside Default.

**Q5 - log_param vs log_metric**
log_param is a fixed value set once before training (hyperparameter) and doesn't change during the run. log_metric is a value produced during/after training that evolves over time (loss, accuracy per epoch), so it takes a step argument to record its value at each point in training - you need the trajectory over time, not just one final number.

**Q6 - where the model artifact lives**
Under the run's Artifacts tab in the mlflow UI, in a folder called "model". On disk it's stored under ./mlruns/<experiment_id>/<run_id>/artifacts/model/, since --default-artifact-root ./mlruns was set when starting the server.

**Q7 - best learning rate**
lr=0.0001 gave the best val_accuracy (~0.78 val_accuracy, 0.82 test_accuracy - the highest point in the scatter plot). lr=0.01 was dramatically worse (~0.15 test_accuracy). So no, higher lr is not always better - too high a learning rate causes the model to overshoot and barely learn, confirmed by train_loss staying near 2.4 for lr=0.01 vs near 0 for lower lr values.

**Q8 - parallel coordinates pattern**
Switching the metric from train_loss to val_accuracy shows lr has a much stronger effect than batch_size: the lr=0.01 line consistently sits low on val_accuracy regardless of batch_size, while lower lr values correlate with higher val_accuracy. batch_size (32 vs 64) shows a weaker, less consistent effect by comparison.

**Q9 - best run**
Sorting the runs table by val_accuracy descending, the best run is glamorous-fowl-913 (lr=0.0001, batch_size=32), with val_accuracy 0.7783 and test_accuracy 0.8157. Run ID: c25492a810cd4a2285d9357831dbee26