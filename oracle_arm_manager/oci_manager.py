import oci
from typing import Dict, Any, List

from oracle_arm_manager.logger import logger
from oracle_arm_manager.config import OracleArmConfig

class OciClientWrapper:
    """封裝底層 OCI API 的存取"""
    def __init__(self, config: OracleArmConfig, region: str) -> None:
        self.region = region
        self.compartment_id = config.compartment_id
        self.base_config: Dict[str, Any] = {
            "user": config.user,
            "key_content": config.key_content,
            "fingerprint": config.fingerprint,
            "tenancy": config.tenancy,
            "region": region,
        }
        
        # 初始化需要的 Clients
        self.compute_client = oci.core.ComputeClient(self.base_config)
        self.identity_client = oci.identity.IdentityClient(self.base_config)
        self.network_client = oci.core.VirtualNetworkClient(self.base_config)

    def list_active_instances(self) -> int:
        """計算運行中/部署中的自動化 AMR 實例數量"""
        try:
            instances = self.compute_client.list_instances(self.compartment_id).data
            active = [
                inst for inst in instances 
                if inst.display_name and inst.display_name.startswith("oracle-arm-auto") 
                and inst.lifecycle_state in ["RUNNING", "PROVISIONING"]
            ]
            count = len(active)
            logger.debug("找到 %s 個現有 ARM 實例", count)
            return count
        except Exception as e:
            logger.error("檢查現有實例失敗: %s", e, exc_info=True)
            return 0

    def list_availability_domains(self) -> List[Any]:
        """讀取該 Region 底下的可用 AD 列表"""
        res = self.identity_client.list_availability_domains(self.compartment_id).data
        return list(res) if res is not None else []

    def launch_instance(self, launch_details: oci.core.models.LaunchInstanceDetails) -> str:
        """
        向 OCI 發送建立實例的請求，並取得公開 IP。
        若失敗，交由上層 catch oci.exceptions.ServiceError 進行細微處置。
        """
        instance = self.compute_client.launch_instance(launch_details).data
        
        # 讀取 VNIC 以取得 public IP
        vnic_attachments = self.compute_client.list_vnic_attachments(
            self.compartment_id, instance_id=instance.id
        ).data
        
        if not vnic_attachments:
            return "N/A (No VNIC)"
            
        vnic_id = vnic_attachments[0].vnic_id
        vnic = self.network_client.get_vnic(vnic_id).data
        return vnic.public_ip or "N/A (No Public IP)"
