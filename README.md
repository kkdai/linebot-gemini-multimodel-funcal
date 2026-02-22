# LINE Bot — 智慧電商客服（Gemini Multimodal Function Response）

> 展示 Gemini **Multimodal Function Response** 功能：讓 AI 代理在呼叫外部函式時，直接接收並分析商品圖片，提供圖文並茂的客服體驗。

[![GitHub](https://img.shields.io/badge/GitHub-kkdai%2Flinebot--gemini--multimodel--funcal-blue)](https://github.com/kkdai/linebot-gemini-multimodel-funcal)

## 功能特色

- **Multimodal Function Response**：函式回應中夾帶商品圖片，Gemini 能「看見」並描述圖片內容
- 智慧電商客服：訂單查詢、商品搜尋、商品規格查詢
- 用 [Pillow](https://pillow.readthedocs.io/) 動態生成商品圖片（無需外部圖床）
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
    │  返回結構化資料 + Pillow 生成的圖片 bytes  │
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
| P001 | 深綠色V領棉質襯衫 | 深綠色 | NT$890 |
| P002 | 白色寬鬆連帽T恤 | 白色 | NT$690 |
| P003 | 深藍色直筒牛仔褲 | 深藍色 | NT$1,290 |
| P004 | 粉紅色格紋洋裝 | 粉紅色 | NT$1,590 |
| P005 | 黑色皮革短靴 | 黑色 | NT$2,490 |

**每位 LINE 用戶的預設訂單（第一次查詢時自動綁定）：**

| 訂單編號 | 日期 | 商品 | 狀態 |
|---------|------|------|------|
| ORD-2026-0115 | 2026-01-15 | P001 深綠色V領棉質襯衫 | 已送達 |
| ORD-2026-0108 | 2026-01-08 | P003 深藍色直筒牛仔褲 | 已送達 |

> **圖片說明**：商品圖片由 Pillow 動態生成（400×400 JPEG），以商品顏色為背景、白色商品名稱文字、黃色價格標籤。圖片在工具函式被呼叫時即時生成，無需預先上傳。

---

### 完整 Demo 腳本

以下是逐步展示 Multimodal Function Response 的建議對話流程：

---

#### 🎬 場景 1：查詢訂單並識別商品（主要展示場景）

**展示亮點**：Gemini 透過函式回應中的圖片，「認出」用戶描述的商品。

**建議輸入句子：**
```
幫我看看我上個月買的那件綠色襯衫
```

**Bot 內部執行流程：**

```
步驟 1  用戶訊息送達
        "幫我看看我上個月買的那件綠色襯衫"
            ↓
步驟 2  Gemini 判斷需要查詢訂單，產生 function call：
        get_order_history(line_user_id="Uxxxxxx", time_range="last_3_months")
            ↓
步驟 3  _execute_tool() 執行：
        - get_order_history() 回傳訂單列表（含 P001 深綠色V領棉質襯衫）
        - generate_product_image(P001) 用 Pillow 生成深綠色 400×400 JPEG
            ↓
步驟 4  建構 Multimodal Function Response：
        FunctionResponsePart(
          inline_data=FunctionResponseBlob(
            mime_type="image/jpeg",
            data=<深綠色商品圖片 bytes>  ← Gemini 在這裡看到圖片！
          )
        )
        Part.from_function_response(
          name="get_order_history",
          response={"orders": [...], "order_count": 2},
          parts=[multimodal_part]         ← 圖片夾帶在函式回應中
        )
            ↓
步驟 5  Gemini 收到「訂單資料 + 商品圖片」，生成回應：
        "是這件深綠色V領棉質襯衫嗎？從圖片可以看到這是一件深綠色的
        V領款式，棉質材質。您的訂單 ORD-2026-0115 已於 2026年1月15日
        送達，數量 1 件，共 NT$890。"
            ↓
步驟 6  LINE Bot 回傳：
        [文字訊息] Gemini 的回答
        [圖片訊息] 深綠色V領棉質襯衫圖片（由 /images/{uuid} 提供）
```

**預期 LINE 畫面**：文字說明 + 深綠色商品圖片同時出現在對話框中。

---

#### 🎬 場景 2：商品搜尋（搜尋 + 圖片辨識）

**展示亮點**：Gemini 根據搜尋結果的圖片描述商品外觀。

**建議輸入句子：**
```
有沒有粉紅色的洋裝？
```

**Bot 內部執行流程：**

```
步驟 1  Gemini 呼叫：
        search_products(description="粉紅色洋裝", color="粉紅色")
            ↓
步驟 2  search_products() 配對到 P004 粉紅色格紋洋裝（得分最高）
        generate_product_image(P004) 生成粉紅色背景圖片
            ↓
步驟 3  Multimodal Function Response：
        Gemini 收到搜尋結果 + 粉紅色格紋洋裝圖片
            ↓
步驟 4  Gemini 回應（結合圖片觀察）：
        "有！圖片中是一件粉紅色格紋洋裝（P004），採 A 字裙擺設計，
        浪漫格紋風格，售價 NT$1,590，目前庫存 5 件。"
```

---

#### 🎬 場景 3：查詢商品規格（直接指定商品 ID）

**建議輸入句子：**
```
P003 那件牛仔褲的詳細規格是什麼？
```

**Bot 內部執行流程：**

```
步驟 1  Gemini 呼叫：
        get_product_details(product_id="P003")
            ↓
步驟 2  回傳 P003 規格 + 深藍色牛仔褲圖片
            ↓
步驟 3  Gemini 回應（對照圖片）：
        "圖片中是一件深藍色直筒牛仔褲（P003），彈性牛仔布料，
        直筒版型適合各種場合，售價 NT$1,290，目前庫存 8 件。"
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
黑色短靴還有庫存嗎？
```
```
我最近三個月的訂單有哪些？
```

---

### 核心技術：Multimodal Function Response 程式碼說明

這是讓 Gemini 「看見」函式回傳圖片的關鍵程式碼（`multi_tool_agent/ecommerce_agent.py`）：

```python
from google.genai import types

# ① 用 Pillow 生成商品圖片（400×400 JPEG bytes）
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
| 客服回應品質 | 「您的訂單是深綠色襯衫」 | 「圖片中是一件深綠色V領棉質款式，布料看起來...」 |
| 程式碼差異 | `Part.from_function_response(name, response)` | `Part.from_function_response(name, response, parts=[FunctionResponsePart(...)])` |

---

## Technologies Used

- Python 3.12+
- [FastAPI](https://fastapi.tiangolo.com/)
- [LINE Messaging API](https://developers.line.biz/en/services/messaging-api/)
- [Google Gemini API](https://ai.google.dev/) via `google-genai 1.49.0`
- [Pillow](https://pillow.readthedocs.io/) — 動態商品圖片生成
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
