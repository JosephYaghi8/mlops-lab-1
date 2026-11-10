import os
import shutil
from pathlib import Path

from PIL import Image

CLASSES = [
    "Bread", "Dairy product", "Dessert", "Egg", "Fried food",
    "Meat", "Noodles-Pasta", "Rice", "Seafood", "Soup", "Vegetable-Fruit",
]

SPLITS = ["training", "evaluation", "validation"]
RAW_DIR = Path("./data/food11_raw")
PROCESSED_DIR = Path("./data/food11_processed")
MINI_DIR = Path("./data/food11_processed_mini")
IMG_SIZE = 128
MINI_LIMIT = 100


def category_from_filename(filename: str) -> str:
    """'3_120.jpg' -> 'Egg'"""
    cat_index = int(filename.split("_")[0])
    return CLASSES[cat_index + 1]


def resize_image(img: "Image.Image", size: int = IMG_SIZE) -> "Image.Image":
    """Returns an RGB image of size x size."""
    return img.convert("RGB").resize((size, size))


def process_split(split: str):
    src_dir = RAW_DIR / split
    if not src_dir.exists():
        print(f"Skipping {split}: {src_dir} not found")
        return

    mini_counts = {cat: 0 for cat in CLASSES}

    for fname in os.listdir(src_dir):
        fpath = src_dir / fname
        if not fpath.is_file():
            continue

        # filename format: "<category_index>_<n>.jpg"
        try:
            category = category_from_filename(fname)
        except (ValueError, IndexError):
            print(f"Skipping unrecognized file: {fname}")
            continue

        out_dir = PROCESSED_DIR / split / category
        out_dir.mkdir(parents=True, exist_ok=True)

        with Image.open(fpath) as img:
            img = resize_image(img)
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