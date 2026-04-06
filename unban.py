#!/usr/bin/env python3
"""
Telegram Channel Unban & Protection Bot
===========================================
A complete solution for managing channel bans, copyright protection,
and admin controls in Telegram groups.

Features:
✅ Unban channels from posting in groups
✅ Ban channels with copyright protection
✅ Auto-restrict new channels
✅ Private bot mode (authorized users only)
✅ Complete admin commands
✅ Ready for Render deployment

Official API Methods:
- unbanChatSenderChat - Unban channels
- banChatSenderChat - Ban channels  
- restrictChatMember - Apply copyright restrictions
- setChatPermissions - Set default permissions
- getChatMember - Check admin status

Author: Telegram Bot API
Version: 2.0
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, List, Any

# ============= DEPENDENCY CHECK =============
try:
    from telegram import Bot, Update, ChatPermissions, ChatMember
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError:
    print("❌ Missing required library. Install with: pip install python-telegram-bot==20.7")
    sys.exit(1)

# ============= CONFIGURATION =============
# Load from environment variables (Render) or config file
CONFIG_FILE = "config.json"

def load_config():
    """Load configuration from environment variables or JSON file"""
    
    # Priority 1: Environment Variables (Render Deployment)
    config = {
        "bot_token": os.environ.get("BOT_TOKEN", "8570816432:AAFcLpn9P7Z-pRNQSJcn433lBAK-iU25q14"),
        "group_id": os.environ.get("GROUP_ID", "-1003840130115"),
        "admin_ids": os.environ.get("ADMIN_IDS", "8531814610").split(",") if os.environ.get("ADMIN_IDS") else [],
        "private_mode": os.environ.get("PRIVATE_MODE", "true").lower() == "true",
        "auto_protect": os.environ.get("AUTO_PROTECT", "true").lower() == "true",
        "restricted_permissions": {
            "can_send_messages": False,
            "can_send_media": False,
            "can_send_other_messages": False,
            "can_add_web_page_previews": False
        }
    }
    
    # Priority 2: Config File (Local Development)
    if not config["bot_token"] or config["bot_token"] == "":
        try:
            with open(CONFIG_FILE, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
                print(f"✅ Loaded configuration from {CONFIG_FILE}")
        except FileNotFoundError:
            # Create template config file
            default_config = {
                "bot_token": "YOUR_BOT_TOKEN_HE",
                "group_id": "@your_group_username",
                "admin_ids": [123456789],  # Your Telegram user ID
                "private_mode": True,
                "auto_protect": True,
                "restricted_permissions": {
                    "can_send_messages": False,
                    "can_send_media": False,
                    "can_send_other_messages": False,
                    "can_add_web_page_previews": False
                }
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(default_config, f, indent=4)
            print(f"📝 Created {CONFIG_FILE} - Please edit it with your bot token and group ID")
            print(f"   Then run: python unban.py")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing {CONFIG_FILE}: {e}")
            sys.exit(1)
    
    # Clean up admin_ids
    if isinstance(config["admin_ids"], list):
        config["admin_ids"] = [int(uid) for uid in config["admin_ids"] if uid]
    elif isinstance(config["admin_ids"], str):
        config["admin_ids"] = [int(uid) for uid in config["admin_ids"].split(",") if uid]
    else:
        config["admin_ids"] = []
    
    return config

config = load_config()

BOT_TOKEN = config.get("bot_token", "")
GROUP_ID = config.get("group_id", "")
ADMIN_IDS = config.get("admin_ids", [])
PRIVATE_MODE = config.get("private_mode", True)
AUTO_PROTECT = config.get("auto_protect", True)
RESTRICTED_PERMS = config.get("restricted_permissions", {})

# ============= LOGGING SETUP =============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============= PERMISSION UTILITIES =============

def get_restricted_permissions() -> ChatPermissions:
    """Create restricted permissions for copyright protection"""
    return ChatPermissions(
        can_send_messages=RESTRICTED_PERMS.get("can_send_messages", False),
        can_send_audios=RESTRICTED_PERMS.get("can_send_media", False),
        can_send_documents=RESTRICTED_PERMS.get("can_send_media", False),
        can_send_photos=RESTRICTED_PERMS.get("can_send_media", False),
        can_send_videos=RESTRICTED_PERMS.get("can_send_media", False),
        can_send_video_notes=RESTRICTED_PERMS.get("can_send_media", False),
        can_send_voice_notes=RESTRICTED_PERMS.get("can_send_media", False),
        can_send_polls=RESTRICTED_PERMS.get("can_send_other_messages", False),
        can_send_other_messages=RESTRICTED_PERMS.get("can_send_other_messages", False),
        can_add_web_page_previews=RESTRICTED_PERMS.get("can_add_web_page_previews", False),
        can_invite_users=True,
        can_pin_messages=False
    )

def get_full_permissions() -> ChatPermissions:
    """Create full permissions for unrestricting"""
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
        can_pin_messages=True
    )

# ============= AUTHORIZATION CHECK =============

async def is_authorized(update: Update) -> bool:
    """Check if user is authorized to use bot commands"""
    if not PRIVATE_MODE:
        return True
    
    user_id = update.effective_user.id
    return user_id in ADMIN_IDS

async def check_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Middleware to check authorization"""
    if await is_authorized(update):
        return True
    
    await update.message.reply_text(
        "🔒 **Private Bot Mode**\n\n"
        "This bot is in private mode. You are not authorized to use it.\n\n"
        "Contact the bot owner for access.",
        parse_mode="Markdown"
    )
    logger.warning(f"Unauthorized access attempt from user {update.effective_user.id}")
    return False

