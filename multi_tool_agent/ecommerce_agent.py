# multi_tool_agent/ecommerce_agent.py
import copy
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


# ── 工具函式 ─────────────────────────────────────────────────────────────────
_TODAY = datetime.date(2026, 2, 22)  # Demo 用固定日期


def search_products(description: str, color: str | None = None) -> dict:
    """根據描述和顏色搜尋商品，返回最多3件商品。"""
    scored = []

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
from google import genai
from google.genai import types

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
            description="查詢當前用戶的訂單歷史記錄，LINE 用戶 ID 由系統自動帶入",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "time_range": types.Schema(
                        type=types.Type.STRING,
                        description="時間範圍：all（全部）、last_month（近一個月）、last_3_months（近三個月）",
                        enum=["all", "last_month", "last_3_months"],
                    ),
                },
                required=[],
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
    """Execute a tool function. Returns (result_dict, image_bytes | None)."""
    primary_product_id: str | None = None

    if func_name == "search_products":
        result = search_products(**func_args)
        primary_product_id = result.get("primary_product_id")
    elif func_name == "get_order_history":
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


class EcommerceAgent:
    """E-commerce customer service agent using Gemini Multimodal Function Response."""

    def __init__(
        self,
        api_key: str | None = None,
        vertexai: bool = False,
        project: str | None = None,
        location: str | None = None,
        model: str = "gemini-2.0-flash",
    ):
        if vertexai:
            self._client = genai.Client(
                vertexai=True, project=project, location=location
            )
        else:
            self._client = genai.Client(api_key=api_key)
        self._model = model
        self._histories: dict[str, list[types.Content]] = {}

    def _get_history(self, user_id: str) -> list[types.Content]:
        return self._histories.get(user_id, [])

    def _save_history(self, user_id: str, contents: list[types.Content]) -> None:
        self._histories[user_id] = contents[-20:]

    async def process_message(
        self, text: str, line_user_id: str
    ) -> tuple[str, bytes | None]:
        """Process a user message. Returns (ai_text, main_image_bytes | None)."""
        history = self._get_history(line_user_id)
        user_content = types.Content(role="user", parts=[types.Part(text=text)])
        contents = history + [user_content]

        final_text = "抱歉，我暫時無法處理您的請求，請稍後再試。"
        final_image: bytes | None = None

        for _iteration in range(5):
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

            fc_parts = [
                p for p in model_content.parts
                if p.function_call and p.function_call.name
            ]

            if not fc_parts:
                final_text = "".join(
                    p.text for p in model_content.parts if p.text
                )
                break

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
                    final_image = image_bytes

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

            contents.append(types.Content(role="tool", parts=tool_parts))

        self._save_history(line_user_id, contents)
        return final_text, final_image
