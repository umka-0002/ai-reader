import os
import secrets
from pathlib import Path

def generate_secret_key():
    return secrets.token_hex(32)

def create_env_file():
    env_path = Path(__file__).parent / '.env'
    
    # Check if .env already exists
    if env_path.exists():
        print(".env file already exists. Do you want to overwrite it? (y/n)")
        if input().lower() != 'y':
            print("Operation cancelled.")
            return
    
    # Generate secure keys
    secret_key = generate_secret_key()
    csrf_key = generate_secret_key()
    
    # Create .env content
    env_content = f"""# Security
secret_key={secret_key}
csrf_secret_key={csrf_key}
admin_password=admin123  # Change this in production!

# Telegram Bot
bot_token=7490482214:AAGw84na2tfbHvo3onjSlTyjIzQLxIlwyzI

# Azure OpenAI
azure_openai_api_key=1NQqBkBk0psCS1ZttrbX9TJx...CHYHv6XJ3w3AAAAACOGk75G
azure_openai_endpoint=https://kitep-mbg8rzqy-e....services.ai.azure.com/
azure_openai_deployment_name=gpt-4o
azure_openai_api_version=2024-11-20

# Database
database_url=sqlite:///./test.db  # Change this in production!

# File Upload
max_upload_size=5242880  # 5MB in bytes

# Session
session_cookie_name=session
session_cookie_secure=true
session_cookie_httponly=true
session_cookie_samesite=Lax
session_expire_minutes=30

# CORS
cors_origins=["http://localhost:8000"]
"""
    
    # Write to .env file
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print(f".env file created at {env_path}")
    print("Please review and modify the values as needed.")

if __name__ == "__main__":
    create_env_file() 