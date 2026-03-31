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
        """
        檢查 OCI 帳號本月費用是否超過閾值。
        
        Args:
            config_dict: OCI SDK 所需的配置字典 (含有 tenancy 等資訊)。
            threshold: 觸發警告的費用美金上限。
            
        Returns:
            bool: 若未超標或檢查發生預期外錯誤回傳 True (放行)，若確定超標則回傳 False (阻擋)。
        """
        import oci
        from oracle_arm_manager.constants import OCI_API_TIMEOUT_SECONDS
        try:
            retry_strategy = oci.retry.DEFAULT_RETRY_STRATEGY
            usage_client = UsageapiClient(config_dict, retry_strategy=retry_strategy)
            kwargs = {"request_kwargs": {"timeout": (OCI_API_TIMEOUT_SECONDS, OCI_API_TIMEOUT_SECONDS)}}
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

            response = usage_client.request_summarized_usages(request_details, **kwargs)
            usage_data = getattr(response.data, 'items', [])
            total_cost = sum(getattr(item, "computed_amount", 0) or 0 for item in usage_data)

            logger.info("本月累計費用: %.4f USD (門檻: %.4f USD)", total_cost, threshold)

            if total_cost > threshold:
                msg = f"⚠️ 預算警報！本月費用 ${total_cost:.4f} 已超過門檻 ${threshold:.4f}。自動停止註冊任務。"
                logger.error(msg)
                send_notification("🚨 OCI 預算超標", msg)
                return False
            
            return True

        except oci.exceptions.ServiceError as e:
            logger.warning("費用檢查 OCI 服務異常，將略過預先檢查 [%s]: %s", e.status, e.message)
            return True
        except Exception as e:
            logger.error("費用檢查發生未預料異常: %s", e, exc_info=True)
            return True
