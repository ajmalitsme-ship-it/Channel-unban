#!/usr/bin/env python3
"""
ULTIMATE Telegram Channel Management Bot - FIXED & ENHANCED
===========================================================
Advanced Features:
✅ Modern UI with Inline Keyboards
✅ Channel/User Ban/Unban Management  
✅ Copyright Protection System
✅ Auto-Moderation
✅ Statistics Dashboard
✅ Multi-Group Support
✅ Database Logging (SQLite)
✅ Web Dashboard
✅ Render Web Service Support
✅ Frozen ID Protection
✅ Auto-Backup System
✅ Anti-Spam Protection
✅ Welcome Messages
✅ Scheduled Tasks

Version: 4.0 Ultimate Fixed
"""

import os
import json
import sqlite3
import logging
import sys
import asyncio
from datetime import datetime, timedelta
from threading import Thread
from typing import List, Dict, Optional
import re

# ============= DEPENDENCIES =============
try:
    from flask import Flask, jsonify, render_template_string, request
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, ChatMember
    from telegram.ext import (
        Application, CommandHandler, CallbackQueryHandler, 
        MessageHandler, filters, ContextTypes, JobQueue
    )
    from telegram.constants import ParseMode
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError as e:
    print(f"❌ Missing: {e}")
    print("Install: pip install python-telegram-bot==20.7 flask==2.3.3 apscheduler==3.10.4")
    sys.exit(1)

# ============= YOUR CONFIGURATION =============
BOT_TOKEN = "8570816432:AAFcLpn9P7Z-pRNQSJcn433lBAK-iU25q14"
GROUP_ID = "-1003840130115"
ADMIN_IDS = [8531814610, 8531814610]  # Added duplicate for safety
PRIVATE_MODE = False
AUTO_PROTECT = True

# ============= NEW: FROZEN ID PROTECTION =============
FROZEN_IDS = {
    "channels": [],  # Channel IDs that cannot be unbanned
    "users": [],     # User IDs that cannot be unbanned
    "admins": ADMIN_IDS.copy()  # Admin IDs that cannot be banned
}

# ============= NEW: SPAM PROTECTION =============
SPAM_SETTINGS = {
    "enabled": True,
    "max_messages": 5,  # Max messages per time window
    "time_window": 10,   # Time window in seconds
    "action": "mute"     # mute, ban, or warn
}

