import os
import sys
import asyncio
import random
import time
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from telethon.tl.types import User, Chat, Channel

# ─── Logging Setup ───
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(name)

# ─── Config from ENV ───
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

if not all([API_ID, API_HASH, SESSION_STRING, ADMIN_IDS]):
    print("❌ ERROR: API_ID, API_HASH, SESSION_STRING, ADMIN_IDS set karo Render env mein!")
    sys.exit(1)

# ─── Bot State ───
class BotState:
    def init(self):
        self.raid_active = False
        self.raid_mode = "off"  # off, groupraid, replyraid, dmraid
        self.raid_target_id = None
        self.raid_target_name = "None"
        self.raid_delay = 2.0
        self.raid_count = 0
        self.raid_limit = 1000
        self.raid_message = "🔥 Raid 🔥"
        self.spam_count = 50
        self.spam_delay = 0.5
        self.flood_active = False
        self.start_time = datetime.now()
        self.admins = set(ADMIN_IDS)
        self.ignored_users = set()
        self.auto_mode = False
        self.lockdown_mode = False

state = BotState()

# ─── Init Client ───
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ─── Helper Functions ───

def is_admin(user_id):
    return user_id in state.admins

async def safe_send(entity, message, reply_to=None):
    """Flood wait handle karke send karega"""
    try:
        if reply_to:
            await client.send_message(entity, message, reply_to=reply_to)
        else:
            await client.send_message(entity, message)
        return True
    except errors.FloodWaitError as e:
        wait = e.seconds
        logger.warning(f"FloodWait: {wait}s — waiting...")
        if wait <= 60:
            await asyncio.sleep(wait + 1)
            return await safe_send(entity, message, reply_to)
        else:
            logger.error(f"FloodWait too long: {wait}s, skipping")
            return False
    except Exception as e:
        logger.error(f"Send error: {e}")
        return False

def format_uptime():
    delta = datetime.now() - state.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"

# ─── Raid Engine ───

async def raid_engine():
    """Background task for continuous raiding"""
    while True:
        try:
            if state.raid_active and state.raid_target_id:
                try:
                    entity = await client.get_entity(state.raid_target_id)
                    msg = state.raid_message
                    # Add variation for anti-ban
                    if random.random() < 0.3:
                        suffixes = [" 🔥", " 💀", " ⚡", " 🚀", " !!", " !!!", ""]
                        msg = msg + random.choice(suffixes)
                    await safe_send(entity, msg)
                    state.raid_count += 1
                    
                    # Auto-stop if limit reached
                    if state.raid_count >= state.raid_limit:
                        state.raid_active = False
                        logger.info(f"Raid limit reached ({state.raid_limit}), auto-stopped")
                except Exception as e:
                    logger.error(f"Raid engine error: {e}")
                    state.raid_active = False
            await asyncio.sleep(state.raid_delay)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Raid engine critical: {e}")
            await asyncio.sleep(5)

# ─── Commands ───

@client.on(events.NewMessage(pattern=r'^\.(help|menu|cmd)$'))
async def help_cmd(event):
    if not is_admin(event.sender_id):
        return
    text = """
⚡ ADVANCED RAID BOT — ADMIN PANEL ⚡

━━━━━━━━━━━━━━━━━━━
🚀 RAID COMMANDS
━━━━━━━━━━━━━━━━━━━
**.raid <delay> <message>** — Group raid start
**.raidstop** ya **.stop** — Raid stop
**.raidlimit <number>** — Message limit set .raidstatus
**.raidstatus** — Raid ki current status dekho

━━━━💬 SPAM COMMANDS SPAM COMMANDS**
━━━━━━━━━━━━━━━━━━━
**.spam <count> <delay> <msg>** — Bulk spam
**.stopspam** — Spam r🔄 REPLYRAID━━━━━━━
**🔄 REPLYRAI.replyraid <msg>━━━
**.replyraid <msg>** — Reply raid ON
**.replyraidstop** — Reply ra📨 DM COMMANDS━━━━━━━━━
**📨 DM COM.dmraid <delay> <msg>━━
**.dmraid <delay> <msg>** — DM ra.dmraidstopo DM karega)
**.dmraidstop** — DM ra🛡️ ADMIN TOOLS━━━━━━━━
**🛡️ ADMIN .ping━━━━━━━━━━━━━━━━━━
**.ping** — Bot alive check
**.uptime.statsitni der se chal raha
**.stats** — Full statistics
**.broadcast <msg>** — Saare groups mein broadcast
**.join <link>** — Group .admins*.leave** — Current group chhodo
**.admins** — Admin list

━━━━━━━━.setdelay <sec>TTINGS**
━━━━━━━━━━━━━━━━━━━
**.setdelay <sec>** — Raid delay badlo
**.setmsg <text>** — Ra.restartadlo
**.setlimit <num>** — Raid limit badlo
**.restart** — Bot restart 🔄
    """
    await event.reply(text, parse_mode='markdown')

