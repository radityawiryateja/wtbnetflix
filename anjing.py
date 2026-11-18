import asyncio
import os
import re
import random
import time
import telethon.utils
from dotenv import load_dotenv
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.extensions import html
from telethon.errors.rpcerrorlist import FloodWaitError
from telethon.tl.types import (
    UpdateMessageReactions,
    ReactionEmoji,
    ReactionCustomEmoji,
    MessageMediaWebPage,  
)
from telethon.tl.functions.messages import SendReactionRequest
from supabase import create_client, Client

# ==========================================
# 1. INIT & LOAD ENV
# ==========================================
load_dotenv(".env.komen")

try:
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID"))
    ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", LOG_GROUP_ID))

    # Konfigurasi Topic ID (Jika 0 atau kosong, bot akan kirim ke grup utama tanpa thread)
    LOG_TOPIC_ID = int(os.getenv("LOG_TOPIC_ID", 0)) or None
    ADMIN_TOPIC_ID = int(os.getenv("ADMIN_TOPIC_ID", 0)) or None

    # Konfigurasi Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    SESSIONS = [
        os.getenv("UBOT_SESSION_1"),
        os.getenv("UBOT_SESSION_2"),
        os.getenv("UBOT_SESSION_3"),
        os.getenv("UBOT_SESSION_4")
    ]
    SESSIONS = [s for s in SESSIONS if s]

except Exception as e:
    print(f"[❌ FATAL ERROR] Cek lagi file .env kamu: {e}")
    exit(1)

if not SESSIONS:
    print("[❌ FATAL ERROR] Tidak ada String Session yang ditemukan di .env!")
    exit(1)

CLIENT_PARAMS = {"use_ipv6": False, "timeout": 30, "connection_retries": 10}

# Client: List Semua Userbot
ubots = [TelegramClient(StringSession(s), API_ID, API_HASH, **CLIENT_PARAMS) for s in SESSIONS]
listener = ubots[0]
bot = TelegramClient('bot_session', API_ID, API_HASH, **CLIENT_PARAMS)

MESSAGE_CACHE = {}
bot_me = None
PM_MAP = {}
COMMENT_LOG_MAP = {}
SKIP_LOG_MAP = {}  

# 🔥 GLOBAL COUNTER UNTUK ROTASI ADIL 🔥
CURRENT_UBOT_INDEX = 0

# ==========================================
# 2. FITUR CACHE ON/OFF AUTO KOMEN (SUPABASE)
# ==========================================
AUTO_KOMEN_CACHE = {
    "status": True,
    "last_updated": 0
}
CACHE_TTL = 60  # Cache bertahan 60 detik agar tidak spam request ke Supabase

def is_auto_komen_active():
    now = time.time()
    if now - AUTO_KOMEN_CACHE["last_updated"] > CACHE_TTL:
        try:
            response = supabase.table("assistant").select("is_active").eq("id", 1).execute()
            if response.data:
                AUTO_KOMEN_CACHE["status"] = response.data[0]["is_active"]
            AUTO_KOMEN_CACHE["last_updated"] = now
        except Exception as e:
            print(f"[Supabase Error] Gagal fetch data: {e}")
    return AUTO_KOMEN_CACHE["status"]

# ==========================================
# 3. KONFIGURASI FILTER & KEYWORD
# ==========================================
TARGET_BASES_WITH_SIGN = [-1001525948158, -1001611324665]
TARGET_BASES_NO_SIGN = [-1001274048263, -1004418766510]
ALL_TARGET_BASES = TARGET_BASES_WITH_SIGN + TARGET_BASES_NO_SIGN

MAX_LENGTH = 200
ADMIN_SIGNS = ["basewib", "wtb"]
ANTI_ADS_WORDS = ["#pp", "#paidpromote", "paid promote", "iklan", "jastip"]

