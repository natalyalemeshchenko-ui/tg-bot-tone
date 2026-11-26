# Бот тональности комментариев

Telegram-бот для одного публичного канала. Он администратор канала и привязанного чата обсуждения. Сохраняет посты и комментарии, которые появились после его запуска, и по ссылке на пост отвечает диаграммой тональности и коротким резюме.
<img width="765" height="977" alt="2026-11-26_13-28-03" src="https://github.com/user-attachments/assets/29b84bf9-250d-49e0-aa92-87ae86e58f38" />



Тональность бот считает через MCP-сервер Hugging Face. Если сервер не отвечает, используется локальная модель `blanchefort/rubert-base-cased-sentiment`. Резюме пишет GigaChat по тексту комментариев: что хвалят, что ругают и о чём говорят.

## Hugging Face MCP

К проекту подключён MCP-сервер Hugging Face: публичный Space тональности. Адрес записан в `.cursor/mcp.json`, а бот ходит туда сам из `hf_mcp.py` при каждом разборе комментариев.

Сервер: [Hariharasudhan07/qwen3-0.6b-sentiment-classification](https://huggingface.co/spaces/Hariharasudhan07/qwen3-0.6b-sentiment-classification). Это Qwen3-0.6B с классами positive, neutral и negative. Эндпоинт MCP: `https://hariharasudhan07-qwen3-0-6b-sentiment-classification.hf.space/gradio_api/mcp`. Токен для этого вызова не нужен.

Если Space не отвечает, бот считает тональность локальной моделью `blanchefort/rubert-base-cased-sentiment` и пишет об этом в подписи к диаграмме. Когда отвечает MCP, в подписи стоит «Тональность: Hugging Face MCP».

Вызов Space бесплатный в пределах дневной квоты ZeroGPU. У бесплатного аккаунта это около 5 минут GPU в сутки. Отдельный токен Hugging Face для этого Space не требуется.

До этого те же отзывы из `test.md` проверялись через общий MCP Hugging Face (`hf_fs` и `dynamic_space`). Английская модель [hugging-apps/sentimental-0-2m-demo](https://huggingface.co/spaces/hugging-apps/sentimental-0-2m-demo) для русских текстов не подошла. Четыре отзыва на Qwen-Space дали 3 позитивных с уверенностью около 99,7% и 1 негативный с уверенностью 86,1%.

Старые посты и комментарии бот не выгружает. Непрочитанные обновления Telegram хранит около суток, поэтому бота лучше не выключать надолго.

## Запуск

Нужен Python 3.12.

```bash
pip install -r requirements.txt
```

Скопируйте `EnvExample` в `.env` и заполните:

- `TELEGRAM_BOT_TONE_TOKEN` — токен от @BotFather
- `GIGACHAT_AUTH_KEY` — ключ авторизации GigaChat, с префиксом `Basic` или без него

Бот должен быть администратором канала и чата обсуждения. Дополнительные права не нужны: достаточно статуса администратора, чтобы он видел посты и все сообщения чата.

```bash
python bot.py
```

Локальная модель скачивается с Hugging Face только если MCP-сервер не ответил.

В личный чат бота любой пользователь может прислать ссылку на пост, например `https://t.me/channel/123`. В ответ придёт диаграмма и резюме. Если комментариев ещё нет, бот так и напишет.

## Сертификаты для GigaChat

Файлы сертификатов в репозиторий не входят. Без них диаграмма строится, а резюме GigaChat не запрашивается: сервер Сбера не проходит обычную проверку сертификата.

Скачайте сертификаты Russian Trusted CA со страницы [Госуслуг](https://www.gosuslugi.ru/crt) и положите файлы `.cer` в папку `Russian_Trusted_CA` рядом с `bot.py`.
