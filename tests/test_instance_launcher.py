import pytest
from unittest.mock import MagicMock
from oracle_arm_manager.instance_launcher import InstanceLauncher, LaunchResult
from oracle_arm_manager.config import OracleArmConfig, RetryConfig

@pytest.fixture
def mock_config():
    return OracleArmConfig(
        user="u", key_content="k", fingerprint="f", tenancy="t",
        compartment_id="c", region_list=["region1"], ssh_key="s",
        image_id="i", subnet_id="sn", max_instances=2,
        ocpus=4, memory_gbs=24, boot_volume_size=50,
        boot_volume_vpus_per_gb=10, cost_threshold=0.1, shape="VM.Standard.A1.Flex",
        jitter_min=0, jitter_max=0,
        retry=RetryConfig(max_retries=1, delay_1=0, delay_2=0)
    )

def test_launch_result_adds_log():
    res = LaunchResult()
    res.add_log("r1", "ad1", "success")
    assert "| r1 | ad1 | success |" in res.logs

def test_launcher_stops_at_max_instances(mocker, mock_config):
    # Mock OciClientWrapper
    mock_wrapper = MagicMock()
    mock_wrapper.list_active_instances.return_value = 2 # Already at max
    mocker.patch("oracle_arm_manager.instance_launcher.OciClientWrapper", return_value=mock_wrapper)
    mocker.patch("oracle_arm_manager.instance_launcher.BudgetChecker.check_usage", return_value=True)

    launcher = InstanceLauncher(mock_config)
    result = launcher.run()
    
    assert result.success is True
    assert "已達上限停止建立" in result.logs[0]

def test_launcher_traverses_ads(mocker, mock_config):
    mock_wrapper = MagicMock()
    mock_wrapper.list_active_instances.return_value = 0
    # Mock Availability Domains
    ad1 = MagicMock(); ad1.name = "AD-1"
    ad2 = MagicMock(); ad2.name = "AD-2"
    mock_wrapper.list_availability_domains.return_value = [ad1, ad2]
    
    # Mock launch_instance to fail on AD-1 and succeed on AD-2
    mock_wrapper.launch_instance.side_effect = [
        Exception("Capacity Error"), # AD-1
        "1.2.3.4" # AD-2 Success
    ]
    
    mocker.patch("oracle_arm_manager.instance_launcher.OciClientWrapper", return_value=mock_wrapper)
    mocker.patch("oracle_arm_manager.instance_launcher.BudgetChecker.check_usage", return_value=True)
    mocker.patch("oracle_arm_manager.instance_launcher.send_notification")

    launcher = InstanceLauncher(mock_config)
    result = launcher.run()
    
    assert result.success is True
    assert mock_wrapper.launch_instance.call_count == 2
