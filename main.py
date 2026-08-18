import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SCHEDULE_FILE = BASE_DIR / "jadwal.json"
STATE_FILE = DATA_DIR / "state.json"
OUTPUT_DIR = DATA_DIR / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not API_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN belum di-set di Variables Railway.")

CHANNEL_IDS = [x.strip() for x in os.getenv("CHANNEL_IDS", "@omtogel_info").split(",") if x.strip()]
if not CHANNEL_IDS:
    raise RuntimeError("CHANNEL_IDS kosong. Isi minimal 1 username/id channel Telegram.")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "6918801560"))
except ValueError as exc:
    raise RuntimeError("ADMIN_ID harus berupa angka Telegram user ID.") from exc

LOGIN_URL = os.getenv("LOGIN_URL", "https://omtogelfine.org/").strip()
PROMO_URL = os.getenv("PROMO_URL", "https://promosiku13.omtogel-prediksi.com/").strip()
TZ = pytz.timezone("Asia/Jakarta")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

from poster import HARI_ID, BULAN_ID, POSTER_VERSION, generate_prediction_data, create_poster


def is_admin(user_id):
    return user_id == ADMIN_ID


def load_schedule():
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict) or not raw:
        raise RuntimeError("jadwal.json harus berupa object dan tidak boleh kosong.")

    cleaned = {}
    for market, value in raw.items():
        name = str(market).strip().upper()
        time_text = str(value).strip()
        if not name:
            raise RuntimeError("Ada nama pasaran kosong di jadwal.json.")
        try:
            datetime.strptime(time_text, "%H:%M")
        except ValueError as exc:
            raise RuntimeError(f"Jam pasaran {name} tidak valid: {time_text}. Wajib HH:MM.") from exc
        cleaned[name] = time_text
    return cleaned


def _default_state():
    return {
        "prediction": set(),
        "reminder": set(),
        "prediction_channels": set(),
        "reminder_channels": set(),
    }


def load_state():
    state = _default_state()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in state:
            state[key] = set(data.get(key, []))
    except FileNotFoundError:
        pass
    except Exception:
        logging.exception("state.json rusak/tidak terbaca, state baru akan dipakai")
    return state


def save_state(state):
    payload = {key: sorted(state[key]) for key in _default_state()}
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE_FILE)


def cleanup_state(state):
    cutoff = (datetime.now(TZ).date() - timedelta(days=3)).isoformat()
    for kind in state:
        state[kind] = {k for k in state[kind] if k[:10] >= cutoff}


def prediction_key(pasaran, result_dt):
    return f"{result_dt.date().isoformat()}|{pasaran}"


def channel_key(key, channel):
    return f"{key}|{channel}"


def buttons():
    kb = types.InlineKeyboardMarkup(row_width=2)
    if LOGIN_URL:
        kb.insert(types.InlineKeyboardButton("🎮 LOGIN OMTOGEL", url=LOGIN_URL))
    if PROMO_URL:
        kb.insert(types.InlineKeyboardButton("🎁 PROMO OMTOGEL", url=PROMO_URL))
    return kb


async def notify_admin(text):
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        logging.exception("Gagal mengirim notifikasi ke admin")


async def send_prediction(pasaran, result_dt, state, force=False):
    key = prediction_key(pasaran, result_dt)
    if key in state["prediction"] and not force:
        return False

    data = generate_prediction_data(pasaran, result_dt)
    poster = create_poster(data)
    if not poster.exists() or poster.stat().st_size < 1000:
        raise RuntimeError(f"File poster gagal dibuat: {poster}")

    caption = (
        f"🧿 <b>PREDIKSI {pasaran.upper()}</b>\n"
        f"🗓 <b>{HARI_ID[result_dt.strftime('%A')]}, {result_dt.day:02d} {BULAN_ID[result_dt.month]} {result_dt.year}</b>\n\n"
        "🔎 <b>CARI KAMI DI GOOGLE : OMTOGEL</b>"
    )

    all_ok = True
    for channel in CHANNEL_IDS:
        ck = channel_key(key, channel)
        if ck in state["prediction_channels"] and not force:
            continue
        try:
            with open(poster, "rb") as photo:
                await bot.send_photo(channel, photo=photo, caption=caption, reply_markup=buttons())
            if not force:
                state["prediction_channels"].add(ck)
                save_state(state)
        except Exception:
            all_ok = False
            logging.exception("Gagal kirim prediksi %s ke %s", pasaran, channel)

    if force:
        if not all_ok:
            raise RuntimeError("Ada channel yang gagal menerima prediksi. Cek log Railway.")
        await notify_admin(f"✅ Prediksi manual <b>{pasaran}</b> berhasil dibuat + dikirim sebagai gambar.")
        return True

    required = {channel_key(key, ch) for ch in CHANNEL_IDS}
    complete = required.issubset(state["prediction_channels"])
    if complete:
        first_complete = key not in state["prediction"]
        state["prediction"].add(key)
        cleanup_state(state)
        save_state(state)
        if first_complete:
            await notify_admin(f"✅ Prediksi <b>{pasaran}</b> berhasil dibuat + dikirim sebagai gambar.")
        return True

    return False


def result_candidates(now, jam_tutup):
    hh, mm = map(int, jam_tutup.split(":"))
    out = []
    for day_delta in (-1, 0, 1):
        d = now.date() + timedelta(days=day_delta)
        out.append(TZ.localize(datetime(d.year, d.month, d.day, hh, mm)))
    return out


