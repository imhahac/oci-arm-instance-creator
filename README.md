# Oracle Cloud ARM 自動開機腳本 (GitHub Actions)

這是一個利用 GitHub Actions 的免費排程資源，24 小時自動化幫你監控並在有資源時自動創建 Oracle Cloud Infrastructure (OCI) Always Free 永久免費 ARM 虛擬機 (4 OCPU / 24GB Memory) 的專案。

## 🌟 功能特色
* **完全免費**：利用 Github Actions 的執行週期自動運作。支援隨機延遲 (1 到 300 秒)，能有效避開許多使用 Github Actions 的整點/半點高峰並降低 API rate limit。
* **多區域輪詢**：自動檢測並輪詢所有可用區 (Availability Domain) 資源。
* **LINE 即時推播**：不管是每日成功申請、狀態報告或失敗訊息都會透過 LINE 推播通知你最新的狀況。
* **日結報告**：每日 UTC 16:00 (台灣早上 0:00) 寄送報告推播。

---

## 🚀 部署教學 (How to Use)

### 1. 取得 LINE Notify Token 及 User ID (接收通知)
首先需設定一組推播通知。這裡使用 [LINE Messaging API (Line Developer)](https://developers.line.biz/zh-hant/) 的 Push Message 功能。
1. 前往 Line Developer Console 創建一個 Provider 及 Channel (類型選擇 Messaging API)。
2. 從 **Channel Access Token** 標籤頁發行一組長時間的 Access Token (這會是 `LINE_ACCESS_TOKEN`)。
3. 在 Basic Settings 裡找到你的 **Your user ID** (這會是 `LINE_USER_ID`)。

### 2. 取出 Oracle Cloud 的相關設定
我們需要 OCI API Key。前往 OCI 控制台：
1. 點擊右上角個人頭像 -> User Settings -> API Keys。
2. 點選 `Add API Key` 後下載私鑰 (`.pem`，這會是 `OCI_CONFIG_KEY_CONTENT`)，並點擊 Add。
3. 畫面上會產生對應的設定檔預覽，裡面包含了所需的各項參數：
   - `user`: 對應 `OCI_CONFIG_USER`
   - `fingerprint`: 對應 `OCI_CONFIG_FINGERPRINT`
   - `tenancy`: 對應 `OCI_CONFIG_TENANCY`
   - `region`: 對應 `OCI_CONFIG_REGION` (例如：ap-osaka-1, ap-tokyo-1 等)

### 3. 取得 OCI 網路及映像檔設定
- **Compartment ID**：進入 Identity -> Compartments 尋找你要建立資源的區塊 ID，這會是 `OCI_COMPARTMENT_ID`。
- **Image ID**：前往 Compute -> Instances -> Create Instance，選擇你要安裝的 Image (通常為 Oracle Linux 或 Ubuntu ARM 版本)，這會是 `OCI_IMAGE_ID`。
- **Subnet ID**：進入 Networking -> Virtual Cloud Networks -> 選擇 VCN，然後進入你要綁定的 Subnet 頁面，獲取 `OCI_SUBNET_ID`。

### 4. 設定 GitHub Secrets
進入您的專案庫 (Repository) -> **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**，將以下的參數一行一行新增進去：

| 變數名稱 (Secret Name) | 說明 (Description) |
| --- | --- |
| `OCI_CONFIG_USER` | 會員 OCID。 |
| `OCI_CONFIG_KEY_CONTENT` | 剛剛下載的 `.pem` 私鑰的完整文字內容。 |
| `OCI_CONFIG_FINGERPRINT` | API Key 的指紋碼。 |
| `OCI_CONFIG_TENANCY` | 租戶 OCID。 |
| `OCI_CONFIG_REGION` | 區域標記，如: ap-osaka-1 |
| `OCI_COMPARTMENT_ID` | Compartment OCID |
| `OCI_IMAGE_ID` | 系統版本 Image OCID |
| `OCI_SUBNET_ID` | 伺服器要使用的 Subnet OCID |
| `OCI_OCPUS` | (選填) OCPU 數量，預設為 4。 |
| `OCI_MEMORY_GBS` | (選填) 記憶體大小 (GB)，預設為 24。 |
| `OCI_BOOT_VOLUME_SIZE` | (選填) 開機磁碟大小 (GB)，預設為 50。 |
| `LINE_ACCESS_TOKEN` | LINE Messaging API 的長效 Access Token |
| `LINE_USER_ID` | 接收訊息的 Line User ID |

### 5. 執行自動化排程
當設定好 Secrets 後，請前往倉庫上方的 **Actions** 分頁點開：
1. **ARM Auto Registration** -> 點擊 `Run workflow` 手動觸發看一次是否設定正確並開始運行，之後每 30 分鐘就會自動執行。
2. 你會同時看到 **Daily Report** 確保每天的 0:00 發送回報訊息。

---

## ⚠️ 免責聲明
- 本專案僅供學術交流與程式設計練習，請勿濫用 Github Actions 免費額度。
- 若違反 OCI 用戶協議，可能會引發帳號停權的風險，使用者須自行負責。
