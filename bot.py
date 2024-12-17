import json
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import aiohttp

# Sabitler
DATA_FILE = '/root/botpy/user_data.json'


API_URL = "https://alps.dill.xyz/api/trpc/stats.getAllValidators"

# User Data
user_pubkeys = {}
user_balance_history = {}

# Data Upload
def load_data():
    global user_pubkeys, user_balance_history
    try:
        with open(DATA_FILE, "r") as file:
            data = json.load(file)
            user_pubkeys = data.get("user_pubkeys", {})
            user_balance_history = data.get("user_balance_history", {})
            print("Data successfully loaded.")
    except FileNotFoundError:
        print("Data file not found. Starting with empty data.")
    except json.JSONDecodeError:
        print("Data file is corrupted. Starting with empty data.")

# Data Save
def save_data():
    with open(DATA_FILE, "w") as file:
        data = {
            "user_pubkeys": user_pubkeys,
            "user_balance_history": user_balance_history
        }
        json.dump(data, file)
        print("Data successfully saved.")

# Balance 
def format_balance(balance):
    return f"{balance / 1e9:.6f}"

# API Validators Info
async def get_validator_info(pubkey):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(API_URL) as response:
                data = await response.json()
                validators = data['result']['data']['json']['data']
                for validator in validators:
                    if validator['validator']['pubkey'] == pubkey:
                        return {
                            "pubkey": validator['validator']['pubkey'],
                            "balance": format_balance(int(validator['balance'])),
                            "raw_balance": validator['balance'],
                            "status": validator['status']
                        }
    except Exception as e:
        print(f"Error fetching validator info: {e}")
        return None

# /start 
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Use /add_pubkey <pubkey> to add, /check to check status, and /delete_pubkey <pubkey> to delete a pubkey."
    )

# /add_pubkey 
async def add_pubkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if len(context.args) != 1:
        await update.message.reply_text("Send a pubkey: /add_pubkey <pubkey>")
        return

    pubkey = context.args[0]
    if user_id not in user_pubkeys:
        user_pubkeys[user_id] = []

    if pubkey in user_pubkeys[user_id]:
        await update.message.reply_text("âœ… Pubkey already added.")
        return

    user_pubkeys[user_id].append(pubkey)
    save_data()
    await update.message.reply_text(f"âœ… Pubkey added: {pubkey}")

# /check 
async def check_pubkeys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)

    if user_id not in user_pubkeys or not user_pubkeys[user_id]:
        await update.message.reply_text("âš ï¸ No pubkeys added yet.")
        return

    results = []
    for pubkey in user_pubkeys[user_id]:
        info = await get_validator_info(pubkey)
        if info:
            previous_balance = user_balance_history.get(user_id, {}).get(pubkey, None)
            current_balance = int(info['raw_balance'])

            # Balance change calculate
            if previous_balance is not None:
                change = current_balance - previous_balance
                icon = "🟩" if change > 0 else "🟥" if change < 0 else "⬜"
                sign = "+" if change > 0 else "-" if change < 0 else ""
                change_str = f"{icon} {sign}{format_balance(abs(change))}"
            else:
                change_str = "(N/A)"  

            # Balance update
            user_balance_history.setdefault(user_id, {})[pubkey] = current_balance
            results.append(
                f"ğŸ” Pubkey: {info['pubkey']}\nBalance: {info['balance']} ({change_str})\nStatus: {info['status']}"
            )
        else:
            results.append(f"âš ï¸ Pubkey not found: {pubkey}")

    save_data()
    await update.message.reply_text("\n\n".join(results))

# /delete_pubkey 
async def delete_pubkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if len(context.args) != 1:
        await update.message.reply_text("Send a pubkey to delete: /delete_pubkey <pubkey>")
        return

    pubkey = context.args[0]
    if user_id not in user_pubkeys or pubkey not in user_pubkeys[user_id]:
        await update.message.reply_text("âš ï¸ Pubkey not found in your list.")
        return

    user_pubkeys[user_id].remove(pubkey)
    save_data()
    await update.message.reply_text(f"âœ… Pubkey deleted: {pubkey}")

# Validator info auto check
async def auto_check_validators(context: ContextTypes.DEFAULT_TYPE):
    for user_id, pubkeys in user_pubkeys.items():
        results = []
        for pubkey in pubkeys:
            info = await get_validator_info(pubkey)
            if info:
                previous_balance = user_balance_history.get(user_id, {}).get(pubkey, None)
                current_balance = int(info['raw_balance'])

                # Balance deÄŸiÅŸimi hesaplama
                if previous_balance is not None:
                    change = current_balance - previous_balance
                    icon = "🟩" if change > 0 else "🟥" if change < 0 else "⬜"
                    sign = "+" if change > 0 else "-" if change < 0 else ""
                    change_str = f"{icon} {sign}{format_balance(abs(change))}"
                else:
                    change_str = "(N/A)"  # First Check

                # Balance change check
                user_balance_history.setdefault(user_id, {})[pubkey] = current_balance

                results.append(
                    f"ğŸ” Pubkey: {info['pubkey']}\nBalance: {info['balance']} ({change_str})\nStatus: {info['status']}"
                )
            else:
                results.append(f"âš ï¸ Pubkey not found: {pubkey}")

        save_data()
        if results:
            try:
                await context.bot.send_message(chat_id=user_id, text="\n\n".join(results))
            except Exception as e:
                print(f"Error sending message to {user_id}: {e}")

# Botu Start
def main():
    load_data()  
    TELEGRAM_TOKEN = "TelegramBotToken"

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_pubkey", add_pubkey))
    application.add_handler(CommandHandler("check", check_pubkeys))
    application.add_handler(CommandHandler("delete_pubkey", delete_pubkey))

    job_queue = application.job_queue
    job_queue.run_repeating(auto_check_validators, interval=900, first=0)  # 900 seconds = 15 minute

    application.run_polling()

if __name__ == "__main__":
    main()  
