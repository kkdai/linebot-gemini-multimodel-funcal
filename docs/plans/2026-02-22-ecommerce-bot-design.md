# 電商客服 LINE Bot 設計文件

**日期：** 2026-02-22
**功能：** 智慧電商客服與視覺化訂單機器人（Multimodal Function Response）

---

## 目標

利用 Gemini 的 **Multimodal Function Response** 功能，讓 LINE Bot 在呼叫查詢函式時，直接在函式回應中包含商品圖片。Gemini 能「看見」圖片並生成更直覺的客服回應，LINE Bot 同時回傳文字說明與商品圖片。

---

## 整體架構

```
linebot-gemini-multimodel-funcall/
├── main.py                           # FastAPI app + LINE webhook + /images/{id} endpoint
├── multi_tool_agent/
│   └── ecommerce_agent.py           # EcommerceAgent class + Mock DB + tools
└── requirements.txt                  # 現有依賴不變（Pillow 已有）
```

### 請求流程

```
LINE User 傳訊息
       ↓
POST / (LINE Webhook)
       ↓
EcommerceAgent.process_message(text, line_user_id)
       ↓
┌─── genai.aio.models.generate_content() ──────────────────────────────┐
│  1. 有 function_call → execute_tool() → (result_dict, image_bytes)   │
│  2. 建構 FunctionResponsePart(inline_data=Blob(image_bytes))         │
│  3. Part.from_function_response(name, result, parts=[image_part])    │
│  4. Gemini 看到圖片 → 生成描述商品的最終文字回應                        │
└───────────────────────────────────────────────────────────────────────┘
       ↓
回傳 (text_response, image_bytes | None)
       ↓
image_bytes → image_cache[uuid] → image_url = {BOT_HOST_URL}/images/{uuid}
       ↓
line_bot_api.reply_message([TextSendMessage(text), ImageSendMessage(url)])
```

### 環境變數

| 變數名 | 說明 | 必要性 |
|--------|------|--------|
| `ChannelSecret` | LINE Channel Secret | 必須 |
| `ChannelAccessToken` | LINE Channel Access Token | 必須 |
| `GOOGLE_API_KEY` | Google AI API Key | 必須（非 Vertex 時）|
| `BOT_HOST_URL` | Bot 公開 URL，例如 `https://xxx.run.app` | 必須 |
| `GOOGLE_GENAI_USE_VERTEXAI` | `True` 則使用 Vertex AI | 可選 |
| `GOOGLE_CLOUD_PROJECT` | GCP 專案 ID（Vertex 用）| Vertex 時必須 |
| `GOOGLE_CLOUD_LOCATION` | GCP 區域（Vertex 用）| Vertex 時必須 |
| `GEMINI_MODEL` | 模型名稱，預設 `gemini-2.0-flash` | 可選 |

---

## 資料層

### 商品庫（`PRODUCTS_DB`）

| ID | 名稱 | 顏色 | 類別 | 價格 | 庫存 |
|----|------|------|------|------|------|
| P001 | 深綠色V領棉質襯衫 | 深綠色 | 上衣 | NT$890 | 15 |
| P002 | 白色寬鬆連帽T恤 | 白色 | 上衣 | NT$690 | 20 |
| P003 | 深藍色直筒牛仔褲 | 深藍色 | 下著 | NT$1290 | 8 |
| P004 | 粉紅色格紋洋裝 | 粉紅色 | 洋裝 | NT$1590 | 5 |
| P005 | 黑色皮革短靴 | 黑色 | 鞋款 | NT$2490 | 3 |

### 訂單庫（Per-user 綁定）

- `user_bindings: dict[line_user_id, list[Order]]`
- 用戶**第一次查詢訂單**時，將 demo 預設訂單（P001 + P003，分別為上月和近三個月內）綁定至其 LINE user_id
- 每筆訂單欄位：`order_id`, `date`, `product_id`, `quantity`, `total`, `status`, `shipping_addr`

### Pillow 圖片生成

