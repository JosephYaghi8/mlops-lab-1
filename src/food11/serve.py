import io
import os

import mlflow.pyfunc
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image
from torchvision import transforms

import mlflow

CATEGORIES = [
    "Bread", "Dairy product", "Dessert", "Egg", "Fried food",
    "Meat", "Noodles-Pasta", "Rice", "Seafood", "Soup", "Vegetable-Fruit",
]

TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
mlflow.set_tracking_uri(TRACKING_URI)

app = FastAPI()

_original_torch_load = torch.load


def _cpu_torch_load(*args, **kwargs):
    kwargs.setdefault("map_location", "cpu")
    return _original_torch_load(*args, **kwargs)


torch.load = _cpu_torch_load

model = None

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


@app.on_event("startup")
def load_model():
    global model
    if os.environ.get("SKIP_MODEL"):
        return
    model = mlflow.pyfunc.load_model("models:/food11@champion")


@app.get("/health")
def health():
    return {"status": "ok"}


_file_param = File(...)


@app.post("/predict")
async def predict(file: UploadFile = _file_param):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")
    input_tensor = transform(image).unsqueeze(0).numpy()

    output = model.predict(input_tensor)
    output_tensor = torch.tensor(output)
    probs = torch.softmax(output_tensor, dim=1)
    confidence, predicted_idx = torch.max(probs, dim=1)

    return {
        "category": CATEGORIES[predicted_idx.item()],
        "confidence": confidence.item(),
    }