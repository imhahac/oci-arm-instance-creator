from datetime import datetime, timedelta
from typing import Dict, Any

from oci.usage_api import UsageapiClient
from oci.usage_api.models import RequestSummarizedUsagesDetails

from oracle_arm_manager.logger import logger
from oracle_arm_manager.config import OracleArmConfig
from oracle_arm_manager.notifier import send_notification

class BudgetChecker:
    @staticmethod
    def check_usage(config_dict: Dict[str, Any], threshold: float) -> bool:
        """檢查 OCI 帳號本月費用是否超過閾值"""
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

            response = usage_client.request_summarized_usages(request_details)
            usage_data = response.data.items if getattr(response.data, 'items', None) else []
            total_cost = sum(item.computed_amount or 0 for item in usage_data)

            logger.info("本月累計費用: %.4f USD (門檻: %.4f USD)", total_cost, threshold)

            if total_cost > threshold:
                msg = f"⚠️ 預算警報！本月費用 ${total_cost:.4f} 已超過門檻 ${threshold:.4f}。自動停止註冊任務。"
                logger.error(msg)
                send_notification("🚨 OCI 預算超標", msg)
                return False
            
            return True

        except Exception as e:
            logger.error("費用檢查失敗，將略過預先檢查: %s", e, exc_info=True)
            return True
