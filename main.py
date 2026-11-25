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
from telethon.tl.functions.account import UpdateProfileRequest
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
        os.getenv("UBOT_SESSION_4"),
        os.getenv("UBOT_SESSION_5")
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
GROUP_REPLY_MAP = {}
ADDON_MSG_MAP = {}

# 🔥 GLOBAL COUNTER UNTUK ROTASI ADIL 🔥
CURRENT_UBOT_INDEX = 0
MUTED_UBOTS = set()
ALLOWED_COMSECT_GROUPS = set()

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
    "udah ada", "sudah ada", "udh ada", "uda ada", "gram", "ton", "jasa hd", "uhd ai", "uhd", "tu noktel", "bekas", "tut", "tutorial", "jasa cari", "hapus", "samain", "skintone", "cariin", "t.u", "tu", "tuker",
    "udah punya", "sudah punya", "udh punya", "uda punya", "punya sendiri", "jasa wink", "tu", "tu btn", "first hand", "fh", "firsthand", "jasa chatgpt", "prank",
    "udah langganan", "sudah langganan", "udh berlangganan", "ready only", "as b", "noktel id", "ress", "reseller", "tamdal", "manips avrep", "jasa gpt", "gmail",
    "daripada", "lebih milih", "alternatif", "alternative", "opsi lain", "pilihan lain", "nokos limper", "noktel limper", "cv stars", "convert stars", "jasa canva",
    "jasa yt", "jasa pay", "jaspay", "canva admin", "penipu", "pilihin foto", "class", "maker", "limbus/limper", "limbus", "edit vidio", "nf", "usn", "username",
    "tapi boong", "tapi bohong", "eits", "ga mau", "ga jadi", "gak mau", "gak jadi", "gk mau", "gk jadi", "kreator", "t.u nokprem", "t.u prem", "tu nokprem",
    "tu prem", "t.u ch", "t.u channel", "tu ch", "tu channel", "hd in", "g jd", "gjd", "ga jd", "gk jd", "gk jdi", "ga jdi", "prankk", "prankk", "prankkk",
    "boong", "bohong", "pi boong", "kerjain", "ngerjain", "tugas", "jj", "jedag jedug", "jedag-jedug", "subs", "subscriber", "jasa tuker", "tuker uang",
    "jasa uang", "tuker nokos", "email", "gmail", "sewa", "tarot", "eh", "ah", "bikinin", "bot", "mau?", "mau ?", "ngajarin", "ba", "seller wtb", "jasa like",
    "jasa", "ss", "nokwa", "nokos wa", "wa", "whatsapp", "capcut 1d", "berlevel", "level 1", "ns", "crack", "empass", "dump", "netpriv", "privat", "private",
    "base", "divisi", "war", "top", "coding", "web", "unsur", "b.o", "based on", "bo", "voucher", "rave", "hearo", "inc", "bud", "rp", "ubot", "nipu", "penipu",
    "joki", "tugas"
]

default_netflix = "https://t.me/c/3923455524/78"
default_canva = "https://t.me/c/3923455524/84"
default_capcut = "https://t.me/c/3923455524/85"
default_teleprem = "https://t.me/c/3923455524/82"

# ── RULES STANDAR (PEMBELI) ──
KEYWORD_RULES = {
    "netflix": default_netflix,
    "netfl1x": default_netflix,
    "netf1ix": default_netflix,
    "n3tflix": default_netflix,
    "netf": default_netflix,
    "canva": default_canva,
    "capcut": default_capcut,
    "teleprem": default_teleprem,
    "telepreem": default_teleprem,
    "teleeprem": default_teleprem,
    "telepremm": default_teleprem,
    "telepremmm": default_teleprem,
    "tgprem": default_teleprem,
    "telprem": default_teleprem,
    "tele prem": default_teleprem,
    "tg prem": default_teleprem,
    "tel3prem": default_teleprem,
    "prem tele": default_teleprem,
    "premtele": default_teleprem,
    "premtele": default_teleprem,
}


