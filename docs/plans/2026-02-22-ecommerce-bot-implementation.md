# 電商客服 LINE Bot（Multimodal Function Response）實作計劃

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 打造能使用 Gemini Multimodal Function Response 的電商客服 LINE Bot，讓 Gemini 能「看見」函式回傳的商品圖片，並生成圖文並茂的客服回應。

**Architecture:** 繞過 Google ADK，直接使用 `google.genai.Client.aio.models.generate_content()` 實作完整的函式呼叫循環。商品圖片以 Pillow 動態生成，透過 FastAPI `/images/{id}` 端點提供 LINE 顯示，同時以 `FunctionResponseBlob` 傳遞給 Gemini 分析。

**Tech Stack:** Python 3.9+, FastAPI, google-genai 1.49.0, line-bot-sdk 3.14.0, Pillow, pytest, pytest-asyncio

---

## 已確認的關鍵 API（google-genai 1.49.0）

```python
# 多模態函式回應的正確構建方式：
multimodal_part = types.FunctionResponsePart(
    inline_data=types.FunctionResponseBlob(
        mime_type="image/jpeg",
        data=image_bytes,  # raw bytes，不需 base64
    )
)
fn_response_part = types.Part.from_function_response(
    name="tool_name",
    response={"key": "value", "image": {"$ref": "display_name"}},
    parts=[multimodal_part],
)

# 非同步 Gemini 呼叫：
response = await client.aio.models.generate_content(
    model="gemini-2.0-flash",
    contents=contents_list,
    config=types.GenerateContentConfig(
        system_instruction="...",
        tools=[types.Tool(function_declarations=[...])],
    ),
)
```

---

## Task 1：設定測試環境

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_ecommerce_agent.py`

**Step 1: 更新 requirements.txt，加入測試依賴**

```
line-bot-sdk==3.14.0
fastapi
uvicorn[standard]
google-adk
pydantic
tiktoken
Pillow
pytest
pytest-asyncio
httpx
```

**Step 2: 建立 tests 目錄**

```bash
mkdir -p tests
touch tests/__init__.py
```

**Step 3: 確認 pytest 可以執行**

```bash
cd /Users/al03034132/Documents/linebot-gemini-multimodel-funcall
pip install pytest pytest-asyncio httpx -q
pytest --version
```

Expected: `pytest 8.x.x`

**Step 4: Commit**

```bash
git add requirements.txt tests/__init__.py
git commit -m "chore: add test dependencies (pytest, pytest-asyncio, httpx)"
```

---

## Task 2：建立 ecommerce_agent.py — Mock 資料庫 + Pillow 圖片生成

**Files:**
- Create: `multi_tool_agent/ecommerce_agent.py`
- Create: `tests/test_ecommerce_agent.py`（第一批測試）

**Step 1: 在 `tests/test_ecommerce_agent.py` 寫失敗測試（圖片生成）**

```python
# tests/test_ecommerce_agent.py
import pytest
from multi_tool_agent.ecommerce_agent import (
    PRODUCTS_DB,
    generate_product_image,
)


def test_products_db_has_five_products():
    assert len(PRODUCTS_DB) == 5


def test_products_db_has_required_fields():
    for pid, product in PRODUCTS_DB.items():
        assert "name" in product
        assert "color" in product
        assert "price" in product
        assert "bg_color" in product  # RGB tuple for Pillow


def test_generate_product_image_returns_jpeg_bytes():
    product = PRODUCTS_DB["P001"]
    image_bytes = generate_product_image(product)
    assert isinstance(image_bytes, bytes)
    assert len(image_bytes) > 0
    # JPEG magic bytes
    assert image_bytes[:2] == b'\xff\xd8'


def test_generate_product_image_for_all_products():
    for pid, product in PRODUCTS_DB.items():
        image_bytes = generate_product_image(product)
        assert len(image_bytes) > 100, f"Image too small for {pid}"
