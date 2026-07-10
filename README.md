# 🗑️ Tilburg Afvalkalender — Web UI + Telegram Reminders

Self-hosted web app that scrapes waste collection dates from the [Gemeente Tilburg afvalkalender](https://21burgerportaal.mendixcloud.com/p/tilburg/landing/), displays them in a clean calendar UI, and sends **Telegram reminders** the evening before and morning of every collection day.

🏠 Built for residents of **Tilburg, Netherlands** who'd rather not miss bin day.

<img width="1131" height="804" alt="image" src="https://github.com/user-attachments/assets/e295558d-bd07-4d96-955c-f0edf9187158" />

## ✨ What it does

1. 🌐 Scrapes the Tilburg municipal waste calendar portal (Mendix-based) with headless Chromium
2. 📝 Reads the next 2 months of collection dates for your address
3. 🔍 Detects two collection types:
   - ⚫🟢 **Rest + GFT** (residual + organic)
   - 🔵🟠 **Papier + PMD** (paper + plastic/metal/cartons)
4. 💾 Stores everything in a local SQLite database
5. 📅 Renders a **lavender-themed calendar dashboard** at `http://localhost:5500`
6. 📲 Sends Telegram reminders:
   - 🌙 Evening before (default 20:00) — *"Put bins out tonight!"*
   - 🌅 Morning of (default 07:00) — *"Make sure bins are at the curb!"*
7. ⚙️ All settings (address, Telegram, schedule times) configurable via a **Settings page** — no restart needed

## 🐳 Quick Start with Docker

### Using the pre-built image from Docker Hub

Create a `docker-compose.yml`:

```yaml
services:
  app:
    image: daimik/afvalkalender-telegram:latest
    container_name: afvalkalender-telegram
    restart: unless-stopped
    ports:
      - "5500:5000"
    volumes:
      - ./data:/data
    environment:
      - POSTCODE=5000AA
      - HUISNUMMER=1
      - TELEGRAM_BOT_TOKEN=
      - TELEGRAM_CHAT_ID=
```

Then run:

```bash
docker compose up -d
```

Open **http://localhost:5500** to see the calendar, and **http://localhost:5500/settings** to configure everything.

### 🔧 Building from source

```bash
git clone https://github.com/daimik/Tilburg-Afvalkalender.git
cd Tilburg-Afvalkalender
cp .env.example .env   # optional — edit values, or leave blank and use the Settings page
docker compose up -d --build
```

## ⚙️ Configuration

The `.env` file is **only used to seed initial values on first run**. After that, all settings live in SQLite and are edited via the Settings page (`/settings`).

| Variable | Default | Description |
|---|---|---|
| `POSTCODE` | `5000AA` | Your postcode in Tilburg |
| `HUISNUMMER` | `1` | Your house number |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Bot token from @BotFather (optional) |
| `TELEGRAM_CHAT_ID` | *(empty)* | Chat ID where reminders are sent (optional) |
| `DB_PATH` | `/data/waste.db` | SQLite path inside the container |

Schedule times (scrape time, evening reminder, morning reminder) are managed entirely from the Settings page.

### 📲 Telegram Bot Setup

1. Open Telegram, search for **@BotFather**, send `/newbot` and follow the prompts
2. Copy the bot token
3. Create a group chat (or use 1-on-1), add your bot
4. Send any message in the chat
5. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
6. Find `"chat":{"id":-100XXXXXXXXX}` — that number is your `TELEGRAM_CHAT_ID`
7. Paste both into the Settings page and click **Test Telegram** to verify

<table>
  <tr>
    <td><img width="389" alt="Telegram reminder example" src="https://github.com/user-attachments/assets/09dc771f-3141-4783-af2c-37cd16b1ffeb" /></td>
    <td><img width="444" alt="Telegram chat setup" src="https://github.com/user-attachments/assets/51bbfc6e-274c-44fa-b58c-9d14df5e14de" /></td>
  </tr>
</table>
## 🖼️ Web UI

- **`/`** — Calendar month view with colored dots on collection days, sidebar with the next 6 upcoming pickups, "Scrape now" and "Test Telegram" buttons, last-scrape timestamp
- **`/settings`** — Address, Telegram credentials, scrape time, evening reminder time, morning reminder time. Saving reloads the scheduler instantly.

<img width="701" height="983" alt="image" src="https://github.com/user-attachments/assets/10c68083-cad7-4659-9383-8edcb49d9d24" />

## 🔁 Container Behavior

- 🚀 Initializes the SQLite DB on startup (seeds defaults from `.env` on first run)
- ⏰ Runs the scrape on the configured cron (default 06:00) — and you can trigger it manually from the UI
- 🌙 Evening reminder (default 20:00) — sends Telegram if anything is scheduled tomorrow
- 🌅 Morning reminder (default 07:00) — sends Telegram if anything is scheduled today
- 🔄 Settings changes reload the scheduler live, no restart
- 🖥️ Headless Chromium runs inside the container, no display required
- 📋 Logs visible via `docker logs afvalkalender-telegram`

## 🗄️ Data

All data persists in a single volume at `./data/waste.db`:

- `collections` — every scraped (date, waste_type) pair
- `scrape_log` — timestamp + count per scrape
- `settings` — all configuration (key/value)

## 🛠️ Tech Stack

- **Python 3.12** + **Flask** (single-file `app.py`)
- **APScheduler 3.x** for cron jobs (do not upgrade to v4 — different API)
- **Selenium 4** + headless Chromium for scraping
- **SQLite** for storage
- **Docker** with `chromium` + `chromium-driver` from Debian repos (multi-arch: amd64 and arm64)

## ⚠️ Disclaimer

This scraper depends on the Gemeente Tilburg waste portal UI structure (Mendix widget classes like `mx-name-text195`). If the municipality updates their website, the scraper may need adjustments.
