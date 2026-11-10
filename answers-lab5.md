# Lab 5 Answers

**Q1 — Why is it bad for a unit test to load the real model from MLflow? List two ways the test could fail even though the code is correct.**

Because it couples a fast, deterministic unit test to a slow, external, stateful system - the test is no longer testing *your logic*, it's testing infrastructure availability.

1. The MLflow server isn't running (or isn't reachable from the CI runner at all - it lives on a laptop). `serve.py` is perfectly correct, but the test fails on a connection error.
2. The `champion` alias doesn't exist yet, or points at a version whose artifact was deleted/moved. `load_model("models:/food11@champion")` throws, even though neither `serve.py` nor the model's logic has a bug - it's a registry-state problem, not a code problem.

(A third, real one we hit ourselves: no GPU on the runner, and `torch.load` defaulting to CUDA - exactly the device-mismatch error (`torch.cuda.FloatTensor` vs CPU tensor) that showed up in our own `mlflow.register_model` warnings during this lab, unrelated to serving code correctness.)

**Q2 — What does `test_predict_returns_valid_json` prove, and what does it *not* prove?**

Proves: the `/predict` endpoint correctly accepts a multipart file upload, decodes it with PIL, runs it through the exact preprocessing pipeline (resize/normalize/transform), calls whatever object sits in the module-level `model` variable, converts the raw output through softmax, picks the argmax, and serializes it into the right JSON shape (`category` as a string from `CATEGORIES`, `confidence` as a float in `[0, 1]`) - i.e., all the *plumbing* around the model is correct.

Does **not** prove: that the real trained model is accurate, that its actual output shape/format matches what `FakeModel` assumes, or anything at all about model quality. A model that is 10% accurate would pass this test identically, because the model itself is replaced.

**Q3 — Which check caught the injected train/eval duplicate? Why is it more dangerous than a corrupted image, even though the corrupted image crashes training and the duplicate doesn't?**

Check 4 - the cross-split MD5 hash check - caught it (confirmed directly: `check_no_cross_split_duplicates` failed on the hash-matched pair, all other checks passed).

A corrupted image fails loudly and immediately - PIL throws on `img.load()`, training crashes, you find out the same minute. A train/eval duplicate fails *silently*: training succeeds, evaluation succeeds, and the reported test accuracy is inflated because the model has effectively memorized a sample it's being "tested" on. Nothing crashes, nothing looks wrong - you ship a model that you believe is more accurate than it actually is, and you'd only ever find out in production. Silent correctness failures are strictly worse than loud crashes because nothing forces you to notice them.

**Q4 — CI can't see your data (it's in DVC). Where should `validate_data.py` run to still protect you? Give two places.**

1. **Locally, before the data ever leaves your machine** - as a required step right after `data.py`/`process_split` runs and before `dvc add`/`dvc push`/`git commit` of the `.dvc` pointer. This is the actual gate for new or changed data, since it's the only place that has the data without needing network access to the DVC remote.
2. **In a dedicated CI job that pulls the data itself**, if your DVC remote is network-reachable from the runner - i.e., add remote credentials as repo secrets, run `dvc pull` as the job's first step, then run `validate_data.py` against the pulled folder. This turns the contract check into an actual, enforced CI gate rather than something that only runs if a human remembers to run it locally.

**Q5 — `smoke` has `needs: test`. What happens to it if a unit test fails? What would happen without `needs`?**

With `needs: test`: if `test` fails, `smoke` is skipped entirely - it never starts. GitHub Actions treats the dependency as "don't bother" once the thing it depends on has failed.

Without `needs`: `test` and `smoke` would run in parallel, independently. `smoke` would go ahead and build the Docker image and run the health-check against known-broken code, wasting runner time on a build that's pointless the moment `test` fails - and worse, if a later `push` job only depended on `smoke` (not transitively on `test`), a broken commit's image could still get built and pushed to the registry as long as the broken code happened not to break the container's startup/health endpoint.

**Q6 — How long did the whole run take? Compare to a second (empty-commit) run. Which step got faster, and why?**

First real 3-job run: `test` 22s, `smoke` 1m43s, `push` 3m59s (total end-to-end ~6m). Comparing just `test`+`smoke` across two runs (first clean run vs. an empty-commit rerun): `test` 22s -> 21s, `smoke` 1m43s -> 1m48s, total 2m12s -> 2m16s.

Honest answer: essentially **nothing got meaningfully faster** - the two runs are within normal run-to-run noise. Two reasons: (1) `enable-cache: true` on `setup-uv` caches the resolved dependency downloads, but this project's `uv sync` is already small/fast, so there's no large download to amortize away - the ~20s for the `test` job is dominated by runner boot and checkout, not dependency installation; (2) the `smoke` job's `docker build` has **no cache configured at all** (`cache-from`/`cache-to` only appear later, on the `push` job) - every runner is a fresh VM with an empty Docker layer cache, so `docker build -t food11-api:ci .` rebuilds every layer from scratch on every single run regardless of what happened last time. That absence of caching in `smoke` is itself a deliberate thing worth noticing, not a bug.

