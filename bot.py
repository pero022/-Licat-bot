import logging
import asyncio
import httpx
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

logging.basicConfig(level=logging.INFO)

# Configuration
TOKEN = "8824201157:AAHq-pj1agxPN9TIDL90RaEZYGbfr_WYrcc"
CREATOR_WALLET = "7RYMbGhxJ3gwc74p9fvFPcxL9DoC7RVXnizv7Mvi9zwe"
CHAT_ID = -1004342444189
SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# Token state
current_ca = None
is_launched = False
last_signature = None

http_client = None

async def monitor_wallet():
    global current_ca, is_launched, last_signature, http_client

    while True:
        try:
            if not http_client:
                http_client = httpx.AsyncClient()
                logging.info("Connected to Solana RPC via httpx")

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [CREATOR_WALLET, {"limit": 5}]
            }

            response = await http_client.post(SOLANA_RPC, json=payload)
            data = response.json()

            if data.get("result"):
                signatures = data["result"]
                if signatures:
                    latest_sig = signatures[0]["signature"]

                    if last_signature != latest_sig:
                        last_signature = latest_sig

                        try:
                            tx_payload = {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "getTransaction",
                                "params": [latest_sig, {"maxSupportedTransactionVersion": 0}]
                            }

                            tx_response = await http_client.post(SOLANA_RPC, json=tx_payload)
                            tx_data = tx_response.json()

                            if is_token_launch(tx_data):
                                ca = extract_ca_from_tx(tx_data)
                                if ca and ca != current_ca:
                                    current_ca = ca
                                    is_launched = True
                                    logging.info(f"🚀 LAUNCH DETECTED: {ca}")
                                    await send_launch_notification(ca)

                        except Exception as e:
                            logging.error(f"Error parsing transaction: {e}")

        except Exception as e:
            logging.error(f"Error monitoring wallet: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(2)

def is_token_launch(tx_data) -> bool:
    return True

def extract_ca_from_tx(tx_data) -> str:
    return None

async def send_launch_notification(ca):
    jupiter_url = f"https://jup.ag/swap/SOL-{ca}"
    pump_url = f"https://pump.fun/{ca}"

    keyboard = [
        [InlineKeyboardButton("🚀 Buy $LICAT", url=jupiter_url)],
        [InlineKeyboardButton("📊 Chart", url=pump_url)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"🚀🚀🚀 $LICAT LAUNCHED! 🚀🚀🚀\n\n"
        f"Contract: `{ca}`\n\n"
        f"Low IQ. Big Bag. Time to moon! 🌙\n\n"
        f"Click below to buy NOW!"
    )

    try:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"Error sending launch notification: {e}")

async def monitor_buys():
    while True:
        await asyncio.sleep(5)

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        username = f"@{member.username}" if member.username else member.first_name
        try:
            await update.message.delete()
        except Exception:
            pass

        if is_launched and current_ca:
            jupiter_url = f"https://jup.ag/swap/SOL-{current_ca}"
            keyboard = [
                [InlineKeyboardButton("🚀 Buy $LICAT", url=jupiter_url)],
                [InlineKeyboardButton("📊 Chart", url=f"https://pump.fun/{current_ca}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"👋 Welcome {username}!\n\n$LICAT is LIVE! 🚀\nContract: `{current_ca}`",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"👋 Welcome {username}!\n\n$LICAT launching soon! 🚀\nStay tuned for the CA drop!"
            )

async def remove_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception:
        pass

async def x_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Join our X/Twitter 🐦", url="https://x.com/lowiqcat")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Follow $LICAT on X for updates! 🐱",
        reply_markup=reply_markup
    )

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_launched and current_ca:
        jupiter_url = f"https://jup.ag/swap/SOL-{current_ca}"
        keyboard = [[InlineKeyboardButton("🚀 Buy $LICAT", url=jupiter_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"💰 $LICAT is LIVE!\n\nContract: `{current_ca}`\n\nClick below to buy!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("Token hasn't launched yet. 🚀")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_launched and current_ca:
        jupiter_url = f"https://jup.ag/swap/SOL-{current_ca}"
        pump_url = f"https://pump.fun/{current_ca}"
        keyboard = [
            [InlineKeyboardButton("🚀 Buy on Jupiter", url=jupiter_url)],
            [InlineKeyboardButton("📊 Chart", url=pump_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"💰 Buy $LICAT now!\n\nContract: `{current_ca}`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("⏳ $LICAT hasn't launched yet!\n\nStay tuned for the CA drop! 🚀")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_launched:
        await update.message.reply_text(
            f"✅ $LICAT is LIVE!\n\nContract: `{current_ca}`\n\nUse /buy to purchase!"
        )
    else:
        await update.message.reply_text(
            "⏳ $LICAT is preparing for launch...\n\nMonitoring creator wallet for launch! 🚀"
        )

async def post_init(application):
    asyncio.create_task(monitor_wallet())
    asyncio.create_task(monitor_buys())

# Build application
app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

# Add handlers
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, remove_left))
app.add_handler(CommandHandler("x", x_command))
app.add_handler(CommandHandler("price", price_command))
app.add_handler(CommandHandler("buy", buy_command))
app.add_handler(CommandHandler("status", status_command))

if __name__ == "__main__":
    logging.info("Starting $LICAT bot...")
    app.run_polling()
