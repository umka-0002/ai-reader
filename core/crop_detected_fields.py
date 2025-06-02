from ultralytics import YOLO
import cv2
import os

def crop_detected_fields(image_path, model_path, output_dir):
    model = YOLO(model_path)
    results = model(image_path)[0]
    image = cv2.imread(image_path)

    basename = os.path.splitext(os.path.basename(image_path))[0]
    os.makedirs(output_dir, exist_ok=True)

    for i, box in enumerate(results.boxes):
        cls = int(box.cls[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        crop = image[y1:y2, x1:x2]
        crop_name = os.path.join(output_dir, f"{basename}_cls{cls}_{i}.jpg")
        cv2.imwrite(crop_name, crop)
