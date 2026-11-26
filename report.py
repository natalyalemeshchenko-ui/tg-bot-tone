import hashlib

from chart import render_chart
from gigachat import ask
from sentiment import classify

COMMENT_LIMIT = 300

SUMMARY_VERSION = "2"
SYSTEM_PROMPT = (
    "Ты редактор обзора комментариев под постом. Пиши по-русски, коротко, без markdown. "
    "Опирайся только на приведённые комментарии и не добавляй людей, которых в списке нет. "
    "Не пиши «большинство» и «участники», если по тексту этого не видно. "
    "Три абзаца с заголовками «Хвалят», «Ругают», «О чём говорят». "
    "Метка в скобках — подсказка. Смысл бери из текста: "
    "благодарность, удачная попытка и отказ от критики — это хвалят; "
    "прямое «не понравилось» — это ругают, не смягчай до сомнения. "
    "Если комментарий поправляет предыдущий, учти оба. "
    "Если для абзаца нет опоры в тексте, так и напиши."
)


def analyzable(text):
    letters = [char for char in text if char.isalpha()]
    return len(letters) >= 2


def fingerprint(comments):
    payload = SUMMARY_VERSION + "\n" + "\n".join(
        f"{item['message_id']}\t{item['text']}" for item in comments
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_stats(comments):
    """Считает тональность и рисует диаграмму. comments уже отфильтрованы."""
    chosen = comments[-COMMENT_LIMIT:]
    scored = classify([item["text"] for item in chosen])
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for item in scored:
        counts[item["label"]] = counts.get(item["label"], 0) + 1
    total = len(scored)
    return {
        "scored": scored,
        "counts": counts,
        "total": total,
        "trimmed": len(comments) > COMMENT_LIMIT,
        "png": render_chart(counts, total),
    }


def summary_prompt(post_text, stats):
    counts = stats["counts"]
    numbered = []
    for index, item in enumerate(stats["scored"], start=1):
        numbered.append(f"{index}. [{item['label']}] {_clip(item['text'], 500)}")
    parts = [
        f"Текст поста: {_clip(post_text or 'без текста', 700)}",
        (
            f"Комментариев в списке ровно {stats['total']}: "
            f"позитивных {counts['positive']}, нейтральных {counts['neutral']}, "
            f"негативных {counts['negative']}."
        ),
        "Комментарии по порядку:\n" + "\n".join(numbered),
    ]
    return "\n\n".join(parts)


def make_summary(auth_key, post_text, stats):
    return ask(auth_key, summary_prompt(post_text, stats), SYSTEM_PROMPT).strip()


def _clip(text, limit):
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"
