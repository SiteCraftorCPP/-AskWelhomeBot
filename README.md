# agrealty-bot2

Telegram-бот Welhome (aiogram 3).

Для нестабильных сетей/блокировок можно задать прокси в `.env`:

```env
TELEGRAM_PROXY=154.81.199.66:64181:hGtcCsrT:S1mhartf
PROXYAPI_TIMEOUT_SECONDS=45
OPENROUTER_TIMEOUT_SECONDS=45
```

Поддерживаются форматы `socks5://user:pass@host:port` и `host:port:user:pass`.

## Локальный запуск

Сначала перейди в каталог с клоном репозитория, потом команды (нужен `.env` с `BOT_TOKEN` и ключами LLM):

```powershell
cd "C:\path\to\agrealty-bot2"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m bot.main
```

## Обновление кода (сервер / прод)

### Прод (VPS: пользователь `askwelhomebot`, каталог `/opt/askwelhomebot/app`)

```bash
sudo -u askwelhomebot -H bash -lc 'cd /opt/askwelhomebot/app && git pull'
sudo systemctl restart askwelhomebot.service
```

При необходимости после `git pull` установи зависимости от имени того же пользователя (если venv лежит в `app`):

```bash
sudo -u askwelhomebot -H bash -lc 'cd /opt/askwelhomebot/app && source .venv/bin/activate && pip install -r requirements.txt'
```

---

**PowerShell (локально, Windows):**

```powershell
cd "C:\path\to\agrealty-bot2"
git fetch origin
git pull origin main
pip install -r requirements.txt
# перезапустите процесс бота (закройте окно / перезапустите задачу планировщика / службу)
```

**Bash (другой Linux / без systemd — шаблон, путь свой):**

```bash
cd /path/to/repo
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
# перезапуск процесса вручную
```

После обновления без systemd перезапусти процесс `python -m bot.main`, иначе крутится старый код.
