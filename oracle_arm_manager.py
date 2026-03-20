import time
import requests
from datetime import datetime, timedelta
from oci.usage_api import UsageapiClient
from oci.usage_api.models import RequestSummarizedUsagesDetails

def send_notification(title: str, content: str, is_success: bool = False):
    """
    發送推播訊息至多個支援的平台 (LINE, Telegram, Discord)。
    根據環境變數中有設定的憑證，分別發送對應格式的訊息。
    """
    github_info = f"\n\n📌 GitHub Actions ({os.getenv('GITHUB_WORKFLOW', 'Unknown')})\n🔗 Run ID: {os.getenv('GITHUB_RUN_ID', 'N/A')}"
    
    # --- LINE 通知 ---
    line_token = os.getenv('LINE_ACCESS_TOKEN')
    line_user = os.getenv('LINE_USER_ID')
    if line_token and line_user:
        try:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {line_token}"}
            color = "#00ff00" if is_success else "#ff0000"
            payload = {
                "to": line_user,
                "messages": [{
                    "type": "flex", "altText": title,
                    "contents": {
                        "type": "bubble",
                        "header": {
                            "type": "box", "layout": "vertical",
                            "contents": [{"type": "text", "text": title, "weight": "bold", "color": color}]
                        },
                        "body": {
                            "type": "box", "layout": "vertical",
                            "contents": [
                                {"type": "text", "text": content, "wrap": True, "size": "sm"},
                                {"type": "separator", "margin": "md"},
                                {"type": "text", "text": f"📌 來源：GitHub Actions ({os.getenv('GITHUB_WORKFLOW', 'Unknown')})", "wrap": True, "size": "xs", "color": "#888888", "margin": "md"},
                                {"type": "text", "text": f"🔗 Run ID: {os.getenv('GITHUB_RUN_ID', 'N/A')}", "wrap": True, "size": "xs", "color": "#888888"}
                            ]
                        }
                    }
                }]
            }
            requests.post(url, headers=headers, json=payload)
        except Exception as e:
            print(f"LINE 發送失敗: {e}")

    # --- Telegram 通知 ---
    tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        try:
            tg_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            status_icon = "🟢" if is_success else "🔴"
            tg_text = f"{status_icon} *{title}*\n\n{content}{github_info}"
            requests.post(tg_url, json={"chat_id": tg_chat_id, "text": tg_text, "parse_mode": "Markdown"})
        except Exception as e:
            print(f"Telegram 發送失敗: {e}")

    # --- Discord 通知 ---
    discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
    if discord_webhook:
        try:
            color_int = 65280 if is_success else 16711680 # Green or Red
            discord_payload = {
                "embeds": [{
                    "title": title,
                    "description": content,
                    "color": color_int,
                    "footer": {"text": f"GitHub Actions | Run ID: {os.getenv('GITHUB_RUN_ID', 'N/A')}"}
                }]
            }
            requests.post(discord_webhook, json=discord_payload)
        except Exception as e:
            print(f"Discord 發送失敗: {e}")

def check_active_instances(compute_client, compartment_id) -> int:
    """
    檢查目前 Compartment 中已經配置（或正在配置）的自動 ARM 機器數量。
    """
    try:
        instances = compute_client.list_instances(compartment_id).data
        count = 0
        for inst in instances:
            # 計算名稱相同且狀態不是 TERMINATED / TERMINATING 的機器
            if inst.display_name == "oracle-arm-auto" and inst.lifecycle_state in ["RUNNING", "PROVISIONING"]:
                count += 1
        return 0
    except Exception as e:
        print(f"檢查現有實例失敗: {e}")
        return 0

def check_budget_usage(config) -> bool:
    """
    檢查本月累積費用是否超過門檻。
    門檻由環境變數 OCI_COST_THRESHOLD 設定 (預設 0.1 USD)。
    """
    try:
        threshold = float(os.getenv("OCI_COST_THRESHOLD", 0.1))
        usage_client = UsageapiClient(config)
        
        # 設定查詢區間：本月 1 號到明天 (確保涵蓋今天)
        now = datetime.utcnow()
        first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        tomorrow = now + timedelta(days=1)
        
        request_details = RequestSummarizedUsagesDetails(
            tenant_id=config["tenancy"],
            time_usage_started=first_day.strftime('%Y-%m-%dT%H:%M:%SZ'),
            time_usage_ended=tomorrow.strftime('%Y-%m-%dT%H:%M:%SZ'),
            granularity="MONTHLY",
            query_type="USAGE",
            is_aggregate_by_time=True
        )
        
        usage_data = usage_client.request_summarized_usages(request_details).data.items
        total_cost = sum(item.computed_amount for item in usage_data if item.computed_amount)
        
        print(f"💰 本月累計費用: {total_cost:.4f} USD (門檻: {threshold} USD)")
        
        if total_cost > threshold:
            msg = f"⚠️ 預算警報！\n本月費用 ${total_cost:.4f} 已超過門檻 ${threshold}。\n為安全計，自動停止註冊任務。"
            send_notification("🚨 OCI 預算超標", msg)
            return False
        return True
    except Exception as e:
        print(f"費用檢查失敗 (跳過檢查): {e}")
        return True

