import os
import shutil
from pathlib import Path
from PIL import Image

CATEGORIES = [
    "Bread", "Dairy product", "Dessert", "Egg", "Fried food",
    "Meat", "Noodles-Pasta", "Rice", "Seafood", "Soup", "Vegetable-Fruit",
]

SPLITS = ["training", "evaluation", "validation"]
RAW_DIR = Path("./data/food11_raw")
PROCESSED_DIR = Path("./data/food11_processed")
MINI_DIR = Path("./data/food11_processed_mini")
IMG_SIZE = (128, 128)
MINI_LIMIT = 100


def process_split(split: str):
    src_dir = RAW_DIR / split
    if not src_dir.exists():
        print(f"Skipping {split}: {src_dir} not found")
        return

    mini_counts = {cat: 0 for cat in CATEGORIES}

    for fname in os.listdir(src_dir):
        fpath = src_dir / fname
        if not fpath.is_file():
            continue

        try:
            cat_index = int(fname.split("_")[0])
            category = CATEGORIES[cat_index]
        except (ValueError, IndexError):
            print(f"Skipping unrecognized file: {fname}")
            continue

        out_dir = PROCESSED_DIR / split / category
        out_dir.mkdir(parents=True, exist_ok=True)

        with Image.open(fpath) as img:
            img = img.convert("RGB").resize(IMG_SIZE)
            img.save(out_dir / fname)

        if mini_counts[category] < MINI_LIMIT:
            mini_out_dir = MINI_DIR / split / category
            mini_out_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(out_dir / fname, mini_out_dir / fname)
            mini_counts[category] += 1

    print(f"Done processing {split}")


def main():
    for split in SPLITS:
        process_split(split)


if __name__ == "__main__":
    main()