# ============= COMMAND HANDLERS =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message with all commands"""
    if not await check_auth(update, context):
        return
    
    await update.message.reply_text(
        "🤖 **Channel Unban & Protection Bot**\n\n"
        "**Channel Management:**\n"
        "/unbanchannel `<channel_id>` - Unban a channel from posting\n"
        "/banchannel - Ban a channel (reply to channel message)\n"
        "/restrictchannel - Apply copyright restrictions\n"
        "/unrestrictchannel - Remove restrictions\n\n"
        "**User Management:**\n"
        "/banuser `<user_id>` - Ban a user\n"
        "/unbanuser `<user_id>` - Unban a user\n\n"
        "**Group Settings:**\n"
        "/protect_on - Enable auto copyright protection\n"
        "/protect_off - Disable auto protection\n"
        "/getperms - View current permissions\n"
        "/setfullperms - Grant full permissions to all\n\n"
        "**Status:**\n"
        "/status - Check bot status\n"
        "/help - Show this help\n\n"
        "📌 **Find Channel ID:** Forward message from channel to @userinfobot",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check bot status and permissions"""
    if not await check_auth(update, context):
        return
    
    try:
        bot = context.bot
        chat = await bot.get_chat(GROUP_ID)
        bot_member = await bot.get_chat_member(GROUP_ID, bot.id)
        
        status_text = (
            f"📊 **Bot Status Report**\n\n"
            f"**Group:** {chat.title}\n"
            f"**Group ID:** `{chat.id}`\n"
            f"**Bot Status:** {bot_member.status}\n"
            f"**Can Restrict:** {bot_member.can_restrict_members if bot_member.status == 'administrator' else 'N/A'}\n"
            f"**Private Mode:** {'🔒 ON' if PRIVATE_MODE else '🔓 OFF'}\n"
            f"**Protection Mode:** {'🛡️ ON' if AUTO_PROTECT else '⚠️ OFF'}\n"
            f"**Authorized Admins:** {len(ADMIN_IDS)}\n\n"
            f"✅ Bot is ready to manage channels!"
        )
        
        await update.message.reply_text(status_text, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Status check failed: {str(e)}")

# ============= CHANNEL BAN/UNBAN COMMANDS =============

async def unban_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Unban a channel from posting in the group.
    Uses official unbanChatSenderChat API method
    """
    if not await check_auth(update, context):
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Usage:** `/unbanchannel <channel_id>`\n\n"
            "Example: `/unbanchannel -1009876543210`\n\n"
            "Find channel ID by forwarding a message from the channel to @userinfobot",
            parse_mode="Markdown"
        )
        return
    
    try:
        channel_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Channel ID must be a number starting with -100")
        return
    
    confirm_msg = await update.message.reply_text(f"🔄 Unbanning channel `{channel_id}`...", parse_mode="Markdown")
    
    try:
        # OFFICIAL API METHOD: unbanChatSenderChat
        result = await context.bot.unban_chat_sender_chat(
            chat_id=GROUP_ID,
            sender_chat_id=channel_id
        )
        
        if result:
            await confirm_msg.edit_text(
                f"✅ **Channel Unbanned Successfully**\n\n"
                f"**Channel ID:** `{channel_id}`\n\n"
                f"The channel can now post messages in this group again.\n\n"
                f"📌 Use `/banchannel` to ban it again if needed.",
                parse_mode="Markdown"
            )
            logger.info(f"✅ Unbanned channel {channel_id} from {GROUP_ID}")
        else:
            await confirm_msg.edit_text("⚠️ Channel was not banned or unban failed.")
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unban failed: {error_msg}")
        
        if "not enough rights" in error_msg.lower():
            await confirm_msg.edit_text(
                "❌ **Bot lacks permissions**\n\n"
                "Make the bot an admin with 'can_restrict_members' right."
            )
        elif "chat not found" in error_msg.lower():
            await confirm_msg.edit_text(
                f"❌ **Group not found**\n\n"
                f"Check GROUP_ID in config: {GROUP_ID}"
            )
        else:
            await confirm_msg.edit_text(f"❌ Error: {error_msg}")

