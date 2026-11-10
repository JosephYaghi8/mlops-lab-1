import argparse
import hashlib
import sys
from pathlib import Path

from PIL import Image

SPLITS = ["training", "validation", "evaluation"]
CLASSES = [
    "Bread", "Dairy product", "Dessert", "Egg", "Fried food",
    "Meat", "Noodles-Pasta", "Rice", "Seafood", "Soup", "Vegetable-Fruit",
]


def iter_images(root: Path):
    for split in SPLITS:
        split_dir = root / split
        if not split_dir.exists():
            continue
        for cls in CLASSES:
            cls_dir = split_dir / cls
            if not cls_dir.exists():
                continue
            for img_path in cls_dir.iterdir():
                if img_path.is_file():
                    yield split, cls, img_path


def check_class_folders(root: Path) -> bool:
    ok = True
    for split in SPLITS:
        split_dir = root / split
        if not split_dir.exists():
            print(f"FAIL: split folder missing: {split_dir}")
            ok = False
            continue
        found = {p.name for p in split_dir.iterdir() if p.is_dir()}
        expected = set(CLASSES)
        if found != expected:
            print(f"FAIL: {split} class folders mismatch "
                  f"(missing={expected - found}, extra={found - expected})")
            ok = False
    if ok:
        print("PASS: each split has exactly the 11 class folders")
    return ok


def check_images_valid(root: Path) -> bool:
    ok = True
    for _, _, img_path in iter_images(root):
        try:
            with Image.open(img_path) as img:
                img.load()
                if img.mode != "RGB" or img.size != (128, 128):
                    print(f"FAIL: {img_path} is not RGB 128x128 "
                          f"(mode={img.mode}, size={img.size})")
                    ok = False
        except (OSError, ValueError) as e:
            print(f"FAIL: {img_path} could not be opened: {e}")
            ok = False
    if ok:
        print("PASS: every image opens with PIL, is RGB, 128x128")
    return ok


def check_min_per_class(root: Path, min_per_class: int) -> bool:
    ok = True
    counts = {}
    for _, cls, _ in iter_images(root):
        counts[cls] = counts.get(cls, 0) + 1
    for cls in CLASSES:
        total = counts.get(cls, 0)
        if total < min_per_class:
            print(f"FAIL: class {cls} has only {total} images (< {min_per_class})")
            ok = False
    if ok:
        print(f"PASS: every class has at least {min_per_class} images")
    return ok


def check_no_cross_split_duplicates(root: Path) -> bool:
    ok = True
    seen = {}
    for split, _, img_path in iter_images(root):
        h = hashlib.md5(img_path.read_bytes()).hexdigest()
        if h in seen and seen[h][0] != split:
            print(f"FAIL: duplicate image across splits: {img_path} "
                  f"and {seen[h][1]} (hash {h})")
            ok = False
        else:
            seen[h] = (split, img_path)
    if ok:
        print("PASS: no image appears in two splits")
    return ok


def check_class_balance(root: Path, tau: float) -> bool:
    train_counts, val_counts = {}, {}
    for split, cls, _ in iter_images(root):
        if split == "training":
            train_counts[cls] = train_counts.get(cls, 0) + 1
        elif split == "validation":
            val_counts[cls] = val_counts.get(cls, 0) + 1

    train_total = sum(train_counts.values())
    val_total = sum(val_counts.values())
    if train_total == 0 or val_total == 0:
        print("FAIL: training or validation split is empty, cannot compare class shares")
        return False

    ok = True
    for cls in CLASSES:
        train_share = train_counts.get(cls, 0) / train_total
        val_share = val_counts.get(cls, 0) / val_total
        diff = abs(train_share - val_share)
        if diff > tau:
            print(f"FAIL: class {cls} share differs by {diff:.3f} (> tau={tau}) "
                  f"between training ({train_share:.3f}) and validation ({val_share:.3f})")
            ok = False
    if ok:
        print(f"PASS: class shares between training and validation are within tau={tau}")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_dir")
    parser.add_argument("--min-per-class", type=int, default=50)
    parser.add_argument("--tau", type=float, default=0.05)
    args = parser.parse_args()

    root = Path(args.dataset_dir)

    results = [
        check_class_folders(root),
        check_images_valid(root),
        check_min_per_class(root, args.min_per_class),
        check_no_cross_split_duplicates(root),
        check_class_balance(root, args.tau),
    ]

    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()