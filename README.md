# LINE Bot — 智慧電商客服（Gemini Multimodal Function Response）

> 展示 Gemini **Multimodal Function Response** 功能：讓 AI 代理在呼叫外部函式時，直接接收並分析商品圖片，提供圖文並茂的客服體驗。

[![GitHub](https://img.shields.io/badge/GitHub-kkdai%2Flinebot--gemini--multimodel--funcal-blue)](https://github.com/kkdai/linebot-gemini-multimodel-funcal)

<img width="455" height="488" alt="Microsoft PowerPoint 2026-02-25 23 46 54" src="https://github.com/user-attachments/assets/12f8dc23-67e3-49a6-a7ac-e9469456b607" />

## 功能特色

- **Multimodal Function Response**：函式回應中夾帶商品圖片，Gemini 能「看見」並描述圖片內容
- 智慧電商客服：訂單查詢、商品搜尋、商品規格查詢
- 使用真實 Unsplash 服飾攝影照片，搭配 `img/` 目錄靜態圖片
- FastAPI 非同步架構，支援 Cloud Run 部署
- 完整的 pytest 測試套件

## 技術架構

```
LINE User
    │  傳訊息
    ▼
POST /  (LINE Webhook)
    │
    ▼
EcommerceAgent.process_message()
    │
    ▼  ① 發送對話歷史給 Gemini
google.genai.Client.aio.models.generate_content()
    │
    │  ② Gemini 決定呼叫工具
    ▼
_execute_tool()  ──────────────────────────┐
    │  返回結構化資料 + 真實商品照片 bytes       │
    │                                       │
    ▼  ③ 建構多模態函式回應                    │
FunctionResponsePart(                      │
  inline_data=FunctionResponseBlob(        │
    data=image_bytes  ◄─────────────────── ┘
  )
)
    │
    ▼  ④ Gemini 看到圖片，生成含圖片描述的回答
generate_content() (再次呼叫)
    │
    ▼
LINE Bot reply:
  [TextSendMessage]  ← Gemini 分析圖片後的文字回應
  [ImageSendMessage] ← GET /images/{uuid} 提供的圖片
```

## Demo 展示說明

### 商品資料庫（預設 Mock 資料）

系統內建 5 件商品與每位 LINE 用戶的 2 筆 demo 訂單：

| 商品 ID | 名稱 | 顏色 | 價格 |
|--------|------|------|------|
| P001 | 棕色飛行員外套 | 棕色 | NT$1,890 |
| P002 | 白色棉質大學T | 白色 | NT$690 |
| P003 | 深藍色牛仔外套 | 深藍色 | NT$1,490 |
| P004 | 米白色針織披肩 | 米白色 | NT$1,290 |
| P005 | 淺藍色簡約T恤 | 淺藍色 | NT$490 |

**每位 LINE 用戶的預設訂單（第一次查詢時自動綁定）：**

| 訂單編號 | 日期 | 商品 | 狀態 |
|---------|------|------|------|
| ORD-2026-0115 | 2026-01-15 | P001 棕色飛行員外套 | 已送達 |
| ORD-2026-0108 | 2026-01-08 | P003 深藍色牛仔外套 | 已送達 |

> **圖片說明**：商品圖片為真實 Unsplash 服飾攝影照片，儲存於 `img/` 目錄。工具函式被呼叫時直接讀取圖片 bytes，夾帶進 Multimodal Function Response 讓 Gemini 分析。

---

### 完整 Demo 腳本

以下是逐步展示 Multimodal Function Response 的建議對話流程：

---

#### 🎬 場景 1：查詢訂單並識別商品（主要展示場景）

**展示亮點**：Gemini 透過函式回應中的真實照片，「看見」並描述用戶曾購買的外套。

**建議輸入句子：**
```
幫我看看我之前買過的外套
```

**Bot 內部執行流程：**

```
步驟 1  用戶訊息送達
        "幫我看看我之前買過的外套"
            ↓
步驟 2  Gemini 判斷需要查詢訂單，產生 function call：
        get_order_history(time_range="all")
            ↓
步驟 3  _execute_tool() 執行：
        - get_order_history() 回傳兩筆訂單（P001、P003）
        - 讀取 img/tobias-tullius-...-unsplash.jpg → P001 棕色飛行員外套照片 bytes
            ↓
步驟 4  建構 Multimodal Function Response：
        FunctionResponsePart(
          inline_data=FunctionResponseBlob(
            mime_type="image/jpeg",
            data=<棕色飛行員外套真實照片 bytes>  ← Gemini 在這裡看到圖片！
          )
        )
        Part.from_function_response(
          name="get_order_history",
          response={"orders": [...], "order_count": 2},
          parts=[multimodal_part]         ← 圖片夾帶在函式回應中
        )
            ↓
步驟 5  Gemini 收到「訂單資料 + 真實商品照片」，生成回應：
        "從照片中可以看到這是一件棕色飛行員外套，輕量尼龍材質，
        側邊有金屬拉鏈裝飾口袋，版型俐落。您的訂單 ORD-2026-0115
        已於 2026年1月15日送達，共 NT$1,890。"
            ↓
步驟 6  LINE Bot 回傳：
        [文字訊息] Gemini 的回答
        [圖片訊息] 棕色飛行員外套照片（由 /images/{uuid} 提供）
```

**預期 LINE 畫面**：文字說明 + 真實外套攝影照同時出現在對話框中。

---

#### 🎬 場景 2：商品搜尋（搜尋 + 圖片辨識）

**展示亮點**：Gemini 根據搜尋結果的真實照片，描述商品的實際外觀與細節。

**建議輸入句子：**
```
有沒有深藍色的外套？
```

**Bot 內部執行流程：**

```
步驟 1  Gemini 呼叫：
        search_products(description="深藍色外套", color="深藍色")
            ↓
步驟 2  search_products() 配對到 P003 深藍色牛仔外套（得分最高）
        讀取 img/caio-coelho-...-unsplash.jpg → 深藍色牛仔外套真實照片
            ↓
步驟 3  Multimodal Function Response：
        Gemini 收到搜尋結果 + 深藍色牛仔外套照片
            ↓
步驟 4  Gemini 回應（結合圖片觀察）：
        "有！照片中這件深藍色牛仔外套（P003）可以看到復古風格的
        縫線設計，翻領搭配金屬鈕扣，成衣感十足。售價 NT$1,490，
        目前庫存 8 件。"
```

---

#### 🎬 場景 3：查詢商品規格（直接指定商品 ID）

**建議輸入句子：**
```
P004 的針織披肩有什麼特色？
```

**Bot 內部執行流程：**

```
步驟 1  Gemini 呼叫：
        get_product_details(product_id="P004")
            ↓
步驟 2  回傳 P004 規格 + 讀取 img/milada-vigerova-...-unsplash.jpg
            ↓
步驟 3  Gemini 回應（對照真實照片）：
        "照片中是一件米白色手工鉤針編織披肩，V 領設計搭配底部流蘇，
        整體質感輕盈優雅。掛在木衣架上可以看到蕾絲感網格編織。
        售價 NT$1,290，庫存 5 件。"
```

---

#### 🎬 其他推薦測試句子

```
我買過哪些東西？
```
```
幫我找找看有什麼白色的上衣
```
```
有適合秋天穿的外套嗎？
```
```
我最近三個月的訂單有哪些？
```

---

### 核心技術：Multimodal Function Response 程式碼說明

這是讓 Gemini 「看見」函式回傳圖片的關鍵程式碼（`multi_tool_agent/ecommerce_agent.py`）：

```python
from google.genai import types

# ① 讀取真實商品照片（JPEG bytes）
image_bytes = generate_product_image(PRODUCTS_DB["P001"])

# ② 建構多模態部件：把圖片包進 FunctionResponsePart
#    注意：要用 FunctionResponseBlob，不是 types.Blob
multimodal_part = types.FunctionResponsePart(
    inline_data=types.FunctionResponseBlob(
        mime_type="image/jpeg",
        data=image_bytes,        # raw bytes，SDK 內部自動處理 base64
    )
)

# ③ 把圖片附加在函式回應的 parts 參數
fn_response_part = types.Part.from_function_response(
    name="get_order_history",
    response={                   # 結構化的文字資料
        "status": "success",
        "orders": [...],
        "order_count": 2,
    },
    parts=[multimodal_part],     # ← 圖片在這裡！Gemini 收到後可以「看見」
)

# ④ 加入對話歷史，讓 Gemini 繼續生成回應
contents.append(types.Content(role="tool", parts=[fn_response_part]))

# ⑤ Gemini 現在能分析圖片 + 文字資料，一起生成更豐富的回應
response = await client.aio.models.generate_content(
    model="gemini-2.0-flash",
    contents=contents,
    config=types.GenerateContentConfig(tools=ECOMMERCE_TOOLS),
)
```

**關鍵差異**（傳統 Function Response vs Multimodal Function Response）：

| | 傳統 Function Response | **Multimodal Function Response** |
|--|--|--|
| 函式回傳值 | 純文字/JSON | JSON + 圖片/PDF |
| Gemini 能感知 | 文字資料 | 文字資料 **+ 視覺內容** |
| 客服回應品質 | 「您的訂單是棕色飛行員外套」 | 「照片中可以看到這件外套的尼龍材質光澤，側邊拉鏈口袋...」 |
| 程式碼差異 | `Part.from_function_response(name, response)` | `Part.from_function_response(name, response, parts=[FunctionResponsePart(...)])` |

---

## Technologies Used

- Python 3.12+
- [FastAPI](https://fastapi.tiangolo.com/)
- [LINE Messaging API](https://developers.line.biz/en/services/messaging-api/)
- [Google Gemini API](https://ai.google.dev/) via `google-genai 1.49.0`
- 商品照片：[Unsplash](https://unsplash.com/)（儲存於 `img/` 目錄）
- Docker / Google Cloud Run（部署）

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/kkdai/linebot-gemini-multimodel-funcal.git
cd linebot-gemini-multimodel-funcal
```

### 2. Set environment variables

| 變數 | 說明 | 必要 |
|------|------|------|
| `ChannelSecret` | LINE Channel Secret | ✅ |
| `ChannelAccessToken` | LINE Channel Access Token | ✅ |
| `GOOGLE_API_KEY` | Google AI Studio API Key | ✅（非 Vertex）|
| `BOT_HOST_URL` | Bot 公開 HTTPS URL，例如 `https://xxx.run.app` | ✅ |
| `GEMINI_MODEL` | Gemini 模型名稱，預設 `gemini-2.0-flash` | 選填 |
| `GOOGLE_GENAI_USE_VERTEXAI` | `True` 使用 Vertex AI | 選填 |
| `GOOGLE_CLOUD_PROJECT` | GCP 專案 ID（Vertex 用）| Vertex 時必填 |
| `GOOGLE_CLOUD_LOCATION` | GCP 區域（Vertex 用），預設 `us-central1` | Vertex 時必填 |

> **BOT_HOST_URL 說明**：LINE Bot 發送圖片時需要提供 HTTPS URL。本機開發可使用 [ngrok](https://ngrok.com/) 取得公開 URL，Cloud Run 部署時使用服務 URL。

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the server

```bash
BOT_HOST_URL=https://your-ngrok-url.ngrok.io \
GOOGLE_API_KEY=your-key \
ChannelSecret=your-secret \
ChannelAccessToken=your-token \
uvicorn main:app --reload --port 8000
```

### 5. Set up LINE webhook

將 LINE Bot webhook URL 設定為 `https://your-ngrok-url.ngrok.io/`。

---

## Running Tests

```bash
pytest tests/ -v
```

Expected: 20 tests PASSED

---

## Deployment Options

### Local Development with ngrok

```bash
ngrok http 8000
# 取得 HTTPS URL，例如 https://xxxx.ngrok.io
# 設定為 BOT_HOST_URL 環境變數
```

### Docker

```bash
docker build -t linebot-gemini-multimodal .
docker run -p 8000:8000 \
  -e ChannelSecret=YOUR_SECRET \
  -e ChannelAccessToken=YOUR_TOKEN \
  -e GOOGLE_API_KEY=YOUR_GEMINI_KEY \
  -e BOT_HOST_URL=https://your-domain.com \
  linebot-gemini-multimodal
```

### Google Cloud Run

```bash
# 1. 設定專案
gcloud config set project YOUR_PROJECT_ID

# 2. Build & push
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/linebot-gemini-multimodal

# 3. Deploy
gcloud run deploy linebot-gemini-multimodal \
  --image gcr.io/YOUR_PROJECT_ID/linebot-gemini-multimodal \
  --platform managed \
  --region asia-east1 \
  --allow-unauthenticated \
  --set-env-vars \
    ChannelSecret=YOUR_SECRET,\
    ChannelAccessToken=YOUR_TOKEN,\
    GOOGLE_API_KEY=YOUR_GEMINI_KEY,\
    BOT_HOST_URL=https://YOUR_CLOUD_RUN_URL

# 4. 取得服務 URL
gcloud run services describe linebot-gemini-multimodal \
  --platform managed --region asia-east1 \
  --format 'value(status.url)'
```

> **注意**：`BOT_HOST_URL` 要設定為 Cloud Run 服務 URL（部署後才能取得）。可先部署一次，取得 URL 後更新環境變數再部署一次。

#### 使用 Secret Manager（推薦）

```bash
# 建立 secrets
echo -n "YOUR_SECRET" | gcloud secrets create line-channel-secret --data-file=-
echo -n "YOUR_TOKEN" | gcloud secrets create line-channel-token --data-file=-
echo -n "YOUR_GEMINI_KEY" | gcloud secrets create gemini-api-key --data-file=-

# 部署時引用
gcloud run deploy linebot-gemini-multimodal \
  --image gcr.io/YOUR_PROJECT_ID/linebot-gemini-multimodal \
  --platform managed --region asia-east1 \
  --allow-unauthenticated \
  --update-secrets=ChannelSecret=line-channel-secret:latest,\
ChannelAccessToken=line-channel-token:latest,\
GOOGLE_API_KEY=gemini-api-key:latest
```

## Monitoring

```bash
# 查看 Cloud Run logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=linebot-gemini-multimodal" \
  --limit 50
```

## Related Resources

- [Gemini Multimodal Function Response 官方文件](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/function-calling#mm-fr)
- [LINE Messaging API 文件](https://developers.line.biz/en/docs/messaging-api/)
- [google-genai Python SDK](https://github.com/googleapis/python-genai)
