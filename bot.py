import sqlite3
import tempfile
import csv
import pytz
import logging
from telegram import ChatMember
from telegram import BotCommand
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.helpers import escape_markdown
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters, CallbackQueryHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
#Log///////////////////////////////////////////////////##
# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Simpan aktivitas pengguna
user_activities = {}

# Fungsi untuk mencetak log aktivitas pengguna
def log_user_activity(update: Update):
    user = update.message.from_user
    chat = update.effective_chat

    # Ambil informasi pengguna
    user_id = user.id
    username = user.username if user.username else "Tidak ada username"
    first_name = user.first_name
    last_name = user.last_name if user.last_name else ""
    full_name = f"{first_name} {last_name}".strip()
    chat_title = chat.title if chat.title else "Grup Tanpa Nama"

    # Simpan atau perbarui aktivitas pengguna
    if user_id not in user_activities:
        user_activities[user_id] = {
            'name': full_name,
            'username': username,
            'user_id': user_id,
            'chat_title': chat_title,
            'work_time': None,
            'activities': [],
            'activity_counts': {},
            'last_date': update.message.date.strftime("%Y-%m-%d")
        }

    # Cetak log ke terminal
    logger.info(f"User Activities: {user_activities[user_id]}")
#/////////////////////////////////////////////////////////////////////////##

group_activities = {}
user_data = {}

