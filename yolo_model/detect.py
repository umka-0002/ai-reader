from ultralytics import YOLO

def detect_cards(model_path, source_dir, save_dir="yolo_model/inference"):
    model = YOLO(model_path)
    model.predict(
        source=source_dir,
        save=True,
        save_txt=True,
        project=save_dir,
        name="detections"
    )

if __name__ == "__main__":
    detect_cards("models/yolov8_card_best.pt", "data/raw")