```

**Step 2: 確認測試失敗**

```bash
pytest tests/test_ecommerce_agent.py -v
```

Expected: `ImportError: cannot import name 'PRODUCTS_DB' from 'multi_tool_agent.ecommerce_agent'`（或 ModuleNotFoundError）

**Step 3: 實作 `multi_tool_agent/ecommerce_agent.py`（資料庫 + 圖片生成）**

```python
# multi_tool_agent/ecommerce_agent.py
import datetime
from io import BytesIO
from PIL import Image, ImageDraw

# ── Mock 商品資料庫 ──────────────────────────────────────────────────────────
PRODUCTS_DB: dict[str, dict] = {
    "P001": {
        "id": "P001",
        "name": "深綠色V領棉質襯衫",
        "color": "深綠色",
        "category": "上衣",
        "price": 890,
        "stock": 15,
        "description": "100% 純棉，透氣舒適，V 領設計，適合日常穿搭",
        "bg_color": (34, 85, 34),
    },
    "P002": {
        "id": "P002",
        "name": "白色寬鬆連帽T恤",
        "color": "白色",
        "category": "上衣",
        "price": 690,
        "stock": 20,
        "description": "棉質混紡，寬鬆版型，帽子可拆卸",
        "bg_color": (200, 200, 200),
    },
    "P003": {
        "id": "P003",
        "name": "深藍色直筒牛仔褲",
        "color": "深藍色",
        "category": "下著",
        "price": 1290,
        "stock": 8,
        "description": "彈性牛仔布料，直筒版型，適合各種場合",
        "bg_color": (26, 51, 102),
    },
    "P004": {
        "id": "P004",
        "name": "粉紅色格紋洋裝",
        "color": "粉紅色",
        "category": "洋裝",
        "price": 1590,
        "stock": 5,
        "description": "浪漫格紋設計，A 字裙擺，優雅氣質",
        "bg_color": (220, 150, 170),
    },
    "P005": {
        "id": "P005",
        "name": "黑色皮革短靴",
        "color": "黑色",
        "category": "鞋款",
        "price": 2490,
        "stock": 3,
        "description": "真皮材質，低跟設計，防滑耐磨",
        "bg_color": (30, 30, 30),
    },
}

# Demo 預設訂單（用戶第一次查詢時綁定）
_DEMO_ORDERS_TEMPLATE = [
    {
        "order_id": "ORD-2026-0115",
        "date": "2026-01-15",
        "product_id": "P001",
        "quantity": 1,
        "total": 890,
        "status": "已送達",
        "shipping_addr": "台北市信義區信義路五段7號",
    },
    {
        "order_id": "ORD-2026-0108",
        "date": "2026-01-08",
        "product_id": "P003",
        "quantity": 1,
        "total": 1290,
        "status": "已送達",
        "shipping_addr": "台北市信義區信義路五段7號",
    },
]

# Per-user 訂單綁定（line_user_id → list[Order]）
_user_orders: dict[str, list[dict]] = {}


def get_user_orders(line_user_id: str) -> list[dict]:
    """第一次呼叫時自動綁定 demo 訂單到此 user_id。"""
    if line_user_id not in _user_orders:
        # 深拷貝，避免不同用戶共享同一物件
        import copy
        _user_orders[line_user_id] = copy.deepcopy(_DEMO_ORDERS_TEMPLATE)
    return _user_orders[line_user_id]


# ── Pillow 圖片生成 ──────────────────────────────────────────────────────────

