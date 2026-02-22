# main.py
import os
import sys
import uuid

import aiohttp
from fastapi import Request, FastAPI, HTTPException
from fastapi.responses import Response

from linebot.models import MessageEvent, TextSendMessage, ImageSendMessage
from linebot.exceptions import InvalidSignatureError
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot import AsyncLineBotApi, WebhookParser

from multi_tool_agent.ecommerce_agent import EcommerceAgent

# ── Environment Variables ─────────────────────────────────────────────────────
channel_secret = os.getenv("ChannelSecret")
channel_access_token = os.getenv("ChannelAccessToken")
BOT_HOST_URL = os.getenv("BOT_HOST_URL", "").rstrip("/")
USE_VERTEX = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "False").lower() == "true"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

if not channel_secret:
    print("ERROR: ChannelSecret is required.")
    sys.exit(1)
if not channel_access_token:
    print("ERROR: ChannelAccessToken is required.")
    sys.exit(1)
if not BOT_HOST_URL:
    print("ERROR: BOT_HOST_URL is required (e.g. https://your-service.run.app)")
    sys.exit(1)
if USE_VERTEX and not GOOGLE_CLOUD_PROJECT:
    print("ERROR: GOOGLE_CLOUD_PROJECT is required when USE_VERTEX=True")
    sys.exit(1)
if not USE_VERTEX and not GOOGLE_API_KEY:
    print("ERROR: GOOGLE_API_KEY is required.")
    sys.exit(1)

# ── FastAPI + LINE Bot ────────────────────────────────────────────────────────
app = FastAPI()

# Lazily initialized LINE Bot API (requires running event loop)
_line_bot_api: AsyncLineBotApi | None = None
_aiohttp_session: aiohttp.ClientSession | None = None


def get_line_bot_api() -> AsyncLineBotApi:
    """Return the singleton AsyncLineBotApi, creating it on first call."""
    global _line_bot_api, _aiohttp_session
    if _line_bot_api is None:
        _aiohttp_session = aiohttp.ClientSession()
        async_http_client = AiohttpAsyncHttpClient(_aiohttp_session)
        _line_bot_api = AsyncLineBotApi(channel_access_token, async_http_client)
    return _line_bot_api


parser = WebhookParser(channel_secret)

# ── EcommerceAgent ────────────────────────────────────────────────────────────
if USE_VERTEX:
    ecommerce_agent = EcommerceAgent(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location=GOOGLE_CLOUD_LOCATION,
        model=GEMINI_MODEL,
    )
else:
    ecommerce_agent = EcommerceAgent(
        api_key=GOOGLE_API_KEY,
        model=GEMINI_MODEL,
    )

print(f"EcommerceAgent initialized (model={GEMINI_MODEL}, vertex={USE_VERTEX})")

# ── In-memory image cache ─────────────────────────────────────────────────────
image_cache: dict[str, bytes] = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/images/{image_id}")
async def serve_image(image_id: str):
    """Serve cached product images for LINE Bot display."""
    image_bytes = image_cache.get(image_id)
    if image_bytes is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=image_bytes, media_type="image/jpeg")


@app.post("/")
async def handle_callback(request: Request):
    """LINE Webhook endpoint."""
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if event.message.type != "text":
            continue

        msg_text = event.message.text
        line_user_id = event.source.user_id
        print(f"[MSG] user={line_user_id}: {msg_text}")

        try:
            ai_text, image_bytes = await ecommerce_agent.process_message(
                msg_text, line_user_id
            )
        except Exception as e:
            print(f"[ERROR] Agent error: {e}")
            ai_text = "抱歉，系統發生錯誤，請稍後再試。"
            image_bytes = None

        reply_messages = [TextSendMessage(text=ai_text)]

        if image_bytes:
            image_id = str(uuid.uuid4())
            image_cache[image_id] = image_bytes
            image_url = f"{BOT_HOST_URL}/images/{image_id}"
            reply_messages.append(
                ImageSendMessage(
                    original_content_url=image_url,
                    preview_image_url=image_url,
                )
            )

        await get_line_bot_api().reply_message(event.reply_token, reply_messages)

    return "OK"