NEGATIVE_PREFIXES = [
    "selain", "slain", "selaen", "slin", "selainnya", "kecuali", "kcuali", "kuali", "kecual", "jasa save", "jasa export", "as buyer", "curhat", "wts", "sell",
    "exclude", "except", "tanpa", "tpa", "tanp", "t.u btn", "t.u noktel", "t.u nokos", "tu nokwa", "jasa ekspor", "template", "nokos ba", "noktel ba", "iphone 18",
    "bukan", "bkn", "bukn", "bukann", "no", "not", "nokos id", "t.u nokwa", "no wd", "report", "jasa edit", "ekspor", "export", "edit canva", "edit capcut", "gajadi",
    "jangan", "jgn", "jngn", "jgnn", "jangn", "jngan", "skip", "nfs", "idc", "hd wink", "uhd wink", "uhd ai wink", "jasdit", "nokos rp", "noktel rp", "ip 18",
    "ga usah", "gak usah", "ngga usah", "nggak usah", "engga usah", "g usah", "paspres", "pasang preset", "preset", "simpan", "canva head", "jasa capcut", "gamau",
    "ga perlu", "gak perlu", "ngga perlu", "wtbs", "wtb service", "wtb services", "ajarin", "tutor", "tutor", "save", "simpen", "jangan custom", "gamau custom",
    "udah ada", "sudah ada", "udh ada", "uda ada", "gram", "ton", "jasa hd", "uhd ai", "uhd", "tu noktel", "bekas", "tut", "tutorial", "jasa cari", "cariin",
    "udah punya", "sudah punya", "udh punya", "uda punya", "punya sendiri", "jasa wink", "tu", "tu btn", "first hand", "fh", "firsthand", "jasa chatgpt", "prank",
    "udah langganan", "sudah langganan", "udh berlangganan", "ready only", "as b", "noktel id", "ress", "reseller", "tamdal", "manips avrep", "jasa gpt", "gmail",
    "daripada", "lebih milih", "alternatif", "alternative", "opsi lain", "pilihan lain", "nokos limper", "noktel limper", "cv stars", "convert stars", "jasa canva",
    "jasa yt", "jasa pay", "jaspay", "canva admin", "penipu", "pilihin foto", "class", "maker", "limbus/limper", "limbus", "edit vidio", "nf", "usn", "username",
    "tapi boong", "tapi bohong", "eits", "ga mau", "ga jadi", "gak mau", "gak jadi", "gk mau", "gk jadi", "kreator", "t.u nokprem", "t.u prem", "tu nokprem",
    "tu prem", "t.u ch", "t.u channel", "tu ch", "tu channel", "hd in", "g jd", "gjd", "ga jd", "gk jd", "gk jdi", "ga jdi", "prankk", "prankk", "prankkk",
    "boong", "bohong", "pi boong", "jasa", "kerjain", "tugas", "jj", "jedag jedug", "jedag-jedug", "tu", "t.u", "ss", "screenshot", "screen shoot", "screenshoot",
    "ngerjain", "kelas", "edit", "editin", "subs", "subscriber", "upsubs", "jasa tuker", "tuker uang", "jasa uang", "tuker nokos", "nokos", "otp", "nomor kosong",
    "email", "gmail", "tarot", "gpt", "chatgpt", "eh", "ah", "bikinin", "bot", "hapus", "samain", "skintone", "pilihin", "mau?", "mau ?", "ptpt", "patungan", "ga",
    "giveaway", "ubot", "nomor", "nokos"
]

default_custom = "https://t.me/c/3923455524/39"
default_seller = "https://t.me/c/3923455524/40"
default_link = "https://t.me/c/3923455524/44"

# ── RULES STANDAR (PEMBELI) ──
KEYWORD_RULES = {
    "teleprem": "https://t.me/c/3923455524/45",
    "telegram premium": "https://t.me/c/3923455524/45",
    "tg premium": "https://t.me/c/3923455524/45",
    "tele premium": "https://t.me/c/3923455524/45",
    "tele prem": "https://t.me/c/3923455524/45",
    "tgprem": "https://t.me/c/3923455524/45",
    "netflix": default_link,
    "disney": default_link,
    "disney+": default_link,
    "amazon prime": default_link,
    "prime video": default_link,
    "youtube premium": default_link,
    "yt prem": default_link,
    "youtube": default_link,
    "yt": default_link,
    "wetv": default_link,
    "viu": default_link,
    "loklok": default_link,
    "vidio": default_link,
    "vidio platinum": default_link,
    "hbo max": default_link,
    "iqiyi": default_link,
    "bstation": default_link,
    "youku": default_link,
    
    "mb basic": default_custom,
    "mb script": default_custom,
    "mb deco": default_custom,
    "moodboard basic": default_custom,
    "moodboard script": default_custom,
    "moodboard deco": default_custom,
    "loveboard": default_custom,
    "moodboard design": default_custom,
    "moodboard": default_custom,
    "storyboard": default_custom,
    "custom wording": default_custom,
    "wording bundle": default_custom,
    "wording": default_custom,
    "wording package": default_custom,
    "custom wd ba": default_custom,
    "wd ba": default_custom,
    "kissed by": default_custom,
    "manips": default_custom,
    "scribble": default_custom,

    "canva": default_link,
    "alight motion": default_link,
    "am": default_link,
    "capcut": default_link,
    "meitu": default_link,
    "picsart": default_link,

    "remini": default_link,
    "grammarly": default_link,
    "quilbot": default_link,
    "quil bot": default_link,
    "scribd": default_link,
    "duolingo": default_link,

    "apple music": default_link,
    "appmus": default_link,
    "spotify": default_link,
    "spoti": default_link,
}

