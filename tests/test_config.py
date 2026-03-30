import os
import pytest
from oracle_arm_manager.config import get_env, validate_required_env, load_config, ConfigurationError

def test_get_env_standard():
    os.environ["TEST_VAR"] = "hello"
    assert get_env("TEST_VAR") == "hello"
    del os.environ["TEST_VAR"]

def test_get_env_empty_fallback():
    os.environ["TEST_VAR"] = ""
    assert get_env("TEST_VAR", "default") == "default"
    del os.environ["TEST_VAR"]

def test_get_env_missing_fallback():
    assert get_env("MISSING_VAR", "default") == "default"

def test_validate_required_env_missing():
    # 確保環境變數是乾淨的進行測試
    for var in ["OCI_CONFIG_USER", "OCI_CONFIG_REGION"]:
        if var in os.environ: del os.environ[var]
    
    with pytest.raises(ConfigurationError) as excinfo:
        validate_required_env()
    assert "缺少必要的環境變數" in str(excinfo.value)

def test_load_config_success(mocker):
    # Mocking environment variables
    mocker.patch("os.getenv", side_effect=lambda k, d=None: {
        "OCI_CONFIG_USER": "u",
        "OCI_CONFIG_KEY_CONTENT": "k",
        "OCI_CONFIG_FINGERPRINT": "f",
        "OCI_CONFIG_TENANCY": "t",
        "OCI_COMPARTMENT_ID": "c",
        "OCI_SSH_KEY": "s",
        "OCI_IMAGE_ID": "i",
        "OCI_SUBNET_ID": "sn",
        "OCI_CONFIG_REGION": "r1, r2",
    }.get(k, d))
    
    cfg = load_config()
    assert cfg.user == "u"
    assert cfg.region_list == ["r1", "r2"]
    assert cfg.shape == "VM.Standard.A1.Flex" # Default value