def generate_product_image(product: dict) -> bytes:
    """用 Pillow 生成 400×400 JPEG 商品圖片。"""
    bg_color = product["bg_color"]
    img = Image.new("RGB", (400, 400), color=bg_color)
    draw = ImageDraw.Draw(img)

    # 白色邊框
    draw.rectangle([10, 10, 390, 390], outline=(255, 255, 255), width=3)

    # 商品名稱（置中）
    name = product["name"]
    # 手動換行：每行最多 8 個字
    lines = [name[i:i+8] for i in range(0, len(name), 8)]
    y_start = 160 - (len(lines) - 1) * 20
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line)
        w = bbox[2] - bbox[0]
        draw.text(((400 - w) // 2 + 2, y_start + i * 40 + 2), line, fill=(0, 0, 0))
        draw.text(((400 - w) // 2, y_start + i * 40), line, fill=(255, 255, 255))

    # 價格標籤（底部）
    price_text = f"NT$ {product['price']:,}"
    bbox = draw.textbbox((0, 0), price_text)
    pw = bbox[2] - bbox[0]
    draw.text(((400 - pw) // 2, 320), price_text, fill=(255, 230, 0))

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()
```

**Step 4: 執行測試確認通過**

```bash
pytest tests/test_ecommerce_agent.py -v
```

Expected: 4 個 PASSED

**Step 5: Commit**

```bash
git add multi_tool_agent/ecommerce_agent.py tests/test_ecommerce_agent.py
git commit -m "feat: add ecommerce mock database and Pillow image generation"
```

---

## Task 3：工具函式 — search_products + get_order_history + get_product_details

**Files:**
- Modify: `multi_tool_agent/ecommerce_agent.py`（加入 3 個工具函式）
- Modify: `tests/test_ecommerce_agent.py`（加入工具函式測試）

**Step 1: 在 `tests/test_ecommerce_agent.py` 加入失敗測試**

```python
# 在 tests/test_ecommerce_agent.py 末尾加入：
from multi_tool_agent.ecommerce_agent import (
    search_products,
    get_order_history,
    get_product_details,
)


class TestSearchProducts:
    def test_find_green_shirt_by_description(self):
        result = search_products(description="綠色襯衫")
        assert result["status"] == "success"
        assert result["count"] >= 1
        products = result["products"]
        assert any(p["product_id"] == "P001" for p in products)

    def test_find_by_color(self):
        result = search_products(description="上衣", color="白色")
        assert result["status"] == "success"
        products = result["products"]
        assert any(p["product_id"] == "P002" for p in products)

    def test_returns_at_most_three_products(self):
        result = search_products(description="衣服")
        assert result["count"] <= 3

    def test_empty_result_when_no_match(self):
        result = search_products(description="火箭筒")
        assert result["count"] == 0


class TestGetOrderHistory:
    def test_returns_orders_for_user(self):
        result = get_order_history(line_user_id="test_user_1", time_range="all")
        assert result["status"] == "success"
        assert result["order_count"] == 2

    def test_last_month_filter(self):
        # ORD-2026-0115 is within last month (today: 2026-02-22, diff=38 days)
        # Actually "last_month" should mean within 31 days
        result = get_order_history(line_user_id="test_user_2", time_range="last_month")
        assert result["status"] == "success"
        # 2026-01-15 is 38 days before 2026-02-22, outside last month
        assert result["order_count"] == 0

    def test_last_3_months_filter(self):
        result = get_order_history(line_user_id="test_user_3", time_range="last_3_months")
        assert result["status"] == "success"
        assert result["order_count"] == 2

    def test_orders_include_product_name(self):
        result = get_order_history(line_user_id="test_user_4", time_range="all")
        orders = result["orders"]
        assert all("product_name" in o for o in orders)


class TestGetProductDetails:
    def test_returns_product_info(self):
        result = get_product_details(product_id="P001")
        assert result["status"] == "success"
        assert result["product"]["name"] == "深綠色V領棉質襯衫"
        assert result["product"]["price"] == 890

    def test_returns_error_for_unknown_product(self):
        result = get_product_details(product_id="P999")
        assert result["status"] == "error"
```

**Step 2: 確認測試失敗**

```bash
pytest tests/test_ecommerce_agent.py::TestSearchProducts -v
```

Expected: `ImportError: cannot import name 'search_products'`

**Step 3: 在 `multi_tool_agent/ecommerce_agent.py` 末尾加入工具函式**

```python
# ── 工具函式 ─────────────────────────────────────────────────────────────────
_TODAY = datetime.date(2026, 2, 22)  # Demo 用固定日期


def search_products(description: str, color: str | None = None) -> dict:
    """根據描述和顏色搜尋商品，返回最多3件商品。"""
    scored = []
    desc_lower = description.lower()

    for pid, product in PRODUCTS_DB.items():
        score = 0
        # 顏色匹配
        if color and color in product["color"]:
            score += 3
        if product["color"] in description:
            score += 2
        # 名稱關鍵字匹配
        for keyword in ["襯衫", "T恤", "牛仔褲", "洋裝", "短靴", "上衣", "下著", "鞋"]:
            if keyword in description and keyword in product["name"]:
                score += 1
        # 類別匹配
        if product["category"] in description:
            score += 1
        if score > 0:
            scored.append((score, pid, product))

    scored.sort(key=lambda x: x[0], reverse=True)
    top3 = scored[:3]

    products = [
        {
            "product_id": pid,
            "name": p["name"],
            "color": p["color"],
            "category": p["category"],
            "price": p["price"],
            "stock": p["stock"],
        }
        for _, pid, p in top3
    ]

    return {
        "status": "success",
        "count": len(products),
        "products": products,
        "primary_product_id": top3[0][1] if top3 else None,
    }


def get_order_history(line_user_id: str, time_range: str = "all") -> dict:
    """查詢用戶訂單歷史（第一次呼叫自動綁定 demo 訂單）。"""
    orders = get_user_orders(line_user_id)
    limit_days = {"last_month": 31, "last_3_months": 92}.get(time_range, None)

    filtered = []
    for order in orders:
        if limit_days is not None:
            order_date = datetime.date.fromisoformat(order["date"])
            if (_TODAY - order_date).days > limit_days:
                continue
        product = PRODUCTS_DB.get(order["product_id"], {})
        filtered.append({
            **order,
            "product_name": product.get("name", "未知商品"),
            "product_color": product.get("color", ""),
        })

    return {
        "status": "success",
        "order_count": len(filtered),
        "orders": filtered,
        "primary_product_id": filtered[0]["product_id"] if filtered else None,
    }


def get_product_details(product_id: str) -> dict:
    """取得特定商品的詳細資訊。"""
    product = PRODUCTS_DB.get(product_id)
    if not product:
        return {"status": "error", "message": f"找不到商品 {product_id}"}

    return {
        "status": "success",
        "product": {
            "id": product["id"],
            "name": product["name"],
            "color": product["color"],
            "category": product["category"],
            "price": product["price"],
            "stock": product["stock"],
            "description": product["description"],
        },
    }
```

**Step 4: 執行所有測試確認通過**

```bash
pytest tests/test_ecommerce_agent.py -v
```

Expected: 所有測試 PASSED（共約 15 個）

**Step 5: Commit**

```bash
git add multi_tool_agent/ecommerce_agent.py tests/test_ecommerce_agent.py
git commit -m "feat: add ecommerce tool functions (search, order history, product details)"
```

---

## Task 4：EcommerceAgent 類別（Multimodal Function Response 核心）

**Files:**
- Modify: `multi_tool_agent/ecommerce_agent.py`（加入 EcommerceAgent class）
- Modify: `tests/test_ecommerce_agent.py`（加入 Agent 測試）

**Step 1: 在 `tests/test_ecommerce_agent.py` 加入 Agent 測試**

```python
# 在 tests/test_ecommerce_agent.py 末尾加入：
from unittest.mock import AsyncMock, MagicMock, patch
from multi_tool_agent.ecommerce_agent import EcommerceAgent
from google.genai import types


def make_mock_response(text: str = None, function_call: dict = None):
    """建立模擬的 Gemini 回應物件。"""
    mock_response = MagicMock()
    mock_candidate = MagicMock()
    mock_response.candidates = [mock_candidate]

    if function_call:
        part = MagicMock()
        part.text = None
        fc = MagicMock()
        fc.name = function_call["name"]
        fc.args = function_call["args"]
        part.function_call = fc
        mock_candidate.content = types.Content(
            role="model",
            parts=[types.Part(function_call=types.FunctionCall(
                name=function_call["name"],
                args=function_call["args"],
            ))]
        )
    else:
        mock_candidate.content = types.Content(
            role="model",
            parts=[types.Part(text=text or "測試回應")]
        )
    return mock_response


@pytest.mark.asyncio
async def test_agent_returns_text_response():
    """Agent 在無函式呼叫時正常回傳文字。"""
    with patch("multi_tool_agent.ecommerce_agent.genai.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=make_mock_response(text="您好，有什麼可以幫您？")
        )

        agent = EcommerceAgent(api_key="fake-key")
        text, image_bytes = await agent.process_message("你好", "user123")

        assert text == "您好，有什麼可以幫您？"
        assert image_bytes is None


@pytest.mark.asyncio
async def test_agent_calls_get_order_history_tool():
    """Agent 在查詢訂單時呼叫 get_order_history 工具。"""
    with patch("multi_tool_agent.ecommerce_agent.genai.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        # 第一次回應：要求呼叫函式
        first_response = make_mock_response(function_call={
            "name": "get_order_history",
            "args": {"line_user_id": "user123", "time_range": "last_3_months"},
        })
        # 第二次回應：最終文字
        second_response = make_mock_response(text="您上個月購買了深綠色V領棉質襯衫！")

        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[first_response, second_response]
        )

        agent = EcommerceAgent(api_key="fake-key")
        text, image_bytes = await agent.process_message(
            "我上個月買了什麼", "user123"
        )

        assert "深綠色V領棉質襯衫" in text
        # 應該有呼叫 generate_content 兩次
        assert mock_client.aio.models.generate_content.call_count == 2
```

**Step 2: 確認測試失敗**

```bash
pytest tests/test_ecommerce_agent.py::test_agent_returns_text_response -v
```

Expected: `ImportError: cannot import name 'EcommerceAgent'`

**Step 3: 在 `multi_tool_agent/ecommerce_agent.py` 加入 EcommerceAgent 類別**

在檔案頂部的 imports 之後加入：

```python
from google import genai
from google.genai import types
import os
```

在檔案末尾加入：

```python
# ── Gemini 工具宣告 ───────────────────────────────────────────────────────────
ECOMMERCE_TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="search_products",
            description="根據描述和顏色搜尋商品，例如：綠色襯衫、藍色牛仔褲",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "description": types.Schema(
                        type=types.Type.STRING,
                        description="商品描述，例如：綠色的上衣",
                    ),
                    "color": types.Schema(
                        type=types.Type.STRING,
                        description="商品顏色（可選），例如：深綠色",
                    ),
                },
                required=["description"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_order_history",
            description="查詢用戶的訂單歷史記錄",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "line_user_id": types.Schema(
                        type=types.Type.STRING,
                        description="LINE 用戶 ID",
                    ),
                    "time_range": types.Schema(
                        type=types.Type.STRING,
                        description="時間範圍：all（全部）、last_month（近一個月）、last_3_months（近三個月）",
                        enum=["all", "last_month", "last_3_months"],
                    ),
                },
                required=["line_user_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_product_details",
            description="取得特定商品的詳細資訊，需提供商品 ID（如 P001）",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "product_id": types.Schema(
                        type=types.Type.STRING,
                        description="商品 ID，例如：P001",
                    ),
                },
                required=["product_id"],
            ),
        ),
    ])
]

