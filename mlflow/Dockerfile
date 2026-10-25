FROM python:3.11-slim

RUN pip install --no-cache-dir mlflow

EXPOSE 5000

CMD ["mlflow", "server", \
     "--host", "0.0.0.0", "--port", "5000", \
     "--backend-store-uri", "sqlite:////mlflow-data/mlflow.db", \
     "--default-artifact-root", "/mlflow-data/mlruns", \
     "--allowed-hosts", "mlflow:5000,localhost:5000,127.0.0.1:5000"]