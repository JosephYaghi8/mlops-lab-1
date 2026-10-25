# Lab 4 Answers

**Note on terminology:** the lab text refers to the deprecated `Staging`/`Production` model stages. My registry uses the `champion` alias system instead (the modern replacement, and what Lab 3 was built on), so every question below that references "Staging" is answered in terms of the `champion` alias.

## Q1 — No volume mounted

Tested directly: ran the mlflow image with no volume, registered nothing, stopped and removed the container, started a fresh one from the same image. The UI came up completely empty — no experiments, no registered models. Everything mlflow writes (`mlflow.db` and `mlruns/`) goes into the container's writable layer by default, and that layer is destroyed the moment the container is removed (`docker rm`, or implicitly by `docker compose down` recreating it). The data was never "lost" so much as it was never anywhere durable to begin with.

## Q2 — Named volume vs bind mount

A named volume is preferred here because it doesn't tie the container to a specific host filesystem layout or path. A bind mount would technically also persist the data, but it requires a real, existing folder on the host at a path you specify, and portability breaks the moment you move the project to another machine or OS (this is exactly the Windows-absolute-path artifact bug I hit in Lab 3). A bind mount is better suited to files you want to edit directly from the host (like source code); a named volume is better for data a service owns and manages itself, like a database or artifact store, where Docker handles the storage location for you.

## Q3 — Why `http://mlflow:5000` resolves now

In Lab 3, the inference container and my host mlflow server were on two separate, unrelated networks — the container had no name-based way to reach a process running directly on the host, so `host.docker.internal` (a special DNS entry Docker Desktop provides for exactly this) or `--network host` were needed instead. In Compose, all three services are attached to the same private network that Compose creates automatically, and Compose runs an embedded DNS server on that network that resolves each service's name (`mlflow`, `inference`, `frontend`) to that service's container IP. `http://mlflow:5000` works because `mlflow` is simply the other container's service name on the same network, not because of any special-casing — the exact same mechanism makes `http://inference:8000` resolve for the frontend.

I also hit this firsthand as a real failure: mlflow's built-in Host-header security middleware initially rejected requests with `403 Invalid Host header — possible DNS rebinding attack detected`, because by default it only allows `localhost`-style hosts. The fix was adding `--allowed-hosts mlflow:5000,localhost:5000,127.0.0.1:5000` to the mlflow server's CMD — DNS resolution and host-header allow-listing are two separate checks, and both have to pass.

## Q4 — Why `INFERENCE_URL` is an env var, not hardcoded

If `http://inference:8000` were hardcoded into `app.py`, the frontend image would only ever work inside this specific Compose stack, where a service literally named `inference` exists on the same network. Run that same image on its own with `docker run` — for local testing, a demo, or a different deployment where the backend has a different name or is reached another way — and the hardcoded hostname simply wouldn't resolve. Reading it from an environment variable with a sensible default (`http://127.0.0.1:8000`, useful for running the frontend locally against a locally-running API) keeps the image itself generic; only the environment it's run in decides what it talks to.

## Q5 — Why `inference` has no published port

`inference` has no `ports:` entry because nothing outside the Compose network ever needs to reach it directly — the only client it has is `frontend`, which is itself inside the same Compose network. Publishing a port maps a container port to the host machine, which is only necessary when something *outside* Docker (your browser, `curl` from your terminal) needs to reach that service. `frontend` reaches `inference` over the internal Compose network via Compose's DNS, at `http://inference:8000` — the exact mechanism from Q3 — with no host involvement at all. `mlflow` and `frontend` are published because a human needs to open the mlflow UI and the Streamlit page directly in a browser.

## Q6 — `depends_on` is start order only, not readiness

Confirmed this firsthand, repeatedly, while debugging this lab. `depends_on: [mlflow]` only guarantees Compose starts the `mlflow` container before `inference`; it does not wait for the mlflow server process inside that container to finish booting and start accepting connections. My `serve.py` loads the model at *import time* (module level, before the FastAPI app is even constructed), so if mlflow isn't ready yet, the `mlflow.pyfunc.load_model(...)` call fails immediately with a connection or REST error, the Python process raises an unhandled exception, and the whole container exits — `docker compose logs inference` shows a full traceback ending in the failed request, and since there's no `restart:` policy set, the container just stays exited rather than retrying. I saw this exact failure mode (crash-and-stay-exited) multiple times when a registered-model lookup hit mlflow's registry before the write had fully landed, or before a volume had the right data. A production-grade fix would be a retry loop or a `restart: on-failure` policy; this lab's compose file has neither, since it's meant to illustrate the problem, not solve it.

