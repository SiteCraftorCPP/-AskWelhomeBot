# agrealty-bot2

Telegram-бот Welhome (aiogram 3).

## Локальный запуск

Из корня репозитория (нужен `.env` с `BOT_TOKEN` и ключами LLM):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m bot.main
```

## Обновление кода (сервер / прод)

Подставьте путь к клону репозитория и имя сервиса, если бот крутится под systemd.

**PowerShell (Windows):**

```powershell
cd "C:\path\to\agrealty-bot2"
git fetch origin
git pull origin main
pip install -r requirements.txt
# перезапустите процесс бота (закройте окно / перезапустите задачу планировщика / службу)
```

**Bash (Linux, VPS):**

```bash
cd /path/to/agrealty-bot2
git fetch origin
git pull origin main
source .venv/bin/activate   # если используете venv
pip install -r requirements.txt
# sudo systemctl restart your-bot-service   # при необходимости
```

Одной строкой (Linux, из каталога репозитория):

```bash
git pull origin main && pip install -r requirements.txt
```

После обновления всегда перезапустите процесс `python -m bot.main`, иначе работает старый код.
