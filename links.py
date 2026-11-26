import re

_LINK = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?"
    r"(?P<username>[A-Za-z][A-Za-z0-9_]{3,})/(?P<msg>\d+)",
    re.IGNORECASE,
)
_SKIP_USERNAMES = {"c", "s", "share", "joinchat", "addstickers", "proxy"}


def parse_post_link(text: str) -> tuple[str, int] | None:
    """Достаёт имя публичного канала и id поста из ссылки t.me."""
    match = _LINK.search(text or "")
    if not match:
        return None
    username = match.group("username").lower()
    if username in _SKIP_USERNAMES:
        return None
    return username, int(match.group("msg"))