_SYSTEM_INSTRUCTION = """你是一位友善專業的電商客服助理。

當你透過工具函式取得商品資訊時：
1. 仔細觀察函式回應中包含的商品圖片
2. 根據圖片描述你看到的商品外觀（顏色、款式等）
3. 結合圖片和文字資料提供完整的回答

請務必用繁體中文回答，並保持親切、專業的態度。"""


def _execute_tool(
    func_name: str, func_args: dict, line_user_id: str
) -> tuple[dict, bytes | None]:
    """
    執行工具函式，返回 (result_dict, image_bytes | None)。
    image_bytes 為商品主圖的 JPEG bytes。
    """
    result: dict
    primary_product_id: str | None = None

    if func_name == "search_products":
        result = search_products(**func_args)
        primary_product_id = result.get("primary_product_id")
    elif func_name == "get_order_history":
        # 確保使用正確的 line_user_id
        args = {**func_args, "line_user_id": line_user_id}
        result = get_order_history(**args)
        primary_product_id = result.get("primary_product_id")
    elif func_name == "get_product_details":
        result = get_product_details(**func_args)
        primary_product_id = func_args.get("product_id")
    else:
        result = {"status": "error", "message": f"未知工具：{func_name}"}

    image_bytes: bytes | None = None
    if primary_product_id and primary_product_id in PRODUCTS_DB:
        image_bytes = generate_product_image(PRODUCTS_DB[primary_product_id])

    return result, image_bytes


