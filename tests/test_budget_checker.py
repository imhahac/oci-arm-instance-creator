import pytest
from unittest.mock import MagicMock
import oci
from oracle_arm_manager.budget_checker import BudgetChecker

@pytest.fixture
def mock_usage_client(mocker):
    return mocker.patch("oracle_arm_manager.budget_checker.UsageapiClient")

def test_check_usage_under_budget(mock_usage_client):
    mock_response = MagicMock()
    mock_item = MagicMock()
    mock_item.computed_amount = 0.05
    mock_response.data.items = [mock_item]
    
    # Setup mock to return the mock_response
    mock_client_instance = mock_usage_client.return_value
    mock_client_instance.request_summarized_usages.return_value = mock_response

    config_dict = {"tenancy": "t", "user": "u", "fingerprint": "f", "key_content": "k", "region": "r"}
    
    result = BudgetChecker.check_usage(config_dict, 0.1)
    
    assert result is True

def test_check_usage_over_budget(mocker, mock_usage_client):
    mocker.patch("oracle_arm_manager.budget_checker.send_notification")
    
    mock_response = MagicMock()
    mock_item = MagicMock()
    mock_item.computed_amount = 0.15 # over 0.1
    mock_response.data.items = [mock_item]
    
    mock_client_instance = mock_usage_client.return_value
    mock_client_instance.request_summarized_usages.return_value = mock_response

    config_dict = {"tenancy": "t", "user": "u", "fingerprint": "f"}
    
    result = BudgetChecker.check_usage(config_dict, 0.1)
    
    assert result is False

def test_check_usage_oci_error(mocker, mock_usage_client):
    mock_client_instance = mock_usage_client.return_value
    
    err = oci.exceptions.ServiceError(status=401, code="AuthError", headers={}, message="Auth failed")
    mock_client_instance.request_summarized_usages.side_effect = err

    config_dict = {"tenancy": "t"}
    
    # Should catch error and return True (pass-through)
    result = BudgetChecker.check_usage(config_dict, 0.1)
    
    assert result is True

def test_check_usage_general_exception(mocker, mock_usage_client):
    mock_client_instance = mock_usage_client.return_value
    mock_client_instance.request_summarized_usages.side_effect = Exception("Unknown Exception")

    config_dict = {"tenancy": "t"}
    
    # Should catch error and return True (pass-through)
    result = BudgetChecker.check_usage(config_dict, 0.1)
    
    assert result is True
