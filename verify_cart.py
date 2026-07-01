from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_init_cart():
    response = client.get("/inventories/stockmovadj/cart/init")
    assert response.status_code == 200
    data = response.json()
    assert data["detail"]["success"] is True
    assert "session_id" in data["data"]
    print("Init Cart Test Passed")

if __name__ == "__main__":
    test_init_cart()