- 每張 400×400px JPEG
- 彩色背景（對應商品顏色 RGB）
- 白色商品名稱文字（置中）
- 黃色價格標籤（底部）

---

## Multimodal Function Response 核心

### Gemini 工具宣告（3個 FunctionDeclaration）

1. **`search_products`** - 根據描述和顏色搜尋商品
2. **`get_order_history`** - 查詢用戶訂單歷史（支援 time_range: all / last_month / last_3_months）
3. **`get_product_details`** - 取得特定商品詳細資訊

### 多模態函式回應構建

```python
# Gemini 「看見」商品圖片的關鍵程式碼
multimodal_part = types.FunctionResponsePart(
    inline_data=types.Blob(mime_type="image/jpeg", data=image_bytes),
    display_name=f"product_{product_id}",
)
fn_response_part = types.Part.from_function_response(
    name=func_name,
    response={**result_dict, "image": {"$ref": f"product_{product_id}"}},
    parts=[multimodal_part],
)
```

### System Instruction

告知 Gemini：
- 你是電商客服助理
- 當收到函式回應時，仔細觀察商品圖片
- 描述你看到的外觀、顏色、款式
- 用繁體中文回答

### 函式呼叫迴圈

最多 5 次迭代防止無限循環：
```
generate_content → function_call? → execute + build multimodal response
                 → generate_content → ... → final text response ✓
```

---

## LINE Bot 端點

### FastAPI Endpoints

- `POST /` — LINE Webhook（現有）
- `GET /images/{image_id}` — 圖片服務（新增）

### 圖片快取

```python
image_cache: dict[str, bytes] = {}  # uuid → JPEG bytes（in-memory）
```

### 訊息回覆策略

- 最多回傳 **1 張主圖** + 文字說明
- 若無圖片，只回傳文字訊息

### 對話記憶

- `conversation_histories: dict[line_user_id, list[Content]]`
- 每用戶保留最後 20 個 Content（約 10 輪對話）

---

## Demo 場景示例

### 主要 Demo 腳本

```
用戶：「幫我看看我上個月買的那件綠色襯衫」
Bot 行為：
  1. 呼叫 get_order_history(user_id, time_range="last_month")
  2. 函式返回訂單資料 + P001 深綠色V領棉質襯衫圖片（Gemini 可見）
  3. Gemini 觀察圖片後回應：
     「是這件深綠色V領棉質襯衫嗎？您的訂單 ORD-2026-0115，
      已於2026年1月15日送達，數量1件，共 NT$890。
      圖片中是一件深綠色的V領款式，棉質材質，非常適合日常穿搭。」
LINE 顯示：文字訊息 + 深綠色棉質襯衫圖片

用戶：「還有其他顏色的版本嗎？」
Bot 行為：
  1. 呼叫 search_products(description="V領棉質襯衫")
  2. 返回相關商品 + 圖片（Gemini 可見）
  3. Gemini 描述各商品外觀並比較
LINE 顯示：文字 + 搜尋結果主圖
```

### 其他測試腳本

```
用戶：「我買過什麼商品？」
用戶：「P003 那件牛仔褲的詳細規格是什麼？」
用戶：「有沒有粉紅色的衣服？」
```

---

## README.md Demo Script 補充（待實作後更新）

README 需新增 **Demo 腳本章節**，包含：
- 預設對話示例
- 觸發 Multimodal Function Response 的建議句子
- 螢幕截圖說明

---

## 實作範圍

**必須實作：**
- [ ] `multi_tool_agent/ecommerce_agent.py` — EcommerceAgent + Mock DB + tools
- [ ] `main.py` — 完整改寫，加入 /images 端點
- [ ] README.md — 新增 Demo Script 章節

**不在範圍內（避免過度工程）：**
- 真實資料庫（SQLite/PostgreSQL）
- 用戶驗證
- 訂單修改/取消功能
- GCS 圖片儲存
- 圖片快取過期機制（demo 用途不需要）
