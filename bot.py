import logging
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

logging.basicConfig(level=logging.INFO)

# Configuration
TOKEN = "8824201157:AAHq-pj1agxPN9TIDL90RaEZYGbfr_WYrcc"
CREATOR_WALLET = "7RYMbGhxJ3gwc74p9fvFPcxL9DoC7RVXnizv7Mvi9zwe"
CHAT_ID = -1004342444189
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
MIN_BUY_SOL = 0.5  # Minimum SOL buy to announce

# Token state
current_ca = None
is_launched = False
last_wallet_signature = None
last_buy_signature = None

http_client = None

# ── PUMP.FUN LAUNCH DETECTION ──────────────────────────────────────────────

async def monitor_wallet():
    """Watch creator wallet for Pump.fun token creation."""
    global current_ca, is_launched, last_wallet_signature, http_client

    while True:
        try:
            if not http_client:
                http_client = httpx.AsyncClient(timeout=10)

            response = await http_client.post(SOLANA_RPC, json={
                "jsonrpc": "2.0", "id": 1,
                "method": "getSignaturesForAddress",
                "params": [CREATOR_WALLET, {"limit": 5}]
            })
            data = response.json()
            signatures = data.get("result", [])

            if signatures:
                latest_sig = signatures[0]["signature"]

                if last_wallet_signature != latest_sig:
                    last_wallet_signature = latest_sig

                    tx_response = await http_client.post(SOLANA_RPC, json={
                        "jsonrpc": "2.0", "id": 1,
                        "method": "getTransaction",
                        "params": [latest_sig, {
                            "encoding": "jsonParsed",
                            "maxSupportedTransactionVersion": 0
                        }]
                    })
                    tx_data = tx_response.json()
                    result = tx_data.get("result")

                    if result:
                        ca = extract_pump_ca(result)
                        if ca and ca != current_ca:
                            current_ca = ca
                            is_launched = True
                            logging.info(f"🚀 LAUNCH DETECTED: {ca}")
                            await send_launch_notification(ca)

        except Exception as e:
            logging.error(f"Wallet monitor error: {e}")

        await asyncio.sleep(3)


def extract_pump_ca(tx_result) -> str:
    """Extract the new token mint address from a Pump.fun launch transaction."""
    try:
        account_keys = tx_result["transaction"]["message"]["accountKeys"]
        post_balances = tx_result.get("meta", {}).get("postTokenBalances", [])

        # Check if Pump.fun program is involved
        program_ids = [k["pubkey"] if isinstance(k, dict) else k for k in account_keys]
        if PUMP_FUN_PROGRAM not in program_ids:
            return None

        # The mint is in postTokenBalances
        if post_balances:
            return post_balances[0].get("mint")

    except Exception as e:
        logging.error(f"CA extraction error: {e}")
    return None


# ── BUY BOT ────────────────────────────────────────────────────────────────

async def monitor_buys():
    """Watch token for large buys and announce them in the group."""
    global last_buy_signature

    while True:
        try:
            if is_launched and current_ca and http_client:
                response = await http_client.post(SOLANA_RPC, json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "getSignaturesForAddress",
                    "params": [current_ca, {"limit": 10}]
                })
                data = response.json()
                signatures = data.get("result", [])

                for sig_info in signatures:
                    sig = sig_info["signature"]
                    if sig == last_buy_signature:
                        break

                    tx_response = await http_client.post(SOLANA_RPC, json={
                        "jsonrpc": "2.0", "id": 1,
                        "method": "getTransaction",
                        "params": [sig, {
                            "encoding": "jsonParsed",
                            "maxSupportedTransactionVersion": 0
                        }]
                    })
                    tx_data = tx_response.json()
                    result = tx_data.get("result")

                    if result:
                        buy_amount = get_buy_amount_sol(result)
                        if buy_amount and buy_amount >= MIN_BUY_SOL:
                            buyer = get_buyer_wallet(result)
                            await send_buy_notification(buy_amount, buyer, sig)

                if signatures:
                    last_buy_signature = signatures[0]["signature"]

        except Exception as e:
            logging.error(f"Buy monitor error: {e}")

        await asyncio.sleep(3)


def get_buy_amount_sol(tx_result) -> float:
    """Calculate SOL spent in transaction."""
    try:
        pre = tx_result["meta"]["preBalances"]
        post = tx_result["meta"]["postBalances"]
        # Buyer is index 0, SOL difference = amount spent
        diff = (pre[0] - post[0]) / 1e9
        if diff > 0:
            return round(diff, 3)
    except Exception:
        pass
    return None


def get_buyer_wallet(tx_result) -> str:
    """Get the buyer's wallet address."""
    try:
        keys = tx_result["transaction"]["message"]["accountKeys"]
        first = keys[0]
        return first["pubkey"] if isinstance(first, dict) else first
    except Exception:
        return "Unknown"