async def send_reminder(pasaran, result_dt, state):
    key = prediction_key(pasaran, result_dt)
    if key in state["reminder"]:
        return False

    text = f"⏰ <b>10 Menit Menuju Result</b>\nPasaran <b>{pasaran.upper()}</b> akan segera keluar."
    for channel in CHANNEL_IDS:
        ck = channel_key(key, channel)
        if ck in state["reminder_channels"]:
            continue
        try:
            await bot.send_message(channel, text, reply_markup=buttons())
            state["reminder_channels"].add(ck)
            save_state(state)
        except Exception:
            logging.exception("Gagal kirim reminder %s ke %s", pasaran, channel)

    required = {channel_key(key, ch) for ch in CHANNEL_IDS}
    if required.issubset(state["reminder_channels"]):
        state["reminder"].add(key)
        cleanup_state(state)
        save_state(state)
        return True
    return False


async def scheduler():
    state = load_state()
    logging.info("Scheduler aktif. Timezone=%s, channel=%s, poster=%s", TZ.zone, ",".join(CHANNEL_IDS), POSTER_VERSION)
    while True:
        try:
            now = datetime.now(TZ)
            schedule = load_schedule()
            for pasaran, jam_tutup in schedule.items():
                for result_dt in result_candidates(now, jam_tutup):
                    pred_dt = result_dt - timedelta(hours=1)
                    rem_dt = result_dt - timedelta(minutes=10)
                    key = prediction_key(pasaran, result_dt)

                    # Catch-up aman: jika Railway sempat restart setelah jam prediksi,
                    # kirim tetap dilakukan selama result belum lewat.
                    if pred_dt <= now < result_dt and key not in state["prediction"]:
                        try:
                            await send_prediction(pasaran, result_dt, state)
                        except Exception as exc:
                            logging.exception("Gagal proses prediksi %s", pasaran)
                            await notify_admin(f"❌ Gagal prediksi <b>{pasaran}</b>: {exc}")

                    if rem_dt <= now < result_dt and key not in state["reminder"]:
                        try:
                            await send_reminder(pasaran, result_dt, state)
                        except Exception:
                            logging.exception("Gagal proses reminder %s", pasaran)

            cleanup_state(state)
            await asyncio.sleep(20)
        except Exception:
            logging.exception("Scheduler error")
            await asyncio.sleep(20)


@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("Silahkan chat admin OMTOGEL di @omtogelcs1")
        return
    await message.reply(
        f"✅ Bot prediksi gambar OMTOGEL aktif.\nPoster: <b>{POSTER_VERSION}</b>\n\n"
        "• Otomatis 1 jam sebelum result\n"
        "• Catch-up otomatis jika Railway baru selesai restart\n"
        "• Semua angka dibuat otomatis\n"
        "• Satu template OMTOGEL\n"
        "• /kirim NAMA PASARAN untuk kirim manual\n"
        "• /preview NAMA PASARAN untuk lihat gambar tanpa kirim ke channel\n"
        "• /cekpasaran untuk daftar pasaran\n"
        "• /infopasaran untuk status kiriman hari ini"
    )


@dp.message_handler(commands=["cekpasaran"])
async def cmd_cekpasaran(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    jadwal = load_schedule()
    daftar = "\n".join([f"• {k} — result {v} / prediksi H-1 jam" for k, v in jadwal.items()])
    await message.reply(f"<b>🗂️ DAFTAR PASARAN</b>\n\n{daftar}")


@dp.message_handler(commands=["infopasaran"])
async def cmd_infopasaran(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    today = datetime.now(TZ).date().isoformat()
    state = load_state()
    sent = sorted(k.split("|", 1)[1] for k in state["prediction"] if k.startswith(today + "|"))
    if not sent:
        await message.reply("📭 Belum ada prediksi yang terkirim untuk tanggal result hari ini.")
        return
    await message.reply("📬 <b>Prediksi Terkirim Hari Ini:</b>\n\n" + "\n".join(f"• {x}" for x in sent))


def resolve_market(text):
    q = text.strip().upper()
    schedule = load_schedule()
    if q in schedule:
        return q
    matches = [k for k in schedule if q and q in k]
    return matches[0] if len(matches) == 1 else None


def next_result_for_market(pasaran, now=None):
    now = now or datetime.now(TZ)
    jam = load_schedule()[pasaran]
    candidates = [x for x in result_candidates(now, jam) if x >= now - timedelta(minutes=1)]
    return min(candidates) if candidates else max(result_candidates(now, jam))


@dp.message_handler(commands=["preview"])
async def cmd_preview(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    pasaran = resolve_market(message.get_args())
    if not pasaran:
        await message.reply("❌ Pasaran tidak ditemukan / nama terlalu umum. Cek /cekpasaran")
        return
    result_dt = next_result_for_market(pasaran)
    poster = create_poster(generate_prediction_data(pasaran, result_dt))
    with open(poster, "rb") as photo:
        await message.reply_photo(photo, caption=f"Preview <b>{pasaran}</b> — <code>{POSTER_VERSION}</code>")


@dp.message_handler(commands=["kirim"])
async def cmd_kirim(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    pasaran = resolve_market(message.get_args())
    if not pasaran:
        await message.reply("❌ Pasaran tidak ditemukan / nama terlalu umum. Cek /cekpasaran")
        return
    result_dt = next_result_for_market(pasaran)
    state = load_state()
    try:
        await send_prediction(pasaran, result_dt, state, force=True)
        await message.reply(f"🚀 <b>{pasaran}</b> berhasil dikirim.")
    except Exception as exc:
        logging.exception("Manual send failed")
        await message.reply(f"❌ Gagal: {exc}")


async def on_startup(_):
    schedule = load_schedule()
    logging.info("Validasi startup OK: %d pasaran | poster=%s", len(schedule), POSTER_VERSION)
    asyncio.create_task(scheduler())


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