# ── EcommerceAgent ────────────────────────────────────────────────────────────

class EcommerceAgent:
    """
    使用 google.genai 直接實作 Multimodal Function Response 的電商客服 Agent。
    """

    def __init__(self, api_key: str | None = None, vertexai: bool = False,
                 project: str | None = None, location: str | None = None,
                 model: str = "gemini-2.0-flash"):
        if vertexai:
            self._client = genai.Client(
                vertexai=True, project=project, location=location
            )
        else:
            self._client = genai.Client(api_key=api_key)
        self._model = model
        # line_user_id → list[types.Content]（對話歷史）
        self._histories: dict[str, list[types.Content]] = {}

    def _get_history(self, user_id: str) -> list[types.Content]:
        return self._histories.get(user_id, [])

    def _save_history(self, user_id: str, contents: list[types.Content]) -> None:
        # 保留最後 20 個 Content（約 10 輪對話）
        self._histories[user_id] = contents[-20:]

    async def process_message(
        self, text: str, line_user_id: str
    ) -> tuple[str, bytes | None]:
        """
        處理用戶訊息，返回 (ai_text_response, main_image_bytes | None)。
        main_image_bytes 是最後一次工具呼叫的主要商品圖片。
        """
        history = self._get_history(line_user_id)
        user_content = types.Content(role="user", parts=[types.Part(text=text)])
        contents = history + [user_content]

        final_text = "抱歉，我暫時無法處理您的請求，請稍後再試。"
        final_image: bytes | None = None

        for _iteration in range(5):  # 最多 5 次迭代
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                    tools=ECOMMERCE_TOOLS,
                ),
            )

            candidate = response.candidates[0]
            model_content = candidate.content
            contents.append(model_content)

            # 取出所有 function_call parts
            fc_parts = [
                p for p in model_content.parts
                if p.function_call and p.function_call.name
            ]

            if not fc_parts:
                # 無函式呼叫 → 最終文字回應
                final_text = "".join(
                    p.text for p in model_content.parts if p.text
                )
                break

            # 處理所有函式呼叫，構建多模態工具回應
            tool_parts: list[types.Part] = []
            for fc_part in fc_parts:
                fc = fc_part.function_call
                func_name = fc.name
                func_args = dict(fc.args)

                print(f"[Tool] {func_name}({func_args})")
                result_dict, image_bytes = _execute_tool(
                    func_name, func_args, line_user_id
                )

                if image_bytes:
                    final_image = image_bytes  # 保留最後一張圖片

                # 構建 Multimodal Function Response ──────────────────────────
                multimodal_parts: list[types.FunctionResponsePart] = []
                if image_bytes:
                    multimodal_parts.append(
                        types.FunctionResponsePart(
                            inline_data=types.FunctionResponseBlob(
                                mime_type="image/jpeg",
                                data=image_bytes,
                            )
                        )
                    )

                tool_parts.append(
                    types.Part.from_function_response(
                        name=func_name,
                        response=result_dict,
                        parts=multimodal_parts if multimodal_parts else None,
                    )
                )

            # 將工具回應加入對話歷史
            contents.append(types.Content(role="tool", parts=tool_parts))

        self._save_history(line_user_id, contents)
        return final_text, final_image
