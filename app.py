import os
import sqlite3
import calendar
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template, redirect, url_for, request
from apscheduler.schedulers.background import BackgroundScheduler
import requests as http_requests
from scraper import scrape_waste_calendar

TZ = ZoneInfo('Europe/Amsterdam')

app = Flask(__name__)

DB_PATH = os.environ.get('DB_PATH', '/data/waste.db')

# --- Database ---

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS collections (
        id INTEGER PRIMARY KEY,
        date TEXT NOT NULL,
        waste_type TEXT NOT NULL,
        UNIQUE(date, waste_type)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS scrape_log (
        id INTEGER PRIMARY KEY,
        scraped_at TEXT NOT NULL,
        count INTEGER NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')
    conn.commit()

    # Seed defaults from .env on first run
    defaults = {
        'postcode': os.environ.get('POSTCODE', '5000AA'),
        'huisnummer': os.environ.get('HUISNUMMER', '1'),
        'telegram_bot_token': os.environ.get('TELEGRAM_BOT_TOKEN', ''),
        'telegram_chat_id': os.environ.get('TELEGRAM_CHAT_ID', ''),
        'scrape_hour': '6',
        'scrape_minute': '0',
        'evening_hour': '20',
        'evening_minute': '0',
        'morning_hour': '7',
        'morning_minute': '0',
    }
    for key, value in defaults.items():
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# --- Settings helpers ---

def get_setting(key, fallback=''):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else fallback

def get_all_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}

def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# --- Scraper job ---

def run_scrape():
    s = get_all_settings()
    postcode = s.get('postcode', '5000AA')
    huisnummer = s.get('huisnummer', '1')
    print(f"[{datetime.now(TZ)}] Starting scrape for {postcode} {huisnummer}...", flush=True)
    results = scrape_waste_calendar(postcode, huisnummer, months_ahead=2)
    if results:
        conn = get_db()
        conn.execute("DELETE FROM collections")
        for r in results:
            conn.execute(
                "INSERT OR REPLACE INTO collections (date, waste_type) VALUES (?, ?)",
                (r['date'], r['waste_type'])
            )
        conn.execute(
            "INSERT INTO scrape_log (scraped_at, count) VALUES (?, ?)",
            (datetime.now(TZ).strftime('%d %b %Y, %H:%M'), len(results))
        )
        conn.commit()
        conn.close()
        print(f"[{datetime.now(TZ)}] Scrape done: {len(results)} collections saved", flush=True)
    else:
        print(f"[{datetime.now(TZ)}] Scrape returned no results", flush=True)

# --- Telegram ---

def send_telegram(message):
    token = get_setting('telegram_bot_token')
    chat_id = get_setting('telegram_chat_id')
    if not token or not chat_id:
        print("Telegram not configured, skipping", flush=True)
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = http_requests.post(url, json={
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }, timeout=10)
        if resp.status_code == 200:
            print(f"Telegram sent OK", flush=True)
        else:
            print(f"Telegram error: {resp.status_code} {resp.text}", flush=True)
    except Exception as e:
        print(f"Telegram error: {e}", flush=True)

def format_waste_icon(waste_type):
    if "Rest" in waste_type:
        return "\u26ab\U0001f7e2"
    return "\U0001f535\U0001f7e0"

def format_waste_label(waste_type):
    if "Rest" in waste_type:
        return "Rest \u26ab + GFT \U0001f7e2"
    return "Papier \U0001f535 + PMD \U0001f7e0"

def check_and_notify_evening():
    tomorrow = (datetime.now(TZ) + timedelta(days=1)).strftime('%Y-%m-%d')
    conn = get_db()
    rows = conn.execute("SELECT waste_type FROM collections WHERE date = ?", (tomorrow,)).fetchall()
    conn.close()
    if rows:
        lines = [f"  {format_waste_icon(r['waste_type'])}  {format_waste_label(r['waste_type'])}" for r in rows]
        msg = (
            "\u2800\n"
            "\U0001f6a8  <b>REMINDER</b>\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "\n"
            "\U0001f5d1\ufe0f  <b>Waste collection tomorrow!</b>\n"
            f"\U0001f4c5  <code>{tomorrow}</code>\n"
            "\n"
            + "\n".join(lines) + "\n"
            "\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "\U0001f553  Put bins out tonight!"
        )
        send_telegram(msg)

def check_and_notify_morning():
    today = datetime.now(TZ).strftime('%Y-%m-%d')
    conn = get_db()
    rows = conn.execute("SELECT waste_type FROM collections WHERE date = ?", (today,)).fetchall()
    conn.close()
    if rows:
        lines = [f"  {format_waste_icon(r['waste_type'])}  {format_waste_label(r['waste_type'])}" for r in rows]
        msg = (
            "\u2800\n"
            "\u2757  <b>TODAY</b>\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "\n"
            "\U0001f5d1\ufe0f  <b>Waste collection today!</b>\n"
            f"\U0001f4c5  <code>{today}</code>\n"
            "\n"
            + "\n".join(lines) + "\n"
            "\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "\u2705  Make sure bins are at the curb!"
        )
        send_telegram(msg)

# --- Scheduler ---

scheduler = BackgroundScheduler(timezone=TZ)

def reload_scheduler():
    """Remove all jobs and re-add with current settings from DB."""
    s = get_all_settings()
    for job_id in ['daily_scrape', 'evening_notify', 'morning_notify']:
        try:
            scheduler.remove_job(job_id)
        except:
            pass
    scheduler.add_job(run_scrape, 'cron',
        hour=int(s.get('scrape_hour', 6)), minute=int(s.get('scrape_minute', 0)),
        id='daily_scrape')
    scheduler.add_job(check_and_notify_evening, 'cron',
        hour=int(s.get('evening_hour', 20)), minute=int(s.get('evening_minute', 0)),
        id='evening_notify')
    scheduler.add_job(check_and_notify_morning, 'cron',
        hour=int(s.get('morning_hour', 7)), minute=int(s.get('morning_minute', 0)),
        id='morning_notify')
    print(f"Scheduler reloaded: scrape={s.get('scrape_hour','6')}:{s.get('scrape_minute','0').zfill(2)}, "
          f"evening={s.get('evening_hour','20')}:{s.get('evening_minute','0').zfill(2)}, "
          f"morning={s.get('morning_hour','7')}:{s.get('morning_minute','0').zfill(2)}", flush=True)

# --- Routes ---

@app.route('/')
def index():
    year = request.args.get('year', type=int, default=datetime.now(TZ).year)
    month = request.args.get('month', type=int, default=datetime.now(TZ).month)

    month_str = f"{year}-{month:02d}"
    conn = get_db()
    rows = conn.execute(
        "SELECT date, waste_type FROM collections WHERE date LIKE ?",
        (f"{month_str}%",)
    ).fetchall()

    last_scrape = conn.execute(
        "SELECT scraped_at, count FROM scrape_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()

    collections = {}
    for row in rows:
        d = row['date']
        if d not in collections:
            collections[d] = []
        collections[d].append(row['waste_type'])

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)

    today = datetime.now(TZ).strftime('%Y-%m-%d')
    month_name = datetime(year, month, 1).strftime('%B %Y')

    conn2 = get_db()
    upcoming_rows = conn2.execute(
        "SELECT date, waste_type FROM collections WHERE date >= ? ORDER BY date LIMIT 6",
        (today,)
    ).fetchall()
    conn2.close()

    upcoming = []
    for row in upcoming_rows:
        days_until = (datetime.strptime(row['date'], '%Y-%m-%d') - datetime.now(TZ).replace(tzinfo=None)).days + 1
        if days_until == 0:
            label = "today"
        elif days_until == 1:
            label = "tomorrow"
        else:
            label = f"in {days_until}d"
        upcoming.append({'date': row['date'], 'waste_type': row['waste_type'], 'days': label})

    return render_template('index.html',
        weeks=weeks, year=year, month=month, month_name=month_name,
        month_str=month_str, collections=collections, today=today,
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
        last_scrape=last_scrape, upcoming=upcoming
    )

@app.route('/scrape', methods=['POST'])
def scrape():
    run_scrape()
    return redirect(url_for('index'))

@app.route('/test-telegram', methods=['POST'])
def test_telegram():
    conn = get_db()
    rows = conn.execute(
        "SELECT date, waste_type FROM collections WHERE date >= ? ORDER BY date",
        (datetime.now(TZ).strftime('%Y-%m-%d'),)
    ).fetchall()
    conn.close()

    if not rows:
        send_telegram("\U0001f5d1\ufe0f  <b>Afvalkalender</b>\n\nNo upcoming collections found.\nTry scraping first.")
    else:
        lines = []
        today = datetime.now(TZ)
        for row in rows:
            d = datetime.strptime(row['date'], '%Y-%m-%d')
            days = (d - today.replace(tzinfo=None)).days + 1
            if days == 0:
                tag = "today"
            elif days == 1:
                tag = "tmrw"
            else:
                tag = f"{days}d"
            icon = format_waste_icon(row['waste_type'])
            label = "Rest + GFT" if "Rest" in row['waste_type'] else "Papier + PMD"
            lines.append(f"  {icon}  <code>{row['date']}</code>  {label}  <i>({tag})</i>")

        msg = (
            "\u2800\n"
            "\U0001f5d3  <b>AFVALKALENDER</b>\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "\n"
            + "\n".join(lines) + "\n"
            "\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"\u26ab Rest  \U0001f7e2 GFT  \U0001f535 Papier  \U0001f7e0 PMD"
        )
        send_telegram(msg)

    return redirect(url_for('index'))

@app.route('/settings')
def settings_page():
    s = get_all_settings()
    saved = request.args.get('saved', '')
    return render_template('settings.html', settings=s, saved=saved)

@app.route('/settings', methods=['POST'])
def settings_save():
    fields = [
        'postcode', 'huisnummer',
        'telegram_bot_token', 'telegram_chat_id',
        'scrape_hour', 'scrape_minute',
        'evening_hour', 'evening_minute',
        'morning_hour', 'morning_minute',
    ]
    conn = get_db()
    for f in fields:
        val = request.form.get(f, '').strip()
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f, val))
    conn.commit()
    conn.close()
    reload_scheduler()
    return redirect(url_for('settings_page', saved='1'))

# --- Startup ---

init_db()
reload_scheduler()
scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