# ── RULES KHUSUS SELLER (AS SELLER / AS S) ──
SELLER_KEYWORD_RULES = {
    "netflix": default_netflix,
    "netfl1x": default_netflix,
    "netf1ix": default_netflix,
    "n3tflix": default_netflix,
    "netf": default_netflix,
    "canva": default_canva,
    "capcut": default_capcut,
    "teleprem": default_teleprem,
    "telepreem": default_teleprem,
    "teleeprem": default_teleprem,
    "telepremm": default_teleprem,
    "telepremmm": default_teleprem,
    "tgprem": default_teleprem,
    "telprem": default_teleprem,
    "tele prem": default_teleprem,
    "tg prem": default_teleprem,
    "tel3prem": default_teleprem,
    "prem tele": default_teleprem,
    "premtele": default_teleprem,
}


BASE_CUSTOM_LINKS = {
    -1001525948158: {  
        "teleprem": "https://t.me/c/3923455524/83",
        "telepreem": "https://t.me/c/3923455524/83",
        "teleeprem": "https://t.me/c/3923455524/83",
        "telepremm": "https://t.me/c/3923455524/83",
        "telepremmm": "https://t.me/c/3923455524/83",
        "tgprem": "https://t.me/c/3923455524/83",
        "telprem": "https://t.me/c/3923455524/83",
        "tele prem": "https://t.me/c/3923455524/83",
        "tg prem": "https://t.me/c/3923455524/83",
        "tel3prem": "https://t.me/c/3923455524/83",
        "prem tele": "https://t.me/c/3923455524/83",
        "premtele": "https://t.me/c/3923455524/83",
    }
}

