import logging
import os
import random
import string
import time
from datetime import datetime, timedelta
from typing import List

import oci
from oci.usage_api import UsageapiClient
from oci.usage_api.models import RequestSummarizedUsagesDetails

from config import CAPACITY_KEYWORDS, OracleArmConfig
from notifications import send_notification


def safe_write_file(path: str, text: str, encoding: str = "utf-8") -> None:
    try:
        with open(path, "w", encoding=encoding) as f:
            f.write(text)
    except OSError as e:
        logging.error("無法寫入文件 %s: %s", path, e, exc_info=True)
        raise


def build_oci_base_config(config: OracleArmConfig, region: str) -> dict:
    return {
        "user": config.user,
        "key_content": config.key_content,
        "fingerprint": config.fingerprint,
        "tenancy": config.tenancy,
        "region": region,
    }


def check_active_instances(compute_client: oci.core.ComputeClient, compartment_id: str) -> int:
    try:
        instances = compute_client.list_instances(compartment_id).data
        active = [inst for inst in instances if inst.display_name and inst.display_name.startswith("oracle-arm-auto") and inst.lifecycle_state in ["RUNNING", "PROVISIONING"]]
        count = len(active)
        logging.debug("找到 %s 個現有 ARM 實例。", count)
        return count
    except Exception as e:
        logging.error("檢查現有實例失敗: %s", e, exc_info=True)
        return 0


def check_budget_usage(config_dict: dict, threshold: float) -> bool:
    try:
        usage_client = UsageapiClient(config_dict)

        now = datetime.utcnow()
        first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        request_details = RequestSummarizedUsagesDetails(
            tenant_id=config_dict["tenancy"],
            time_usage_started=first_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
            time_usage_ended=tomorrow.strftime("%Y-%m-%dT%H:%M:%SZ"),
            granularity="MONTHLY",
            query_type="USAGE",
            is_aggregate_by_time=True,
        )

        usage_data = usage_client.request_summarized_usages(request_details).data.items
        total_cost = sum(item.computed_amount or 0 for item in usage_data)

        logging.info("本月累計費用: %.4f USD (門檻: %.4f USD)", total_cost, threshold)

        if total_cost > threshold:
            msg = f"⚠️ 預算警報！本月費用 ${total_cost:.4f} 已超過門檻 ${threshold:.4f}。自動停止註冊任務。"
            send_notification("🚨 OCI 預算超標", msg)
            return False
        return True
    except Exception as e:
        logging.error("費用檢查失敗，將忽略預算檢查: %s", e, exc_info=True)
        return True


def create_instance_launch_details(config: OracleArmConfig, region: str, ad_name: str, suffix: str) -> oci.core.models.LaunchInstanceDetails:
    return oci.core.models.LaunchInstanceDetails(
        display_name=f"oracle-arm-auto-{suffix}",
        compartment_id=config.compartment_id,
        availability_domain=ad_name,
        shape=config.shape,
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=config.ocpus, memory_in_gbs=config.memory_gbs),
        source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=config.image_id, boot_volume_size_in_gbs=config.boot_volume_size, boot_volume_vpus_per_gb=config.boot_volume_vpus_per_gb),
        create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=config.subnet_id, assign_public_ip=True),
        metadata={"ssh_authorized_keys": config.ssh_key},
    )


def _try_launch_instance_in_ad(
    compute_client: oci.core.ComputeClient,
    region_config: dict,
    config: OracleArmConfig,
    region: str,
    ad_name: str,
) -> tuple[bool, str]:
    """嘗試在特定 AD 建立實例。傳回 (是否成功, 日誌訊息)"""
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    launch_details = create_instance_launch_details(config, region, ad_name, suffix)

    # 根據用戶要求，Capacity 錯誤直接跳過，不進行 retries
    try:
        instance = compute_client.launch_instance(launch_details).data
        vnic_id = compute_client.list_vnic_attachments(config.compartment_id, instance_id=instance.id).data[0].vnic_id
        vnic = oci.core.VirtualNetworkClient(region_config).get_vnic(vnic_id).data
        public_ip = vnic.public_ip

        msg = f"| {region} | {ad_name} | ✅ 成功: {public_ip} |"
        send_notification("✅ Oracle ARM 成功", f"IP: {public_ip}\n區域: {region}\nAD: {ad_name}", is_success=True)
        return True, msg

    except oci.exceptions.ServiceError as svc_err:
        message = (svc_err.message or "").lower()
        is_capacity_error = any(keyword in message for keyword in CAPACITY_KEYWORDS)

        if is_capacity_error:
            # 用戶要求：Capacity 直接跳過
            return False, f"| {region} | {ad_name} | ❌ 容量不足 (已跳過) |"

        if "too many requests" in message:
            # 速率限制通常是暫時的，可以記錄但通常在一個 run 裡重試沒意義，這邊維持紀錄
            return False, f"| {region} | {ad_name} | ⚠️ 速率限制 |"

        return False, f"| {region} | {ad_name} | ❌ 失敗: {svc_err.code} |"

    except Exception as e:
        return False, f"| {region} | {ad_name} | ❌ 未知錯誤: {str(e)[:30]}... |"


def launch_instance(config: OracleArmConfig) -> bool:
    jitter = random.uniform(0, 60)
    logging.info("隨機延遲 %.2f 秒", jitter)
    time.sleep(jitter)

    if not config.region_list:
        raise ValueError("OCI_CONFIG_REGION 必須設定至少一個可用區域")

    base_config = build_oci_base_config(config, config.region_list[0])

    if not check_budget_usage(base_config, config.cost_threshold):
        return False

    initial_compute_client = oci.core.ComputeClient(base_config)
    active_count = check_active_instances(initial_compute_client, config.compartment_id)
    logging.info("目前已建立 %s 台 ARM 實例, 上限 %s", active_count, config.max_instances)

    if active_count >= config.max_instances:
        message = f"現有 ARM 實例 {active_count}/{config.max_instances}，停止建立。"
        send_notification("✅ 任務結束", message, is_success=True)
        return True

    detailed_logs: List[str] = []

    for region in config.region_list:
        logging.info("切換區域: %s", region)
        region_config = build_oci_base_config(config, region)
        compute_client = oci.core.ComputeClient(region_config)
        identity_client = oci.identity.IdentityClient(region_config)

        try:
            ads = identity_client.list_availability_domains(config.compartment_id).data
        except Exception as e:
            logging.warning("讀取可用區域失敗 %s: %s", region, e)
            detailed_logs.append(f"| {region} | N/A | ❌ 無法讀取 AD 列表 |")
            continue

        for ad in ads:
            success, log_msg = _try_launch_instance_in_ad(compute_client, region_config, config, region, ad.name)
            detailed_logs.append(log_msg)
            if success:
                safe_write_file("detailed_log.txt", "\n".join(detailed_logs))
                return True

    safe_write_file("detailed_log.txt", "\n".join(detailed_logs))
    return False


# Entry point: oracle_arm_manager.py