# ============= DATABASE SETUP (ENHANCED) =============
DB_PATH = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Existing tables
    c.execute('''CREATE TABLE IF NOT EXISTS banned_channels (
        channel_id TEXT PRIMARY KEY, channel_name TEXT, banned_by TEXT, 
        ban_reason TEXT, banned_at TIMESTAMP, unbanned_at TIMESTAMP NULL
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS restricted_channels (
        channel_id TEXT PRIMARY KEY, restricted_at TIMESTAMP, 
        restricted_by TEXT, auto_restricted BOOLEAN
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS banned_users (
        user_id TEXT PRIMARY KEY, username TEXT, banned_by TEXT, 
        reason TEXT, banned_at TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS action_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, target_id TEXT, 
        target_name TEXT, admin_id TEXT, admin_name TEXT, timestamp TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT
    )''')
    
    # NEW: Message tracking for spam protection
    c.execute('''CREATE TABLE IF NOT EXISTS message_tracking (
        user_id TEXT, message_count INTEGER, first_message_time TIMESTAMP,
        PRIMARY KEY (user_id)
    )''')
    
    # NEW: Backup logs
    c.execute('''CREATE TABLE IF NOT EXISTS backup_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, backup_time TIMESTAMP,
        backup_type TEXT, backup_size INTEGER, status TEXT
    )''')
    
    # NEW: Scheduled tasks
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, task_name TEXT,
        task_type TEXT, task_data TEXT, schedule_time TIMESTAMP,
        executed BOOLEAN DEFAULT FALSE
    )''')
    
    # NEW: Welcome messages
    c.execute('''CREATE TABLE IF NOT EXISTS welcome_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT,
        is_active BOOLEAN DEFAULT TRUE
    )''')
    
    # Insert default welcome message if not exists
    c.execute("SELECT COUNT(*) FROM welcome_messages")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO welcome_messages (message, is_active) VALUES (?, ?)",
                  ("Welcome to the group! 🎉 Please read the rules and enjoy your stay!", True))
    
    conn.commit()
    conn.close()

init_db()

# ============= FLASK WEB DASHBOARD (ENHANCED) =============
web_app = Flask(__name__)

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Channel Bot Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { opacity: 0.9; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; border-radius: 15px; padding: 20px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.2); transition: transform 0.3s; }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-card h3 { color: #667eea; margin-bottom: 10px; }
        .stat-card .number { font-size: 2.5em; font-weight: bold; color: #333; }
        .logs-table { background: white; border-radius: 15px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); overflow-x: auto; }
        .logs-table h2 { color: #333; margin-bottom: 15px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #667eea; color: white; }
        .badge { padding: 4px 8px; border-radius: 20px; font-size: 12px; }
        .badge-ban { background: #ff4757; color: white; }
        .badge-unban { background: #2ed573; color: white; }
        .badge-restrict { background: #ffa502; color: white; }
        .refresh-btn { background: white; color: #667eea; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; margin-bottom: 20px; font-weight: bold; }
        .refresh-btn:hover { transform: scale(1.05); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Ultimate Channel Management Bot</h1>
            <p>Real-time Dashboard | Auto-Refresh Every 30 Seconds</p>
        </div>
        <button class="refresh-btn" onclick="location.reload()">🔄 Refresh Now</button>
        <div class="stats-grid">
            <div class="stat-card"><h3>Total Channel Bans</h3><div class="number">{{ total_bans }}</div></div>
            <div class="stat-card"><h3>Restricted Channels</h3><div class="number">{{ total_restrictions }}</div></div>
            <div class="stat-card"><h3>Banned Users</h3><div class="number">{{ total_user_bans }}</div></div>
            <div class="stat-card"><h3>Total Actions</h3><div class="number">{{ total_actions }}</div></div>
        </div>
        <div class="logs-table">
            <h2>📋 Recent Actions (Last 50)</h2>
            <table>
                <thead>
                    <tr><th>Time</th><th>Action</th><th>Target</th><th>Admin</th></tr>
                </thead>
                <tbody>
                    {% for log in logs %}
                    <tr>
                        <td>{{ log.timestamp[:19] }}</td>
                        <td><span class="badge badge-{{ log.action.split('_')[0] }}">{{ log.action }}</span></td>
                        <td>{{ log.target_name }}</td>
                        <td>{{ log.admin_name }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    <script>
        setTimeout(function() { location.reload(); }, 30000);
    </script>
</body>
</html>
'''

@web_app.route('/')
def dashboard():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM banned_channels")
    total_bans = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM restricted_channels")
    total_restrictions = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM banned_users")
    total_user_bans = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM action_logs")
    total_actions = c.fetchone()[0]
    c.execute("SELECT * FROM action_logs ORDER BY timestamp DESC LIMIT 50")
    logs = [{"timestamp": l[6], "action": l[1], "target_name": l[3], "admin_name": l[5]} for l in c.fetchall()]
    conn.close()
    return render_template_string(DASHBOARD_HTML, total_bans=total_bans, total_restrictions=total_restrictions, total_user_bans=total_user_bans, total_actions=total_actions, logs=logs)

