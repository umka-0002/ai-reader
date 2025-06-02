import os
import shutil
import random

def prepare_yolo_dataset(source_images_dir, source_labels_dir, output_dir, split_ratio=0.8):
    image_files = [f for f in os.listdir(source_images_dir) if f.endswith(".jpg") or f.endswith(".png")]
    random.shuffle(image_files)

    split_index = int(len(image_files) * split_ratio)
    train_files = image_files[:split_index]
    val_files = image_files[split_index:]

    for subset, files in [("train", train_files), ("val", val_files)]:
        img_out = os.path.join(output_dir, "images", subset)
        lbl_out = os.path.join(output_dir, "labels", subset)
        os.makedirs(img_out, exist_ok=True)
        os.makedirs(lbl_out, exist_ok=True)

        for file in files:
            shutil.copy(os.path.join(source_images_dir, file), os.path.join(img_out, file))
            label_file = file.rsplit(".", 1)[0] + ".txt"
            shutil.copy(os.path.join(source_labels_dir, label_file), os.path.join(lbl_out, label_file))