ADDON_TEXT_WITH_SIGN = "Sini nder, fast process lagi on (bisa liat last seen @hughtons). Kalau ada kendala, fast fixing no cacicu."

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
    {"username": "hughtons", "order": "nettflixapp", "botdecav": "decavstore"},  # Userbot 1
    {"username": "hughtons", "order": "nettflixapp", "botdecav": "decavstore"},  # Userbot 2
    {"username": "hughtons", "order": "nettflixapp", "botdecav": "decavstore"},  # Userbot 3
    {"username": "hughtons", "order": "nettflixapp", "botdecav": "decavstore"},  # Userbot 4
    {"username": "hughtons", "order": "nettflixapp", "botdecav": "decavstore"},  # Userbot 5
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
        await asyncio.sleep(random.uniform(0.5, 0.7))
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
            
            # ====================================================
            # 🔥 TAMBAHAN FILTER ANTI-BOT PM DI SINI 🔥
            # ====================================================
            # 1. Cek apakah pengirim adalah Bot resmi Telegram
            if getattr(sender, 'bot', False):
                return  # Abaikan pesan
            
            # 2. Cek apakah username pengirim berakhiran 'bot' (case-insensitive)
            if sender and getattr(sender, 'username', None):
                if sender.username.lower().endswith('bot'):
                    return  # Abaikan pesan
            # ====================================================

            # 🔥 CEK APAKAH UBOT INI SEDANG DI-MUTE 🔥
            if u_idx in MUTED_UBOTS:
                return

            sender_name = getattr(sender, 'first_name', 'User') or 'User'
            original_text = event.message.text or ""
            
            # ====================================================
            # 🔥 FITUR GANTI NAMA (COMMAND /changename) 🔥
            # ====================================================
            if original_text.lower().startswith("/changename "):
                # WAJIB: Isi dengan ID Telegram akun utamamu agar buyer tidak bisa iseng ganti nama bot
                OWNER_IDS = [5760818847, 6085456747] 
                
                if event.sender_id in OWNER_IDS:
                    new_name = original_text.split(" ", 1)[1].strip()
                    try:
                        await u_client(UpdateProfileRequest(first_name=new_name))
                        await event.reply(f"✅ Nama Userbot {u_idx+1} berhasil diubah menjadi: **{new_name}**")
                    except Exception as e:
                        await event.reply(f"❌ Gagal mengubah nama: {e}")
                else:
                    # Abaikan atau balas jika yang mencoba bukan admin
                    await event.reply("❌ Anda tidak memiliki izin menggunakan command ini.")
                
                return  # Hentikan eksekusi di sini agar pesan command tidak di-forward ke Grup Admin
            # ====================================================

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

    @u_client.on(events.NewMessage(incoming=True))
    async def group_reply_handler(event):
        # Abaikan pesan PM atau pesan yang bukan balasan (reply)
        if event.is_private or not event.is_reply:
            return

        # 🔥 FILTER BARU: Hentikan jika reply terjadi di luar grup comsect yang dilacak
        # (ID grup akan otomatis ditambahkan ke set ALLOWED_COMSECT_GROUPS saat bot berhasil komen)
        if event.chat_id not in ALLOWED_COMSECT_GROUPS:
            return

        # 🔥 CEK APAKAH UBOT INI SEDANG DI-MUTE 🔥
        if u_idx in MUTED_UBOTS:
            return

        try:
            me = await u_client.get_me()
            reply_to_msg = await event.get_reply_message()
            
            # Cek apakah pesan tersebut sedang me-reply pesan milik ubot ini
            if reply_to_msg and reply_to_msg.sender_id == me.id:
                sender = await event.get_sender()
                sender_name = getattr(sender, 'first_name', 'User') or 'User'
                chat = await event.get_chat()
                chat_title = getattr(chat, 'title', 'Grup')
                
                text_msg = event.message.text or "*(Mengirim Media/Stiker)*"
                
                # Format notifikasi ke grup admin
                notif_text = (
                    f"🔔 **BALASAN DI GRUP (Ubot {u_idx+1})**\n"
                    f"👥 **Grup:** {chat_title}\n"
                    f"👤 **Dari:** {sender_name}\n"
                    f"💬 **Pesan:**\n__{text_msg}__\n\n"
                    f"👉 *Balas (reply) notifikasi ini untuk merespons kembali ke grup tersebut.*"
                )
                
                notif_msg = await bot.send_message(
                    ADMIN_GROUP_ID,
                    notif_text,
                    reply_to=ADMIN_TOPIC_ID
                )
                
                # Simpan data agar admin bisa membalasnya
                GROUP_REPLY_MAP[notif_msg.id] = {
                    "ubot_idx": u_idx,
                    "chat_id": event.chat_id,
                    "msg_id": event.message.id 
                }
                
                # Bersihkan map agar RAM tidak penuh
                if len(GROUP_REPLY_MAP) > 5000:
                    GROUP_REPLY_MAP.clear()
        except Exception as e:
            print(f"[Error Group Reply] {e}")
            
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
    if not reply_to: return

    mapping = None
    target_chat_id = None
    target_msg_id = None
    
    # Cek apakah ini membalas notif PM atau notif Grup
    if reply_to.id in PM_MAP:
        mapping = PM_MAP[reply_to.id]
        target_chat_id = mapping["user_id"]
        target_msg_id = mapping["user_msg_id"]
    elif reply_to.id in GROUP_REPLY_MAP:
        mapping = GROUP_REPLY_MAP[reply_to.id]
        target_chat_id = mapping["chat_id"]
        target_msg_id = mapping["msg_id"]

    if mapping:
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
                        target_chat_id,
                        file_path,
                        caption=event.message.text or "",
                        reply_to=target_msg_id,
                        force_document=is_file
                    )
                    await loading_msg.delete()
                else:
                    await loading_msg.edit("❌ **Gagal mengunduh media dari pesan ini.**")
            else:
                # Teks biasa
                await target_ubot.send_message(
                    target_chat_id,
                    event.message.text,
                    reply_to=target_msg_id,
                    link_preview=True
                )

            sukses_msg = await event.reply("✅ **Terkirim.**")
            await asyncio.sleep(3)
            await sukses_msg.delete()

        except Exception as e:
            await event.reply(f"❌ **Gagal membalas:** {e}")
        finally:
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

            # Hapus pesan komentar utamanya
            ok, err = await _attempt_delete(ubots[ubot_idx], chat_id, msg_id)
            
            # CEK DAN HAPUS PESAN ADD-ON JIKA ADA
            if msg_id in ADDON_MSG_MAP:
                addon_id = ADDON_MSG_MAP.pop(msg_id)
                await _attempt_delete(ubots[ubot_idx], chat_id, addon_id)
            
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
        
