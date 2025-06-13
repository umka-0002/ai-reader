import os
import json
import requests
from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class IntegrationManager:
    def __init__(self):
        self.config_file = "config/integrations.json"
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load integration configurations"""
        if not os.path.exists(self.config_file):
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            return {}
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading integration config: {e}")
            return {}

    def _save_config(self):
        """Save integration configurations"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving integration config: {e}")

    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a service"""
        return self.config.get(service, {}).get('api_key')

    def set_api_key(self, service: str, api_key: str):
        """Set API key for a service"""
        if service not in self.config:
            self.config[service] = {}
        self.config[service]['api_key'] = api_key
        self._save_config()

class OCRService:
    def __init__(self, integration_manager: IntegrationManager):
        self.integration_manager = integration_manager
        self.api_key = self.integration_manager.get_api_key('ocr')
        
    def process_image(self, image_path: str) -> Dict:
        """Process image using OCR service"""
        if not self.api_key:
            raise ValueError("OCR API key not configured")
            
        try:
            # Example using a hypothetical OCR API
            url = "https://api.ocr-service.com/v1/process"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            with open(image_path, 'rb') as image_file:
                files = {'image': image_file}
                response = requests.post(url, headers=headers, files=files)
                response.raise_for_status()
                
            return response.json()
        except Exception as e:
            logger.error(f"Error processing image with OCR: {e}")
            raise

class LibrarySystem:
    def __init__(self, integration_manager: IntegrationManager):
        self.integration_manager = integration_manager
        self.api_key = self.integration_manager.get_api_key('library')
        
    def export_card(self, card_data: Dict) -> bool:
        """Export card to library system"""
        if not self.api_key:
            raise ValueError("Library system API key not configured")
            
        try:
            # Example using a hypothetical library system API
            url = "https://api.library-system.com/v1/cards"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, headers=headers, json=card_data)
            response.raise_for_status()
            
            return True
        except Exception as e:
            logger.error(f"Error exporting card to library system: {e}")
            return False

class NotificationService:
    def __init__(self, integration_manager: IntegrationManager):
        self.integration_manager = integration_manager
        self.api_key = self.integration_manager.get_api_key('notifications')
        
    def send_notification(self, user_email: str, subject: str, message: str) -> bool:
        """Send notification to user"""
        if not self.api_key:
            raise ValueError("Notification service API key not configured")
            
        try:
            # Example using a hypothetical notification API
            url = "https://api.notification-service.com/v1/send"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "to": user_email,
                "subject": subject,
                "message": message
            }
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            return True
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False

# Initialize integration manager
integration_manager = IntegrationManager()

# Initialize services
ocr_service = OCRService(integration_manager)
library_system = LibrarySystem(integration_manager)
notification_service = NotificationService(integration_manager) 