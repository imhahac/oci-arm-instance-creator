# Oracle Cloud ARM 自動開機腳本 (GitHub Actions)

[![ARM Auto Registration](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/register.yml/badge.svg)](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/register.yml)
[![Daily Report](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/daily_report.yml/badge.svg)](https://github.com/imhahac/oci-arm-instance-creator/actions/workflows/daily_report.yml)

這是一個利用 GitHub Actions 的免費排程資源，24 小時自動化幫你監控並在有資源時自動創建 Oracle Cloud Infrastructure (OCI) Always Free 永久免費 ARM 虛擬機 (4 OCPU / 24GB Memory) 的專案。

## 🌟 功能特色
* **完全免費與智慧防撞**：利用 Github Actions 自動運作。具備自動休眠與併發上限機制 (Concurrency Control)，避免流量過高與重複執行。
* **多區域輪詢 (Multi-Region)**：支援設定多個機房，若 A 機房滿載，無縫自動跳轉 B 機房嘗試。
* **容量不足跳過 (Skip on Capacity)**：遇到資源不足時會自動跳過該區域並嘗試下一個地域。
* **自動停止 (Auto-Stop)**：申請成功或已達上限數量時，自動中止 GitHub 排程以節省資源。
* **跨平台通知**：支援 LINE、Telegram、Discord 跨平台通知。
* **日結報告**：每日發送狀態回報推播。

---

## 🚀 部署教學 (Deployment Guide)

### 1. 準備 OCI 相關資訊
登入 OCI 控制台獲取以下資訊：
- **使用者設定 -> API 金鑰**：生成金鑰並下載私鑰 (`.pem`)。
- **租戶 OCID (Tenancy)** / **使用者 OCID (User)** / **區間 OCID (Compartment)**。
- **子網路 OCID (Subnet)** / **映像檔 OCID (Image)**。

### 2. 設定 GitHub Secrets (機密資訊)
前往專案 `Settings` -> `Secrets and variables` -> `Actions` -> `Secrets`：

| Secret 名稱 | 說明 |
| :--- | :--- |
| `OCI_CONFIG_USER` | 使用者 OCID |
| `OCI_CONFIG_TENANCY` | 租戶 OCID |
| `OCI_CONFIG_FINGERPRINT` | API 金鑰的指紋 (Fingerprint) |
| `OCI_CONFIG_KEY_CONTENT` | API 私鑰內容 (PEM 格式) |
| `OCI_COMPARTMENT_ID` | 區間 OCID |
| `OCI_SSH_KEY` | 實例啟動後要植入的 **SSH 公鑰** |
| `LINE_ACCESS_TOKEN` / `LINE_USER_ID` | (選填) LINE 通知凭證 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | (選填) Telegram 通知凭證 |
| `DISCORD_WEBHOOK_URL` | (選填) Discord Webhook |

### 3. 設定 GitHub Variables (一般變數)
分頁選擇 `Variables` -> `New repository variable`：

| Variable 名稱 | 範例 | 說明 |
| :--- | :--- | :--- |
| `OCI_CONFIG_REGION` | `ap-osaka-1, ap-tokyo-1` | 嘗試區域 (多個以逗號隔開) |
| `OCI_IMAGE_ID` | `ocid1.image.oc1...` | 映像檔 OCID |
| `OCI_SUBNET_ID` | `ocid1.subnet.oc1...` | 子網路 OCID |
| `OCI_MAX_INSTANCES` | `1` | 限制此腳本最多建立幾台實例 |
| `OCI_OCPUS` | `4` | CPU 數量 |
| `OCI_MEMORY_GBS` | `24` | 記憶體 (GB) |
| `OCI_SHAPE` | `VM.Standard.A1.Flex` | 實例規格 |

---

## 🏃 啟動與結果
1. **手動執行**：在 Actions 分頁選擇 `ARM Auto Registration` 並點選 `Run workflow`。
2. **自動化**：設有排程，成功後會自動 Disable 工作流以防止資源重複佔用。
3. **查看日誌**：每次執行的詳細結果會呈現在工作流頁面的 **Job Summary**。

---

## ⚠️ 免責聲明
- 本專案僅供學術交流與程式設計練習，請勿濫用 Github Actions 免費額度。
- 若違反 OCI 用戶協議，可能會引發帳號停權的風險，使用者須自行負責。