```

**Step 4: 確認 pytest 設定（asyncio mode）**

建立 `pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
```

**Step 5: 執行 Agent 測試確認通過**

```bash
pytest tests/test_ecommerce_agent.py -v
```

Expected: 所有測試 PASSED（包含 2 個 asyncio 測試）

**Step 6: Commit**

```bash
git add multi_tool_agent/ecommerce_agent.py tests/test_ecommerce_agent.py pytest.ini
git commit -m "feat: add EcommerceAgent with Multimodal Function Response support"
```

---

## Task 5：更新 main.py — 圖片服務 + LINE Webhook

**Files:**
- Modify: `main.py`（完整改寫）
- Create: `tests/test_main.py`

**Step 1: 在 `tests/test_main.py` 寫圖片服務測試**

```python
# tests/test_main.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import uuid


@pytest.fixture
def client():
    """建立 FastAPI 測試客戶端（跳過 LINE/Gemini 初始化）"""
    with patch.dict("os.environ", {
        "ChannelSecret": "test-secret",
        "ChannelAccessToken": "test-token",
        "GOOGLE_API_KEY": "test-key",
        "BOT_HOST_URL": "https://test.example.com",
    }):
        import importlib
        import main
        importlib.reload(main)
        yield TestClient(main.app)


def test_image_endpoint_returns_404_for_unknown_id(client):
    response = client.get("/images/nonexistent-id")
    assert response.status_code == 404


