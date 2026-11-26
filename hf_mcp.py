"""Клиент MCP-сервера тональности на Hugging Face Space."""

import ast
import asyncio

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = (
    "https://hariharasudhan07-qwen3-0-6b-sentiment-classification"
    ".hf.space/gradio_api/mcp"
)
TOOL_NAME = "qwen3_0_6b_sentiment_classification_classify_review"


def classify_with_mcp(texts):
    """Классифицирует тексты через MCP и возвращает метку с уверенностью."""
    if not texts:
        return []
    from sentiment import _canonical

    raw = asyncio.run(_classify(list(texts)))
    scored = []
    for text, label, score in raw:
        scored.append(
            {
                "text": text,
                "label": _canonical(label, {}),
                "score": score,
            }
        )
    return scored


async def _classify(texts):
    timeout = httpx2.Timeout(180.0, connect=30.0)
    async with httpx2.AsyncClient(timeout=timeout) as http_client:
        async with streamable_http_client(MCP_URL, http_client=http_client) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                scored = []
                for text in texts:
                    result = await session.call_tool(TOOL_NAME, {"review": text})
                    if result.is_error:
                        raise RuntimeError(_content_text(result) or "MCP вернул ошибку")
                    label, score = _parse(_content_text(result))
                    scored.append((text, label, score))
                return scored


def _content_text(result):
    parts = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _parse(payload):
    data = ast.literal_eval(payload)
    if isinstance(data, list):
        data = data[0]
    label = str(data.get("label") or "")
    score = 0.0
    confidences = data.get("confidences") or []
    if confidences:
        score = float(confidences[0].get("confidence") or 0.0)
    if not label:
        raise ValueError("В ответе MCP нет метки тональности")
    return label, score
