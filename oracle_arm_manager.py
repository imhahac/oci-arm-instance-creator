import oci
import os
import random
import time
import requests

def send_line_push(title: str, content: str, is_success: bool = False):
    """
    發送推播訊息至 LINE 會話。

    使用 LINE Messaging API (push 語法) 及 Flex Message 格式發送給定的使用者 ID。

    Args:
        title (str): 訊息的標題（例如：「✅ Oracle ARM 成功開通」）。
        content (str): 要顯示的主要文字內容。
        is_success (bool): 狀態標記，成功為 True (顯示綠燈顏色)，失敗預設為 False (顯示紅燈顏色)。
    """
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('LINE_ACCESS_TOKEN')}"
    }
    
    # 使用 Flex Message 讓資訊更整齊易讀。如果成功顯示綠色 (#00ff00)，否則為紅色 (#ff0000)
    color = "#00ff00" if is_success else "#ff0000"
    payload = {
        "to": os.getenv("LINE_USER_ID"),
        "messages": [{
            "type": "flex",
            "altText": title,
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box", "layout": "vertical",
                    "contents": [{"type": "text", "text": title, "weight": "bold", "color": color}]
                },
                "body": {
                    "type": "box", "layout": "vertical",
                    "contents": [{"type": "text", "text": content, "wrap": True, "size": "sm"}]
                }
            }
        }]
    }
    # 發送 POST 請求給 LINE API
    requests.post(url, headers=headers, json=payload)

def launch_instance() -> bool:
    """
    嘗試在 Oracle Cloud Infrastructure (OCI) 上建立 ARM VM 實例。

    此函式首先會休眠一小段隨機時間以避免與整點排程產生請求高峰。
    之後輪詢所有可用區 (Availability Domain) 嘗試建立實例，若成功則傳送 LINE 訊息通知並回傳 True，
    若容量不足或發生其他錯誤則繼續嘗試下一個可用區或直接失敗回傳 False。

    Returns:
        bool: 如果成功註冊建立實例回傳 True，皆失敗則回傳 False。
    """
    # 隨機延遲 (1 到 300 秒)，能有效避開許多使用 Github Actions 的整點/半點高峰並降低 API rate limit 影響
    delay = random.randint(1, 300)
    print(f"Random delay: {delay} seconds...")
    time.sleep(delay)

    # 讀取系統環境變數設定 OCI 設定檔 (這些通常在 Github Actions Secret 中配置)
    config = {
        "user": os.getenv("OCI_CONFIG_USER"),
        "key_content": os.getenv("OCI_CONFIG_KEY_CONTENT"),
        "fingerprint": os.getenv("OCI_CONFIG_FINGERPRINT"),
        "tenancy": os.getenv("OCI_CONFIG_TENANCY"),
        "region": os.getenv("OCI_CONFIG_REGION")
    }

    # 建立運算實例和身份識別客戶端
    compute_client = oci.core.ComputeClient(config)
    identity_client = oci.identity.IdentityClient(config)
    
    # 透過租戶區塊 ID (Compartment ID) 獲取所有可用區 (Availability Domain / AD)
    ads = identity_client.list_availability_domains(os.getenv("OCI_COMPARTMENT_ID")).data
    
    # 從環境變數讀取規格配置，若未設定則使用預設值 (4 OCPU, 24GB RAM, 50GB Boot Volume)
    ocpus = int(os.getenv("OCI_OCPUS", 4))
    memory_in_gbs = int(os.getenv("OCI_MEMORY_GBS", 24))
    boot_volume_size_in_gbs = int(os.getenv("OCI_BOOT_VOLUME_SIZE", 50))
    
    # 輪詢每一個可用區嘗試部署 ARM VM
    for ad in ads:
        print(f"Attempting to launch in {ad.name} with {ocpus} OCPUs, {memory_in_gbs}GB RAM, and {boot_volume_size_in_gbs}GB Boot Volume...")
        try:
            # 設定準備申請的 ARM VM 相關資訊
            launch_details = oci.core.models.LaunchInstanceDetails(
                display_name="Oracle-ARM-Auto",
                compartment_id=os.getenv("OCI_COMPARTMENT_ID"),
                availability_domain=ad.name,
                shape="VM.Standard.A1.Flex",
                shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=ocpus, memory_in_gbs=memory_in_gbs),
                source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=os.getenv("OCI_IMAGE_ID"), boot_volume_size_in_gbs=boot_volume_size_in_gbs),
                create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=os.getenv("OCI_SUBNET_ID")),
                assign_public_ip=True
            )
            
            # 開始送出建立要求
            res = compute_client.launch_instance(launch_details).data
            
            # 以下為如果成功建立後的資訊獲取流程 (包含獲取指派的公開 IP 供 LINE 通知)
            vnic_id = compute_client.list_vnic_attachments(os.getenv("OCI_COMPARTMENT_ID"), instance_id=res.id).data[0].vnic_id
            vnic = oci.core.VirtualNetworkClient(config).get_vnic(vnic_id).data
            public_ip = vnic.public_ip
            
            # 建立成功的推播文字，可自行將 'ubuntu / opc' 對應你使用的 OS Image
            msg = f"🚀 註冊成功！\n📍 IP: {public_ip}\n🔑 帳號: ubuntu / opc\n🏢 區域: {ad.name}"
            send_line_push("✅ Oracle ARM 成功開通", msg, is_success=True)
            return True
            
        except oci.exceptions.ServiceError as e:
            # "Out of capacity" 表示 Oracle Cloud 伺服器端目前沒有足夠硬體資源能開出來，為正常預期狀況
            if "Out of capacity" in e.message:
                print(f"Capacity full in {ad.name}")
                continue
            else:
                # 其它非預期的錯誤 (例如驗證失敗，配額不足等)
                print(f"Error: {e.message}")
    
    # 如果全部的可用區都開不出來則回傳不成功
    return False

if __name__ == "__main__":
    # 執行主函式
    success = launch_instance()
    
    # 這裡將結果寫入檔案，可供 GitHub Actions 後續讀取或統計使用 (例: 如果 success 就不再排程)
    with open("result.txt", "w") as f:
        f.write("success" if success else "fail")