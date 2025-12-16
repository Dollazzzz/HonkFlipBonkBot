import os
import time
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes




# ============= CONFIGURATION =============

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# MUST be Dexscreener *PAIR IDs* (the string after /solana/ on the pair page)
# Example:
# https://dexscreener.com/solana/<PAIR_ID>
HONK_PAIR_ID = "BZivKpJWgQvrA3yYe3ubomufeGVouoYoUhosmBEdqF9y"
BONK_PAIR_ID = "5zpyutJu9ee6jFymDGoK7F6S5Kczqtc9FomP3ueKuyA9"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

# ============= SILENT CACHE =============

CACHE_TTL = 30  # seconds
_last_fetch_time = 0.0
_cached_message = None

# =========================================


async def get_pair_data(session: aiohttp.ClientSession, pair_id: str) -> dict | None:
    """Fetch pair data from DexScreener by pair ID"""
    url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_id}"
    try:
        async with session.get(url, headers={"User-Agent": "honk-flip-bot/1.0"}) as response:
            if response.status != 200:
                # Helpful debug in logs
                text = await response.text()
                print(f"[Dexscreener] HTTP {response.status} for {url}: {text[:250]}")
                return None

            data = await response.json()
            pairs = data.get("pairs") or []
            if not pairs:
                print(f"[Dexscreener] No pairs in response for {url}")
                return None

            return pairs[0]

    except Exception as e:
        print(f"[Dexscreener] Error fetching {url}: {e}")
        return None


def pick_mcap(pair: dict) -> float:
    """Prefer marketCap; fallback to fdv."""
    v = pair.get("marketCap")
    if v is None:
        v = pair.get("fdv")
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def format_number(num: float) -> str:
    return f"${num:,.0f}"


def format_ath(num: float) -> str:
    if num >= 1_000_000_000:
        return f"${num/1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"${num/1_000_000:.1f}M"
    else:
        return f"${num:,.0f}"


def create_flip_message(honk_mc: float, bonk_mc: float, honk_ath: float, bonk_ath: float) -> str:
    # Avoid division by zero
    if bonk_mc <= 0:
        bonk_mc = 1
    if bonk_ath <= 0:
        bonk_ath = 1
    if honk_mc <= 0:
        honk_mc = 1
    if honk_ath <= 0:
        honk_ath = 1

    # Calculate progress percentages
    mc_progress = (honk_mc / bonk_mc) * 100
    mc_remaining = 100 - mc_progress
    mc_multiplier = bonk_mc / honk_mc

    ath_progress = (honk_ath / bonk_ath) * 100
    ath_remaining = 100 - ath_progress
    ath_multiplier = bonk_ath / honk_ath

    # Progress bars
    bar_length = 20

    filled_mc = max(0, min(bar_length, int(bar_length * mc_progress / 100)))
    bar_mc = "█" * filled_mc + "░" * (bar_length - filled_mc)

    filled_ath = max(0, min(bar_length, int(bar_length * ath_progress / 100)))
    bar_ath = "█" * filled_ath + "░" * (bar_length - filled_ath)

    # Use a code block so Telegram preserves alignment
    return f"""```text
🎯 FLIP THE BONK GOAL (LIVE)

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃      $HONK   │  PROGRESS  │  $BONK      ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ MC   │ {format_number(honk_mc)}  │  ✖️{mc_multiplier:.2f}  │ {format_number(bonk_mc)} ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ ATH  │ {format_ath(honk_ath)}  │  ✖️{ath_multiplier:.2f}  │ {format_ath(bonk_ath)} ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

📊 PROGRESS BEFORE THE FLIPPENING

Market Cap Progress:
{bar_mc}
{mc_progress:.2f}% Complete  |  {mc_remaining:.2f}% To Go

ATH Progress:
{bar_ath}
{ath_progress:.2f}% Complete  |  {ath_remaining:.2f}% To Go

🚀 Keep HONKing! 🚀
```"""


async def flip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _last_fetch_time, _cached_message

    now = time.time()

    # Silent cache (prevents spamming free API)
    if _cached_message and (now - _last_fetch_time) < CACHE_TTL:
        await update.message.reply_text(_cached_message, parse_mode="Markdown")
        return

    # Quick guard so you don’t forget to paste IDs
    if "PASTE_" in HONK_PAIR_ID or "PASTE_" in BONK_PAIR_ID:
        await update.message.reply_text("❌ Paste your HONK_PAIR_ID and BONK_PAIR_ID into the code first.")
        return

    await update.message.reply_text("🔍 Fetching latest market data…")

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        honk_pair = await get_pair_data(session, HONK_PAIR_ID)
        bonk_pair = await get_pair_data(session, BONK_PAIR_ID)

        if not honk_pair or not bonk_pair:
            await update.message.reply_text("❌ Error fetching market data. Try again in a moment.")
            return

        honk_mc = pick_mcap(honk_pair)
        bonk_mc = pick_mcap(bonk_pair)

        # Your original code used FDV as a stand-in; keep that behavior
        honk_ath = float(honk_pair.get("fdv") or honk_mc or 0)
        bonk_ath = float(bonk_pair.get("fdv") or bonk_mc or 0)

        if honk_mc <= 0 or bonk_mc <= 0:
            await update.message.reply_text("❌ Unable to retrieve marketCap/fdv values.")
            return

        message = create_flip_message(honk_mc, bonk_mc, honk_ath, bonk_ath)

        # Save to cache
        _cached_message = message
        _last_fetch_time = now

        await update.message.reply_text(message, parse_mode="Markdown")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "🎺 Welcome to the HONK Flip BONK Tracker! 🎺\n\n"
        "Commands:\n"
        "/flip - Check progress toward flipping $BONK\n"
        "/commands - Show all available commands\n"
        "/start - Show this message\n\n"
        "Let’s flip the BONK! 🚀"
    )
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_message = (
        "📖 HONK Flip BONK Tracker Help\n\n"
        "Available Commands:\n"
        "• /flip - See current progress toward flipping BONK\n"
        "• /commands - Show all available commands\n"
        "• /start - Welcome message\n"
        "• /help - This help message\n\n"
        "The bot compares Market Cap (marketCap/fdv) from Dexscreener pair data."
    )
    await update.message.reply_text(help_message)


async def commands_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands_message = (
        "🎺 HONK Flip BONK Bot Commands 🎺\n\n"
        "📊 /flip\n"
        "→ Check live progress toward flipping $BONK\n\n"
        "ℹ️ /start\n"
        "→ Welcome message\n\n"
        "❓ /help\n"
        "→ Detailed help information\n\n"
        "📋 /commands\n"
        "→ Show this commands list\n\n"
        "🚀 HONK TO THE MOON! 🚀"
    )
    await update.message.reply_text(commands_message)


def main():
    print("🤖 Starting HONK Flip BONK Tracker Bot...")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("flip", flip_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("commands", commands_command))

    print("✅ Bot is HONKing! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
