# LINE Bot with Google ADK (Agent SDK) and Google Gemini

## Project Background

This project is a LINE bot that uses Google ADK (Agent SDK) and Google Gemini models to generate responses to text inputs. The bot can answer questions in Traditional Chinese and provide helpful information.

## Screenshot

![image](https://github.com/user-attachments/assets/2bcbd827-0047-4a3a-8645-f8075d996c10)

## Features

- Text message processing using AI models (Google ADK or Google Gemini)
- Support for function calling with custom tools
- Integration with LINE Messaging API
- Built with FastAPI for high-performance async processing
- Containerized with Docker for easy deployment

## Demo — Multimodal Function Response 展示腳本

本 Bot 展示 Gemini 的 **Multimodal Function Response** 功能：當 Bot 呼叫查詢函式時，函式回應中直接包含商品圖片，讓 Gemini 能「看見」圖片並生成更精準的客服回應。

### 建議測試對話

以下對話可完整展示 Multimodal Function Response 的效果：

**場景 1：查詢上個月的訂單**

```
您：幫我看看我上個月買的那件綠色襯衫
Bot 行為：
  - 呼叫 get_order_history（Gemini 收到訂單資料 + 商品圖片）
  - Gemini 觀察圖片後回應：「是這件深綠色V領棉質襯衫嗎？您的訂單
    ORD-2026-0115 已於1月15日送達，共 NT$890。」
  - LINE 同時顯示：文字訊息 + 深綠色棉質襯衫圖片
```

**場景 2：搜尋商品**

```
您：有沒有粉紅色的洋裝？
Bot 行為：
  - 呼叫 search_products（Gemini 收到搜尋結果 + 商品圖片）
  - Gemini 描述圖片中的商品外觀
  - LINE 同時顯示：文字介紹 + 粉紅色格紋洋裝圖片
```

**場景 3：查詢商品詳細規格**

```
您：P003 那件牛仔褲的詳細資訊
Bot 行為：
  - 呼叫 get_product_details（Gemini 收到規格 + 牛仔褲圖片）
  - Gemini 結合圖片說明：深藍色直筒版型、彈性牛仔布料、NT$1,290
  - LINE 同時顯示：規格說明 + 商品圖片
```

**其他測試句子**
- `「我買過哪些東西？」`
- `「幫我找找看有什麼白色的上衣」`
- `「黑色短靴還有庫存嗎？」`

### 技術亮點

本 Demo 使用 **google-genai 1.49.0** 的 Multimodal Function Response API：

```python
# 商品圖片以 inline_data 傳給 Gemini（Gemini 可直接看見圖片）
multimodal_part = types.FunctionResponsePart(
    inline_data=types.FunctionResponseBlob(
        mime_type="image/jpeg",
        data=product_image_bytes,  # Pillow 動態生成的 JPEG
    )
)
fn_response = types.Part.from_function_response(
    name="get_order_history",
    response=order_data_dict,
    parts=[multimodal_part],  # ← Gemini 在這裡「看見」商品圖片！
)
```

## Technologies Used

- Python 3.9+
- FastAPI
- LINE Messaging API
- Google ADK (Agent SDK)
- Google Gemini API
- Docker
- Google Cloud Run (for deployment)

## Setup

1. Clone the repository to your local machine.
2. Set the following environment variables:
   - `ChannelSecret`: Your LINE channel secret
   - `ChannelAccessToken`: Your LINE channel access token
   - `GEMINI_API_KEY`: Your Google Gemini API key
   - `BOT_HOST_URL`: 您的 Bot 公開 URL，例如 `https://xxx.run.app`（供圖片服務使用）
   - `GEMINI_MODEL`: （可選）Gemini 模型名稱，預設 `gemini-2.0-flash`

3. Install the required dependencies:

   ```
   pip install -r requirements.txt
   ```

4. Start the FastAPI server:

   ```
   uvicorn main:app --reload
   ```

5. Set up your LINE bot webhook URL to point to your server's endpoint.

## Usage

### Text Processing

Send any text message to the LINE bot, and it will use the configured AI model to generate a response. The bot is optimized for Traditional Chinese responses.

### Available Tools

The bot can be configured with various function tools such as:

- Weather information retrieval
- Translation services
- Data lookup capabilities
- Custom tools based on your specific needs

## Deployment Options

### Local Development

Use ngrok or similar tools to expose your local server to the internet for webhook access:

```
ngrok http 8000
```

### Docker Deployment

You can use the included Dockerfile to build and deploy the application:

```
docker build -t linebot-adk .
docker run -p 8000:8000 \
  -e ChannelSecret=YOUR_SECRET \
  -e ChannelAccessToken=YOUR_TOKEN \
  -e GEMINI_API_KEY=YOUR_GEMINI_KEY \
  linebot-adk
```

### Google Cloud Deployment

#### Prerequisites

1. Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
2. Create a Google Cloud project and enable the following APIs:
   - Cloud Run API
   - Container Registry API or Artifact Registry API
   - Cloud Build API

#### Steps for Deployment

1. Authenticate with Google Cloud:

   ```
   gcloud auth login
   ```

2. Set your Google Cloud project:

   ```
   gcloud config set project YOUR_PROJECT_ID
   ```

3. Build and push the Docker image to Google Container Registry:

   ```
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/linebot-adk
   ```

4. Deploy to Cloud Run:

   ```
   gcloud run deploy linebot-adk \
     --image gcr.io/YOUR_PROJECT_ID/linebot-adk \
     --platform managed \
     --region asia-east1 \
     --allow-unauthenticated \
     --set-env-vars ChannelSecret=YOUR_SECRET,ChannelAccessToken=YOUR_TOKEN,GEMINI_API_KEY=YOUR_GEMINI_KEY
   ```

   Note: For production, it's recommended to use Secret Manager for storing sensitive environment variables.

5. Get the service URL:

   ```
   gcloud run services describe linebot-adk --platform managed --region asia-east1 --format 'value(status.url)'
   ```

6. Set the service URL as your LINE Bot webhook URL in the LINE Developer Console.

#### Setting Up Secrets in Google Cloud (Recommended)

For better security, store your API keys as secrets:

1. Create secrets for your sensitive values:

   ```
   echo -n "YOUR_SECRET" | gcloud secrets create line-channel-secret --data-file=-
   echo -n "YOUR_TOKEN" | gcloud secrets create line-channel-token --data-file=-
   echo -n "YOUR_GEMINI_KEY" | gcloud secrets create gemini-api-key --data-file=-
   ```

2. Give the Cloud Run service access to these secrets:

   ```
   gcloud secrets add-iam-policy-binding line-channel-secret --member=serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor
   gcloud secrets add-iam-policy-binding line-channel-token --member=serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor
   gcloud secrets add-iam-policy-binding gemini-api-key --member=serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor
   ```

3. Deploy with secrets:

   ```
   gcloud run deploy linebot-adk \
     --image gcr.io/YOUR_PROJECT_ID/linebot-adk \
     --platform managed \
     --region asia-east1 \
     --allow-unauthenticated \
     --update-secrets=ChannelSecret=line-channel-secret:latest,ChannelAccessToken=line-channel-token:latest,GEMINI_API_KEY=gemini-api-key:latest
   ```

## Maintenance and Monitoring

After deployment, you can monitor your service through the Google Cloud Console:

1. View logs: `gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=linebot-adk"`
2. Check service metrics: Access the Cloud Run dashboard in Google Cloud Console
3. Set up alerts for error rates or high latency in Cloud Monitoring
