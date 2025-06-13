import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
from config import get_settings

settings = get_settings()

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)

def test_read_main(client):
    response = client.get("/")
    assert response.status_code == 200

def test_signup(client):
    response = client.post(
        "/signup",
        data={
            "username": "testuser",
            "password": "testpass123",
            "csrf_token": "test_token"
        }
    )
    assert response.status_code == 200
    assert "pending_approval.html" in response.text

def test_login(client):
    # First create a user
    client.post(
        "/signup",
        data={
            "username": "testuser",
            "password": "testpass123",
            "csrf_token": "test_token"
        }
    )
    
    # Try to login
    response = client.post(
        "/login",
        data={
            "username": "testuser",
            "password": "testpass123"
        }
    )
    assert response.status_code == 200
    assert "pending_approval.html" in response.text  # Because user is not approved yet 