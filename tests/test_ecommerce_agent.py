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
        assert "image_path" in product  # path to real product image


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
from multi_tool_agent.ecommerce_agent import (
    search_products,
    get_order_history,
    get_product_details,
)


class TestSearchProducts:
    def test_find_bomber_jacket_by_description(self):
        result = search_products(description="棕色飛行員外套")
        assert result["status"] == "success"
        assert result["count"] >= 1
        products = result["products"]
        assert any(p["product_id"] == "P001" for p in products)

    def test_find_by_color(self):
        result = search_products(description="上衣", color="淺藍色")
        assert result["status"] == "success"
        products = result["products"]
        assert any(p["product_id"] == "P005" for p in products)

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
        # Both orders are > 31 days before 2026-02-22, so 0 results
        result = get_order_history(line_user_id="test_user_2", time_range="last_month")
        assert result["status"] == "success"
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
        assert result["product"]["name"] == "棕色飛行員外套"
        assert result["product"]["price"] == 1890

    def test_returns_error_for_unknown_product(self):
        result = get_product_details(product_id="P999")
        assert result["status"] == "error"
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from multi_tool_agent.ecommerce_agent import EcommerceAgent
from google.genai import types


def make_text_response(text: str):
    """Build a mock Gemini response with a text part (no function call)."""
    mock_response = MagicMock()
    mock_candidate = MagicMock()
    mock_response.candidates = [mock_candidate]
    mock_candidate.content = types.Content(
        role="model",
        parts=[types.Part(text=text)]
    )
    return mock_response


def make_function_call_response(func_name: str, func_args: dict):
    """Build a mock Gemini response with a function call."""
    mock_response = MagicMock()
    mock_candidate = MagicMock()
    mock_response.candidates = [mock_candidate]
    mock_candidate.content = types.Content(
        role="model",
        parts=[types.Part(function_call=types.FunctionCall(
            name=func_name,
            args=func_args,
        ))]
    )
    return mock_response


@pytest.mark.asyncio
async def test_agent_returns_text_response():
    """Agent returns text when no function call is made."""
    with patch("multi_tool_agent.ecommerce_agent.genai.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=make_text_response("您好，有什麼可以幫您？")
        )

        agent = EcommerceAgent(api_key="fake-key")
        text, image_bytes = await agent.process_message("你好", "user_test_a")

        assert text == "您好，有什麼可以幫您？"
        assert image_bytes is None


@pytest.mark.asyncio
async def test_agent_calls_tool_and_returns_image():
    """Agent calls get_order_history tool and returns text + image."""
    with patch("multi_tool_agent.ecommerce_agent.genai.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_client.aio.models.generate_content = AsyncMock(side_effect=[
            make_function_call_response(
                "get_order_history",
                {"line_user_id": "user_test_b", "time_range": "all"},
            ),
            make_text_response("您購買了棕色飛行員外套！"),
        ])

        agent = EcommerceAgent(api_key="fake-key")
        text, image_bytes = await agent.process_message("我買過什麼", "user_test_b")

        assert "棕色飛行員外套" in text
        assert image_bytes is not None  # P001 image generated
        assert isinstance(image_bytes, bytes)
        assert mock_client.aio.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_agent_history_persists_across_messages():
    """Conversation history is maintained between messages."""
    with patch("multi_tool_agent.ecommerce_agent.genai.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=make_text_response("好的！")
        )

        agent = EcommerceAgent(api_key="fake-key")
        await agent.process_message("你好", "user_test_c")
        await agent.process_message("再說一次", "user_test_c")

        # Second call should include history (more contents in call)
        second_call_contents = mock_client.aio.models.generate_content.call_args_list[1][1]["contents"]
        assert len(second_call_contents) > 1  # has history
