import argparse

import mlflow
import mlflow.pytorch
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, models, transforms


def get_dataloaders(dataset_name: str, batch_size: int):
    data_dir = f"./data/food11_{dataset_name}" if dataset_name != "processed" else "./data/food11_processed"

    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    train_dir = f"{data_dir}/training"
    eval_dir = f"{data_dir}/evaluation"
    val_dir = f"{data_dir}/validation"

    train_dataset = datasets.ImageFolder(train_dir, transform=transform)
    eval_dataset = datasets.ImageFolder(eval_dir, transform=transform)
    val_dataset = datasets.ImageFolder(val_dir, transform=transform)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    eval_loader = DataLoader(eval_dataset, batch_size=batch_size, shuffle=False)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    return train_loader, eval_loader, val_loader, len(train_dataset.classes)


def build_model(num_classes: int):
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


def run_epoch(model, loader, criterion, optimizer, device, train: bool):
    model.train() if train else model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    context = torch.enable_grad() if train else torch.no_grad()
    with context:
        for inputs, labels in loader:
            inputs, labels = inputs.to(device), labels.to(device)

            if train:
                optimizer.zero_grad()

            outputs = model(inputs)
            loss = criterion(outputs, labels)

            if train:
                loss.backward()
                optimizer.step()

            total_loss += loss.item() * inputs.size(0)
            _, preds = torch.max(outputs, 1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)

    avg_loss = total_loss / total
    accuracy = correct / total
    return avg_loss, accuracy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["processed", "mini"], default="mini")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    mlflow.set_tracking_uri("http://127.0.0.1:5000")
    mlflow.set_experiment("food11")

    dataset_name = "processed_mini" if args.dataset == "mini" else "processed"
    train_loader, eval_loader, val_loader, num_classes = get_dataloaders(dataset_name, args.batch_size)

    model = build_model(num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    with mlflow.start_run():
        mlflow.log_params({
            "dataset": args.dataset,
            "epochs": args.epochs,
            "lr": args.lr,
            "batch_size": args.batch_size,
        })

        for epoch in range(args.epochs):
            train_loss, _ = run_epoch(model, train_loader, criterion, optimizer, device, train=True)
            val_loss, val_accuracy = run_epoch(model, val_loader, criterion, optimizer, device, train=False)

            mlflow.log_metric("train_loss", train_loss, step=epoch)
            mlflow.log_metric("val_loss", val_loss, step=epoch)
            mlflow.log_metric("val_accuracy", val_accuracy, step=epoch)

            print(f"Epoch {epoch+1}/{args.epochs} - train_loss: {train_loss:.4f} - val_loss: {val_loss:.4f} - val_accuracy: {val_accuracy:.4f}")

        test_loss, test_accuracy = run_epoch(model, eval_loader, criterion, optimizer, device, train=False)
        mlflow.log_metric("test_accuracy", test_accuracy)
        print(f"Final test_accuracy: {test_accuracy:.4f}")

        sample_input = next(iter(train_loader))[0][:1].to(device)
        mlflow.pytorch.log_model(model, "model", input_example=sample_input.cpu().numpy(), serialization_format="pickle")


if __name__ == "__main__":
    main()