@client.on(events.NewMessage(pattern=r'^\.raid (.+)'))
async def cmd_raid(event):
    if not is_admin(event.sender_id):
        await event.reply("⛔ Sirf admin!")
        return
    
    try:
        parts = event.message.text.split(maxsplit=2)
        delay = float(parts[1])
        message = parts[2] if len(parts) > 2 else "🔥 Raid 🔥"
        
        chat = await event.get_chat()
        target_id = chat.id
        target_name = chat.title if hasattr(chat, 'title') else "DM"
        
        state.raid_active = True
        state.raid_mode = "groupraid"
        state.raid_target_id = target_id
        state.raid_target_name = target_name
        state.raid_delay = max(0.5, delay)
        state.raid_message = message
        state.raid_count RAID ACTIVATED   await event.reply(
      {target_name}ACTIVATED**\n"
            {delay}s**{target_name}**\n"
            f"└ Delay: **{delay}s**\n"
            f"└ Message: {message[:50]}\n"
            f"└ Limit: **{state.raid_limit}** msgs\n"
            f"📌 Stop: .stop ya .raidstop"
        )
        logger.info(f"Raid started by {event.sender_id} on {target_name}")
    except Exception as e:
        await event.reply(f"❌ Error: .raid <delay> <message>\n{e}")

@client.on(events.NewMessage(pattern=r'^\.(raidstop|stop|stopraid)$'))
async def cmd_stop(event):
    if not is_admin(event.sender_id):
        return
    
    old_mode = state.raid_mode
    state.raid_active = False
    state.raid_mode = "off"
    state.raid_count = 0
    state.flood_active = False
Stopped!to_mode = False
    
    await event{state.raid_count}**\n└ Mode: {old_mode}\n└ Total sent: **{state.raid_count}** msgs")

@client.on(events.NewMessage(pattern=r'^\.raidlimit (\d+)'))
async def cmd_raidlimit(event):
    if not is_admin(event.sender_id):
        return
    limit = int(event.pattern_match.group(1))
    state.raid{limit}mit
    await event.reply(f"✅ Raid limit set to: **{limit}** messages")

@client.on(events.NewMessage(pattern=r'^\.raidstatus$'))
async def cmd_raidstatus(event):
    if notACTIVEevent.sender_id):
        returnINACTIVE= "🟢 **ACTIVE**" if state.raid_act📊 RAID STATUSCTIVE**"
    await event.reply(
        f"**📊 RAID STATUS**\n"
        f"└ Status: {status}\n"
        f"└ Mode: {state.raid_mode}\n"
       {state.raid_delay}said_target_name}**\n"
{state.raid_count}state.raid_delay}s**\n"
        f"└ Sent: **{state.raid_count}** / {state.raid_limit}\n"
        f"└ Msg: {state.raid_message[:40]}"
    )

@client.on(events.NewMessage(pattern=r'^\.spam (\d+) (\d*\.?\d*) (.+)'))
async def cmd_spam(event):
    if not is_admin(event.sender_id):
        return
    
    match = event.pattern_match
    count = int(match.group(1))
    delay = float(match.group(2)) if match.group(2) else 0.5
    message = match.group(3)
    
    state.flood_active = True
    
    await event.reply(f"💬 Spamming {count} msgs with {delay}s delay...")
    
    sent = 0
    for i in range(min(count, 500)):
        if not state.flood_active:
            await event.reply("⏹️ Spam stopped by user")
            break
        try:
            await event.respond(message)
            sent += 1
            await asyncio.sleep(delay)
        except errors.FloodWaitError as e:
            wait = min(e.seconds, 30)
            await event.reply(f"⏳ Flood wait: {wait}s...")
            await asyncio.sleep(wait)
        except Exception as e:
            await event.reply(f"❌ Error: {e}")
            break
    
    state.flood_active = False
    await event.reply(f"✅ Spam complete — {sent} messages sent")

@client.on(events.NewMessage(pattern=r'^\.stopspam$'))
async def cmd_stopspam(event):
    if not is_admin(event.sender_id):
        return
    state.flood_active = False
    await event.reply("⏹️ Spam stopped")