async def ban_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ban a channel from posting"""
    if not await check_auth(update, context):
        return
    
    # Check if replying to a channel message
    if update.message.reply_to_message:
        sender_chat = update.message.reply_to_message.sender_chat
        if sender_chat:
            channel_id = sender_chat.id
            channel_name = sender_chat.title or f"Channel {channel_id}"
        else:
            await update.message.reply_text("❌ Reply to a message from the channel you want to ban")
            return
    elif context.args:
        try:
            channel_id = int(context.args[0])
            channel_name = f"Channel {channel_id}"
        except ValueError:
            await update.message.reply_text("❌ Provide a valid channel ID (e.g., -1001234567890)")
            return
    else:
        await update.message.reply_text("❌ Reply to a channel message or provide channel ID: /banchannel -1001234567890")
        return

    try:
        # OFFICIAL API METHOD: banChatSenderChat
        result = await context.bot.ban_chat_sender_chat(
            chat_id=GROUP_ID,
            sender_chat_id=channel_id
        )
        
        if result:
            await update.message.reply_text(
                f"✅ **Channel Banned**\n\n"
                f"**Channel:** {channel_name}\n"
                f"**ID:** `{channel_id}`\n\n"
                f"Use `/unbanchannel {channel_id}` to unban.",
                parse_mode="Markdown"
            )
            logger.info(f"Banned channel {channel_id}")
        else:
            await update.message.reply_text("⚠️ Ban failed")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============= RESTRICTION COMMANDS =============

async def restrict_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Apply copyright protection restrictions to a channel"""
    if not await check_auth(update, context):
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a channel message to restrict it")
        return
    
    sender_chat = update.message.reply_to_message.sender_chat
    if not sender_chat:
        await update.message.reply_text("❌ This message is not from a channel")
        return
    
    try:
        result = await context.bot.restrict_chat_member(
            chat_id=GROUP_ID,
            user_id=sender_chat.id,
            permissions=get_restricted_permissions()
        )
        
        if result:
            await update.message.reply_text(
                f"🔒 **Copyright Protection Applied**\n\n"
                f"**Channel:** {sender_chat.title or sender_chat.id}\n\n"
                f"**Restrictions:**\n"
                f"❌ Cannot send messages\n"
                f"❌ Cannot send media\n"
                f"❌ Cannot send polls or stickers\n\n"
                f"Use `/unrestrictchannel` to remove restrictions.",
                parse_mode="Markdown"
            )
            logger.info(f"Restricted channel {sender_chat.id}")
        else:
            await update.message.reply_text("⚠️ Failed to restrict channel")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def unrestrict_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove restrictions from a channel"""
    if not await check_auth(update, context):
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a restricted channel's message")
        return
    
    sender_chat = update.message.reply_to_message.sender_chat
    if not sender_chat:
        await update.message.reply_text("❌ This message is not from a channel")
        return
    
    try:
        result = await context.bot.restrict_chat_member(
            chat_id=GROUP_ID,
            user_id=sender_chat.id,
            permissions=get_full_permissions()
        )
        
        if result:
            await update.message.reply_text(
                f"✅ **Channel Unrestricted**\n\n"
                f"**Channel:** {sender_chat.title or sender_chat.id}\n\n"
                f"Full permissions granted.",
                parse_mode="Markdown"
            )
            logger.info(f"Unrestricted channel {sender_chat.id}")
        else:
            await update.message.reply_text("⚠️ Failed to unrestrict channel")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============= PROTECTION MODE =============

async def protect_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable automatic copyright protection"""
    if not await check_auth(update, context):
        return
    
    global AUTO_PROTECT
    AUTO_PROTECT = True
    config["auto_protect"] = True
    
    # Save to config file
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except:
        pass
    
    await update.message.reply_text(
        "🛡️ **Copyright Protection Mode: ENABLED**\n\n"
        "New channels posting in the group will be automatically restricted.\n\n"
        "Use `/protect_off` to disable.",
        parse_mode="Markdown"
    )

