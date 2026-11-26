import os
import threading
import time
import uuid
from pathlib import Path

import certifi
import requests

from config import load_env

TOKEN_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
DEFAULT_SCOPE = "GIGACHAT_API_PERS"
ROOT = Path(__file__).resolve().parent
CERT_DIR = ROOT / "Russian_Trusted_CA"
CA_BUNDLE = ROOT / "data" / "ca_bundle.pem"

_lock = threading.Lock()
_access_token = None
_expires_at = 0


class GigaChatError(RuntimeError):
    pass


def ask(auth_key, user_text, system_text):
    """Отправляет текст в GigaChat и возвращает ответ."""
    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
    }

    def request(token):
        return requests.post(
            CHAT_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
            verify=russian_ca_bundle(),
        )

    response = request(_token(auth_key))
    if response.status_code == 401:
        response = request(_token(auth_key, force=True))
    if response.status_code >= 400:
        raise GigaChatError(
            f"GigaChat ответил {response.status_code}: {response.text[:300]}"
        )
    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as error:
        raise GigaChatError("В ответе GigaChat нет текста.") from error


def russian_ca_bundle():
    """Собирает обычные CA и сертификаты Минцифры в один файл."""
    parts = [Path(certifi.where()).read_text(encoding="utf-8").strip()]
    certs = sorted(CERT_DIR.glob("*.cer"))
    if not certs:
        raise FileNotFoundError(f"В папке {CERT_DIR} нет сертификатов .cer")
    for cert in certs:
        text = cert.read_text(encoding="utf-8").strip()
        if "BEGIN CERTIFICATE" not in text:
            raise ValueError(f"Файл {cert.name} не в формате PEM")
        parts.append(text)
    CA_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    CA_BUNDLE.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return str(CA_BUNDLE)


def _token(auth_key, force=False):
    global _access_token, _expires_at
    now_ms = int(time.time() * 1000)
    with _lock:
        if force or not _access_token or now_ms >= _expires_at - 60_000:
            data = _fetch_token(auth_key)
            _access_token = data["access_token"]
            _expires_at = int(data.get("expires_at") or 0)
        return _access_token


def _fetch_token(auth_key):
    load_env()
    key = (auth_key or os.getenv("GIGACHAT_AUTH_KEY") or "").strip()
    if not key:
        raise GigaChatError("Не задан GIGACHAT_AUTH_KEY.")
    if not key.lower().startswith("basic "):
        key = f"Basic {key}"
    scope = os.getenv("GIGACHAT_SCOPE", DEFAULT_SCOPE).strip() or DEFAULT_SCOPE
    response = requests.post(
        TOKEN_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": key,
        },
        data={"scope": scope},
        timeout=30,
        verify=russian_ca_bundle(),
    )
    if response.status_code >= 400:
        raise GigaChatError(
            f"Не удалось получить токен GigaChat: {response.status_code}"
        )
    payload = response.json()
    if not payload.get("access_token"):
        raise GigaChatError("В ответе GigaChat нет access_token.")
    return payload