@bot.on(events.NewMessage(chats=ADMIN_GROUP_ID, pattern=r'^/(mute|unmute)\s+(\d+)$'))
async def toggle_mute_ubot(event):
    action = event.pattern_match.group(1).lower()
    ubot_num = int(event.pattern_match.group(2))
    ubot_idx = ubot_num - 1

    if ubot_idx < 0 or ubot_idx >= len(ubots):
        await event.reply(f"❌ **Userbot {ubot_num} tidak ditemukan!** (Saat ini hanya ada {len(ubots)} userbot berjalan)")
        return

    if action == "mute":
        MUTED_UBOTS.add(ubot_idx)
        await event.reply(f"🔇 **Userbot {ubot_num} di-MUTE.**\n(Notifikasi PM & Reply Grup tidak akan dikirim ke sini)")
    else:
        MUTED_UBOTS.discard(ubot_idx)
        await event.reply(f"🔊 **Userbot {ubot_num} di-UNMUTE.**\n(Notifikasi PM & Reply Grup kembali normal)")                   

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

    # 🔥 Cek apakah base ini punya link wording khusus 🔥
    base_overrides = BASE_CUSTOM_LINKS.get(event.chat_id, {})
    if matched_kw in base_overrides:
        matched_link = base_overrides[matched_kw]
    elif "_default" in base_overrides:
        matched_link = base_overrides["_default"]

    try:
        # Delay diperkecil (dulu 1.5-3s) dan dijalankan PARALEL bareng fetch
        # template, biar komentar terkirim lebih cepat / lebih responsif.
        source_msg, _ = await asyncio.gather(
            get_template_message(matched_link),
            asyncio.sleep(random.uniform(0.5, 0.7))
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
                formatted_botdecav = await get_manual_tag(current_sender, idx_to_try, needs_sign, "botdecav")

                template_text = html.unparse(source_msg.message, source_msg.entities)
                # .replace() aman walau placeholder-nya gak ada di template --
                # gak akan raise error, cuma gak ngapa-ngapain.
                modified_text = (
                    template_text
                    .replace("{username}", formatted_username)
                    .replace("{bot}", formatted_order)
                    .replace("{botdecav}", formatted_botdecav)
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

                # ====================================================
                # 🔥 TAMBAHAN FITUR ADD-ON REPLY KHUSUS BASE WITH SIGN
                # ====================================================
                if needs_sign and comment_msg:
                    async def send_addon_reply():
                        try:
                            await asyncio.sleep(1.5)
                            addon_msg = await current_sender.send_message(
                                comment_msg.chat_id,
                                ADDON_TEXT_WITH_SIGN,
                                reply_to=comment_msg.id,
                                link_preview=False
                            )
                            # Simpan ID pesan add-on yang terhubung dengan komen utama
                            ADDON_MSG_MAP[comment_msg.id] = addon_msg.id
                            
                            # Bersihkan memori agar RAM tidak penuh
                            if len(ADDON_MSG_MAP) > 5000:
                                ADDON_MSG_MAP.clear()
                        except Exception as e:
                            print(f"[!] Gagal kirim add-on reply: {e}")
                    
                    asyncio.create_task(send_addon_reply())
                # ====================================================

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

        # 🔥 TAMBAHKAN BARIS INI 🔥
        # Otomatis mendaftarkan ID grup comsect (tempat komen mendarat)
        ALLOWED_COMSECT_GROUPS.add(comment_msg.chat_id)

        # Link komentar (bukan link post) — biar admin bisa langsung cek
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

        # ==========================================
        # 🔥 TAMBAHKAN INI AGAR BOT MENGENALI GRUP 🔥
        # ==========================================
        try:
            await bot.get_entity(ADMIN_GROUP_ID)
            if LOG_GROUP_ID != ADMIN_GROUP_ID:
                await bot.get_entity(LOG_GROUP_ID)
            print("✅ Entitas Grup Admin/Log berhasil dikenali bot.")
        except Exception as e:
            print(f"⚠️ PERINGATAN: Bot belum mengenali Grup Admin/Log: {e}")
            print("Pastikan bot sudah di-invite ke grup dan diberi akses admin.")
        # ==========================================

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