async def protect_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disable automatic copyright protection"""
    if not await check_auth(update, context):
        return
    
    global AUTO_PROTECT
    AUTO_PROTECT = False
    config["auto_protect"] = False
    
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except:
        pass
    
    await update.message.reply_text(
        "⚠️ **Copyright Protection Mode: DISABLED**\n\n"
        "Channels will not be automatically restricted.\n\n"
        "Use `/protect_on` to enable.",
        parse_mode="Markdown"
    )

async def set_full_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set full permissions for all members"""
    if not await check_auth(update, context):
        return
    
    try:
        result = await context.bot.set_chat_permissions(
            chat_id=GROUP_ID,
            permissions=get_full_permissions()
        )
        
        if result:
            await update.message.reply_text(
                "✅ **Full permissions granted to all members**\n\n"
                "Use `/restrictchannel` to apply copyright restrictions to specific channels.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Failed to update permissions")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def get_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get current permissions for the group"""
    if not await check_auth(update, context):
        return
    
    try:
        chat = await context.bot.get_chat(GROUP_ID)
        perms = chat.permissions
        
        perms_text = (
            f"📊 **Current Group Permissions**\n\n"
            f"Send Messages: {'✅' if perms.can_send_messages else '❌'}\n"
            f"Send Media: {'✅' if perms.can_send_audios else '❌'}\n"
            f"Send Polls: {'✅' if perms.can_send_polls else '❌'}\n"
            f"Send Stickers/GIFs: {'✅' if perms.can_send_other_messages else '❌'}\n"
            f"Add Web Previews: {'✅' if perms.can_add_web_page_previews else '❌'}\n\n"
            f"**Protection Mode:** {'🛡️ ON' if AUTO_PROTECT else '⚠️ OFF'}\n"
            f"**Private Mode:** {'🔒 ON' if PRIVATE_MODE else '🔓 OFF'}"
        )
        
        await update.message.reply_text(perms_text, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============= USER BAN/UNBAN =============

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ban a user from the group"""
    if not await check_auth(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /banuser <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        await context.bot.ban_chat_member(GROUP_ID, user_id)
        await update.message.reply_text(f"✅ User {user_id} banned successfully")
        logger.info(f"Banned user {user_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unban a user from the group"""
    if not await check_auth(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /unbanuser <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        await context.bot.unban_chat_member(GROUP_ID, user_id)
        await update.message.reply_text(f"✅ User {user_id} unbanned successfully")
        logger.info(f"Unbanned user {user_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============= AUTO PROTECT HANDLER =============

async def auto_protect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Automatically restrict new channels when they post"""
    if not AUTO_PROTECT:
        return
    
    message = update.message
    if not message or not message.sender_chat:
        return
    
    # Check if this is a channel posting
    if message.sender_chat.type == "channel":
        channel_id = message.sender_chat.id
        
        try:
            # Auto-restrict the channel
            await context.bot.restrict_chat_member(
                chat_id=GROUP_ID,
                user_id=channel_id,
                permissions=get_restricted_permissions()
            )
            logger.info(f"Auto-restricted channel {channel_id}")
            
            # Notify admins (optional)
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"🛡️ **Auto Protection Triggered**\n\n"
                        f"Channel `{channel_id}` has been automatically restricted.\n"
                        f"Use `/unrestrictchannel` to remove restrictions.",
                        parse_mode="Markdown"
                    )
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Auto-protect failed: {e}")

# ============= HEALTH CHECK (for Render) =============

async def health_check():
    """Simple health check for Render deployment"""
    print("🤖 Bot is running and healthy")
    print(f"Group ID: {GROUP_ID}")
    print(f"Private Mode: {PRIVATE_MODE}")
    print(f"Auto Protect: {AUTO_PROTECT}")
    print(f"Authorized Admins: {len(ADMIN_IDS)}")

# ============= MAIN FUNCTION =============

def main() -> None:
    """Start the bot"""
    # Validate configuration
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: BOT_TOKEN not configured!")
        print("\nSetup options:")
        print("1. Local: Edit config.json and add your bot token")
        print("2. Render: Set BOT_TOKEN environment variable")
        print("\nGet a token from @BotFather on Telegram")
        return
    
    if not GROUP_ID or GROUP_ID == "@your_group_username":
        print("⚠️ WARNING: GROUP_ID not configured")
        print("The bot will not work until you set the group ID")
    
    if PRIVATE_MODE and not ADMIN_IDS:
        print("⚠️ WARNING: Private mode is ON but no admin IDs configured")
        print("Add your Telegram user ID to ADMIN_IDS in config.json or ADMIN_IDS env var")
        print("Find your ID: Send /start to @userinfobot on Telegram")
    
    def main() -> None:
    """Start the bot"""
    # Validate configuration
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: BOT_TOKEN not configured!")
        return
    
    if PRIVATE_MODE and not ADMIN_IDS:
        print("⚠️ WARNING: Private mode is ON but no admin IDs configured")
        print("Add ADMIN_IDS environment variable or add to config.json")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("unbanchannel", unban_channel))
    application.add_handler(CommandHandler("banchannel", ban_channel))
    application.add_handler(CommandHandler("restrictchannel", restrict_channel))
    application.add_handler(CommandHandler("unrestrictchannel", unrestrict_channel))
    application.add_handler(CommandHandler("protect_on", protect_on))
    application.add_handler(CommandHandler("protect_off", protect_off))
    application.add_handler(CommandHandler("setfullperms", set_full_permissions))
    application.add_handler(CommandHandler("getperms", get_permissions))
    application.add_handler(CommandHandler("banuser", ban_user))
    application.add_handler(CommandHandler("unbanuser", unban_user))
    application.add_handler(MessageHandler(filters.ALL, auto_protect_handler))
    
    # Print startup message
    print("\n" + "="*50)
    print("🤖 Telegram Channel Unban Bot Started")
    print("="*50)
    print(f"Group: {GROUP_ID}")
    print(f"Private Mode: {'ON' if PRIVATE_MODE else 'OFF'}")
    print(f"Auto Protect: {'ON' if AUTO_PROTECT else 'OFF'}")
    print(f"Admins: {len(ADMIN_IDS)}")
    print("="*50 + "\n")
    
    # REMOVED: asyncio.create_task(health_check())  # ← DELETE THIS LINE
    
    # Start polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
