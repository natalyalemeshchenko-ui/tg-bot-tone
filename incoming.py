"""Разбор обновлений канала и чата обсуждения."""


def snapshot_from_message(message, depth=0):
    if message is None or depth > 6:
        return None
    user = getattr(message, "from_user", None)
    chat = message.chat
    forward_channel_id = None
    forward_message_id = None
    forward_username = None
    origin = getattr(message, "forward_origin", None)
    if origin is not None and getattr(origin, "type", None) == "channel":
        forward_channel_id = origin.chat.id
        forward_message_id = origin.message_id
        forward_username = getattr(origin.chat, "username", None)
    else:
        forwarded_chat = getattr(message, "forward_from_chat", None)
        forwarded_id = getattr(message, "forward_from_message_id", None)
        if forwarded_chat is not None and forwarded_id:
            forward_channel_id = forwarded_chat.id
            forward_message_id = forwarded_id
            forward_username = getattr(forwarded_chat, "username", None)
    return {
        "chat_id": chat.id,
        "chat_username": getattr(chat, "username", None),
        "chat_type": chat.type,
        "message_id": message.message_id,
        "text": message.text or message.caption or "",
        "date": int(message.date or 0),
        "is_auto": bool(getattr(message, "is_automatic_forward", False)),
        "from_bot": bool(user and getattr(user, "is_bot", False)),
        "thread_id": getattr(message, "message_thread_id", None),
        "forward_channel_id": forward_channel_id,
        "forward_message_id": forward_message_id,
        "forward_username": forward_username,
        "reply": snapshot_from_message(getattr(message, "reply_to_message", None), depth + 1),
        **_external_reply(getattr(message, "external_reply", None)),
    }


def _external_reply(external):
    if external is None:
        return {
            "external_chat_id": None,
            "external_message_id": None,
            "external_channel_id": None,
            "external_channel_message_id": None,
        }
    chat = getattr(external, "chat", None)
    origin = getattr(external, "origin", None)
    channel_id = None
    channel_message_id = None
    if origin is not None and getattr(origin, "type", None) == "channel":
        channel_id = origin.chat.id
        channel_message_id = origin.message_id
    return {
        "external_chat_id": getattr(chat, "id", None),
        "external_message_id": getattr(external, "message_id", None),
        "external_channel_id": channel_id,
        "external_channel_message_id": channel_message_id,
    }


def on_channel_post(store, snap):
    username = snap.get("chat_username")
    if not username:
        return None
    store.upsert_post(
        channel_id=snap["chat_id"],
        message_id=snap["message_id"],
        username=username,
        text=snap["text"],
        posted_at=snap["date"],
    )
    return f"Пост {username.lower()}/{snap['message_id']} сохранён"


def on_group_message(store, snap):
    if snap.get("is_auto"):
        return _save_forward(store, snap)
    text = (snap.get("text") or "").strip()
    if not text:
        return None
    target = _resolve_post(store, snap)
    if target is None:
        reply = snap.get("reply") or {}
        return (
            f"Комментарий {snap['chat_id']}/{snap['message_id']} не привязан к посту "
            f"(ветка {snap.get('thread_id')}, ответ на {reply.get('message_id')})"
        )
    channel_id, channel_message_id = target
    store.save_comment(
        discussion_chat_id=snap["chat_id"],
        message_id=snap["message_id"],
        channel_id=channel_id,
        channel_message_id=channel_message_id,
        text=text,
        commented_at=snap["date"],
    )
    return f"Комментарий к посту {channel_id}/{channel_message_id} сохранён"


def _save_forward(store, snap):
    channel_id = snap.get("forward_channel_id")
    message_id = snap.get("forward_message_id")
    if not channel_id or not message_id:
        return None
    store.upsert_post(
        channel_id=channel_id,
        message_id=message_id,
        username=snap.get("forward_username"),
        text=snap.get("text") or "",
        posted_at=snap.get("date"),
        discussion_chat_id=snap["chat_id"],
        discussion_message_id=snap["message_id"],
    )
    return f"Обсуждение поста {channel_id}/{message_id} привязано"


def _resolve_post(store, snap):
    thread_id = snap.get("thread_id")
    if thread_id:
        post = store.post_by_discussion(snap["chat_id"], thread_id)
        if post:
            return post["channel_id"], post["message_id"]
    reply = snap.get("reply")
    while reply:
        post = store.post_by_discussion(snap["chat_id"], reply["message_id"])
        if post:
            return post["channel_id"], post["message_id"]
        found = store.comment_target(snap["chat_id"], reply["message_id"])
        if found:
            return found
        if reply.get("thread_id"):
            post = store.post_by_discussion(snap["chat_id"], reply["thread_id"])
            if post:
                return post["channel_id"], post["message_id"]
        channel_id = reply.get("forward_channel_id")
        message_id = reply.get("forward_message_id")
        if channel_id and message_id and reply.get("is_auto"):
            store.upsert_post(
                channel_id=channel_id,
                message_id=message_id,
                username=reply.get("forward_username"),
                text=reply.get("text") or "",
                posted_at=reply.get("date"),
                discussion_chat_id=snap["chat_id"],
                discussion_message_id=reply["message_id"],
            )
            return channel_id, message_id
        reply = reply.get("reply")

    channel_id = snap.get("external_channel_id")
    message_id = snap.get("external_channel_message_id")
    if channel_id and message_id:
        return channel_id, message_id
    ext_chat = snap.get("external_chat_id")
    ext_mid = snap.get("external_message_id")
    if ext_chat and ext_mid:
        post = store.post_by_discussion(ext_chat, ext_mid)
        if post:
            return post["channel_id"], post["message_id"]
        post = store.post_by_ids(ext_chat, ext_mid)
        if post:
            return post["channel_id"], post["message_id"]

    posts = store.posts_by_discussion_chat(snap["chat_id"])
    if len(posts) == 1:
        return posts[0]["channel_id"], posts[0]["message_id"]
    return None