async def send_buy_notification(amount_sol, buyer, signature):
    """Send buy alert to Telegram group."""
    dex_url = f"https://dexscreener.com/solana/{current_ca}"
    pump_url = f"https://pump.fun/{current_ca}"

    # Emoji scale based on buy size
    if amount_sol >= 5:
        emoji = "🐳🐳🐳"
        label = "WHALE BUY"
    elif amount_sol >= 2:
        emoji = "🦈🦈"
        label = "BIG BUY"
    else:
        emoji = "🟢"
        label = "BUY"

    short_buyer = f"{buyer[:4]}...{buyer[-4:]}" if len(buyer) > 8 else buyer

    message = (
        f"{emoji} *{label} DETECTED!*\n\n"
        f"💰 Amount: *{amount_sol} SOL*\n"
        f"👤 Buyer: `{short_buyer}`\n"
        f"🪙 Token: *$LICAT*\n\n"
        f"[View TX](https://solscan.io/tx/{signature})"
    )

    keyboard = [
        [InlineKeyboardButton("📊 Chart", url=dex_url)],
        [InlineKeyboardButton("🚀 Buy $LICAT", url=pump_url)]
    ]

    try:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"Buy notification error: {e}")


# ── LAUNCH NOTIFICATION ────────────────────────────────────────────────────

async def send_launch_notification(ca):
    jupiter_url = f"https://jup.ag/swap/SOL-{ca}"
    pump_url = f"https://pump.fun/{ca}"

    keyboard = [
        [InlineKeyboardButton("🚀 Buy $LICAT", url=pump_url)],
        [InlineKeyboardButton("📊 Chart", url=jupiter_url)],
    ]

    message = (
        f"🚀🚀🚀 *$LICAT LAUNCHED!* 🚀🚀🚀\n\n"
        f"Contract: `{ca}`\n\n"
        f"Low IQ. Big Bag. Time to moon! 🌙\n\n"
        f"Click below to buy NOW!"
    )

    try:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"Launch notification error: {e}")


# ── TELEGRAM HANDLERS ──────────────────────────────────────────────────────

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        username = f"@{member.username}" if member.username else member.first_name
        try:
            await update.message.delete()
        except Exception:
            pass

        if is_launched and current_ca:
            keyboard = [
                [InlineKeyboardButton("🚀 Buy $LICAT", url=f"https://pump.fun/{current_ca}")],
                [InlineKeyboardButton("📊 Chart", url=f"https://dexscreener.com/solana/{current_ca}")]
            ]
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"👋 Welcome {username}!\n\n$LICAT is LIVE! 🚀\nContract: `{current_ca}`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"👋 Welcome {username}!"
            )


async def remove_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception:
        pass


async def x_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Join our X/Twitter 🐦", url="https://x.com/lowiqcat")]]
    await update.message.reply_text(
        "Follow $LICAT on X for updates! 🐱",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_launched and current_ca:
        keyboard = [[InlineKeyboardButton("🚀 Buy $LICAT", url=f"https://pump.fun/{current_ca}")]]
        await update.message.reply_text(
            f"💰 $LICAT is LIVE!\n\nContract: `{current_ca}`\n\nClick below to buy!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("Token hasn't launched yet. 🚀")


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_launched and current_ca:
        keyboard = [
            [InlineKeyboardButton("🚀 Buy on Pump.fun", url=f"https://pump.fun/{current_ca}")],
            [InlineKeyboardButton("📊 Chart", url=f"https://dexscreener.com/solana/{current_ca}")]
        ]
        await update.message.reply_text(
            f"💰 Buy $LICAT now!\n\nContract: `{current_ca}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
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
            "⏳ $LICAT is preparing for launch...\n\nMonitoring creator wallet! 🚀"
        )


async def setca_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to manually set CA if auto-detection fails."""
    global current_ca, is_launched
    if context.args:
        ca = context.args[0]
        current_ca = ca
        is_launched = True
        await update.message.reply_text(f"✅ CA set to: `{ca}`", parse_mode='Markdown')
        await send_launch_notification(ca)
    else:
        await update.message.reply_text("Usage: /setca <contract_address>")


# ── STARTUP ────────────────────────────────────────────────────────────────

async def post_init(application):
    asyncio.create_task(monitor_wallet())
    asyncio.create_task(monitor_buys())
    logging.info("🐱 $LICAT bot started — monitoring wallet and buys")


app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, remove_left))
app.add_handler(CommandHandler("x", x_command))
app.add_handler(CommandHandler("price", price_command))
app.add_handler(CommandHandler("buy", buy_command))
app.add_handler(CommandHandler("status", status_command))
app.add_handler(CommandHandler("setca", setca_command))

if __name__ == "__main__":
    app.run_polling()