# ── RULES KHUSUS SELLER (AS SELLER / AS S) ──
SELLER_KEYWORD_RULES = {
    "teleprem": "https://t.me/c/3923455524/45",
    "telegram premium": "https://t.me/c/3923455524/45",
    "tg premium": "https://t.me/c/3923455524/45",
    "tele premium": "https://t.me/c/3923455524/45",
    "tele prem": "https://t.me/c/3923455524/45",
    "tgprem": "https://t.me/c/3923455524/45",
    "netflix": default_link,
    "disney": default_link,
    "disney+": default_link,
    "amazon prime": default_link,
    "prime video": default_link,
    "youtube premium": default_link,
    "yt prem": default_link,
    "youtube": default_link,
    "yt": default_link,
    "wetv": default_link,
    "viu": default_link,
    "loklok": default_link,
    "vidio": default_link,
    "vidio platinum": default_link,
    "hbo max": default_link,
    "iqiyi": default_link,
    "bstation": default_link,
    "youku": default_link,
    
    "mb basic": default_seller,
    "mb script": default_seller,
    "mb deco": default_seller,
    "moodboard basic": default_seller,
    "moodboard script": default_seller,
    "moodboard deco": default_seller,
    "loveboard": default_seller,
    "moodboard design": default_seller,
    "moodboard": default_seller,
    "storyboard": default_seller,
    "custom wording": default_seller,
    "wording bundle": default_seller,
    "wording": default_seller,
    "wording package": default_seller,
    "custom wd ba": default_seller,
    "wd ba": default_seller,
    "kissed by": default_seller,
    "manips": default_seller,
    "scribble": default_seller,

    "canva": default_link,
    "alight motion": default_link,
    "am": default_link,
    "capcut": default_link,
    "meitu": default_link,
    "picsart": default_link,

    "remini": default_link,
    "grammarly": default_link,
    "quilbot": default_link,
    "quil bot": default_link,
    "scribd": default_link,
    "duolingo": default_link,

    "apple music": default_link,
    "appmus": default_link,
    "spotify": default_link,
    "spoti": default_link,
}

# ==========================================
# 3a. KONFIGURASI USERNAME MANUAL PER USERBOT (BARU)
# ==========================================
# Diisi MANUAL (bukan auto-fetch get_me() lagi) biar presisi & gak ketuker.
#
# - "username" -> nilai buat placeholder {username} di wording
# - "order"    -> nilai buat placeholder {bot} di wording (misal kontak/tag
#                 khusus order, bisa sama atau beda dengan "username")
#
# Isi TANPA prefix "@" atau "@." -- prefix-nya otomatis ditentukan oleh
# format_tag() di bawah, tergantung base-nya pakai sign atau nggak:
#   - Base WITH SIGN (contoh: @basewib, @basewtb) -> jadi "@username"
#   - Base NO SIGN   (contoh: @moneyfess)          -> jadi "@.username"
#
# Index list = index urutan SESSION di .env (UBOT_SESSION_1 -> index 0, dst).
UBOT_USERNAME_CONFIG = [
    {"username": "hughtons", "order": "decavbot", "apolise": "apolisebot"},       
    {"username": "jakesiim", "order": "decavbot", "apolise": "apolisebot"},
    {"username": "hughtons", "order": "decavbot", "apolise": "apolisebot"},
    {"username": "userbot4", "order": "userbot4_order"},    # Userbot 4
]

def format_tag(raw_username, needs_sign):
   
    if not raw_username:
        return ""
    raw_username = raw_username.lstrip('@').lstrip('.')
    return f"@{raw_username}" if needs_sign else f"@.{raw_username}"

# ==========================================
# 3b. PRECOMPILED REGEX (biar nggak compile ulang tiap pesan masuk)
# ==========================================
def _build_pattern(word):
    return re.compile(
        r'(?<!\w)' + re.escape(word).replace(r'\ ', r'\W+(?:\w+\W+){0,3}') + r'(?!\w)',
        re.IGNORECASE
    )

COMPILED_KEYWORD_RULES = {kw: (_build_pattern(kw), link) for kw, link in KEYWORD_RULES.items()}
COMPILED_SELLER_KEYWORD_RULES = {kw: (_build_pattern(kw), link) for kw, link in SELLER_KEYWORD_RULES.items()}
COMPILED_NEGATIVE_PREFIXES = [(neg, _build_pattern(neg)) for neg in NEGATIVE_PREFIXES]

# ==========================================
# 4. HELPER FUNCTIONS
# ==========================================
def parse_link(url):
    match = re.match(r'https?://t\.me/(c/)?([^/]+)/(\d+)', url)
    if match:
        is_private = match.group(1)
        chat = match.group(2)
        msg_id = int(match.group(3))
        chat_id = int(f"-100{chat}") if is_private else chat
        return chat_id, msg_id
    return None, None

async def get_template_message(link):
    chat_id, msg_id = parse_link(link)
    if not chat_id: return None
    cache_key = f"{chat_id}_{msg_id}"
    if cache_key in MESSAGE_CACHE: return MESSAGE_CACHE[cache_key]

    source_msg = await listener.get_messages(chat_id, ids=msg_id)
    if source_msg: MESSAGE_CACHE[cache_key] = source_msg
    return source_msg

