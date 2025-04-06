# coding: utf-8

from fastapi.testclient import TestClient


from openapi_server.models.get_current_time200_response import GetCurrentTime200Response  # noqa: F401


def test_get_current_time(client: TestClient):
    """Test case for get_current_time

    Get current time in JST
    """

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/time",
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