@client.on(events.NewMessage(pattern=r'^\.replyraid (.+)'))
async def cmd_replyraid(event):
    if not is_admin(event.sender_id):
        return
    message = event.pattern_match.group(1)
    state.raid_mode = "replyraid"
    state.raid_active = True
    state.raid_message = message
    await event.reply(f"✅ ReplyRaid ON\n└ Reply msg: {message[:50]}\n📌 Stop: .replyraidstop")

@client.on(events.NewMessage(pattern=r'^\.replyraidstop$'))
async def cmd_replyraidstop(event):
    if not is_admin(event.sender_id):
        return
    state.raid_active = False
    state.raid_mode = "off"
    await event.reply("🛑 ReplyRaid stopped")

@client.on(events.NewMessage(pattern=r'^\.dmraid (\d+\.?\d*) (.+)'))
async def cmd_dmraid(event):
    if not is_admin(event.sender_id):
        return
    delay = float(event.pattern_match.group(1))
    message = event.pattern_match.group(2)
    
    state.raid_mode = "dmraid"
    state.raid_active = True
    state.raid_delay = max(1.0, delay)
    state.raid_message = message
    state.raid_target_id = None  # Will send to all admins
    
    await event.reply(f"✅ DM Raid ON\n└ Admin IDs: {list(state.admins)}\n└ Delay: {delay}s\n└ Msg: {message[:40]}")

@client.on(events.NewMessage(pattern=r'^\.dmraidstop$'))
async def cmd_dmraidstop(event):
    if not is_admin(event.sender_id):
        return
    state.raid_active = False
    state.raid_mode = "off"
    await event.reply("🛑 DM Raid stopped")

@client.on(events.NewMessage(pattern=r'^\.setdelay (\d+\.?\d*)'))
async def cmd_setdelay(event):
    if not is_admin(event.sender_id):
        return
    delay = float(event.pattern_match.group(1))
    state.raid_delay = max(0.3, delay)
    await event.reply(f"✅ Delay set to: {state.raid_delay}s")

@client.on(events.NewMessage(pattern=r'^\.setmsg (.+)'))
async def cmd_setmsg(event):
    if not is_admin(event.sender_id):
        return
    state.raid_message = event.pattern_match.group(1)
    await event.reply(f"✅ Raid message updated to: {state.raid_message[:60]}")

@client.on(events.NewMessage(pattern=r'^\.setlimit (\d+)'))
async def cmd_setlimit(event):
    if not is_admin(event.sender_id):
        return
    state.raid_limit = int(event.pattern_match.group(1))
    await event.reply(f"✅ Raid limit set to: {state.raid_limit}")

@client.on(events.NewMessage(pattern=r'^\.ping$'))
async def cmd_ping(event):
    if not is_admin(event.sender_id):
        return
    start = time.time()
    m = await event.reply("🏓 Pinging...")
    end = time.time()
    ping_ms = round((end - start) * 1000, 2)
    await m.edit(f"🏓 Pong! {ping_ms}ms ⚡")

@client.on(events.NewMessage(pattern=r'^\.uptime$'))
async def cmd_uptime(event):
    if not is_admin(event.sender_id):
        return
    await event.reply(f"⏱️ Uptime: {format_uptime()}")

@client.on(events.NewMessage(pattern=r'^\.stats$'))
async def cmd_stats(event):
    if not is_admin(event.sender_id):
        return
    me = await client.get_me()
    await event.reply(
        f"📊 BOT STATISTICS\n"
        f"└ User: {me.first_name} ({me.id})\n"
        f"└ DC: {me.dc_id}\n"
        f"└ Uptime: {format_uptime()}\n"
        f"└ Admins: {len(state.admins)}\n"
        f"└ Raid: {'🟢 ON' if state.raid_active else '🔴 OFF'}\n"
        f"└ Mode: {state.raid_mode}\n"
        f"└ Raid Delay: {state.raid_delay}s\n"
        f"└ Msgs Sent: {state.raid_count}\n"
        f"└ Limit: {state.raid_limit}\n"
        f"└ Flood Active: {state.flood_active}"
    )

