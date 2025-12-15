import os
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============= CONFIGURATION =============
# Load from Replit Secrets for security
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
HONK_PAIR_ADDRESS = "3ag1Mj9AKz9FAkCQ6gAEhpLSX8B2pUbPdkb9iBsDLZNB"
BONK_TOKEN_ADDRESS = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set in Replit Secrets!")
# =========================================

async def get_token_data(session, pair_address=None, token_address=None):
    """Fetch token data from DexScreener"""
    try:
        if pair_address:
            url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
        elif token_address:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        else:
            return None
        
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if pair_address and 'pair' in data:
                    return data['pair']
                elif token_address and 'pairs' in data and len(data['pairs']) > 0:
                    # Get the pair with highest liquidity
                    pairs = data['pairs']
                    return max(pairs, key=lambda x: float(x.get('liquidity', {}).get('usd', 0)))
                return None
            return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def format_number(num):
    """Format large numbers with commas"""
    return f"${num:,.0f}"

def format_ath(num):
    """Format ATH numbers"""
    if num >= 1_000_000_000:
        return f"${num/1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"${num/1_000_000:.1f}M"
    else:
        return f"${num:,.0f}"

def create_flip_message(honk_mc, bonk_mc, honk_ath, bonk_ath):
    """Create the flip tracker message in the exact style from the image"""
    
    # Calculate progress percentages
    mc_progress = (honk_mc / bonk_mc) * 100
    mc_remaining = 100 - mc_progress
    mc_multiplier = bonk_mc / honk_mc
    
    ath_progress = (honk_ath / bonk_ath) * 100
    ath_remaining = 100 - ath_progress
    ath_multiplier = bonk_ath / honk_ath
    
    # Create progress bar for MC
    bar_length = 20
    filled_mc = int(bar_length * mc_progress / 100)
    bar_mc = '█' * filled_mc + '░' * (bar_length - filled_mc)
    
    # Create progress bar for ATH
    filled_ath = int(bar_length * ath_progress / 100)
    bar_ath = '█' * filled_ath + '░' * (bar_length - filled_ath)
    
    message = f"""
🎯 FLIP THE BONK GOAL (LIVE)

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃      $HONK   │  PROGRESS  │  $BONK      ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ MC   │ {format_number(honk_mc)}  │  ✖️{mc_multiplier:.0f}  │ {format_number(bonk_mc)} ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ ATH  │ {format_ath(honk_ath)}  │  ✖️{ath_multiplier:.0f}  │ {format_ath(bonk_ath)} ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

📊 PROGRESS BEFORE THE FLIPPENING

Market Cap Progress:
{bar_mc}
{mc_progress:.2f}% Complete  |  {mc_remaining:.2f}% To Go

ATH Progress:
{bar_ath}
{ath_progress:.2f}% Complete  |  {ath_remaining:.2f}% To Go

🚀 Keep HONKing! 🚀
"""
    
    return message

async def flip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /flip command"""
    await update.message.reply_text("🔍 Fetching latest market data...")
    
    async with aiohttp.ClientSession() as session:
        # Fetch both tokens' data
        honk_data = await get_token_data(session, pair_address=HONK_PAIR_ADDRESS)
        bonk_data = await get_token_data(session, token_address=BONK_TOKEN_ADDRESS)
        
        if not honk_data or not bonk_data:
            await update.message.reply_text("❌ Error fetching market data. Please try again later.")
            return
        
        # Extract market cap data
        honk_mc = float(honk_data.get('marketCap', 0))
        bonk_mc = float(bonk_data.get('marketCap', 0))
        
        # Extract ATH data (use fdv as proxy if marketCap not available)
        honk_ath = float(honk_data.get('fdv', honk_mc))
        bonk_ath = float(bonk_data.get('fdv', bonk_mc))
        
        if honk_mc == 0 or bonk_mc == 0:
            await update.message.reply_text("❌ Unable to retrieve market cap data.")
            return
        
        # Create and send the formatted message
        message = create_flip_message(honk_mc, bonk_mc, honk_ath, bonk_ath)
        await update.message.reply_text(message)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_message = """
🎺 Welcome to the HONK Flip Tracker! 🎺

Commands:
/flip - Check progress toward flipping $BONK
/commands - Show all available commands
/start - Show this message

Let's flip that BONK! 🚀
"""
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_message = """
📖 HONK Flip Tracker Help

Available Commands:
- /flip - See current progress toward flipping BONK
- /commands - Show all available commands
- /start - Welcome message
- /help - This help message

The bot tracks both Market Cap and ATH comparisons!
"""
    await update.message.reply_text(help_message)

async def commands_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /commands command"""
    commands_message = """
🎺 HONK Bot Commands 🎺

📊 /flip
   → Check live progress toward flipping $BONK
   → Shows MC and ATH comparisons
   → Displays progress bars

ℹ️ /start
   → Welcome message
   → Quick introduction to the bot

❓ /help
   → Detailed help information

📋 /commands
   → Show this commands list

🚀 HONK TO THE MOON! 🚀
"""
    await update.message.reply_text(commands_message)

def main():
    """Start the bot"""
    print("🤖 Starting HONK Flip Tracker Bot...")
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("flip", flip_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("commands", commands_command))
    
    # Start the bot
    print("✅ Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()