#////////////////////////////////////////////////////////////////////////////#
ACTIVITY_DURATIONS = {
    'pipis': timedelta(minutes=5),
    'boker': timedelta(minutes=15),
    'merokok': timedelta(minutes=8),
    'ambil_pesanan': timedelta(minutes=8),
    'colmek': timedelta(minutes=5)
}
#////////////////////////////////////////////////////////////////////////////#
async def show_keyboard(update: Update, context: CallbackContext):
    keyboard = [
        ['masuk', 'pulang'],
        ['makan', 'boker'],
        ['merokok', 'pipis'],
        ['kembali', 'ambil_pesanan', 'colmek']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome_message = "👋 **Selamat datang!** Silakan pilih aktivitas yang sesuai dari menu di bawah ini."
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def mulai(update: Update, context: CallbackContext):
    await show_keyboard(update, context)

async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    if update.effective_chat.type != 'private':
        await update.message.reply_text("Silakan hubungi bot ini secara pribadi untuk memulai.")
        return

    if user_id not in user_data:
        user_data[user_id] = {
            'name': user_name,
            'activities': []
        }

    welcome_message = (
        f"🎉 **Selamat Datang, {user_name}!** 🎉\n\n"
        "Sebelum menggunakan bot ini, harap baca dengan seksama catatan berikut, "
        "lalu tambahkan bot ini ke grup absensi yang Anda buat, jika tidak, "
        "Anda mungkin tidak dapat menggunakan bot ini!\n\n"
        "**CARA** Gunakan (/mulai di group) untuk menampilkan keyboard Aktivitas Group\n\n"
        "**Perhatian!** Bot harus menjadi admin di grup, jika tidak, bot mungkin tidak dapat "
        "berfungsi dengan baik dan akan keluar dari grup. Bot versi gratis secara ketat melarang "
        "penyalahgunaan dan spam. Jika ditemukan, bot akan menolak untuk memberikan layanan "
        "kepada grup dan pengguna tersebut secara permanen.\n\n"
        "Kami memanfaatkan sumber daya yang tersedia untuk menjalankan bot ini agar dapat "
        "digunakan secara ringan. Namun, kami tidak dapat menjamin tingkat online dan kecepatan "
        "respons yang tinggi. Kami juga tidak memberikan panduan atau bantuan untuk pengguna "
        "versi gratis. Silakan hubungi bot secara pribadi untuk melihat petunjuk bantuan. "
        "Jika Anda memerlukan bot versi khusus, silakan hubungi: [https://t.me/PT717TT]\n\n"
        "Kecuali dinyatakan lain, perintah pengaturan dan manajemen bot harus dikirimkan di "
        "dalam grup. Pengiriman pesan di luar grup tidak akan berfungsi.\n\n"
        "Saat mengirim perintah manajemen di grup, pastikan Anda adalah admin grup tersebut. "
        "Daftar admin grup diperbarui setiap 24 jam, sehingga bagi pengguna yang baru saja "
        "ditunjuk sebagai admin, bot mungkin tidak akan menerima perintah pengaturan darinya.\n\n"
        "Sebelum menggunakan bot, pastikan Anda telah membaca bagian bantuan dengan judul "
        "'Catatan Penting'.\n\n"
    )

    add_to_group_link = f"https://t.me/Moreno477_bot?startgroup=config"
    keyboard = [[InlineKeyboardButton("Tambahkan ke Grup", url=add_to_group_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
#////////////////////////////////////////////////////////////////////////////#

async def handle_keyboard_input(update: Update, context: CallbackContext):
    user_input = update.message.text

    if user_input == 'Panduan':
        await panduan(update, context)
    else:
        pass

def get_full_name(user):
    return f"{user.first_name} {user.last_name or ''}".strip()

def format_time(dt):
    return dt.strftime('%H:%M:%S')

def format_duration(duration):
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours} jam, {minutes} menit, {seconds} detik"
    elif minutes > 0:
        return f"{minutes} menit, {seconds} detik"
    else:
        return f"{seconds} detik"

def reset_all_activities():
    print("Resetting activities for all users and groups at 00:00 WIB")
    for group_id in group_activities:
        for user_id in group_activities[group_id]:
            user_activities = group_activities[group_id][user_id]
            user_activities['activities'] = []
            user_activities['activity_counts'] = {}
            user_activities['is_working'] = False
            user_activities['work_time'] = None
            user_activities['last_date'] = get_today_date()
    print("Reset completed!")

def get_today_date():
    wib_timezone = pytz.timezone('Asia/Jakarta')
    today = datetime.now(wib_timezone).strftime('%Y-%m-%d')
    return today

def schedule_reset_task():
    wib_timezone = pytz.timezone('Asia/Jakarta')
    scheduler = BackgroundScheduler(timezone=wib_timezone)
    scheduler.add_job(reset_all_activities, 'cron', hour=0, minute=0)
    scheduler.start()
    print("Scheduled reset task at 00:00 WIB every day")

def reset_if_date_changed(user_id, group_id):
    today = get_today_date()
    if group_id not in group_activities:
        return

    user_activities = group_activities[group_id].get(user_id, {})
    last_date = user_activities.get('last_date')

    if last_date != today:
        print(f"Resetting activities for user {user_id} in group {group_id} (last active date: {last_date}, today: {today})")
        user_activities['last_date'] = today
        user_activities['activities'] = []
        user_activities['activity_counts'] = {}
        user_activities['is_working'] = False
        group_activities[group_id][user_id] = user_activities
        
#////////////////////////////////////////////////////////////////////////////#
async def masuk_kerja(update: Update, context: CallbackContext):
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Silakan gunakan perintah ini di dalam grup.")
        return

    user_id = update.message.from_user.id
    full_name = get_full_name(update.message.from_user)
    group_id = update.message.chat.id

    reset_if_date_changed(user_id, group_id)

    if group_id not in group_activities:
        group_activities[group_id] = {}

    if user_id not in group_activities[group_id]:
        group_activities[group_id][user_id] = {
            'name': full_name,
            'work_time': None,
            'activities': [],
            'activity_counts': {},
            'last_date': get_today_date()
        }

    user_activities = group_activities[group_id][user_id]

    if user_activities.get('work_time'):
        await update.message.reply_text("Anda telah mencatat waktu masuk kerja hari ini. Hindari pencatatan ulang.")
        return

    wib_timezone = pytz.timezone('Asia/Jakarta')
    work_time = datetime.now(wib_timezone)

    #////////////////////////////////////////////////////////////////////////////#
    if not (8 <= work_time.hour < 23):
        await update.message.reply_text("Waktu masuk kerja hanya diperbolehkan antara jam 8 pagi hingga 11 malam.")
        return

    user_activities['work_time'] = work_time

    escaped_full_name = escape_markdown(full_name, version=2)
    formatted_time = escape_markdown(format_time(work_time), version=2)

    reply_message = (
        f"Nama: {escaped_full_name}\n"
        f"\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
        f"✅ Check\-in Berhasil: Masuk kerja \- `{formatted_time}`\n"
        f"\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
        "Welcome : `Selamat Pagi dan selamat beraktifitas, Tetap semangat ya kak` 🤭\n"
        "`Terimakasih Sudah melakukan Absent Tepat Waktu` 🤝\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
        "Catatan : `Jika melanggar Peraturan yang diberikan oleh Perusahaan Maka, Karyawan SIAP untuk menerima Denda yang berlaku !`\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
           
 )

    await update.message.reply_text(reply_message, parse_mode='MarkdownV2')
    
#////////////////////////////////////////////////////////////////////////////#

async def pulang_kerja(update: Update, context: CallbackContext):
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Silakan gunakan perintah ini di dalam grup.")
        return

    user_id = update.message.from_user.id
    full_name = get_full_name(update.message.from_user)
    group_id = update.message.chat.id

    reset_if_date_changed(user_id, group_id)

    if group_id not in group_activities or user_id not in group_activities[group_id]:
        await update.message.reply_text("Tidak ada waktu masuk kerja yang dicatat untuk Anda.")
        return

    user_activities = group_activities[group_id][user_id]

    if not user_activities.get('work_time'):
        await update.message.reply_text("Belum ada waktu masuk kerja yang dicatat.")
        return

    end_time_today = datetime.now(pytz.timezone('Asia/Jakarta')).date()
    if 'last_end_time' in user_activities:
        last_end_time = user_activities['last_end_time'].date()
    else:
        last_end_time = None

    if last_end_time == end_time_today:
        await update.message.reply_text("Anda sudah mencatat aktivitas pulang kerja hari ini.")
        return

    end_time = datetime.now(pytz.timezone('Asia/Jakarta'))
    start_time = user_activities['work_time']
    duration = end_time - start_time

    user_activities['end_time'] = end_time
    user_activities['work_duration'] = duration
    user_activities['last_end_time'] = end_time

    escaped_full_name = escape_markdown(full_name, version=2)
    formatted_time = escape_markdown(format_time(end_time), version=2)
    formatted_duration = escape_markdown(format_duration(duration), version=2)

    reply_message = (
        f"Nama: {escaped_full_name}\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
        f"✅ Check\-out Berhasil: Pulang kerja \- `{formatted_time}`\n"
        f"Durasi kerja : `{formatted_duration}`\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-"
        "Tips: `Selamat Beristirahat dan Semoga Sehat selalu` 😚\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-"
    )

    await update.message.reply_text(reply_message, parse_mode='MarkdownV2')
#Record->////////////////////////////////////////////////////////////////////////////# 
async def record_activity(update: Update, context: CallbackContext, activity=None):
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Silakan gunakan perintah ini di dalam grup.")
        return

    user_id = update.message.from_user.id
    full_name = get_full_name(update.message.from_user)
    group_id = update.message.chat.id  

    tz = pytz.timezone('Asia/Jakarta')

    if group_id not in group_activities:
        group_activities[group_id] = {}

    if user_id not in group_activities[group_id]:
        group_activities[group_id][user_id] = {
            'name': full_name,
            'work_time': None,
            'activities': [],
            'activity_counts': {},
            'last_date': get_today_date()
        }

    user_activities = group_activities[group_id][user_id]

    logging.info(f"User Activities: {user_activities}")

    if user_activities['activities'] and user_activities['activities'][-1]['end_time'] is None:
        ongoing_activity = user_activities['activities'][-1]['activity']
        await update.message.reply_text(
            f"Nama: {escape_markdown(full_name, version=2)}\n"
            "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
            f"Anda belum menyelesaikan aktivitas {escape_markdown(ongoing_activity, version=2)} sebelumnya\n"
            "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-"
            f"Saya sedang merekam waktu {escape_markdown(ongoing_activity, version=2)} Anda\n"
            "Harap akhiri aktivitas tersebut terlebih dahulu\n"
            "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-",
            parse_mode='MarkdownV2'
        )
        return

    if user_activities['work_time'] is None:
        await update.message.reply_text("Anda perlu melakukan check-in (Masuk Kerja) terlebih dahulu sebelum mencatat aktivitas lainnya.")
        return

    if user_activities['activities'] and user_activities['activities'][-1]['activity'] == activity and user_activities['activities'][-1]['end_time'] is None:
        await update.message.reply_text(
            f"Anda belum menyelesaikan aktivitas '{escape_markdown(activity, version=2)}' sebelumnya. Harap akhiri aktivitas tersebut terlebih dahulu dengan menekan tombol 'Kembali' sebelum memulai aktivitas baru.",
            parse_mode='MarkdownV2'
        )
        return

    activity_time = datetime.now(tz)
    if activity not in user_activities['activity_counts']:
        user_activities['activity_counts'][activity] = 0
    user_activities['activity_counts'][activity] += 1

    user_activities['activities'].append({
        'activity': activity,
        'start_time': activity_time,
        'end_time': None,
        'duration': None
    })

    count = user_activities['activity_counts'][activity]
    formatted_time = escape_markdown(activity_time.strftime('%m/%d %H:%M:%S'), version=2)

    reply_message = (
        f"Nama: {escape_markdown(full_name, version=2)}\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
        f"✅ Check\\-in Berhasil: {escape_markdown(activity, version=2)} \\- `{formatted_time}`\n"
        f"Perhatian: Ini adalah check\\-in ke\\-{count} {escape_markdown(activity, version=2)} Anda\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-"
        "Tips: `Mohon untuk melakukan check\\-in pada pukul Kembali ke Kursi setelah menyelesaikan kegiatan`\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-"
        "Kembali ke Kursi: `KEMBALI`\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
        "Catatan :`Jika melanggar Peraturan yang diberikan oleh Perusahaan Maka, Karyawan SIAP untuk menerima Denda yang berlaku !`"
    )

    await update.message.reply_text(reply_message, parse_mode='MarkdownV2')
    
#////////////////////////////////////////////////////////////////////////////#
async def end_activity(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    full_name = get_full_name(update.message.from_user)
    group_id = update.message.chat.id

    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Silakan gunakan perintah ini di dalam grup.")
        return

    tz = pytz.timezone('Asia/Jakarta')

    reset_if_date_changed(user_id, group_id)

    if group_id not in group_activities or user_id not in group_activities[group_id]:
        await update.message.reply_text("Tidak ada aktivitas yang sedang dicatat untuk Anda.")
        return

    activities = group_activities[group_id][user_id]['activities']

    if not activities or activities[-1].get('end_time'):
        await update.message.reply_text("Tidak ada aktivitas yang sedang dicatat atau aktivitas telah selesai.")
        return

    last_activity = activities[-1]
    end_time = datetime.now(tz)
    duration = end_time - last_activity['start_time']
    last_activity['end_time'] = end_time
    last_activity['duration'] = duration

    # Pengecekan durasi aktivitas
    activity_type = last_activity['activity'].lower()
    if activity_type in ACTIVITY_DURATIONS and duration > ACTIVITY_DURATIONS[activity_type]:
        warning_message = f"⚠️ Peringatan: Durasi {activity_type} Anda melebihi batas yang ditentukan ({ACTIVITY_DURATIONS[activity_type]}).\n"
        
        # Kirim pesan pribadi ke admin/pemilik grup tentang pelanggaran
        await notify_admins(update, context, group_id, user_id, full_name, activity_type, duration) # type: ignore
    else:
        warning_message = ""

    formatted_duration = format_duration(duration)
    formatted_time = end_time.strftime('%m/%d %H:%M:%S')

    activity_counts = group_activities[group_id][user_id]['activity_counts']
    summary = "\n".join(
        [f"• {escape_markdown(activity, version=2)}: {count} kali" for activity, count in activity_counts.items()]
    )

    escaped_warning = escape_markdown(warning_message)
    escaped_summary = escape_markdown(summary)

    reply_message = (
        f"Nama: {escape_markdown(full_name, version=2)}\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
        f"✅ Aktivitas {escape_markdown(last_activity['activity'], version=2)} Selesai \\- `{formatted_time}`\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
        f"Terima kasih telah kembali ke kursi\n"
        f"Ini adalah check\\-in ke\\-{activity_counts.get(last_activity['activity'], 0)} {escape_markdown(last_activity['activity'], version=2)} Anda\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
        f"Durasi: `{formatted_duration}`\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
        f"`{escaped_warning}`"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-"
        f"Tips: `Mohon untuk melakukan check\\-in pada pukul Kembali ke Kursi setelah menyelesaikan kegiatan`\n"
        "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-"
        f"Rangkuman Aktivitas:\n"
        f"`{escaped_summary}`"
    )
    await update.message.reply_text(reply_message, parse_mode='MarkdownV2')
    
#////////////////////////////////////////////////////////////////////////////#
async def panduan(update: Update, context: CallbackContext):
    print("Panduan function called")  

    
    if update.message.chat.type != 'private':
        await update.message.reply_text(
            "Silakan gunakan bot ini dalam pesan pribadi untuk mengakses panduan. "
            "Ketikkan /start di pesan pribadi untuk memulai."
        )
        return

    
    keyboard = [
        [InlineKeyboardButton("Perintah Utama", callback_data='main_commands')],
        [InlineKeyboardButton("FAQ", callback_data='faq')],
        [InlineKeyboardButton("Kontak Admin", callback_data='contact_admin')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    
    await update.message.reply_text(
        "🎉 **Panduan Pengguna Bot Absen** 🎉\n\n"
        "Selamat datang di Bot Absen! Untuk memulai, silakan pilih salah satu opsi di bawah ini:\n\n"
        "🔹 **Perintah Utama**: Temukan daftar perintah yang bisa Anda gunakan untuk mencatat aktivitas.\n"
        "🔹 **FAQ**: Pertanyaan yang sering diajukan dan jawabannya untuk membantu Anda.\n"
        "🔹 **Kontak Admin**: Dapatkan informasi kontak admin untuk bantuan lebih lanjut.\n\n"
        "Silakan pilih opsi di atas untuk melanjutkan:",
        reply_markup=reply_markup
    )
    
#////////////////////////////////////////////////////////////////////////////#
async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == 'main_commands':
        guide_message = (
            "🔹 **Perintah Utama**:\n"
            "1. \\*Masuk Kerja\\*: Gunakan untuk mencatat waktu masuk.\n"
            "2. \\*Pulang Kerja\\*: Gunakan untuk mencatat waktu pulang.\n"
            "3. \\*Makan\\*: Gunakan untuk mencatat waktu makan.\n"
            "4. \\*Toilet\\*: Gunakan untuk mencatat waktu ke toilet.\n"
            "5. \\*Merokok\\*: Gunakan untuk mencatat waktu merokok.\n"
            "6. \\*Lain\\*: Gunakan untuk mencatat aktivitas lainnya.\n"
            "7. \\*Kembali\\*: Gunakan untuk mencatat kembali setelah melakukan aktivitas.\n\n"
            "📌 \\*Catatan\\*: Pastikan untuk menggunakan perintah sesuai dengan aktivitas yang dilakukan."
        )

        
        keyboard = [
            [InlineKeyboardButton("Kembali", callback_data='back_to_guide')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(guide_message.replace(".", "\\.").replace("-", "\\-"), parse_mode='MarkdownV2', reply_markup=reply_markup)

    elif query.data == 'faq':
        faq_message = (
            "📝 **FAQ**:\n"
            "1. \\*Bagaimana cara menggunakan bot ini?\\*\n"
            "   - Cukup pilih opsi dari tombol yang tersedia.\n\n"
            "2. \\*Apa yang harus dilakukan jika saya lupa mencatat waktu?\\*\n"
            "   - Anda dapat menghubungi admin untuk bantuan lebih lanjut.\n\n"
            "3. \\*Siapa yang dapat saya hubungi untuk bantuan?\\*\n"
            "   - Silakan lihat opsi 'Kontak Admin' untuk informasi lebih lanjut."
        )

        
        keyboard = [
            [InlineKeyboardButton("Kembali", callback_data='back_to_guide')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(faq_message.replace(".", "\\.").replace("-", "\\-"), parse_mode='MarkdownV2', reply_markup=reply_markup)

    elif query.data == 'contact_admin':
        await query.edit_message_text("📞 **Kontak Admin**:\nSilakan hubungi admin di https://t.me/PT717TT untuk bantuan lebih lanjut.")

    elif query.data == 'back_to_guide':
        await query.edit_message_text("🎉 **Panduan Pengguna Bot Absen** 🎉\n\n"
                                       "Silakan pilih salah satu opsi di bawah ini:",
                                       reply_markup=InlineKeyboardMarkup([
                                           [InlineKeyboardButton("Perintah Utama", callback_data='main_commands')],
                                           [InlineKeyboardButton("FAQ", callback_data='faq')],
                                           [InlineKeyboardButton("Kontak Admin", callback_data='contact_admin')]
                                       ]))
#//////////////////////////////////////////////////////////////////////////////////////#
async def is_admin_or_owner(update: Update, context: CallbackContext) -> bool:
    """
    Memeriksa apakah pengguna yang mengirim perintah adalah admin atau pemilik grup.
    
    Args:
        update (Update): Objek Update dari Telegram.
        context (CallbackContext): Objek Context dari Telegram.
    
    Returns:
        bool: True jika pengguna adalah admin atau pemilik grup, False jika tidak.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Dapatkan daftar admin grup
    admins = await context.bot.get_chat_administrators(chat_id)
    
    # Periksa apakah pengguna adalah admin atau pemilik grup
    for admin in admins:
        if admin.user.id == user_id:
            return True
    return False
# Fungsi untuk memeriksa apakah pengguna adalah admin atau pemilik grup
async def is_admin_or_owner(update: Update, context: CallbackContext) -> bool:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Dapatkan daftar admin grup
    admins = await context.bot.get_chat_administrators(chat_id)
    
    # Periksa apakah pengguna adalah admin atau pemilik grup
    for admin in admins:
        if admin.user.id == user_id:
            return True
    return False
#////////////////////////////////////////////////////////////#
# Fungsi untuk membuat laporan CSV yang dinamis dan rapi
async def get_user_name(context, group_id, user_id):
    try:
        chat_member = await context.bot.get_chat_member(group_id, user_id)
        return chat_member.user.full_name
    except Exception as e:
        print(f"Error fetching user name: {e}")
        return 'Unknown'

async def create_report_csv(group_id, context):
    if group_id not in group_activities:
        return None

    # Buat file CSV sementara
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.csv', delete=False, newline='', encoding='utf-8') as temp_file:
        writer = csv.writer(temp_file)
        # Header kolom
        writer.writerow(["Nama", "Aktivitas", "Jumlah Aktivitas", "Durasi Total"])

        for user_id, user_data in group_activities[group_id].items():
            # Ambil nama pengguna dari user_data atau dari Telegram
            user_name = user_data.get('name', None)
            if user_name is None:
                user_name = await get_user_name(context, group_id, user_id)

            activities = user_data.get('activities', [])
            activity_counts = user_data.get('activity_counts', {})

            # Hitung durasi total untuk setiap aktivitas
            for activity, count in activity_counts.items():
                total_duration = timedelta()  # Inisialisasi durasi total
                for act in activities:
                    if act['activity'] == activity and act['duration']:
                        total_duration += act['duration']

                # Format durasi total
                formatted_duration = format_duration(total_duration)

                # Tulis baris ke CSV
                writer.writerow([user_name, activity, count, formatted_duration])

        temp_file_path = temp_file.name

    return temp_file_path

# Fungsi untuk memformat durasi
def format_duration(duration):
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours} jam {minutes} menit {seconds} detik"
    elif minutes > 0:
        return f"{minutes} menit {seconds} detik"
    else:
        return f"{seconds} detik"

async def laporan(update: Update, context: CallbackContext):
    # Periksa apakah pengguna adalah admin atau pemilik grup
    if not await is_admin_or_owner(update, context):
        await update.message.reply_text("Hanya admin atau pemilik grup yang dapat menggunakan perintah ini.")
        return

    group_id = update.effective_chat.id

    # Buat laporan CSV
    csv_file_path = await create_report_csv(group_id, context)
    if not csv_file_path:
        await update.message.reply_text("Tidak ada aktivitas yang dicatat untuk grup ini.")
        return

    # Kirim file CSV ke grup
    with open(csv_file_path, 'rb') as csv_file:
        await update.message.reply_document(
            document=csv_file,
            caption="📊 **Laporan Aktivitas Grup**\nBerikut adalah ringkasan aktivitas semua member grup dalam format CSV."
        )
        
#Laporan-->////////////////////////////////////////////////////////////////////////////#

    
#////////////////////////////////////////////////////////////////////////////#
async def set_commands(application):
    commands = [
        BotCommand("mulai", "Memulai bot"),
        BotCommand("panduan", "Melihat panduan penggunaan"),
        BotCommand("laporan", "Melihat laporan aktivitas"),
    ]
    await application.bot.set_my_commands(commands)

def main():
    schedule_reset_task()

    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    application.add_handler(CommandHandler("mulai", mulai))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex('masuk'), masuk_kerja))
    application.add_handler(MessageHandler(filters.Regex('pulang'), pulang_kerja))
    application.add_handler(MessageHandler(filters.Regex('makan'), lambda update, context: record_activity(update, context, "Makan")))
    application.add_handler(MessageHandler(filters.Regex('boker'), lambda update, context: record_activity(update, context, "BAB")))
    application.add_handler(MessageHandler(filters.Regex('pipis'), lambda update, context: record_activity(update, context, "PIPIS")))
    application.add_handler(MessageHandler(filters.Regex('merokok'), lambda update, context: record_activity(update, context, "Merokok")))
    application.add_handler(MessageHandler(filters.Regex('ambil_pesanan'), lambda update, context: record_activity(update, context, "Ambil Pesanan")))
    application.add_handler(MessageHandler(filters.Regex('colmek'), lambda update, context: record_activity(update, context, "Colmek")))
    application.add_handler(MessageHandler(filters.Regex('kembali'), end_activity))
    application.add_handler(CommandHandler("panduan", panduan))
    application.add_handler(CommandHandler("laporan", laporan))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyboard_input))
    application.run_polling()

if __name__ == "__main__":
    main()