async def get_manual_tag(current_sender, idx, needs_sign, kind="username"):
  
    cfg = UBOT_USERNAME_CONFIG[idx] if idx < len(UBOT_USERNAME_CONFIG) else {}
    raw = cfg.get(kind)

    if not raw:
        if not hasattr(current_sender, 'bot_username_cache'):
            me = await current_sender.get_me()
            current_sender.bot_username_cache = me.username or str(me.id)
        raw = current_sender.bot_username_cache

    return format_tag(raw, needs_sign)

EMOJI_PATTERN = re.compile(
    "(?:"
    "[\U0001F1E6-\U0001F1FF"   
    "\U0001F300-\U0001FAFF"   
    "\U00002600-\U000027BF"    
    "\U00002B00-\U00002BFF"    
    "\U0001F900-\U0001F9FF"    
    "]"
    "[\U0000FE0F\U0001F3FB-\U0001F3FF\U0000200D\U000020E3]*"  
    ")+"
)


EXCLUDED_EMOJIS = {
    "🚀",   
    "🛍",   
    "💰",   
}

def _strip_variation(emoji_str):
    
    return emoji_str.replace("\uFE0F", "").replace("\u200D", "")

def extract_emojis(text):
   
    found = EMOJI_PATTERN.findall(text)
    return [e for e in found if _strip_variation(e) not in EXCLUDED_EMOJIS]

async def _attempt_delete(u_client, chat_id, msg_id):
 
    try:
        result = await u_client.delete_messages(chat_id, msg_id)
        affected = 0
        if result:
            for r in result:
                affected += getattr(r, 'pts_count', 0) or 0
        return affected > 0, None
    except Exception as e:
        return False, e

async def _mark_deleted(event, ubot_num):
    
    msg = await event.get_message()
    original_text = msg.raw_text or ""
    updated_text = original_text + f"\n\n🗑 **STATUS: SUDAH DIHAPUS** (oleh Userbot {ubot_num})"
    await event.edit(updated_text, buttons=None)

async def _auto_react_or_append(client, chat_id, msg_id, emoji, base_text=None, parse_mode='html'):

    try:
        await asyncio.sleep(random.uniform(0.4, 0.7))
        await client(SendReactionRequest(
            peer=chat_id,
            msg_id=msg_id,
            reaction=[ReactionEmoji(emoticon=emoji)]
        ))
    except Exception as e:
        print(f"[-] Emoji '{emoji}' gak bisa dipakai react di chat ini, coba fallback teks. ({e})")
        if base_text is None:
            return
        try:
            await client.edit_message(
                chat_id,
                msg_id,
                f"{base_text} {emoji}",
                parse_mode=parse_mode
            )
        except Exception as edit_err:
            # Kalau editnya juga gagal (misal komentar udah dihapus admin
            # duluan), ya sudah diabaikan aja, gak ada cara lain.
            print(f"[-] Gagal juga nambahin emoji '{emoji}' sebagai teks: {edit_err}")

# ==========================================
# 5. EVENT HANDLERS KELOLA PRIVATE MESSAGE (PM)
# ==========================================
def setup_handlers(u_client, u_idx):
    @u_client.on(events.NewMessage(func=lambda e: e.is_private and not e.out))
    async def pm_handler(event):
        if bot_me and event.sender_id == bot_me.id:
            return

        try:
            sender = await event.get_sender()
            sender_name = getattr(sender, 'first_name', 'User') or 'User'
            original_text = event.message.text or ""

            info_header = (
                f"📩 **PM (Ubot {u_idx+1})**\n"
                f"👤 [{sender_name}](tg://user?id={event.sender_id}) | `{event.sender_id}`\n"
                f"💬 "
            )

            forwarded_msg = None

            has_real_media = bool(event.message.media) and not isinstance(event.message.media, MessageMediaWebPage)

            if has_real_media:
                file_path = await u_client.download_media(event.message)

                if len(info_header + original_text) <= 1024:
                    combined_text = info_header + f"**Pesan:**\n{original_text}" if original_text else info_header + "*(Mengirim Media)*"
                    forwarded_msg = await bot.send_file(
                        ADMIN_GROUP_ID,
                        file_path,
                        caption=combined_text,
                        reply_to=ADMIN_TOPIC_ID
                    )
                else:
                    msg_media = await bot.send_file(
                        ADMIN_GROUP_ID,
                        file_path,
                        caption=info_header + "\n*(Media)*",
                        reply_to=ADMIN_TOPIC_ID
                    )
                    forwarded_msg = await bot.send_message(
                        ADMIN_GROUP_ID,
                        f"**Pesan Panjang dari User:**\n{original_text}",
                        reply_to=msg_media.id
                    )
                    PM_MAP[msg_media.id] = {"user_id": event.sender_id, "user_msg_id": event.message.id, "ubot_idx": u_idx}

                if os.path.exists(file_path):
                    os.remove(file_path)

            # JIKA PESAN TEKS BIASA (TERMASUK PESAN YANG CUMA BERISI LINK)
            else:
                combined_text = info_header + f"**Pesan:**\n{original_text}"
                forwarded_msg = await bot.send_message(
                    ADMIN_GROUP_ID,
                    combined_text,
                    reply_to=ADMIN_TOPIC_ID,
                    link_preview=True
                )

            if len(PM_MAP) > 5000:
                PM_MAP.clear()

            if forwarded_msg:
                PM_MAP[forwarded_msg.id] = {
                    "user_id": event.sender_id,
                    "user_msg_id": event.message.id,
                    "ubot_idx": u_idx
                }

        except Exception as e:
            print(f"[Error PM] Gagal meneruskan PM: {e}")

    @u_client.on(events.Raw(UpdateMessageReactions))
    async def reaction_handler(event):
        try:
            peer_id = telethon.utils.get_peer_id(event.peer)
            if abs(peer_id) != abs(ADMIN_GROUP_ID):
                return

            msg_id = event.msg_id
            if msg_id not in PM_MAP:
                return

            mapping = PM_MAP[msg_id]
            if mapping["ubot_idx"] != u_idx:
                return

            emojis = []
            for r in event.reactions.results:
                if isinstance(r.reaction, ReactionEmoji):
                    emojis.append(r.reaction.emoticon)
                elif isinstance(r.reaction, ReactionCustomEmoji):
                    emojis.append(ReactionCustomEmoji(document_id=r.reaction.document_id))

            await u_client(SendReactionRequest(
                peer=mapping["user_id"],
                msg_id=mapping["user_msg_id"],
                reaction=emojis
            ))
        except Exception as e:
            pass