## Q7 — `docker compose ps`
NAME SERVICE PORTS
mlops-lab-1-frontend-1 frontend 0.0.0.0:8501->8501/tcp
mlops-lab-1-inference-1 inference 8000/tcp
mlops-lab-1-mlflow-1 mlflow 0.0.0.0:5000->5000/tcp


Matches expectations exactly: `frontend` and `mlflow` both show a host-mapped port (`0.0.0.0:PORT->PORT/tcp`), and `inference` shows only the bare container port `8000/tcp` with no host mapping — consistent with `docker-compose.yml`, where only `mlflow` and `frontend` declare a `ports:` section.

## Q8 — Promoting a new model version

Registered a second model version (trained with different hyperparameters, `lr=0.0001` instead of `0.001`, substantially better accuracy: 82% vs 51% test accuracy) and reassigned the `champion` alias to it. Re-uploaded the identical test image to the frontend before and after: before, "Bread (92.4%)"; after a bare `docker compose restart inference`, "Bread (95.8%)" — same predicted label but a different confidence score, proving the underlying model weights actually changed, not just a UI refresh. The single command that picks up the new `champion` version without rebuilding any image is:

```bash
docker compose restart inference
```

## Q9 — Why `restart` alone works, no rebuild

`restart` works without a rebuild because nothing about *which* model to load is baked into the image at build time — the image only contains the application code (`serve.py`) and its Python dependencies. The actual model weights are fetched at container *startup*, over the network, from the mlflow server, via `mlflow.pyfunc.load_model("models:/food11@champion")`. Since `champion` is an alias that can be reassigned to any version in the registry, and the lookup happens fresh every time the process starts, a plain restart (new process, same image) re-runs that lookup and picks up whatever version the alias currently points to. This is exactly the separation MLOps is going for: code/environment (image, rebuilt rarely) versus model artifact (registry, changed frequently) are decoupled, so promoting a model is a registry operation plus a cheap restart, not a rebuild-and-redeploy.

## Q10 — Persistence across `down`/`up`

Tested both cases directly.

`docker compose down` followed by `docker compose up`: the registered model and `champion` alias were **still there** — `inference` started cleanly with no errors and served predictions from the same model. `down` removes the containers and the network but leaves the named volume untouched, so the next `up` reattaches to the same volume with all its data intact.

`docker compose down -v` followed by `docker compose up`: completely different result. `down -v` explicitly removed the named volume itself (`docker compose down -v` output showed `Volume mlops-lab-1_mlflow-data Removed`), so the next `up` created a **brand-new, empty volume**. `inference` immediately crash-exited again with the same `RESOURCE_DOES_NOT_EXIST: Registered Model with name=food11 not found` error from the very start of this lab — proving the registry, the database, and every registered model version were gone, not just unavailable. The `-v` flag is the difference between "stop the services" and "delete their persistent state."

## Q11 — What Docker Compose can't give you

Docker Compose is fundamentally single-machine orchestration — it has no concept of a cluster of machines, so anything requiring work to be spread across or survive the loss of a physical machine is out of scope for it entirely.

- **Replicas behind a load balancer for `inference`**: Compose can start multiple instances of a service (`docker compose up --scale inference=3`), but it provides no built-in load balancer to distribute traffic across those replicas, and no mechanism to add or remove replicas automatically based on load. You'd need an external reverse proxy (nginx, Traefik) in front of them at minimum, and for real elasticity, a proper orchestrator.
- **mlflow surviving a machine failure**: Compose's named volumes are local to the single Docker host they're created on — there's no replication, no automatic failover, nothing. If that machine goes down, the volume and everything in it goes down with it. Surviving a machine failure needs the mlflow server's state (the SQLite DB and artifact store) moved off that single machine entirely — a managed/replicated database instead of SQLite, and object storage like S3 instead of a local volume — plus an orchestrator that can reschedule the mlflow container onto a different healthy machine (and route traffic to it) when the original one dies.

In short: what's missing is everything **Kubernetes** (or a managed equivalent) provides — multi-node scheduling, service discovery across machines, horizontal autoscaling, a real load balancer, and storage that isn't bound to one host's disk. Compose is the right tool for "run these containers together on one machine"; it was never meant to solve distributed, fault-tolerant deployment.