# coding: utf-8
import pytest
from datetime import datetime

from fastapi.testclient import TestClient
from openapi_server.models.get_current_time200_response import GetCurrentTime200Response


def test_get_current_time(client: TestClient):
    """Test case for get_current_time

    Get current time in JST
    """
    response = client.get("/time")
    assert response.status_code == 200

    # レスポンスの形式を確認
    data = response.json()
    assert "current_time" in data

    # 時刻の形式を確認
    try:
        datetime.fromisoformat(data["current_time"])
    except ValueError:
        pytest.fail("Invalid datetime format in response")


def test_get_current_time_response_format(client: TestClient):
    """Test case for response format of get_current_time

    Verify that the response follows the expected format
    """
    response = client.get("/time")
    data = response.json()

    # レスポンスモデルで検証
    try:
        GetCurrentTime200Response(**data)
    except Exception as e:
        pytest.fail(f"Response does not match expected format: {str(e)}")
