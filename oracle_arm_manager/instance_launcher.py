import random
import string
import time
from typing import Tuple, List, Dict, Any

import oci
from oracle_arm_manager.logger import logger
from oracle_arm_manager.config import OracleArmConfig, CAPACITY_KEYWORDS
from oracle_arm_manager.oci_manager import OciClientWrapper
from oracle_arm_manager.budget_checker import BudgetChecker
from oracle_arm_manager.notifier import send_notification

class LaunchResult:
    def __init__(self):
        self.success = False
        self.logs: List[str] = []
        # 給儀表板統計用
        self.stats: Dict[str, Any] = {
            "attempts": 0,
            "success": False,
            "regions_tried": [],
            "error_distribution": {},
            "active_instances": 0
        }
        
    def add_log(self, region: str, ad: str, status: str):
        self.logs.append(f"| {region} | {ad} | {status} |")
        
    def record_error(self, region: str, err_type: str):
        if region not in self.stats["regions_tried"]:
            self.stats["regions_tried"].append(region)
        self.stats["error_distribution"][err_type] = self.stats["error_distribution"].get(err_type, 0) + 1

class InstanceLauncher:
    def __init__(self, config: OracleArmConfig) -> None:
        self.config = config

    def _apply_jitter(self) -> None:
        """隨機等待，防止瞬間擁塞"""
        if self.config.jitter_max > 0:
            jitter = random.uniform(self.config.jitter_min, self.config.jitter_max)
            logger.info("隨機延遲 %.2f 秒", jitter)
            time.sleep(jitter)

    def _build_launch_details(self, ad_name: str) -> oci.core.models.LaunchInstanceDetails:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
        return oci.core.models.LaunchInstanceDetails(
            display_name=f"oracle-arm-auto-{suffix}",
            compartment_id=self.config.compartment_id,
            availability_domain=ad_name,
            shape=self.config.shape,
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=self.config.ocpus, 
                memory_in_gbs=self.config.memory_gbs
            ),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                image_id=self.config.image_id, 
                boot_volume_size_in_gbs=self.config.boot_volume_size, 
                boot_volume_vpus_per_gb=self.config.boot_volume_vpus_per_gb
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=self.config.subnet_id, 
                assign_public_ip=True
            ),
            metadata={"ssh_authorized_keys": self.config.ssh_key},
        )

    def _try_launch_in_ad(self, oci_wrapper: OciClientWrapper, ad_name: str, result: LaunchResult) -> bool:
        """嘗試在單一 AD 中建立，回傳是否成功"""
        result.stats["attempts"] += 1
        launch_details = self._build_launch_details(ad_name)

        try:
            public_ip = oci_wrapper.launch_instance(launch_details)
            msg = f"✅ 成功: {public_ip}"
            result.add_log(oci_wrapper.region, ad_name, msg)
            result.stats["success"] = True
            send_notification("✅ Oracle ARM 成功", f"IP: {public_ip}\n區域: {oci_wrapper.region}\nAD: {ad_name}", is_success=True)
            return True

        except oci.exceptions.ServiceError as svc_err:
            message = (svc_err.message or "").lower()
            is_capacity_error = any(keyword in message for keyword in CAPACITY_KEYWORDS)

            if is_capacity_error:
                # 遵循原本設計：容量不足直接跳過，不 retry
                result.add_log(oci_wrapper.region, ad_name, "❌ 容量不足 (已跳過)")
                result.record_error(oci_wrapper.region, "Out of Capacity")
                return False

            if "too many requests" in message:
                result.add_log(oci_wrapper.region, ad_name, "⚠️ 速率限制")
                result.record_error(oci_wrapper.region, "Rate Limit")
                return False

            result.add_log(oci_wrapper.region, ad_name, f"❌ 失敗: {svc_err.code}")
            result.record_error(oci_wrapper.region, f"Error: {svc_err.code}")
            return False

        except Exception as e:
            err_head = str(e)[:30] + "..."
            result.add_log(oci_wrapper.region, ad_name, f"❌ 未知錯誤: {err_head}")
            result.record_error(oci_wrapper.region, "Unknown Exception")
            logger.error("在 AD %s 建立實例時遭遇未知錯誤", ad_name, exc_info=True)
            return False

    def run(self) -> LaunchResult:
        result = LaunchResult()
        self._apply_jitter()

        # 取第一個區域作為租戶主要配置點進行檢查
        primary_wrapper = OciClientWrapper(self.config, self.config.region_list[0])
        
        # 1. 預算檢查
        if not BudgetChecker.check_usage(primary_wrapper.base_config, self.config.cost_threshold):
            result.add_log("ALL", "ALL", "🛑 預算超標，停止執行")
            result.stats["error_distribution"]["Budget Limit Reached"] = 1
            return result

        # 2. 已有實例檢查
        active_count = primary_wrapper.list_active_instances()
        result.stats["active_instances"] = active_count
        logger.info("目前已建立 %s 台 ARM 實例, 上限 %s", active_count, self.config.max_instances)
        
        if active_count >= self.config.max_instances:
            msg = f"現有 ARM 實例 {active_count}/{self.config.max_instances}，已達上限停止建立。"
            result.add_log("ALL", "ALL", msg)
            result.success = True  # 已經達成目標，所以視為成功
            result.stats["success"] = True
            logger.info("已達設定上限，任務結束。")
            return result

        # 3. 遍歷區域與 AD
        for region in self.config.region_list:
            logger.info("切換區域: %s", region)
            wrapper = OciClientWrapper(self.config, region)

            try:
                ads = wrapper.list_availability_domains()
            except Exception as e:
                logger.warning("讀取可用區域失敗 %s: %s", region, e)
                result.add_log(region, "N/A", "❌ 無法讀取 AD 列表")
                continue

            for ad in ads:
                if self._try_launch_in_ad(wrapper, ad.name, result):
                    result.success = True
                    return result

        return result
