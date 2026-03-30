# Oracle Cloud ARM 自動開機腳本與儀表板

[![ARM Auto Registration](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/register.yml/badge.svg)](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/register.yml)
[![Daily Report](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/daily_report.yml/badge.svg)](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/daily_report.yml)

這是一個利用 GitHub Actions 的免費排程資源，24 小時自動化幫你監控並在有資源時自動創建 Oracle Cloud Infrastructure (OCI) Always Free 永久免費 ARM 虛擬機 (4 OCPU / 24GB Memory) 的專案。**內建精美的靜態網頁與統計圖表儀表板 (Dashboard)**。

## 🏗 架構設計 (Architecture)

```mermaid
graph TD
    A[GitHub Actions 排程] -->|觸發| B(oracle_arm_manager.py)
    B --> C{預算與配額檢查}
    C -->|超過預算| H[發送停用警告]
    C -->|配額未滿| D{嘗試指定區域 API}
    D -->|Capacity Error| E[切換下個區域 / AD]
    D -->|Rate Limit Error| E
    D -->|成功| F[發送成功通知與 IP]
    F --> G[Github 停止排程]
    E -->|迴圈結束全失敗| I[記錄並寫入 stats.json]
    I --> J[推播更新 GitHub Pages 面板]
```

## 🌟 功能特色
* **完全免費與智慧防撞**：具備自動休眠、併發上限機制與隨機延遲 (Jitter)，避免流量集中被封鎖。
* **多區域輪詢 (Multi-Region)**：若機房 A 容量不足，無縫自動跳轉機房 B 嘗試。
* **靜態儀表板 (Dashboard)**：透過 GitHub Actions 每次發布執行數據 (`stats.json`)，自動生成精美的成功率與錯誤分佈圖表。
* **自動停止 (Auto-Stop)**：建立成功或已達上限數量時，自動中止 GitHub 排程。
* **跨平台通知**：支援 LINE、Telegram、Discord 即時發送執行明細與報表。

---

## 🚀 部署教學 (Deployment Guide)

### 1. 準備 OCI 相關資訊
登入 OCI 控制台獲取以下資訊：
- **使用者設定 -> API 金鑰**：生成金鑰並下載私鑰 (`.pem`)。
- **配置與 OCID**：收集 Tenant, User, Compartment, Subnet, Image 等 OCID。

### 2. 設定 GitHub Secrets (機密資訊)
前往專案 `Settings` -> `Secrets and variables` -> `Actions` -> `Secrets`，加入以下必填：
- `OCI_CONFIG_USER`, `OCI_CONFIG_TENANCY`, `OCI_CONFIG_FINGERPRINT`, `OCI_CONFIG_KEY_CONTENT`, `OCI_COMPARTMENT_ID`, `OCI_SSH_KEY`

通知憑證 (選填)：
- `LINE_ACCESS_TOKEN` / `LINE_USER_ID`
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
- `DISCORD_WEBHOOK_URL`

### 3. 設定 GitHub Variables (一般變數)
分頁選擇 `Variables`：
| Variable 名稱 | 範例 | 說明 |
| :--- | :--- | :--- |
| `OCI_CONFIG_REGION` | `ap-osaka-1, ap-tokyo-1` | 嘗試區域 (多個以逗號隔開) |
| `OCI_IMAGE_ID` | `ocid1.image.oc1...` | 映像檔 OCID |
| `OCI_SUBNET_ID` | `ocid1.subnet.oc1...` | 子網路 OCID |
| `OCI_SHAPE` | `VM.Standard.A1.Flex` | 實例規格 (ARM 均為此值) |
| `OCI_OCPUS` | `4` | CPU 核心數 (永久免費上限 4) |
| `OCI_MEMORY_GBS` | `24` | 記憶體大小 (永久免費上限 24) |
| `OCI_MAX_INSTANCES` | `2` | 該區域最多允許建立的實例數量 |
| `OCI_BOOT_VOLUME_SIZE`| `50` | 引導磁碟大小 (GB) |
| `OCI_COST_THRESHOLD` | `0.1` | 本月預算門檻 (USD)，超過將停用 API 呼叫 |

### 4. 啟用 GitHub Pages 儀表板
前往專案 `Settings` -> `Pages`：
1. Source 選擇 `Deploy from a branch`
2. Branch 選擇 `main`，資料夾選擇 `/root`
3. 儲存後，等待 GitHub Pages 發布完成，即可透過 `https://<你的帳號>.github.io/<專案名>/dashboard/` 查看儀表板！

---

## 🛠 故障排除 (Troubleshooting)

| 錯誤現象 | 可能原因 | 解決方式 |
| :--- | :--- | :--- |
| **API 身分驗證失敗 (401)** | `OCI_CONFIG_KEY_CONTENT` 格式錯誤 | 請確保貼上 PEM 內容時包含 `-----BEGIN PRIVATE KEY-----` 等標籤，且沒有多餘換行。 |
| **讀取 AD 列表失敗** | 區間(Compartment) 或 租戶 ID 錯誤 | 請確認 `OCI_COMPARTMENT_ID` 及權限設置正確。 |
| **Rate Limit / 429 Error** | 執行過度頻繁被 Oracle 暫禁 | 這是正常現象，腳本會紀錄並在下一輪自動重試，請勿將排程降低至小於 10 分鐘。 |
| **圖表沒顯示資料** | `stats.json` 尚未產生 | 請手動進 Actions 點擊 `Run workflow` 跑一次取得首波資料。 |

---

## 👨‍💻 開發者文檔 (Developer Guide)

本專案採用高度模組化架構，主代碼位於 `oracle_arm_manager/` 目錄：
- `config.py`: 環境變數收納與防呆檢查。
- `oci_manager.py`: OCI SDK 基礎通訊層。
- `notifier.py`: 基於 Strategy Pattern 設計的多管道通知模組。
- `instance_launcher.py`: 核心重試與跳轉邏輯調度。

**如何測試本地端：**
1. 複製 `.env.example` 為 `.env` 並填寫測試憑證。
2. 建立虛擬環境執行 `pip install -r requirements.txt` (自行產生)。
3. 執行主程式：`python oracle_arm_manager.py`。
4. 前端檢視：使用 VS Code Live Server 打開 `dashboard/index.html`。

---

## ⚠️ 免責聲明
- 本專案僅供學術交流與程式設計練習，請勿濫用 Github Actions。
- 若違反 OCI 用戶協議引發帳號停權風險，使用者須自行負責。