for i, ubot in enumerate(ubots):
    setup_handlers(ubot, i)

# ==========================================
# 6. BOT NOTIFIKASI MEMBALAS PM & COMMAND LAIN
# ==========================================
@bot.on(events.NewMessage(chats=ADMIN_GROUP_ID))
async def admin_reply_pm(event):
    if not event.is_reply: return

    reply_to = await event.get_reply_message()
    if reply_to and reply_to.id in PM_MAP:
        mapping = PM_MAP[reply_to.id]
        target_ubot = ubots[mapping["ubot_idx"]]
        file_path = None
        loading_msg = None
        try:
            
            has_real_media = bool(event.message.media) and not isinstance(event.message.media, MessageMediaWebPage)

            if has_real_media:
                loading_msg = await event.reply("⏳ **Mengunduh & mengirim media...**")
                file_path = await bot.download_media(event.message)

                is_file = bool(event.message.document) and not event.message.video and not event.message.audio and not event.message.voice

                if file_path:
                 
                    await target_ubot.send_file(
                        mapping["user_id"],
                        file_path,
                        caption=event.message.text or "",
                        reply_to=mapping["user_msg_id"],
                        force_document=is_file
                    )
                    await loading_msg.delete()
                else:
                    await loading_msg.edit("❌ **Gagal mengunduh media dari pesan ini.**")
            else:
                # Teks biasa, TERMASUK pesan yang isinya cuma link.
                await target_ubot.send_message(
                    mapping["user_id"],
                    event.message.text,
                    reply_to=mapping["user_msg_id"],
                    link_preview=True
                )

            sukses_msg = await event.reply("✅ **Terkirim.**")
            await asyncio.sleep(3)
            await sukses_msg.delete()

        except Exception as e:
            await event.reply(f"❌ **Gagal membalas ke User:** {e}")
        finally:
            # Cleanup file selalu dijalankan sekali, tidak peduli sukses/gagal
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                
@bot.on(events.NewMessage(chats=LOG_GROUP_ID))
async def log_notif_reply_handler(event):
    if not event.is_reply:
        return
    if event.message.text and event.message.text.startswith('/'):
        return

    reply_to = await event.get_reply_message()
    if not reply_to:
        return

    text_to_send = event.message.text or ""

    # ── CASE A: reply ke notif "BERHASIL KOMEN" ──
    # WAJIB pakai userbot yg sama, reply ke pesan komentar yg sama (bukan post asli)
    if reply_to.id in COMMENT_LOG_MAP:
        mapping = COMMENT_LOG_MAP[reply_to.id]
        ubot_client = ubots[mapping["ubot_idx"]]
        try:
            await ubot_client.send_message(
                mapping["target_chat_id"],
                text_to_send,
                reply_to=mapping["target_msg_id"]
            )
            confirm = await event.reply(f"✅ **Terkirim via Userbot {mapping['ubot_idx']+1} (thread sama).**")
        except FloodWaitError as e:
            confirm = await event.reply(f"⏳ **Userbot {mapping['ubot_idx']+1} kena flood wait {e.seconds}s.** Coba lagi nanti (harus pakai ubot ini karena thread-nya).")
        except Exception as e:
            confirm = await event.reply(f"❌ **Gagal kirim reply:** {e}")

        await asyncio.sleep(3)
        try:
            await confirm.delete()
        except Exception:
            pass
        return

    # ── CASE B: reply ke notif "SKIP MENFESS" ──
    # Bebas, pakai ubot manapun yg free (fallback rotasi kalau ada yg flood)
    if reply_to.id in SKIP_LOG_MAP:
        mapping = SKIP_LOG_MAP[reply_to.id]
        sent_msg = None
        used_idx = None

        for i in range(len(ubots)):
            idx = (CURRENT_UBOT_INDEX + i) % len(ubots)
            try:
                sent_msg = await ubots[idx].send_message(
                    mapping["base_chat_id"],
                    text_to_send,
                    comment_to=mapping["post_msg_id"]
                )
                used_idx = idx
                break
            except FloodWaitError as e:
                print(f"⏳ [FLOOD WAIT] Userbot {idx+1} limit {e.seconds}s saat manual comment. Coba bot sebelahnya...")
                continue
            except Exception as e:
                print(f"[❌ ERROR MANUAL COMMENT] Userbot {idx+1}: {e}")
                continue

        if sent_msg:
            confirm = await event.reply(f"✅ **Terkirim via Userbot {used_idx+1}.**")
        else:
            confirm = await event.reply("❌ **Semua userbot gagal / limit.**")

        await asyncio.sleep(3)
        try:
            await confirm.delete()
        except Exception:
            pass
        return

