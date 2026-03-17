# Oracle Cloud ARM 自動開機腳本 (GitHub Actions)

[![ARM Auto Registration](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/register.yml/badge.svg)](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/register.yml)
[![Daily Report](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/daily_report.yml/badge.svg)](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/daily_report.yml)

這是一個利用 GitHub Actions 的免費排程資源，24 小時自動化幫你監控並在有資源時自動創建 Oracle Cloud Infrastructure (OCI) Always Free 永久免費 ARM 虛擬機 (4 OCPU / 24GB Memory) 的專案。

## 🌟 功能特色
* **完全免費與智慧防撞**：利用 Github Actions 自動運作。具備自動休眠與併發上限機制 (Concurrency Control)，避免流量過高與重複執行。
* **多區域輪詢 (Multi-Region)**：支援設定多個機房，若 A 機房滿載，無縫自動跳轉 B 機房嘗試。
* **自動停止 (Auto-Stop) 與上限保護**：設定機器數量上限（例：只開 1 台）。當申請成功或已達上限數量時，自動中止 GitHub 排程以節省資源。
* **多平台即時推播**：支援 LINE、Telegram、Discord 跨平台通知。不管是每日成功申請、狀態報告或失敗訊息都會送到你的裝置。
* **日結報告 & 儀表板**：每日發送回報推播，並附贈 GitHub Actions 首頁的 Job Summary 儀表板狀態檢視。

---

## 🚀 部署教學 (How to Use)

### 1. 取得通知憑證 (LINE / Telegram / Discord)
本腳本支援三種平台的推播，您只需要挑選喜歡的平台設定對應的 Secrets 即可（可全設）：
* **LINE**:
  - 前往 [LINE Messaging API](https://developers.line.biz/zh-hant/) 申請 Channel。這會給你一組 `LINE_ACCESS_TOKEN`，並從 Basic Settings 找到 `LINE_USER_ID`。
* **Telegram**:
  - 找找 `@BotFather` 申請 Bot 取回 `TELEGRAM_BOT_TOKEN`。並透過 `@userinfobot` 取得你的 `TELEGRAM_CHAT_ID`。
* **Discord**:
  - 在你的伺服器頻道中，點擊編輯頻道 -> 整合 -> Webhooks，建立並複製 Webhook 網址為 `DISCORD_WEBHOOK_URL`。

### 2. 取出 Oracle Cloud 的相關設定
我們需要 OCI API Key。前往 OCI 控制台：
1. 點擊右上角個人頭像 -> User Settings -> API Keys。
2. 點選 `Add API Key` 後下載私鑰 (`.pem`，這會是 `OCI_CONFIG_KEY_CONTENT`)，並點擊 Add。
3. 畫面上會產生對應的設定檔預覽，裡面包含了所需的各項參數：
   - `user`: 對應 `OCI_CONFIG_USER`
   - `fingerprint`: 對應 `OCI_CONFIG_FINGERPRINT`
   - `tenancy`: 對應 `OCI_CONFIG_TENANCY`
   - `region`: 對應 `OCI_CONFIG_REGION` (支援填入單個如 `ap-osaka-1` 或逗號分隔的多區域輪詢如 `ap-osaka-1, ap-tokyo-1`)

### 3. 取得 OCI 網路及映像檔設定
- **Compartment ID**：進入 Identity -> Compartments 尋找你要建立資源的區塊 ID，這會是 `OCI_COMPARTMENT_ID`。
- **Image ID**：前往 Compute -> Instances -> Create Instance，選擇你要安裝的 Image (通常為 Oracle Linux 或 Ubuntu ARM 版本)，這會是 `OCI_IMAGE_ID`。
- **Subnet ID**：進入 Networking -> Virtual Cloud Networks -> 選擇 VCN，然後進入你要綁定的 Subnet 頁面，獲取 `OCI_SUBNET_ID`。

### 4. 設定 GitHub Secrets 與 Variables
進入您的專案庫 (Repository) -> **Settings** -> **Secrets and variables** -> **Actions**

#### 🔐 Secrets（機密資訊：帳號/金鑰）
點選 **Secrets** 標籤 -> **New repository secret**：

| 名稱 | 說明 |
| --- | --- |
| `OCI_CONFIG_USER` | 使用者 OCID |
| `OCI_CONFIG_KEY_CONTENT` | 下載的 `.pem` 私鑰完整文字內容 |
| `OCI_CONFIG_FINGERPRINT` | API Key 的指紋碼 |
| `OCI_CONFIG_TENANCY` | 租戶 OCID |
| `OCI_COMPARTMENT_ID` | Compartment OCID |
| `OCI_SSH_KEY` | SSH 公鑰完整內容 (例如：`ssh-rsa AAAAB3Nza...`) |
| `LINE_ACCESS_TOKEN` | LINE Messaging API 的 Token (選用) |
| `LINE_USER_ID` | 接收訊息的 Line User ID (選用) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token 碼 (選用) |
| `TELEGRAM_CHAT_ID` | Telegram 接收訊息的 Chat ID (選用) |
| `DISCORD_WEBHOOK_URL` | Discord 頻道的 Webhook 網址 (選用) |

> 註：LINE、Telegram、Discord 擇一設定即可，如果都有設定則會同時發送訊息。

#### ⚙️ Variables（非機密設定值）
點選 **Variables** 標籤 -> **New repository variable**：

| 名稱 | 說明 | 範例 |
| --- | --- | --- |
| `OCI_CONFIG_REGION` | OCI 區域標記 (支援多個以 `,` 分隔) | `ap-osaka-1, ap-tokyo-1` |
| `OCI_IMAGE_ID` | 系統版本 Image OCID | `ocid1.image.oc1...` |
| `OCI_SUBNET_ID` | 伺服器要使用的 Subnet OCID | `ocid1.subnet.oc1...` |
| `OCI_OCPUS` | OCPU 數量 (Always Free 上限為 4) | `4` |
| `OCI_MEMORY_GBS` | 記憶體大小 GB (Always Free 上限為 24) | `24` |
| `OCI_BOOT_VOLUME_SIZE` | 開機磁碟大小 GB | `50` |
| `OCI_BOOT_VOLUME_VPUS_PER_GB`| 磁碟效能控制單位 (對於 ARM 推薦 10) | `10` |
| `OCI_MAX_INSTANCES` | Compartment 內允許擁有的 ARM 數量上限 | `1` (或 `2`) |

### 5. 執行自動化排程
當設定好 Secrets 與 Variables 後，請前往倉庫上方的 **Actions** 分頁點開：
1. **ARM Auto Registration** -> 點擊 `Run workflow` 手動觸發看一次是否設定正確並開始運行，之後每 30 分鐘就會自動執行。
2. 你會同時看到 **Daily Report** 確保每天的 0:00 發送回報訊息。

---

## ⚠️ 免責聲明
- 本專案僅供學術交流與程式設計練習，請勿濫用 Github Actions 免費額度。
- 若違反 OCI 用戶協議，可能會引發帳號停權的風險，使用者須自行負責。