def test_image_endpoint_returns_jpeg_for_known_id(client):
    # 直接操作 image_cache
    import main
    test_id = str(uuid.uuid4())
    main.image_cache[test_id] = b'\xff\xd8\xff\xe0' + b'\x00' * 100  # fake JPEG
    response = client.get(f"/images/{test_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
```

**Step 2: 確認測試失敗**

```bash
pytest tests/test_main.py -v
```

Expected: ImportError 或 validation error（因為 main.py 尚未更新）

**Step 3: 完整改寫 `main.py`**

```python
# main.py
import os
import sys
import uuid
import asyncio
from io import BytesIO

import aiohttp
from fastapi import Request, FastAPI, HTTPException
from fastapi.responses import Response

from linebot.models import MessageEvent, TextSendMessage, ImageSendMessage
from linebot.exceptions import InvalidSignatureError
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot import AsyncLineBotApi, WebhookParser

from multi_tool_agent.ecommerce_agent import EcommerceAgent

# ── 環境變數驗證 ──────────────────────────────────────────────────────────────
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

# ── FastAPI + LINE Bot 初始化 ──────────────────────────────────────────────────
app = FastAPI()
_aiohttp_session = aiohttp.ClientSession()
async_http_client = AiohttpAsyncHttpClient(_aiohttp_session)
line_bot_api = AsyncLineBotApi(channel_access_token, async_http_client)
parser = WebhookParser(channel_secret)

# ── EcommerceAgent 初始化 ──────────────────────────────────────────────────────
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

# ── In-memory 圖片快取 ──────────────────────────────────────────────────────────
# { image_id (str uuid) → jpeg_bytes }
image_cache: dict[str, bytes] = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/images/{image_id}")
async def serve_image(image_id: str):
    """提供暫存的商品圖片給 LINE Bot 顯示。"""
    image_bytes = image_cache.get(image_id)
    if image_bytes is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=image_bytes, media_type="image/jpeg")


@app.post("/")
async def handle_callback(request: Request):
    """LINE Webhook endpoint。"""
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

        # 組合回覆訊息
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

        await line_bot_api.reply_message(event.reply_token, reply_messages)

    return "OK"
```

**Step 4: 執行測試確認通過**

```bash
pytest tests/test_main.py -v
```

Expected: PASSED（圖片端點測試）

**Step 5: 確認整個測試套件無回歸**

```bash
pytest tests/ -v
```

Expected: 所有測試 PASSED

**Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: update main.py with EcommerceAgent, image serving endpoint, and LINE image reply"
```

---

## Task 6：更新 README.md 加入 Demo Script

**Files:**
- Modify: `README.md`

**Step 1: 在 README.md 的 Features 章節後加入 Demo Script 章節**

在 `## Technologies Used` 前插入以下內容：