@listener.on(events.NewMessage(pattern=r'^/grupid$'))
async def check_group_id(event):
    await event.reply(f"📌 **ID Chat/Grup ini:** `{event.chat_id}`\n🔖 **ID Topic/Thread (jika ada):** `{event.message.reply_to_msg_id}`")

@bot.on(events.CallbackQuery(pattern=b'^del_'))
async def delete_comment_callback(event):
    try:
        data = event.data.decode('utf-8').split('_')
        if len(data) == 4:
            ubot_idx = int(data[1])
            chat_id = int(data[2])
            msg_id = int(data[3])

            ok, err = await _attempt_delete(ubots[ubot_idx], chat_id, msg_id)
            if ok:
                await _mark_deleted(event, ubot_idx + 1)
            elif err:
                await event.answer(f"❌ Gagal Hapus: {err}", alert=True)
            else:
                # Tidak error, tapi pts_count = 0 -> memang tidak ada yang terhapus
                await event.answer(
                    "⚠️ Tidak ada yang terhapus (pesan mungkin sudah hilang / chat_id salah). "
                    "Cek manual lewat link komentar di notif ini.",
                    alert=True
                )
        else:
            # Format lama (fallback), tetap divalidasi pts_count-nya
            chat_id = int(data[1])
            msg_id = int(data[2])
            done = False
            for idx, u in enumerate(ubots):
                ok, err = await _attempt_delete(u, chat_id, msg_id)
                if ok:
                    await _mark_deleted(event, idx + 1)
                    done = True
                    break
            if not done:
                await event.answer("❌ Gagal! Pesan mungkin sudah dihapus atau bukan milik userbot manapun.", alert=True)

    except Exception as e:
        await event.answer(f"Error bot: {e}", alert=True)

# COMMAND MANUAL ON/OFF VIA TELEGRAM
@bot.on(events.NewMessage(chats=ADMIN_GROUP_ID, pattern=r'^/(on|off)$'))
async def toggle_autokomen(event):
    new_status = True if event.pattern_match.group(1).lower() == 'on' else False
    try:
        supabase.table("assistant").update({"is_active": new_status}).eq("id", 1).execute()

        AUTO_KOMEN_CACHE["status"] = new_status
        AUTO_KOMEN_CACHE["last_updated"] = time.time()

        status_text = "🟢 NYALA (ON)" if new_status else "🔴 MATI (OFF)"
        await event.reply(f"✅ **Status Auto Komen berhasil diubah menjadi: {status_text}**")
    except Exception as e:
        await event.reply(f"❌ **Gagal update database:** {e}")

