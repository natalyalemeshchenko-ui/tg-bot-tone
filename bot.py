from io import BytesIO
from pathlib import Path

import telebot

from config import get_settings
from db import Store
from gigachat import GigaChatError
from incoming import on_channel_post, on_group_message, snapshot_from_message
from links import parse_post_link
from report import analyzable, build_stats, fingerprint, make_summary

ROOT = Path(__file__).resolve().parent
MEDIA = [
    "text",
    "photo",
    "video",
    "animation",
    "document",
    "audio",
    "voice",
    "video_note",
    "sticker",
    "poll",
]
START_TEXT = (
    "Пришлите ссылку на пост канала, например https://t.me/channel/123.\n\n"
    "Я разбираю только посты, которые вышли после того, как меня добавили в канал, "
    "и комментарии, которые пришли, пока я был запущен."
)


def main():
    settings = get_settings()
    store = Store(ROOT / "data" / "tone.db")
    bot = telebot.TeleBot(settings.bot_token, parse_mode=None)

    @bot.channel_post_handler(content_types=MEDIA)
    def channel(message):
        _log(on_channel_post(store, snapshot_from_message(message)))

    @bot.edited_channel_post_handler(content_types=MEDIA)
    def channel_edit(message):
        _log(on_channel_post(store, snapshot_from_message(message)))

    @bot.message_handler(
        func=lambda message: message.chat.type in {"group", "supergroup"},
        content_types=MEDIA,
    )
    def group(message):
        snap = snapshot_from_message(message)
        _log(on_group_message(store, snap))
        if not (snap.get("text") or "").strip() and not snap.get("is_auto"):
            _log(
                f"Сообщение без текста {snap['chat_id']}/{snap['message_id']} "
                f"не сохранено"
            )

    @bot.edited_message_handler(
        func=lambda message: message.chat.type in {"group", "supergroup"},
        content_types=MEDIA,
    )
    def group_edit(message):
        _log(on_group_message(store, snapshot_from_message(message)))

    @bot.message_handler(
        commands=["start", "help"],
        func=lambda message: message.chat.type == "private",
    )
    def start(message):
        bot.reply_to(message, START_TEXT)

    @bot.message_handler(
        func=lambda message: message.chat.type == "private",
        content_types=["text"],
    )
    def private(message):
        _analyze(bot, store, settings.gigachat_key, message)

    print("Бот запущен. Жду посты канала и комментарии.")
    bot.infinity_polling(
        skip_pending=False,
        timeout=30,
        allowed_updates=[
            "message",
            "edited_message",
            "channel_post",
            "edited_channel_post",
        ],
    )


def _analyze(bot, store, gigachat_key, message):
    parsed = parse_post_link(message.text or "")
    if not parsed:
        bot.reply_to(
            message,
            "Нужна ссылка на пост, например https://t.me/channel/123",
        )
        return
    username, message_id = parsed
    post = store.post_by_username(username, message_id)
    if not post:
        bot.reply_to(
            message,
            "Этого поста у меня нет. Я вижу только посты канала, "
            "где состою администратором, и только вышедшие после моего добавления.",
        )
        return
    comments = [
        item
        for item in store.comments_for(post["channel_id"], post["message_id"])
        if analyzable(item["text"])
    ]
    if not comments:
        bot.reply_to(
            message,
            "Под этим постом пока нет комментариев, которые можно разобрать.",
        )
        return

    bot.send_chat_action(message.chat.id, "typing")
    try:
        stats = build_stats(comments)
    except Exception as error:
        print(f"Ошибка тональности: {type(error).__name__}: {error}")
        bot.reply_to(message, "Не получилось посчитать тональность. Попробуйте ещё раз.")
        return

    caption = f"Разобрано комментариев: {stats['total']}"
    if stats["trimmed"]:
        caption += f" (последние {stats['total']})"
    image = BytesIO(stats["png"])
    image.name = "tone.png"
    bot.send_photo(message.chat.id, image, caption=caption, reply_to_message_id=message.message_id)

    key = fingerprint(comments[-len(stats["scored"]) :])
    cached = store.get_summary(post["channel_id"], post["message_id"], key)
    if cached:
        _send_long(bot, message.chat.id, cached)
        return
    try:
        summary = make_summary(gigachat_key, post["text"], stats)
    except GigaChatError as error:
        print(f"Ошибка GigaChat: {error}")
        bot.send_message(
            message.chat.id,
            "Статистику посчитал, краткое резюме сейчас не получилось.",
        )
        return
    store.save_summary(post["channel_id"], post["message_id"], key, summary)
    _send_long(bot, message.chat.id, summary)


def _send_long(bot, chat_id, text):
    chunk = 4000
    for start in range(0, len(text), chunk):
        bot.send_message(chat_id, text[start : start + chunk])


def _log(line):
    if line:
        print(line)


if __name__ == "__main__":
    main()