```markdown
## Demo — Multimodal Function Response 展示腳本

本 Bot 展示 Gemini 的 **Multimodal Function Response** 功能：當 Bot 呼叫查詢函式時，函式回應中直接包含商品圖片，讓 Gemini 能「看見」圖片並生成更精準的客服回應。

### 建議測試對話

以下對話可完整展示 Multimodal Function Response 的效果：

#### 場景 1：查詢上個月的訂單
```
您：幫我看看我上個月買的那件綠色襯衫
Bot：
  - 呼叫 get_order_history（Gemini 收到訂單資料 + 商品圖片）
  - Gemini 觀察圖片後回應：「是這件深綠色V領棉質襯衫嗎？您的訂單
    ORD-2026-0115 已於1月15日送達，共 NT$890。從圖片可以看出這是一件
    深綠色的V領款式棉質材質，非常適合日常穿搭。」
  - LINE 同時顯示：文字訊息 + 深綠色棉質襯衫圖片
```

#### 場景 2：搜尋商品
```
您：有沒有粉紅色的洋裝？
Bot：
  - 呼叫 search_products（Gemini 收到搜尋結果 + 商品圖片）
  - Gemini 描述圖片中的商品外觀
  - LINE 同時顯示：文字介紹 + 粉紅色格紋洋裝圖片
```

#### 場景 3：查詢商品詳細規格
```
您：P003 那件牛仔褲的詳細資訊
Bot：
  - 呼叫 get_product_details（Gemini 收到規格 + 牛仔褲圖片）
  - Gemini 結合圖片說明：深藍色直筒版型、彈性牛仔布料、NT$1,290
  - LINE 同時顯示：規格說明 + 商品圖片
```

#### 其他測試句子
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
```

**Step 2: 在 `## Setup` 章節加入 BOT_HOST_URL 環境變數說明**

在 `- GEMINI_API_KEY` 後加入：
```markdown
   - `BOT_HOST_URL`: 您的 Bot 公開 URL，例如 `https://xxx.run.app`（供圖片服務使用）
   - `GEMINI_MODEL`: （可選）Gemini 模型名稱，預設 `gemini-2.0-flash`
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add Multimodal Function Response demo script to README"
```

---

## Task 7：最終驗證

**Step 1: 執行完整測試套件**

```bash
pytest tests/ -v --tb=short
```

Expected: 所有測試 PASSED，0 failures

**Step 2: 確認應用程式可啟動（本機測試）**

```bash
BOT_HOST_URL=https://example.com \
GOOGLE_API_KEY=your-key \
ChannelSecret=your-secret \
ChannelAccessToken=your-token \
uvicorn main:app --reload --port 8000
```

Expected: `EcommerceAgent initialized (model=gemini-2.0-flash, vertex=False)` 且無錯誤

**Step 3: 最終 Commit**

```bash
git status  # 確認無未追蹤的變更
```

---

## 環境變數快速參考

| 變數 | 範例值 | 必要性 |
|------|--------|--------|
| `ChannelSecret` | `abc123...` | 必須 |
| `ChannelAccessToken` | `xyz456...` | 必須 |
| `GOOGLE_API_KEY` | `AIza...` | 必須（非 Vertex）|
| `BOT_HOST_URL` | `https://xxx.run.app` | 必須 |
| `GEMINI_MODEL` | `gemini-2.0-flash` | 可選 |
| `GOOGLE_GENAI_USE_VERTEXAI` | `True` | 可選 |
| `GOOGLE_CLOUD_PROJECT` | `my-project` | Vertex 時必須 |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | Vertex 時必須 |

---

## 關鍵 API 備忘

```python
# ✅ 正確的 Multimodal Function Response 構建方式（google-genai 1.49.0）
types.FunctionResponsePart(
    inline_data=types.FunctionResponseBlob(mime_type="image/jpeg", data=bytes)
)
# 注意：不是 types.Blob，是 types.FunctionResponseBlob

# ✅ 正確的 Part 建構
types.Part.from_function_response(
    name=func_name,
    response=result_dict,
    parts=[multimodal_part],  # Optional[list[FunctionResponsePart]]
)

# ✅ 非同步呼叫
await client.aio.models.generate_content(model=..., contents=..., config=...)
```
