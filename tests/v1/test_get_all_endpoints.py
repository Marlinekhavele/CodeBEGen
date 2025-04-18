from unittest.mock import patch

from conftest import TEST_BASE_URL


@patch(
    "app.api.v1.services.get_all_endpoints.GetAllEndpoints.get_all_endpoints_from_repo"
)
def test_get_all_endpoints_empty(mock_get_all_endpoints, client):
    """
    Test case when no endpoints exist in the database.
    """
    # Mock return value as an empty list
    mock_get_all_endpoints.return_value = []

    response = client.get(f"{TEST_BASE_URL}/api/v1/projects/12345/endpoints")

    mock_get_all_endpoints.assert_called_once()
    assert response.status_code == 200
    expected_response = {
        "status_code": 200,
        "success": True,
        "message": "Endpoint Retrieved Succesfully",
        "data": [],
    }
    assert response.json() == expected_response


@patch(
    "app.api.v1.services.get_all_endpoints.GetAllEndpoints.get_all_endpoints_from_repo"
)
def test_get_all_endpoints_with_data(mock_get_all_endpoints, client):
    """
    Test case when the database contains endpoints.
    """
    # Mock return value with actual dictionaries (not Pydantic models)
    mock_get_all_endpoints.return_value = [
        {"path": "get_users", "method": "GET"},
        {"path": "create_user", "method": "POST"},
    ]

    response = client.get(f"{TEST_BASE_URL}/api/v1/projects/12345/endpoints")

    mock_get_all_endpoints.assert_called_once()
    assert response.status_code == 200
    # The response should contain the transformed data
    response_data = response.json()
    assert response_data["status_code"] == 200
    assert response_data["success"] is True
    assert response_data["message"] == "Endpoint Retrieved Succesfully"

    # Check that the data contains the expected endpoints
    assert len(response_data["data"]) == 2
    assert {"path": "get_users", "method": "GET"} in response_data["data"]
    assert {"path": "create_user", "method": "POST"} in response_data["data"]