# ==========================================
# 7. AUTO-COMMENT MENFESS (ADIL BERGANTIAN)
# ==========================================
@listener.on(events.NewMessage(chats=ALL_TARGET_BASES, incoming=True))
async def auto_comment_handler(event):
    # CEK CACHE DATABASE DULU SEBELUM JALAN
    if not is_auto_komen_active():
        return

    global CURRENT_UBOT_INDEX

    text = event.message.message or ""

    if not text: return
    if len(text) > MAX_LENGTH: return

    if re.search(r'@[a-zA-Z0-9_]+', text):
        return

    chat = await event.get_chat()
    chat_username = f"@{chat.username.lower()}" if getattr(chat, 'username', None) else None

    if chat_username:
        post_link = f"https://t.me/{chat.username}/{event.message.id}"
    else:
        clean_chat_id = str(event.chat_id).replace("-100", "")
        post_link = f"https://t.me/c/{clean_chat_id}/{event.message.id}"

    needs_sign = (event.chat_id in TARGET_BASES_WITH_SIGN) or (chat_username in TARGET_BASES_WITH_SIGN)

    if needs_sign:
        author_sign = event.message.post_author or ""
        if not any(sign in author_sign.lower() for sign in ADMIN_SIGNS):
            return
    else:
        if any(ads in text.lower() for ads in ANTI_ADS_WORDS): return

    is_seller = re.search(r'\b(as s|as seller|seller only)\b', text, re.IGNORECASE)
    active_rules = COMPILED_SELLER_KEYWORD_RULES if is_seller else COMPILED_KEYWORD_RULES

    found_keywords = []

    for kw, (pattern, link) in active_rules.items():
        if pattern.search(text):
            found_keywords.append(kw)
            # HAPUS 'break' di sini agar bot mengecek semua keyword yang ada di pesan

    if not found_keywords:
        return

    # 🔥 LOGIKA BARU: Hindari jebakan (2 keyword atau lebih) 🔥
    if len(found_keywords) > 1:
        msg_notif = (
            f"⚠️ **SKIP MENFESS (JEBAKAN MULTIPLE KEYWORD)!**\n\n"
            f"📍 **Base:** `{event.chat_id}`\n"
            f"🔗 **Link Post:** {post_link}\n"
            f"🎯 **Terdeteksi {len(found_keywords)} Keyword:** `{', '.join(found_keywords)}`\n"
            f"🚫 **Alasan:** Menghindari menfess labil/jebakan (terdapat lebih dari 1 produk).\n\n"
            f"📄 **Isi Pesan:**\n__{text}__"
        )
        async def _send_jebakan_log():
            m = await bot.send_message(
                LOG_GROUP_ID,
                msg_notif,
                link_preview=False,
                reply_to=LOG_TOPIC_ID
            )
            # Opsional: Simpan ke SKIP_LOG_MAP agar admin bisa balas manual jika ternyata bukan jebakan
            SKIP_LOG_MAP[m.id] = {
                "base_chat_id": event.chat_id,
                "post_msg_id": event.message.id,
            }
            if len(SKIP_LOG_MAP) > 5000:
                SKIP_LOG_MAP.clear()

        asyncio.create_task(_send_jebakan_log())
        return  # Batalkan proses komen

    for neg, pattern_neg in COMPILED_NEGATIVE_PREFIXES:
        if pattern_neg.search(text):
            msg_notif = (
                f"⚠️ **SKIP MENFESS (MODE KETAT)!**\n\n"
                f"📍 **Base:** `{event.chat_id}`\n"
                f"🔗 **Link Post:** {post_link}\n"
                f"🎯 **Keyword:** `{', '.join(found_keywords)}`\n"
                f"🚫 **Trigger:** Terdeteksi kata `{neg}`\n\n"
                f"📄 **Isi Pesan:**\n__{text}__"
            )
            async def _send_skip_log():
                m = await bot.send_message(
                    LOG_GROUP_ID,
                    msg_notif,
                    link_preview=False,
                    reply_to=LOG_TOPIC_ID
                )
                # Simpan post aslinya. Kalau admin reply notif ini, kirim
                # komen manual ke post ini pakai UBOT BEBAS (fallback rotasi).
                SKIP_LOG_MAP[m.id] = {
                    "base_chat_id": event.chat_id,
                    "post_msg_id": event.message.id,
                }
                if len(SKIP_LOG_MAP) > 5000:
                    SKIP_LOG_MAP.clear()

            asyncio.create_task(_send_skip_log())
            return

    matched_kw = found_keywords[0]
    matched_link = active_rules[matched_kw][1]

    try:
        # Delay diperkecil (dulu 1.5-3s) dan dijalankan PARALEL bareng fetch
        # template, biar komentar terkirim lebih cepat / lebih responsif.
        source_msg, _ = await asyncio.gather(
            get_template_message(matched_link),
            asyncio.sleep(random.uniform(0.4, 0.7))
        )
        if not source_msg:
            return

        comment_msg = None
        bot_pengirim = 0

        start_idx = CURRENT_UBOT_INDEX
        CURRENT_UBOT_INDEX = (CURRENT_UBOT_INDEX + 1) % len(ubots)

        idx_to_try = start_idx
        for i in range(len(ubots)):
            idx_to_try = (start_idx + i) % len(ubots)
            current_sender = ubots[idx_to_try]

            try:
                # === GANTI TOTAL: dulu auto-detect via get_me(), sekarang
                # manual via UBOT_USERNAME_CONFIG (dengan fallback auto-detect
                # kalau config kosong). Ada 2 placeholder sekarang:
                #   {username} -> tag utama
                #   {bot}      -> tag kedua (misal buat "order")
                # Prefix @ / @. otomatis ditentukan dari needs_sign (base
                # with-sign vs no-sign), jadi gak perlu filter manual lagi
                # tiap kali pakai wording.
                formatted_username = await get_manual_tag(current_sender, idx_to_try, needs_sign, "username")
                formatted_order = await get_manual_tag(current_sender, idx_to_try, needs_sign, "order")
                formatted_apolise = await get_manual_tag(current_sender, idx_to_try, needs_sign, "apolise")

                template_text = html.unparse(source_msg.message, source_msg.entities)
                # .replace() aman walau placeholder-nya gak ada di template --
                # gak akan raise error, cuma gak ngapa-ngapain.
                modified_text = (
                    template_text
                    .replace("{username}", formatted_username)
                    .replace("{bot}", formatted_order)
                    .replace("{apolise}", formatted_apolise)
                )

                if source_msg.media:
                    comment_msg = await current_sender.send_message(
                        event.chat_id,
                        modified_text,
                        file=source_msg.media,
                        comment_to=event.message.id,
                        parse_mode='html',
                        link_preview=False
                    )
                else:
                    comment_msg = await current_sender.send_message(
                        event.chat_id,
                        modified_text,
                        comment_to=event.message.id,
                        parse_mode='html',
                        link_preview=False
                    )

                bot_pengirim = idx_to_try + 1

                emojis_found = extract_emojis(text)
                if len(emojis_found) == 1:
                    asyncio.create_task(_auto_react_or_append(
                        current_sender,
                        comment_msg.chat_id,
                        comment_msg.id,
                        emojis_found[0],
                        base_text=modified_text, 
                        parse_mode='html'
                    ))
                break

            except FloodWaitError as e:
                print(f"⏳ [FLOOD WAIT] Userbot {idx_to_try + 1} limit {e.seconds}s. Coba bot sebelahnya...")
                continue

            except Exception as send_err:
                print(f"[❌ ERROR PENGIRIMAN] Userbot {idx_to_try + 1} gagal: {send_err}")
                continue

        if not comment_msg:
            asyncio.create_task(bot.send_message(
                LOG_GROUP_ID,
                "❌ **SEMUA USERBOT LIMIT / GAGAL!** Komen dibatalkan.",
                reply_to=LOG_TOPIC_ID
            ))
            return

        # Link komentar (bukan link post) — biar admin bisa langsung cek
        # apakah komentarnya masih ada / masih bisa diklik atau sudah hilang.
        if chat_username:
            comment_link = f"https://t.me/{chat.username}/{event.message.id}?comment={comment_msg.id}"
        else:
            comment_link = f"https://t.me/c/{clean_chat_id}/{event.message.id}?comment={comment_msg.id}"

        btn_data = f"del_{idx_to_try}_{comment_msg.chat_id}_{comment_msg.id}".encode('utf-8')

        success_msg = (
            f"✅ **BERHASIL KOMEN!**\n"
            f"🤖 **Pengirim:** `Userbot {bot_pengirim}` (Rotasi)\n\n"
            f"📍 **Base:** `{event.chat_id}`\n"
            f"🔗 **Link Komentar:** {comment_link}\n"
            f"🔑 **Produk:** `{matched_kw}`\n\n"
            f"📄 **Pesan Asli:**\n__{text}__"
        )

        async def _send_success_log():
            m = await bot.send_message(
                LOG_GROUP_ID,
                success_msg,
                buttons=[Button.inline("🗑 Hapus Komen", data=btn_data)],
                link_preview=False,
                reply_to=LOG_TOPIC_ID
            )
            # Simpan siapa (ubot mana) & kemana (chat diskusi + msg id komentar)
            # supaya kalau admin reply notif ini, balasannya pasti nyambung
            # ke thread komen yg BENAR pakai akun ubot yg SAMA.
            COMMENT_LOG_MAP[m.id] = {
                "ubot_idx": idx_to_try,
                "target_chat_id": comment_msg.chat_id,
                "target_msg_id": comment_msg.id,
            }
            if len(COMMENT_LOG_MAP) > 5000:
                COMMENT_LOG_MAP.clear()

        asyncio.create_task(_send_success_log())

    except Exception as e:
        print(f"[❌ ERROR KESELURUHAN] {e}")

