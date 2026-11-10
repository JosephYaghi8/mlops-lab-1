# Lab 5 Pipeline Diagram

From `git push` to a running container, and where each version is decided.
+-----------------------------------------------------------------------+
| HUMAN: write code, git push                                           |
|   -> commit SHA is fixed here. This is where the CODE VERSION is      |
|      decided - everything downstream is keyed off this one SHA.       |
+------------------------------------+----------------------------------+
                                     | (push / pull_request event)
                                     v
+-----------------------------------------------------------------------+
| AUTOMATIC: GitHub Actions triggers ci.yml                              |
|                                                                        |
|  +-------------+     +--------------+     +---------------------+     |
|  |  test job   | --> |  smoke job   | --> |  push job           |     |
|  | ruff + lint |     | docker build |     | (main branch only)  |     |
|  | uv run      |     | run + /health|     | build + push image  |     |
|  | pytest      |     | poll loop    |     | to ghcr.io tagged   |     |
|  +-------------+     +--------------+     | with the commit SHA |     |
|                                            +----------+-----------+   |
+-------------------------------------------------------|----------------+
                                                         |
                                           (image now sits in ghcr.io,
                                            immutably tagged by SHA -
                                            this is the CODE VERSION
                                            that will actually run)
                                                         v
+-----------------------------------------------------------------------+
| HUMAN: branch protection gate on main                                  |
|   PR required, test + smoke must be green before merge is allowed.    |
|   Broken test on a branch -> PR blocked, merge button greyed out      |
|   (verified directly - admin-bypass checkbox is the only way around   |
|   it). This is enforcement, not automation: a human still opens,      |
|   reviews and clicks merge.                                           |
+-----------------------------------------------------------------------+

   (separate, parallel track - the MODEL is versioned independently)

+-----------------------------------------------------------------------+
| HUMAN: kicks off a training run locally (uv run python train.py)      |
|   -> logs params/metrics/artifact to MLflow, registers a new model    |
|      version                                                          |
+------------------------------------+----------------------------------+
                                     v
+-----------------------------------------------------------------------+
| HUMAN (manually invoked today - see Q11): uv run promote.py --version |
|   Reads candidate's and champion's test_accuracy, computes            |
|   2*se threshold, decides promote vs. challenger, tags the decision.  |
|   -> This is where the MODEL VERSION is decided (which registry       |
|      version gets the champion alias).                                |
+------------------------------------+----------------------------------+
                                     v
+-----------------------------------------------------------------------+
| AUTOMATIC at container startup: serve.py's FastAPI startup hook       |
|   calls mlflow.pyfunc.load_model("models:/food11@champion")           |
|   -> pulls in whichever version promote.py most recently aliased.     |
+------------------------------------+----------------------------------+
                                     v
+-----------------------------------------------------------------------+
| Running container serving /predict - code pinned by image SHA,        |
| model pinned by champion alias. The two version axes are fully        |
| decoupled: you can ship new code without retraining, and promote a    |
| new model without a code change or redeploy of the image itself       |
| (only a container restart to re-resolve the alias).                   |
+-----------------------------------------------------------------------+
**Automatic**: everything inside `ci.yml` (test -> smoke -> push), branch-protection *enforcement* (the block itself), and the alias resolution at container startup.

**Still human**: writing/pushing code, opening and merging the PR, kicking off training runs, and invoking `promote.py` (Q11 covers why that last one isn't automated yet - it needs network access to the MLflow server that GitHub's cloud runners don't have).