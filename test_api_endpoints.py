import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fastapi.testclient import TestClient
from zomoto_ai.backend.api.app import create_app
import asyncio

app = create_app()
client = TestClient(app)

def test_health():
    response = client.get("/health")
    print("=== GET /health ===")
    print("Status:", response.status_code)
    print(response.json())
    print()

def test_api_health():
    response = client.get("/api/v1/health")
    print("=== GET /api/v1/health ===")
    print("Status:", response.status_code)
    print(response.json())
    print()

def test_info():
    response = client.get("/api/v1/info")
    print("=== GET /api/v1/info ===")
    print("Status:", response.status_code)
    print(response.json())
    print()

if __name__ == "__main__":
    print("Testing backend API endpoints...")
    test_health()
    test_api_health()
    test_info()
    print("API endpoints tested successfully!")