**Q7 — Why tag with the commit SHA rather than `latest`? Give a concrete scenario where `latest` causes two machines to run different code.**

Because `latest` is a mutable, overwritten label - it answers "what's the newest build" but not "what code is actually running right now," and there's no way to pin or reproduce a specific past state from it.

Concrete scenario: Machine A pulls `ghcr.io/josephyaghi8/mlops-lab-1:latest` on Monday, right after commit `X` lands on `main` and gets pushed as `latest`. On Wednesday, commit `Y` (say, a change to the preprocessing pipeline) lands on `main` and overwrites `latest`. Machine B, which hadn't pulled since before Monday, pulls `latest` on Thursday and gets `Y`. A and B are now running genuinely different code under the identical tag name, with no way to tell from the tag alone which commit either of them is running, and no way to roll A back to exactly what it had before if `Y` turns out to be broken. Tagging by the full commit SHA (as we verified: the 40-character SHA, not GitHub's displayed 7-character short form) makes the tag immutable and traceable - `ghcr.io/.../repo:<sha>` is forever exactly commit `<sha>`, so pulling it at any point in time, on any machine, gets byte-identical code.

**Q8 — Why does the `push` job declare `permissions:` explicitly? What could a compromised step do with a token with write access to everything?**

By default, the auto-generated `GITHUB_TOKEN` can have broad permissions (write access to contents, issues, pull requests, etc., depending on the repo/org's default token policy) - far more than this job actually needs. Declaring `permissions: {contents: read, packages: write}` explicitly scopes the token down to the minimum required: read the repo to build the image, write to the package registry to push it. Nothing else.

If a step were compromised (a malicious or hijacked third-party `uses:` action, or a poisoned dependency pulled in during `docker build`) and the token had full write access, it could push arbitrary commits directly to the repo, delete branches, rewrite or delete releases and other packages, tamper with issues/PRs to cover its tracks, or even modify repo settings including branch protection itself. Scoping the token down to `contents: read, packages: write` means the worst a compromised step in *this* job can do is push a bad image to the registry - it can't touch the repo's history, settings, or anything else.

**Q9 — What does the PR page show? Could you still merge? What does that change for a team vs. "everyone tests locally before pushing"?**

With the intentionally broken test pushed on a branch, the PR page showed `test` and `smoke` both failing, explicitly labeled "Required," and the merge button greyed out/disabled - the only way around it was an admin-only "bypass branch protection" checkbox, which we did not use. After fixing the test and pushing again, both checks went green and the merge button became active; merge succeeded (confirmed via `git pull` showing the fast-forward to the merge commit).

Compared to "everyone runs tests on their laptop before pushing": this removes dependence on individual discipline and trust entirely. It doesn't matter if a teammate forgot to run the tests, has a different local environment where a bug happens not to reproduce, or is in a hurry and skips it - the platform itself refuses the merge until the checks genuinely pass on a clean, standardized runner. It converts "tests should have passed" from a social expectation into a structural fact, with a visible, auditable record of exactly which checks ran and passed before any given commit reached `main`.

**Q10 — For each candidate, what did the gate decide, and with which numbers? How many accuracy points does `2*se` represent for your test-set size?**

Champion throughout: version 1, `test_accuracy = 0.8184`. Test split size `n = 1096`, giving `se = sqrt(0.8184 * (1 - 0.8184) / 1096) = 0.0116`, and a promotion threshold of `0.8184 + 2*0.0116 = 0.8417`.

- **Candidate A** (`lr=0.00001`, 3 epochs - deliberately under-trained): `test_accuracy = 0.5255`. Far below the 0.8417 threshold -> gate set `challenger`, champion stayed at v1.
- **Candidate B** (`lr=0.0001`, 8 epochs - "best settings"): `test_accuracy = 0.8212`, actually *above* the champion's raw 0.8184. Still below the 0.8417 threshold -> gate again set `challenger`, champion stayed at v1.

`2*se = 0.0233`, i.e. about **2.3 accuracy points**. Candidate B's raw improvement over the champion was only +0.3 points - well inside the noise band the test set can support at `n=1096`. The gate correctly treated that as statistically indistinguishable from no improvement, rather than promoting on what could easily be test-set luck.

**Q11 — `promote.py` needs your MLflow server, which GitHub's cloud runners can't reach. Name two ways to make it run automatically after training.**

1. **Host MLflow somewhere network-reachable from GitHub's runners** - either self-host the MLflow server on a machine with a stable public address, or use a hosted MLflow provider (DagsHub offers a per-repo hosted MLflow server, as the lab hints). Point both the training script's and the CI workflow's `MLFLOW_TRACKING_URI` (with credentials in repo secrets) at that same remote server, and add `promote.py --version <n>` as a workflow step after training completes in CI.
2. **Use a self-hosted GitHub Actions runner** on the same machine/network where MLflow already lives (instead of `runs-on: ubuntu-latest`). The workflow still triggers from GitHub on a push/schedule, but the job actually executes on your own hardware, where `http://127.0.0.1:5000` (or your LAN address) is directly reachable - no need to move MLflow anywhere.

**Q12 — Pipeline diagram.**

See `lab/lab5.md`.
