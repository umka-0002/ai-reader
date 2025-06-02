from ultralytics import YOLO

def train_model(data_yaml, model_path="yolov8n.pt", epochs=50, imgsz=640, project_dir="yolo_model/runs"):
    model = YOLO(model_path)
    model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        project=project_dir,
        name="card_detector"
    )

if __name__ == "__main__":
    train_model("yolo_model/data.yaml")