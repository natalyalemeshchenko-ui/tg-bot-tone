import os
import threading

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

MODEL_NAME = "blanchefort/rubert-base-cased-sentiment"

_pipeline = None
_id2label = {}
_lock = threading.Lock()


def classify(texts):
    """Возвращает метку и уверенность для каждого текста, в том же порядке."""
    if not texts:
        return []
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
