import pytest
from unittest.mock import MagicMock
import oci

from oracle_arm_manager.oci_manager import OciClientWrapper
from oracle_arm_manager.config import OracleArmConfig, RetryConfig
from oracle_arm_manager.exceptions import OciApiError, OciCapacityError, OciRateLimitError

@pytest.fixture
def mock_config():
    return OracleArmConfig(
        user="u", key_content="k", fingerprint="f", tenancy="t",
        compartment_id="c", region_list=["region1"], ssh_key="s",
        image_id="i", subnet_id="sn", max_instances=1,
        ocpus=4, memory_gbs=24, boot_volume_size=50,
        boot_volume_vpus_per_gb=10, cost_threshold=0.1, shape="VM.Standard.A1.Flex",
        jitter_min=0, jitter_max=0,
        retry=RetryConfig(max_retries=1, delay_1=0, delay_2=0)
    )

@pytest.fixture
def mock_clients(mocker):
    """Mock OCI clients to prevent deep config validation errors."""
    mocker.patch("oci.core.ComputeClient")
    mocker.patch("oci.identity.IdentityClient")
    mocker.patch("oci.core.VirtualNetworkClient")

def test_launch_instance_success(mocker, mock_config, mock_clients):
    wrapper = OciClientWrapper(mock_config, "region1")
    
    # Mocking launch_instance response
    mock_instance = MagicMock()
    mock_instance.id = "inst-123"
    wrapper.compute_client.launch_instance = MagicMock(return_value=MagicMock(data=mock_instance))
    
    # Mocking VNIC attachments
    mock_vnic_attach = MagicMock()
    mock_vnic_attach.vnic_id = "vnic-123"
    wrapper.compute_client.list_vnic_attachments = MagicMock(return_value=MagicMock(data=[mock_vnic_attach]))
    
    # Mocking get_vnic public IP
    mock_vnic = MagicMock()
    mock_vnic.public_ip = "192.168.1.1"
    wrapper.network_client.get_vnic = MagicMock(return_value=MagicMock(data=mock_vnic))
    
    launch_details = MagicMock()
    ip = wrapper.launch_instance(launch_details)
    
    assert ip == "192.168.1.1"

def test_launch_instance_capacity_error(mocker, mock_config, mock_clients):
    wrapper = OciClientWrapper(mock_config, "region1")
    
    # Mock ServiceError OutOfCapacity
    err = oci.exceptions.ServiceError(status=500, code="OutOfCapacity", headers={}, message="Out of capacity")
    wrapper.compute_client.launch_instance = MagicMock(side_effect=err)
    
    with pytest.raises(OciCapacityError):
        wrapper.launch_instance(MagicMock())

def test_launch_instance_rate_limit(mocker, mock_config, mock_clients):
    wrapper = OciClientWrapper(mock_config, "region1")
    
    # Mock ServiceError TooManyRequests
    err = oci.exceptions.ServiceError(status=429, code="TooManyRequests", headers={}, message="Too many requests")
    wrapper.compute_client.launch_instance = MagicMock(side_effect=err)
    
    with pytest.raises(OciRateLimitError):
        wrapper.launch_instance(MagicMock())

def test_launch_instance_generic_api_error(mocker, mock_config, mock_clients):
    wrapper = OciClientWrapper(mock_config, "region1")
    
    err = oci.exceptions.ServiceError(status=401, code="NotAuthorized", headers={}, message="Invalid limits context")
    wrapper.compute_client.launch_instance = MagicMock(side_effect=err)
    
    with pytest.raises(OciApiError):
        wrapper.launch_instance(MagicMock())