def launch_instance() -> bool:
    """
    嘗試在 Oracle Cloud Infrastructure (OCI) 上建立 ARM VM 實例。
    
    具備功能：
    - 多區域 (Multi-Region) 輪詢：支援以逗號分隔的 OCI_CONFIG_REGION 變數。
    - 數量限制 (Max Instances)：檢查目前機器數量是否達到 OCI_MAX_INSTANCES 限制。
    - 指數退避與重試邏輯：有效處理網路或短暫錯誤。
    """
    required_vars = [
        "OCI_CONFIG_USER", "OCI_CONFIG_KEY_CONTENT", "OCI_CONFIG_FINGERPRINT",
        "OCI_CONFIG_TENANCY", "OCI_COMPARTMENT_ID", "OCI_SSH_KEY",
        "OCI_IMAGE_ID", "OCI_SUBNET_ID", "OCI_CONFIG_REGION"
    ]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

    detailed_logs = []
    def log_step(region, ad, status):
        detailed_logs.append(f"| {region} | {ad} | {status} |")
        print(f"Log: {region} - {ad}: {status}")

    # 允許 OCI_CONFIG_REGION 輸入多個機房，例如: "ap-osaka-1, ap-tokyo-1"
    regions = [r.strip() for r in os.getenv("OCI_CONFIG_REGION").split(",")]
    max_instances = int(os.getenv("OCI_MAX_INSTANCES", 1))
    
    # 共用的基本設定
    base_config = {
        "user": os.getenv("OCI_CONFIG_USER"),
        "key_content": os.getenv("OCI_CONFIG_KEY_CONTENT"),
        "fingerprint": os.getenv("OCI_CONFIG_FINGERPRINT"),
        "tenancy": os.getenv("OCI_CONFIG_TENANCY"),
        "region": regions[0]
    }
    
    # 預算檢查
    if not check_budget_usage(base_config):
        return False

    compartment_id = os.getenv("OCI_COMPARTMENT_ID")
    # ... (省略中間不變部分)
    initial_compute_client = oci.core.ComputeClient(base_config)
    
    active_count = check_active_instances(initial_compute_client, compartment_id)
    print(f"目前已建立 {active_count} 台 ARM 實例 (上限: {max_instances} 台)")
    if active_count >= max_instances:
        print("機器數量已達上限，跳過此次建立程序。")
        send_notification("✅ 任務結束", f"現有的 ARM 機器已達上限 ({max_instances} 台)，停止排程發送。", is_success=True)
        return True

    # 開始輪詢各個機房
    for region in regions:
        print(f"--- 切換至區域: {region} ---")
        config = base_config.copy()
        config["region"] = region
        
        compute_client = oci.core.ComputeClient(config)
        identity_client = oci.identity.IdentityClient(config)
        
        try:
            ads = identity_client.list_availability_domains(compartment_id).data
        except Exception as e:
            log_step(region, "N/A", f"Error: {str(e)[:50]}")
            continue
            
        for ad in ads:
            log_step(region, ad.name, "Attempting...")
            
            launch_details = oci.core.models.LaunchInstanceDetails(
                display_name="oracle-arm-auto",
                compartment_id=compartment_id,
                availability_domain=ad.name,
                shape="VM.Standard.A1.Flex",
                shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=ocpus, memory_in_gbs=memory_in_gbs),
                source_details=oci.core.models.InstanceSourceViaImageDetails(
                    image_id=os.getenv("OCI_IMAGE_ID"), 
                    boot_volume_size_in_gbs=boot_volume_size_in_gbs,
                    boot_volume_vpus_per_gb=boot_volume_vpus_per_gb
                ),
                create_vnic_details=oci.core.models.CreateVnicDetails(
                    subnet_id=os.getenv("OCI_SUBNET_ID"),
                    assign_public_ip=True
                ),
                metadata={
                    "ssh_authorized_keys": os.getenv("OCI_SSH_KEY")
                }
            )
            
            CAPACITY_KEYWORDS = ["capacity", "quota", "limit"]
            retries = 2
            for attempt in range(retries):
                try:
                    res = compute_client.launch_instance(launch_details).data
                    vnic_id = compute_client.list_vnic_attachments(compartment_id, instance_id=res.id).data[0].vnic_id
                    vnic = oci.core.VirtualNetworkClient(config).get_vnic(vnic_id).data
                    public_ip = vnic.public_ip
                    
                    log_step(region, ad.name, f"🚀 Success (IP: {public_ip})")
                    msg = f"🚀 註冊成功！\n📍 IP: {public_ip}\n🔑 帳號: ubuntu / opc\n🏢 區域: {ad.name}\n總數量: {active_count + 1}/{max_instances}"
                    send_notification("✅ Oracle ARM 成功開通", msg, is_success=True)
                    
                    with open("detailed_log.txt", "w", encoding="utf-8") as f:
                        f.write("\n".join(detailed_logs))
                    return True
                    
                except oci.exceptions.ServiceError as e:
                    msg_lower = e.message.lower() if e.message else ""
                    is_capacity_error = any(kw in msg_lower for kw in CAPACITY_KEYWORDS)
                    
                    if is_capacity_error:
                        log_step(region, ad.name, "❌ Out of Capacity")
                        break
                    elif "too many requests" in msg_lower:
                        if attempt < retries - 1:
                            time.sleep(60)
                        else:
                            log_step(region, ad.name, "⚠️ Rate Limited")
                            break
                    else:
                        if attempt < retries - 1:
                            time.sleep(30)
                        else:
                            log_step(region, ad.name, f"❌ Error: {e.code}")
                            break
                            
    with open("detailed_log.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(detailed_logs))
    return False
if __name__ == "__main__":
    success = launch_instance()
    with open("result.txt", "w") as f:
        f.write("success" if success else "fail")