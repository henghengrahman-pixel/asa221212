import hashlib
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR)))
OUTPUT_DIR = DATA_DIR / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOGO_FILE = BASE_DIR / "assets" / "logo_omtogel.png"

SHIO = ["TIKUS", "KERBAU", "HARIMAU", "KELINCI", "NAGA", "ULAR", "KUDA", "KAMBING", "MONYET", "AYAM", "ANJING", "BABI"]
HARI_ID = {"Monday":"SENIN", "Tuesday":"SELASA", "Wednesday":"RABU", "Thursday":"KAMIS", "Friday":"JUMAT", "Saturday":"SABTU", "Sunday":"MINGGU"}
BULAN_ID = ["", "JANUARI", "FEBRUARI", "MARET", "APRIL", "MEI", "JUNI", "JULI", "AGUSTUS", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DESEMBER"]

# Warna template OMTOGEL
BG = (3, 4, 5)
PANEL = (7, 9, 11)
PANEL_2 = (11, 12, 14)
SILVER = (220, 224, 228)
SILVER_DARK = (125, 130, 136)
WHITE = (248, 248, 248)
GOLD = (225, 181, 70)
GOLD_SOFT = (193, 147, 48)
BLACK = (8, 8, 8)


def seeded_rng(pasaran, result_dt):
    seed_src = f"OMTOGEL|{pasaran.upper()}|{result_dt.date().isoformat()}"
    seed = int(hashlib.sha256(seed_src.encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(seed)


def unique_combos(rng, digits, length, count):
    combos = []
    seen = set()
    max_space = len(digits) ** length
    if count > max_space:
        raise ValueError("Jumlah kombinasi yang diminta melebihi ruang kombinasi.")
    while len(combos) < count:
        value = "".join(rng.choice(digits) for _ in range(length))
        if value not in seen:
            seen.add(value)
            combos.append(value)
    return combos


def validate_prediction_data(data):
    bbfs = data["bbfs"]
    ai = data["ai"]
    if len(bbfs) != 7 or len(set(bbfs)) != 7 or not bbfs.isdigit():
        raise ValueError("BBFS generator tidak valid.")
    if len(ai) != 4 or len(set(ai)) != 4 or not set(ai).issubset(set(bbfs)):
        raise ValueError("AI generator tidak valid.")

    checks = [("d4", 4, 4), ("d3", 3, 7), ("d2", 2, 10)]
    for key, length, count in checks:
        values = data[key].split(" - ")
        if len(values) != count or len(set(values)) != count:
            raise ValueError(f"{key.upper()} generator tidak valid/duplikat.")
        if any(len(v) != length or not v.isdigit() or not set(v).issubset(set(bbfs)) for v in values):
            raise ValueError(f"{key.upper()} memiliki angka di luar BBFS.")

    cm = data["cm"].split(".")
    if len(cm) != 3 or len(set(cm)) != 3 or any(len(v) != 2 or not v.isdigit() or not set(v).issubset(set(bbfs)) for v in cm):
        raise ValueError("CM generator tidak valid.")

    twins = [x.strip() for x in data["twin"].split("&")]
    if len(twins) != 2 or len(set(twins)) != 2 or any(len(v) != 2 or v[0] != v[1] or v[0] not in bbfs for v in twins):
        raise ValueError("TWIN generator tidak valid.")
    if data["hot"] not in bbfs:
        raise ValueError("ANGKA PANAS harus berasal dari BBFS.")
    return True


def generate_prediction_data(pasaran, result_dt):
    rng = seeded_rng(pasaran, result_dt)
    bbfs_digits = rng.sample(list("0123456789"), 7)
    ai_digits = rng.sample(bbfs_digits, 4)
    cb_digits = rng.sample(ai_digits, 2)
    cm_pairs = unique_combos(rng, bbfs_digits, 2, 3)
    twins = rng.sample([f"{d}{d}" for d in bbfs_digits], 2)

    data = {
        "pasaran": pasaran.upper(),
        "result_dt": result_dt,
        "bbfs": "".join(bbfs_digits),
        "ai": "".join(ai_digits),
        "cb": f"{cb_digits[0]} & {cb_digits[1]}",
        "cm": ".".join(cm_pairs),
        "d4": " - ".join(unique_combos(rng, bbfs_digits, 4, 4)),
        "d3": " - ".join(unique_combos(rng, bbfs_digits, 3, 7)),
        "d2": " - ".join(unique_combos(rng, bbfs_digits, 2, 10)),
        "shio": rng.choice(SHIO),
        "twin": " & ".join(twins),
        "hot": rng.choice(bbfs_digits),
    }
    validate_prediction_data(data)
    return data


def font(size, bold=True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def fit_font(draw, text, max_width, start_size, min_size=22, bold=True):
    """Cari font terbesar yang muat pada lebar yang tersedia."""
    text = str(text)
    for size in range(int(start_size), int(min_size) - 1, -1):
        fnt = font(size, bold)
        bb = draw.textbbox((0, 0), text, font=fnt)
        if bb[2] - bb[0] <= max_width:
            return fnt
    return font(min_size, bold)


def center_text(draw, box, text, fnt, fill=WHITE, stroke=0, stroke_fill=BLACK):
    x1, y1, x2, y2 = box
    text = str(text)
    bb = draw.textbbox((0, 0), text, font=fnt, stroke_width=stroke)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    x = x1 + (x2 - x1 - w) / 2
    y = y1 + (y2 - y1 - h) / 2 - bb[1]
    draw.text((x, y), text, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


def rounded_panel(draw, box, radius=18, fill=PANEL, outline=SILVER, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_search_icon(draw, cx, cy, r=16, color=SILVER, width=4):
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=color, width=width)
    draw.line((cx+r-2, cy+r-2, cx+r+13, cy+r+13), fill=color, width=width)


def draw_label_value(draw, box, label, value, label_size=34, value_size=60, value_min=30):
    x1, y1, x2, y2 = box
    rounded_panel(draw, box, 16, PANEL, SILVER, 2)
    label_h = 58
    split = y1 + label_h
    draw.line((x1, split, x2, split), fill=SILVER_DARK, width=1)
    center_text(draw, (x1, y1, x2, split), label, font(label_size), GOLD)
    fnt = fit_font(draw, value, x2 - x1 - 24, value_size, value_min)
    center_text(draw, (x1 + 6, split, x2 - 6, y2), value, fnt, WHITE, 1, (25, 25, 25))


def create_poster(data):
    """Buat poster 1080x1350 dengan font besar dan layout rapat untuk Telegram/HP."""
    validate_prediction_data(data)
    if not LOGO_FILE.exists():
        raise FileNotFoundError(f"Logo OMTOGEL tidak ditemukan: {LOGO_FILE}")

    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Background hitam-metallic halus.
    for y in range(H):
        d = abs(y - H * 0.52) / (H * 0.52)
        shade = max(3, min(14, int(13 - 8 * d)))
        draw.line((0, y, W, y), fill=(shade, shade + 1, shade + 2))

    # Garis sudut dekoratif tipis agar tampilan tetap ringan dan rapi.
    for offset, col, wd in ((0, SILVER, 2), (18, (80, 84, 88), 1), (30, GOLD_SOFT, 1)):
        draw.line((offset, offset, 125, 125), fill=col, width=wd)
        draw.line((W-offset, offset, W-125, 125), fill=col, width=wd)
        draw.line((offset, H-offset, 125, H-125), fill=col, width=wd)
        draw.line((W-offset, H-offset, W-125, H-125), fill=col, width=wd)

    # Header logo: tetap besar tetapi tidak memakan ruang angka.
    with Image.open(LOGO_FILE) as src:
        logo = src.convert("RGBA")
        alpha = logo.getchannel("A")
        bbox = alpha.getbbox()
        if bbox:
            logo = logo.crop(bbox)
        logo.thumbnail((760, 138), Image.Resampling.LANCZOS)
        img.paste(logo, ((W - logo.width) // 2, 22), logo)

    center_text(draw, (35, 152, W-35, 246), "PREDIKSI TOGEL", font(78), WHITE, 1, (80, 80, 80))

    # Pasaran + tanggal. Font otomatis mengecil hanya jika nama pasarannya panjang.
    rounded_panel(draw, (38, 258, 1042, 402), 20, PANEL_2, SILVER, 2)
    market_f = fit_font(draw, data["pasaran"], 900, 64, 38)
    center_text(draw, (75, 267, 1005, 337), data["pasaran"], market_f, WHITE, 1, BLACK)
    dt = data["result_dt"]
    date_text = f"{HARI_ID[dt.strftime('%A')]}, {dt.day:02d} {BULAN_ID[dt.month]} {dt.year}"
    date_f = fit_font(draw, date_text, 780, 34, 28)
    center_text(draw, (140, 340, 940, 393), date_text, date_f, GOLD)

    # 4 kotak utama: label dan nilai sama-sama dibesarkan.
    y1, y2 = 420, 588
    margin, gap = 38, 8
    colw = (W - 2 * margin - 3 * gap) // 4
    fields = [
        ("BBFS", data["bbfs"], 61, 36),
        ("AI", data["ai"], 62, 36),
        ("CB", data["cb"], 60, 36),
        ("CM", data["cm"], 52, 32),
    ]
    for i, (label, value, val_size, val_min) in enumerate(fields):
        x1 = margin + i * (colw + gap)
        draw_label_value(draw, (x1, y1, x1 + colw, y2), label, value, 35, val_size, val_min)

    # 4D / 3D / 2D. Tinggi baris dirapatkan dan angka diperbesar.
    rows = [
        ("4D BB", data["d4"], 52, 36),
        ("3D BB", data["d3"], 43, 31),
        ("2D BB", data["d2"], 39, 28),
    ]
    row_y = 604
    row_h = 104
    row_gap = 8
    label_w = 205
    for idx, (label, value, start_size, min_size) in enumerate(rows):
        top = row_y + idx * (row_h + row_gap)
        bottom = top + row_h
        rounded_panel(draw, (38, top, 1042, bottom), 16, PANEL, SILVER, 2)
        # label gold/metal seperti referensi, lebih kontras.
        draw.rounded_rectangle((38, top, 38 + label_w, bottom), radius=16, fill=(215, 175, 75), outline=SILVER, width=1)
        draw.rectangle((38 + label_w - 16, top, 38 + label_w, bottom), fill=(215, 175, 75))
        center_text(draw, (38, top, 38 + label_w, bottom), label, font(43), BLACK)
        vf = fit_font(draw, value, 1042 - (38 + label_w) - 30, start_size, min_size)
        center_text(draw, (38 + label_w + 12, top, 1030, bottom), value, vf, WHITE, 1, BLACK)

    # SHIO: label + nama dibuat jauh lebih besar dan mudah dibaca.
    sy1, sy2 = 944, 1078
    rounded_panel(draw, (38, sy1, 1042, sy2), 16, PANEL, SILVER, 2)
    center_text(draw, (300, sy1 + 4, 780, sy1 + 58), "SHIO", font(38), GOLD)
    shio_f = fit_font(draw, data["shio"], 520, 62, 46)
    center_text(draw, (270, sy1 + 48, 810, sy2 - 4), data["shio"], shio_f, WHITE, 1, BLACK)
    # ornamen sederhana yang selalu tersedia (tanpa font emoji yang rawan hilang)
    center_text(draw, (62, sy1 + 15, 205, sy2 - 12), "◆", font(72), SILVER)
    center_text(draw, (875, sy1 + 15, 1018, sy2 - 12), "◆", font(72), SILVER)

    # TWIN dan ANGKA PANAS: ukuran angka dibesarkan.
    draw_label_value(draw, (38, 1094, 532, 1224), "TWIN", data["twin"], 34, 63, 40)
    draw_label_value(draw, (548, 1094, 1042, 1224), "ANGKA PANAS", data["hot"], 31, 72, 52)

    # Footer lebih tebal dan besar; tanpa panel promosi tambahan.
    rounded_panel(draw, (70, 1242, 1010, 1321), 22, PANEL_2, SILVER_DARK, 2)
    draw_search_icon(draw, 116, 1279, 16, SILVER, 4)
    draw_search_icon(draw, 964, 1279, 16, SILVER, 4)
    footer = "CARI KAMI DI GOOGLE : OMTOGEL"
    footer_f = fit_font(draw, footer, 770, 36, 28)
    center_text(draw, (155, 1242, 925, 1321), footer, footer_f, WHITE)

    safe_market = "".join(c if c.isalnum() else "_" for c in data["pasaran"]).strip("_")
    out = OUTPUT_DIR / f"prediksi_{data['result_dt'].date().isoformat()}_{safe_market}.png"
    tmp = out.with_suffix(".tmp.png")
    img.save(tmp, "PNG", optimize=True)
    os.replace(tmp, out)
    return out
