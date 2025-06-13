import cv2
import numpy as np
from ultralytics import YOLO
import os
from typing import List, Dict, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize YOLO model
model = None
try:
    model_path = os.path.join(os.path.dirname(__file__), '../yolo_model/best.pt')
    if os.path.exists(model_path):
        model = YOLO(model_path)
        logger.info(f"Successfully loaded YOLO model from {model_path}")
    else:
        logger.warning(f"YOLO model not found at {model_path}. Using fallback detection.")
except Exception as e:
    logger.error(f"Error loading YOLO model: {e}")
    logger.warning("Using fallback detection.")

def detect_fields(image_path: str) -> List[Dict[str, any]]:
    """
    Detect fields in a card image using YOLO model or fallback method.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        List of dictionaries containing field information:
        {
            'class': field class name,
            'confidence': detection confidence,
            'bbox': [x1, y1, x2, y2] coordinates
        }
    """
    # Read image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image at {image_path}")
    
    # If YOLO model is available, use it
    if model is not None:
        try:
            # Run YOLO detection
            results = model(image)
            
            # Process results
            detections = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Get box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    # Get class and confidence
                    class_id = int(box.cls[0].cpu().numpy())
                    confidence = float(box.conf[0].cpu().numpy())
                    
                    # Get class name
                    class_name = result.names[class_id]
                    
                    detections.append({
                        'class': class_name,
                        'confidence': confidence,
                        'bbox': [int(x1), int(y1), int(x2), int(y2)]
                    })
            
            return detections
        except Exception as e:
            logger.error(f"Error during YOLO detection: {e}")
            logger.warning("Falling back to basic detection")
    
    # Fallback: Basic field detection using image processing
    height, width = image.shape[:2]
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply threshold
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter and process contours
    detections = []
    for contour in contours:
        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)
        
        # Filter small contours
        if w < 50 or h < 20:  # Adjust these thresholds as needed
            continue
        
        # Calculate confidence based on contour area and position
        area = cv2.contourArea(contour)
        confidence = min(area / (width * height) * 10, 0.95)  # Normalize confidence
        
        detections.append({
            'class': 'text_field',  # Generic class name for fallback
            'confidence': confidence,
            'bbox': [x, y, x + w, y + h]
        })
    
    return detections

def draw_detections(image_path: str, output_path: str) -> None:
    """
    Draw detected fields on the image and save it.
    
    Args:
        image_path: Path to input image
        output_path: Path to save annotated image
    """
    # Read image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image at {image_path}")
    
    # Get detections
    detections = detect_fields(image_path)
    
    # Draw boxes and labels
    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        conf = det['confidence']
        class_name = det['class']
        
        # Draw box
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Draw label
        label = f"{class_name}: {conf:.2f}"
        cv2.putText(image, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    # Save image
    cv2.imwrite(output_path, image)

if __name__ == "__main__":
    # Test detection
    test_image = "data/raw/test_card.jpg"
    output_image = "data/processed/test_card_detected.jpg"
    draw_detections(test_image, output_image) 