@client.on(events.NewMessage(pattern=r'^\.broadcast (.+)'))
async def cmd_broadcast(event):
    if not is_admin(event.sender_id):
        return
    message = event.pattern_match.group(1)
    sent = 0
    failed = 0
    
    m = await event.reply("📡 Broadcasting... please wait")
    
    async for dialog in client.iter_dialogs():
        if isinstance(dialog.entity, (Channel, Chat)) and dialog.entity.username:
            try:
                if hasattr(dialog.entity, 'title'):
                    await client.send_message(dialog.entity.id, message)
                    sent += 1
                    await asyncio.sleep(2)  # Flood wait bachao
            except:
                failed += 1
    
    await m.edit(f"📡 Broadcast complete\n└ Sent: {sent} groups\n└ Failed: {failed} groups")

@client.on(events.NewMessage(pattern=r'^\.join (.+)'))
async def cmd_join(event):
    if not is_admin(event.sender_id):
        return
    link = event.pattern_match.group(1)
    try:
        await client.join_chat(link)
        await event.reply(f"✅ Joined: {link}")
    except Exception as e:
        await event.reply(f"❌ Join failed: {e}")

@client.on(events.NewMessage(pattern=r'^\.leave$'))
async def cmd_leave(event):
    if not is_admin(event.sender_id):
        return
    chat = await event.get_chat()
    try:
        await event.reply("👋 Leaving this group...")
        await client.delete_dialog(chat.id)
    except Exception as e:
        await event.reply(f"❌ Leave failed: {e}")

@client.on(events.NewMessage(pattern=r'^\.admins$'))
async def cmd_admins(event):
    if not is_admin(event.sender_id):
        return
    lines = [f"👑 Admin ID: {aid}" for aid in state.admins]
    await event.reply("📋 ADMIN LIST\n" + "\n".join(lines))

@client.on(events.NewMessage(pattern=r'^\.addadmin (\d+)'))
async def cmd_addadmin(event):
    if not is_admin(event.sender_id):
        return
    uid = int(event.pattern_match.group(1))
    state.admins.add(uid)
    await event.reply(f"✅ Added admin: {uid}")

@client.on(events.NewMessage(pattern=r'^\.deladmin (\d+)'))
async def cmd_deladmin(event):
    if not is_admin(event.sender_id):
        return
    uid = int(event.pattern_match.group(1))
    state.admins.discard(uid)
    await event.reply(f"✅ Removed admin: {uid}")

@client.on(events.NewMessage(pattern=r'^\.restart$'))
async def cmd_restart(event):
    if not is_admin(event.sender_id):
        return
    await event.reply("🔄 Restarting...")
    os.execl(sys.executable, sys.executable, *sys.argv)

# ─── ReplyRaid Handler ───

@client.on(events.NewMessage)
async def replyraid_handler(event):
    if not state.raid_active or state.raid_mode != "replyraid":
        return
    if event.sender_id in state.admins:
        return
    if not event.is_group:
        return
    if event.text and event.text.startswith('.'):
        return
    
    try:
        await asyncio.sleep(state.raid_delay)

reply_msg = state.raid_message
        
        # Variable replacement
        reply_msg = reply_msg.replace("{name}", event.sender.first_name or "User")
        reply_msg = reply_msg.replace("{msg}", event.text[:50] if event.text else "")
        
        await event.reply(reply_msg)
    except:
        pass

# ─── DM Raid Engine ───

async def dmraid_engine():
    """Background DM raiding"""
    while True:
        try:
            if state.raid_active and state.raid_mode == "dmraid":
                for admin_id in list(state.admins):
                    try:
                        await safe_send(admin_id, state.raid_message)
                        await asyncio.sleep(state.raid_delay)
                    except:
                        pass
            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            break
        except:
            await asyncio.sleep(5)

# ─── Main ───

async def main():
    await client.start()
    me = await client.get_me()
    
    print(f"""
╔══════════════════════════════════╗
║     🔥 ADVANCED RAID BOT 🔥      ║
║──────────────────────────────────║
║ User: {str(me.first_name):>25} ║
║ ID:   {str(me.id):>25} ║
║ DC:   {str(me.dc_id):>25} ║
║ Admins: {len(state.admins):>21} ║
╚══════════════════════════════════╝
    """)
    
    await client.send_message(
        list(state.admins)[0],
        f"🔥 Bot Started!\n"
        f"└ User: {me.first_name}\n"
        f"└ ID: {me.id}\n"
        f"└ Use .help for commands"
    )
    
    # Start background tasks
    raid_task = asyncio.create_task(raid_engine())
    dmraid_task = asyncio.create_task(dmraid_engine())
    
    try:
        await client.run_until_disconnected()
    finally:
        raid_task.cancel()
        dmraid_task.cancel()

if name == "main":
    asyncio.run(main())
