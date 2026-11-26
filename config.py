import os
from dataclasses import dataclass
from pathlib import Path


def load_env(path: Path | None = None) -> None:
    """Подхватывает .env в окружение, не затирая уже заданные переменные."""
    candidates: list[Path] = []
    if path is not None:
        candidates.append(path)
    else:
        candidates.append(Path.cwd() / ".env")
        candidates.append(Path(__file__).resolve().parent / ".env")

    seen: set[Path] = set()
    for env_path in candidates:
        resolved = env_path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        _apply_env_file(resolved)


def _apply_env_file(env_path: Path) -> None:
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    gigachat_key: str


def get_settings() -> Settings:
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TONE_TOKEN", "").strip()
    key = os.environ.get("GIGACHAT_AUTH_KEY", "").strip()
    missing = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TONE_TOKEN", token),
            ("GIGACHAT_AUTH_KEY", key),
        )
        if not value
    ]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(
            f"Не заданы переменные: {names}. Заполните .env по образцу EnvExample."
        )
    return Settings(bot_token=token, gigachat_key=key)