# ==========================================
# 8. RUNNER
# ==========================================
async def main():
    global bot_me
    print(f"⏳ Menghidupkan {len(ubots)} Userbot & Bot Notifikasi...\n")
    try:
        await bot.start(bot_token=BOT_TOKEN)
        bot_me = await bot.get_me()
        print("✅ Bot Notifikasi aktif.")

        for idx, u in enumerate(ubots, start=1):
            await u.start()
            print(f"✅ Userbot {idx} aktif.")

        print("\n🚀 SISTEM FULL AKTIF DENGAN SEMUA FITUR GABUNGAN!")
        print("1. Thread Routing Grup & Supabase Toggle ON")
        print("2. Deteksi otomatis mode As S / As Seller")
        print("3. Tag {username} & {bot} MANUAL via UBOT_USERNAME_CONFIG (fallback auto-detect kalau kosong)")
        print("4. Pesan link (URL) di PM & admin-reply sekarang diteruskan sebagai teks, bukan media -> gak gagal lagi")
        print("5. Auto-React 1-emoji Ubot ON (background, non-blocking, invalid reaction diabaikan)")
        print("6. Delete komentar sekarang diverifikasi (pts_count) & wording notif dipertahankan\n")

        tasks = [u.run_until_disconnected() for u in ubots] + [bot.run_until_disconnected()]
        await asyncio.gather(*tasks)

    except Exception as e:
        print(f"[❌ FATAL] Gagal nyala: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[🛑] Dihentikan user.")