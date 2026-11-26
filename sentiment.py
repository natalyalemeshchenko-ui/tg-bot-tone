import os
import threading

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

MODEL_NAME = "blanchefort/rubert-base-cased-sentiment"

_pipeline = None
_id2label = {}
_lock = threading.Lock()


_last_source = "local"


def last_source():
    return _last_source


def classify(texts):
    """Сначала спрашивает MCP Hugging Face, при сбое считает локальной моделью."""
    global _last_source
    if not texts:
        return []
    try:
        from hf_mcp import classify_with_mcp

        scored = classify_with_mcp(texts)
        _last_source = "mcp"
        print(f"Тональность через Hugging Face MCP, комментариев: {len(scored)}")
        return scored
    except Exception as error:
        _last_source = "local"
        print(f"MCP недоступен, считаю локальной моделью: {type(error).__name__}: {error}")
    pipe, id2label = _model()
    raw = pipe(list(texts), truncation=True, max_length=512, top_k=1)
    scored = []
    for text, item in zip(texts, raw):
        label, score = _top(item)
        scored.append(
            {
                "text": text,
                "label": _canonical(label, id2label),
                "score": score,
            }
        )
    return scored


def _model():
    global _pipeline, _id2label
    if _pipeline is not None:
        return _pipeline, _id2label
    with _lock:
        if _pipeline is None:
            from transformers import pipeline

            print("Загружаю модель тональности...")
            _pipeline = pipeline("sentiment-analysis", model=MODEL_NAME)
            config = _pipeline.model.config
            _id2label = dict(getattr(config, "id2label", {}) or {})
            print(f"Модель готова, метки: {_id2label}")
    return _pipeline, _id2label


def _top(item):
    if isinstance(item, list):
        item = item[0] if item else {}
    return str(item.get("label", "")), float(item.get("score") or 0.0)


def _canonical(label, id2label):
    raw = label
    if raw.upper().startswith("LABEL_"):
        index = raw.split("_")[-1]
        mapped = id2label.get(int(index)) if index.isdigit() else None
        if mapped is None:
            mapped = id2label.get(index, raw)
        raw = str(mapped)
    name = raw.lower()
    if "neg" in name or "нег" in name:
        return "negative"
    if "pos" in name or "поз" in name:
        return "positive"
    return "neutral"