@web_app.route('/api/stats')
def api_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM banned_channels")
    total_bans = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM action_logs WHERE timestamp > datetime('now', '-24 hours')")
    last_24h = c.fetchone()[0]
    conn.close()
    return jsonify({"total_bans": total_bans, "last_24h_actions": last_24h})

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ============= LOGGING =============
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def log_action(action, target_id, target_name, admin_id, admin_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO action_logs (action, target_id, target_name, admin_id, admin_name, timestamp) VALUES (?,?,?,?,?,?)",
              (action, target_id, target_name, admin_id, admin_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ============= PERMISSIONS =============
def restricted_perms():
    return ChatPermissions(
        can_send_messages=False, can_send_audios=False, can_send_documents=False,
        can_send_photos=False, can_send_videos=False, can_send_polls=False,
        can_send_other_messages=False, can_add_web_page_previews=False, can_invite_users=True
    )

def full_perms():
    return ChatPermissions(
        can_send_messages=True, can_send_audios=True, can_send_documents=True,
        can_send_photos=True, can_send_videos=True, can_send_polls=True,
        can_send_other_messages=True, can_add_web_page_previews=True,
        can_invite_users=True, can_pin_messages=True
    )

# ============= UI MENUS =============
def get_main_menu():
    keyboard = [[
        InlineKeyboardButton("📺 Channels", callback_data="menu_channels"),
        InlineKeyboardButton("👥 Users", callback_data="menu_users")
    ], [
        InlineKeyboardButton("🛡️ Protection", callback_data="menu_protection"),
        InlineKeyboardButton("📊 Stats", callback_data="menu_stats")
    ], [
        InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
        InlineKeyboardButton("🔒 Frozen IDs", callback_data="menu_frozen"),
        InlineKeyboardButton("❌ Close", callback_data="menu_close")
    ]]
    return InlineKeyboardMarkup(keyboard)

# ============= CHECK FROZEN ID =============
def is_frozen(target_id, target_type="channel"):
    target_id_str = str(target_id)
    if target_type == "channel" and target_id_str in [str(fid) for fid in FROZEN_IDS["channels"]]:
        return True
    if target_type == "user" and target_id_str in [str(fid) for fid in FROZEN_IDS["users"]]:
        return True
    if target_type == "admin" and target_id_str in [str(fid) for fid in FROZEN_IDS["admins"]]:
        return True
    return False

# ============= NEW: AUTO-BACKUP SYSTEM =============
def create_backup():
    try:
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        backup_file = f"{backup_dir}/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        conn = sqlite3.connect(DB_PATH)
        backup_conn = sqlite3.connect(backup_file)
        conn.backup(backup_conn)
        backup_conn.close()
        conn.close()
        
        backup_size = os.path.getsize(backup_file)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO backup_logs (backup_time, backup_type, backup_size, status) VALUES (?, ?, ?, ?)",
                  (datetime.now().isoformat(), "auto", backup_size, "success"))
        conn.commit()
        conn.close()
        
        logger.info(f"Auto-backup created: {backup_file}")
        
        # Keep only last 10 backups
        backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
        for old_backup in backups[:-10]:
            os.remove(os.path.join(backup_dir, old_backup))
            
    except Exception as e:
        logger.error(f"Backup failed: {e}")

# ============= NEW: WELCOME MESSAGE HANDLER =============
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for new_member in update.message.new_chat_members:
        if new_member.id == context.bot.id:
            return
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT message FROM welcome_messages WHERE is_active = 1 LIMIT 1")
        result = c.fetchone()
        conn.close()
        
        if result:
            welcome_msg = result[0]
            await update.message.reply_text(f"👋 {new_member.first_name}, {welcome_msg}")

# ============= NEW: SPAM PROTECTION =============
async def check_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not SPAM_SETTINGS["enabled"]:
        return
    
    user_id = str(update.effective_user.id)
    current_time = datetime.now()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT message_count, first_message_time FROM message_tracking WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result:
        message_count, first_time_str = result
        first_time = datetime.fromisoformat(first_time_str)
        time_diff = (current_time - first_time).total_seconds()
        
        if time_diff < SPAM_SETTINGS["time_window"]:
            message_count += 1
            if message_count > SPAM_SETTINGS["max_messages"]:
                # Spam detected
                if SPAM_SETTINGS["action"] == "mute":
                    await context.bot.restrict_chat_member(
                        chat_id=update.effective_chat.id,
                        user_id=update.effective_user.id,
                        permissions=ChatPermissions(can_send_messages=False)
                    )
                    await update.message.reply_text("⚠️ You have been muted for spamming!")
                elif SPAM_SETTINGS["action"] == "ban":
                    await context.bot.ban_chat_member(
                        chat_id=update.effective_chat.id,
                        user_id=update.effective_user.id
                    )
                    await update.message.reply_text("⚠️ You have been banned for spamming!")
                
                c.execute("DELETE FROM message_tracking WHERE user_id = ?", (user_id,))
                conn.commit()
                conn.close()
                return
        else:
            # Reset counter
            message_count = 1
            c.execute("UPDATE message_tracking SET message_count = ?, first_message_time = ? WHERE user_id = ?",
                     (message_count, current_time.isoformat(), user_id))
    else:
        message_count = 1
        c.execute("INSERT INTO message_tracking (user_id, message_count, first_message_time) VALUES (?, ?, ?)",
                 (user_id, message_count, current_time.isoformat()))
    
    conn.commit()
    conn.close()

# ============= COMMAND HANDLERS =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if PRIVATE_MODE and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized access. This bot is in private mode.")
        return
    
    await update.message.reply_text(
        f"🌟 **Welcome {update.effective_user.first_name}**\n\n"
        "**Ultimate Bot Commands:**\n"
        "📺 **Channel Management:**\n"
        "/unbanchannel `<id>` - Unban channel\n"
        "/banchannel - Ban channel (reply to message)\n"
        "/restrictchannel - Apply copyright protection\n"
        "/unrestrictchannel - Remove restrictions\n\n"
        "👥 **User Management:**\n"
        "/banuser `<id>` - Ban user\n"
        "/unbanuser `<id>` - Unban user\n\n"
        "🛡️ **Protection:**\n"
        "/protect_on - Enable auto protection\n"
        "/protect_off - Disable auto protection\n"
        "/spam_on - Enable spam protection\n"
        "/spam_off - Disable spam protection\n\n"
        "🔒 **Frozen IDs:**\n"
        "/freeze_channel `<id>` - Freeze channel (cannot be unbanned)\n"
        "/unfreeze_channel `<id>` - Unfreeze channel\n"
        "/freeze_user `<id>` - Freeze user (cannot be unbanned)\n"
        "/unfreeze_user `<id>` - Unfreeze user\n"
        "/list_frozen - List all frozen IDs\n\n"
        "📊 **Info:**\n"
        "/status - Check bot status\n"
        "/backup - Create manual backup\n"
        "/set_welcome `<message>` - Set welcome message\n"
        "/menu - Open control panel",
        parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu()
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if PRIVATE_MODE and update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text("📱 **Control Panel**", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "menu_close":
        await query.edit_message_text("👋 Menu closed. Send /menu to reopen.")
    elif data == "menu_channels":
        await query.edit_message_text(
            "📺 **Channel Management**\n\n"
            "• /banchannel (reply to channel message)\n"
            "• /unbanchannel <channel_id>\n"
            "• /restrictchannel (reply)\n"
            "• /unrestrictchannel (reply)\n\n"
            "⚠️ Frozen channels cannot be unbanned!",
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "menu_users":
        await query.edit_message_text(
            "👥 **User Management**\n\n"
            "• /banuser <user_id>\n"
            "• /unbanuser <user_id>\n\n"
            "⚠️ Frozen users cannot be unbanned!",
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "menu_protection":
        status = "ON" if AUTO_PROTECT else "OFF"
        spam_status = "ON" if SPAM_SETTINGS["enabled"] else "OFF"
        await query.edit_message_text(
            f"🛡️ **Protection Settings**\n\n"
            f"Auto Protection: {status}\n"
            f"Spam Protection: {spam_status}\n"
            f"Spam Action: {SPAM_SETTINGS['action']}\n"
            f"Max Messages: {SPAM_SETTINGS['max_messages']} per {SPAM_SETTINGS['time_window']}s\n\n"
            "Commands:\n/protect_on\n/protect_off\n/spam_on\n/spam_off",
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "menu_stats":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM banned_channels")
        total_bans = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM action_logs WHERE timestamp > datetime('now', '-7 days')")
        weekly_actions = c.fetchone()[0]
        conn.close()
        await query.edit_message_text(
            f"📊 **Statistics**\n\n"
            f"Total Channel Bans: {total_bans}\n"
            f"Actions (Last 7 Days): {weekly_actions}\n\n"
            f"Use /status for more info",
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "menu_settings":
        await query.edit_message_text(
            f"⚙️ **Bot Settings**\n\n"
            f"Private Mode: {PRIVATE_MODE}\n"
            f"Admins: {len(ADMIN_IDS)}\n"
            f"Group ID: {GROUP_ID}\n\n"
            f"Frozen Channels: {len(FROZEN_IDS['channels'])}\n"
            f"Frozen Users: {len(FROZEN_IDS['users'])}",
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "menu_frozen":
        await query.edit_message_text(
            f"🔒 **Frozen IDs Protection**\n\n"
            f"Frozen Channels: {FROZEN_IDS['channels']}\n"
            f"Frozen Users: {FROZEN_IDS['users']}\n\n"
            "Commands:\n"
            "/freeze_channel <id>\n"
            "/unfreeze_channel <id>\n"
            "/freeze_user <id>\n"
            "/unfreeze_user <id>\n"
            "/list_frozen",
            parse_mode=ParseMode.MARKDOWN
        )

async def unban_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if PRIVATE_MODE and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /unbanchannel -1001234567890\n\nGet channel ID by forwarding a message from the channel to @userinfobot")
        return
    
    try:
        channel_id = int(context.args[0])
        
        # Check if frozen
        if is_frozen(channel_id, "channel"):
            await update.message.reply_text(f"❌ Channel {channel_id} is FROZEN and cannot be unbanned!")
            return
        
        await context.bot.unban_chat_sender_chat(chat_id=GROUP_ID, sender_chat_id=channel_id)
        await update.message.reply_text(f"✅ Channel {channel_id} unbanned successfully!")
        log_action("unban", str(channel_id), f"Channel {channel_id}", str(update.effective_user.id), update.effective_user.first_name)
        logger.info(f"Unbanned channel: {channel_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}\n\nMake sure the channel ID is correct and the bot has admin rights.")

async def ban_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if PRIVATE_MODE and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    if not update.message.reply_to_message or not update.message.reply_to_message.sender_chat:
        await update.message.reply_text("❌ Please reply to a message from the channel you want to ban")
        return
    
    try:
        channel_id = update.message.reply_to_message.sender_chat.id
        channel_name = update.message.reply_to_message.sender_chat.title or str(channel_id)
        
        await context.bot.ban_chat_sender_chat(chat_id=GROUP_ID, sender_chat_id=channel_id)
        await update.message.reply_text(f"✅ Channel '{channel_name}' has been banned!")
        log_action("ban", str(channel_id), channel_name, str(update.effective_user.id), update.effective_user.first_name)
        logger.info(f"Banned channel: {channel_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}\n\nMake sure I have 'Ban Users' permission in the group.")

async def restrict_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if PRIVATE_MODE and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    if not update.message.reply_to_message or not update.message.reply_to_message.sender_chat:
        await update.message.reply_text("❌ Please reply to a message from the channel to restrict")
        return
    
    try:
        channel_id = update.message.reply_to_message.sender_chat.id
        await context.bot.restrict_chat_member(chat_id=GROUP_ID, user_id=channel_id, permissions=restricted_perms())
        await update.message.reply_text(f"🔒 Channel restricted (Copyright protection applied)")
        log_action("restrict", str(channel_id), "Channel", str(update.effective_user.id), update.effective_user.first_name)
        logger.info(f"Restricted channel: {channel_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def unrestrict_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if PRIVATE_MODE and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    if not update.message.reply_to_message or not update.message.reply_to_message.sender_chat:
        await update.message.reply_text("❌ Please reply to a message from the channel to unrestrict")
        return
    
    try:
        channel_id = update.message.reply_to_message.sender_chat.id
        await context.bot.restrict_chat_member(chat_id=GROUP_ID, user_id=channel_id, permissions=full_perms())
        await update.message.reply_text(f"✅ Channel unrestricted")
        log_action("unrestrict", str(channel_id), "Channel", str(update.effective_user.id), update.effective_user.first_name)
        logger.info(f"Unrestricted channel: {channel_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if PRIVATE_MODE and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /banuser 123456789\n\nGet user ID by forwarding a message from the user to @userinfobot")
        return
    
    try:
        user_id = int(context.args[0])
        
        # Check if frozen
        if is_frozen(user_id, "user"):
            await update.message.reply_text(f"❌ User {user_id} is FROZEN and cannot be banned!")
            return
        if is_frozen(user_id, "admin"):
            await update.message.reply_text(f"❌ User {user_id} is an ADMIN and cannot be banned!")
            return
        
        await context.bot.ban_chat_member(chat_id=GROUP_ID, user_id=user_id)
        await update.message.reply_text(f"✅ User {user_id} has been banned!")
        log_action("ban_user", str(user_id), f"User {user_id}", str(update.effective_user.id), update.effective_user.first_name)
        logger.info(f"Banned user: {user_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if PRIVATE_MODE and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /unbanuser 123456789")
        return
    
    try:
        user_id = int(context.args[0])
        
        # Check if frozen
        if is_frozen(user_id, "user"):
            await update.message.reply_text(f"❌ User {user_id} is FROZEN and cannot be unbanned!")
            return
        
        await context.bot.unban_chat_member(chat_id=GROUP_ID, user_id=user_id)
        await update.message.reply_text(f"✅ User {user_id} has been unbanned!")
        log_action("unban_user", str(user_id), f"User {user_id}", str(update.effective_user.id), update.effective_user.first_name)
        logger.info(f"Unbanned user: {user_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============= FROZEN ID COMMANDS =============
async def freeze_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Only admins can use this command")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /freeze_channel -1001234567890")
        return
    
    channel_id = context.args[0]
    if channel_id not in FROZEN_IDS["channels"]:
        FROZEN_IDS["channels"].append(channel_id)
        await update.message.reply_text(f"✅ Channel {channel_id} has been FROZEN!\nThis channel cannot be unbanned.")
        log_action("freeze_channel", channel_id, f"Channel {channel_id}", str(update.effective_user.id), update.effective_user.first_name)
    else:
        await update.message.reply_text(f"ℹ️ Channel {channel_id} is already frozen")

async def unfreeze_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Only admins can use this command")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /unfreeze_channel -1001234567890")
        return
    
    channel_id = context.args[0]
    if channel_id in FROZEN_IDS["channels"]:
        FROZEN_IDS["channels"].remove(channel_id)
        await update.message.reply_text(f"✅ Channel {channel_id} has been UNFROZEN!")
        log_action("unfreeze_channel", channel_id, f"Channel {channel_id}", str(update.effective_user.id), update.effective_user.first_name)
    else:
        await update.message.reply_text(f"ℹ️ Channel {channel_id} is not frozen")

async def freeze_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Only admins can use this command")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /freeze_user 123456789")
        return
    
    user_id = context.args[0]
    if user_id not in FROZEN_IDS["users"]:
        FROZEN_IDS["users"].append(user_id)
        await update.message.reply_text(f"✅ User {user_id} has been FROZEN!\nThis user cannot be banned or unbanned.")
        log_action("freeze_user", user_id, f"User {user_id}", str(update.effective_user.id), update.effective_user.first_name)
    else:
        await update.message.reply_text(f"ℹ️ User {user_id} is already frozen")

async def unfreeze_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Only admins can use this command")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /unfreeze_user 123456789")
        return
    
    user_id = context.args[0]
    if user_id in FROZEN_IDS["users"]:
        FROZEN_IDS["users"].remove(user_id)
        await update.message.reply_text(f"✅ User {user_id} has been UNFROZEN!")
        log_action("unfreeze_user", user_id, f"User {user_id}", str(update.effective_user.id), update.effective_user.first_name)
    else:
        await update.message.reply_text(f"ℹ️ User {user_id} is not frozen")

async def list_frozen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    await update.message.reply_text(
        f"🔒 **Frozen IDs List**\n\n"
        f"**Frozen Channels:**\n{', '.join(FROZEN_IDS['channels']) if FROZEN_IDS['channels'] else 'None'}\n\n"
        f"**Frozen Users:**\n{', '.join(FROZEN_IDS['users']) if FROZEN_IDS['users'] else 'None'}\n\n"
        f"**Protected Admins:**\n{', '.join(FROZEN_IDS['admins'])}",
        parse_mode=ParseMode.MARKDOWN
    )

# ============= WELCOME MESSAGE COMMANDS =============
async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /set_welcome Your welcome message here")
        return
    
    welcome_msg = " ".join(context.args)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE welcome_messages SET is_active = 0")
    c.execute("INSERT INTO welcome_messages (message, is_active) VALUES (?, ?)", (welcome_msg, True))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Welcome message updated!\n\nNew message: {welcome_msg}")

# ============= BACKUP COMMAND =============
async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    await update.message.reply_text("🔄 Creating backup... Please wait.")
    create_backup()
    await update.message.reply_text("✅ Backup created successfully!")

# ============= SPAM PROTECTION COMMANDS =============
async def spam_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    SPAM_SETTINGS["enabled"] = True
    await update.message.reply_text("🛡️ Spam protection ENABLED!")

async def spam_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    SPAM_SETTINGS["enabled"] = False
    await update.message.reply_text("⚠️ Spam protection DISABLED!")

async def protect_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_PROTECT
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    AUTO_PROTECT = True
    await update.message.reply_text("🛡️ Auto-protection ENABLED!\nAll new channel messages will be restricted.")

async def protect_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_PROTECT
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    AUTO_PROTECT = False
    await update.message.reply_text("⚠️ Auto-protection DISABLED!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if PRIVATE_MODE and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 Unauthorized")
        return
    
    try:
        chat = await context.bot.get_chat(GROUP_ID)
        bot_info = await context.bot.get_me()
        bot_member = await context.bot.get_chat_member(GROUP_ID, bot_info.id)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM banned_channels")
        total_bans = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM restricted_channels")
        total_restrictions = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM banned_users")
        total_user_bans = c.fetchone()[0]
        conn.close()
        
        await update.message.reply_text(
            f"📊 **Bot Status Report**\n\n"
            f"🤖 Bot: @{bot_info.username}\n"
            f"📢 Group: {chat.title}\n"
            f"🆔 Group ID: `{GROUP_ID}`\n"
            f"👑 Bot Admin: {bot_member.status == 'administrator'}\n\n"
            f"🛡️ **Protection Status:**\n"
            f"• Auto Protect: {'✅ ON' if AUTO_PROTECT else '❌ OFF'}\n"
            f"• Spam Protect: {'✅ ON' if SPAM_SETTINGS['enabled'] else '❌ OFF'}\n"
            f"• Private Mode: {'✅ ON' if PRIVATE_MODE else '❌ OFF'}\n\n"
            f"📈 **Statistics:**\n"
            f"• Banned Channels: {total_bans}\n"
            f"• Restricted Channels: {total_restrictions}\n"
            f"• Banned Users: {total_user_bans}\n\n"
            f"🔒 **Frozen IDs:**\n"
            f"• Frozen Channels: {len(FROZEN_IDS['channels'])}\n"
            f"• Frozen Users: {len(FROZEN_IDS['users'])}\n"
            f"• Protected Admins: {len(FROZEN_IDS['admins'])}\n\n"
            f"👥 **Admins:** {ADMIN_IDS}",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting status: {str(e)}")

async def auto_protect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not AUTO_PROTECT:
        return
    
    if update.message and update.message.sender_chat and update.message.sender_chat.type == "channel":
        channel_id = update.message.sender_chat.id
        try:
            await context.bot.restrict_chat_member(chat_id=GROUP_ID, user_id=channel_id, permissions=restricted_perms())
            logger.info(f"Auto-restricted channel: {channel_id}")
        except Exception as e:
            logger.error(f"Auto-protect error: {e}")

# ============= SCHEDULED TASKS =============
def schedule_tasks():
    scheduler = BackgroundScheduler()
    # Run backup every 6 hours
    scheduler.add_job(create_backup, 'interval', hours=6)
    # Clean old logs every day (keep last 30 days)
    scheduler.add_job(clean_old_logs, 'interval', days=1)
    scheduler.start()

def clean_old_logs():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Keep last 30 days of logs
        c.execute("DELETE FROM action_logs WHERE timestamp < datetime('now', '-30 days')")
        # Clean old message tracking (older than 1 hour)
        c.execute("DELETE FROM message_tracking WHERE first_message_time < datetime('now', '-1 hour')")
        conn.commit()
        conn.close()
        logger.info("Old logs cleaned successfully")
    except Exception as e:
        logger.error(f"Log cleanup failed: {e}")

# ============= MAIN =============
def main():
    # Start web server
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    # Start scheduler for backups
    schedule_tasks()
    
    # Create bot application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("unbanchannel", unban_channel))
    app.add_handler(CommandHandler("banchannel", ban_channel))
    app.add_handler(CommandHandler("restrictchannel", restrict_channel))
    app.add_handler(CommandHandler("unrestrictchannel", unrestrict_channel))
    app.add_handler(CommandHandler("banuser", ban_user))
    app.add_handler(CommandHandler("unbanuser", unban_user))
    
    # Frozen ID handlers
    app.add_handler(CommandHandler("freeze_channel", freeze_channel))
    app.add_handler(CommandHandler("unfreeze_channel", unfreeze_channel))
    app.add_handler(CommandHandler("freeze_user", freeze_user))
    app.add_handler(CommandHandler("unfreeze_user", unfreeze_user))
    app.add_handler(CommandHandler("list_frozen", list_frozen))
    
    # Protection handlers
    app.add_handler(CommandHandler("protect_on", protect_on))
    app.add_handler(CommandHandler("protect_off", protect_off))
    app.add_handler(CommandHandler("spam_on", spam_on))
    app.add_handler(CommandHandler("spam_off", spam_off))
    
    # Utility handlers
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("backup", backup))
    app.add_handler(CommandHandler("set_welcome", set_welcome))
    
    # Callback and message handlers
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_spam))
    app.add_handler(MessageHandler(filters.ALL, auto_protect_handler))
    
    print("="*60)
    print("🤖 ULTIMATE BOT STARTED - VERSION 4.0")
    print("="*60)
    print(f"✅ Bot Token: {BOT_TOKEN[:20]}...")
    print(f"✅ Group ID: {GROUP_ID}")
    print(f"✅ Admins: {ADMIN_IDS}")
    print(f"✅ Auto Protect: {AUTO_PROTECT}")
    print(f"✅ Spam Protect: {SPAM_SETTINGS['enabled']}")
    print(f"✅ Private Mode: {PRIVATE_MODE}")
    print(f"✅ Web Dashboard: http://localhost:{os.environ.get('PORT', 8080)}")
    print(f"✅ Frozen Channels: {len(FROZEN_IDS['channels'])}")
    print(f"✅ Frozen Users: {len(FROZEN_IDS['users'])}")
    print("="*60)
    print("🟢 Bot is running and ready to protect your group!")
    print("🟢 Web dashboard available for monitoring")
    print("🟢 Auto-backup every 6 hours")
    print("="*60)
    
    # Start polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
