from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
API_KEY = "bank_alpha_secret_key_991"

def test_unauthorized_batch_access():
    response = client.post("/v1/batch-evaluate", json={"transactions": []})
    assert response.status_code == 401

def test_batch_evaluation_flow():
    headers = {"x-api-key": API_KEY}
    payload = {
        "transactions": [
            {
                "transaction_id": "TXN_BATCH_101",
                "cardholder_id": "USER_01",
                "amount": 1200.0,
                "distance_from_home": 10.5,
                "velocity_1h": 1,
                "velocity_24h": 2,
                "is_international": 0
            }
        ]
    }
    response = client.post("/v1/batch-evaluate", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_processed"] == 1
    assert "shap_explanation" in data["evaluations"][0]