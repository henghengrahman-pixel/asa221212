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

# Template OMTOGEL V6: font besar, tebal, rapat, aman di Railway/Pillow minimal.
BG = (3, 4, 5)
PANEL = (8, 10, 12)
PANEL_2 = (12, 13, 15)
WHITE = (248, 248, 248)
SILVER = (220, 224, 228)
SILVER_DARK = (112, 118, 124)
GOLD = (231, 185, 70)
GOLD_BRIGHT = (247, 202, 81)
GOLD_DARK = (178, 132, 34)
BLACK = (7, 7, 7)
POSTER_VERSION = "V6-BOLD-LAYOUT-20260818"


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


_FONT_CACHE = {}


def font(size, bold=True):
    """Font scalable yang aman di local dan Railway.

    Tidak pernah fallback ke bitmap kecil tanpa ukuran. Jika font sistem tidak ada,
    Pillow scalable default tetap memakai size yang diminta. Ketebalan tambahan
    dibuat lewat stroke saat menggambar sehingga hasil tetap tebal di Railway.
    """
    size = max(8, int(size))
    key = (size, bool(bold))
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansCondensed-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSansCondensed.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "DejaVuSansCondensed-Bold.ttf" if bold else "DejaVuSansCondensed.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            fnt = ImageFont.truetype(path, size)
            _FONT_CACHE[key] = fnt
            return fnt
        except Exception:
            pass

    try:
        fnt = ImageFont.load_default(size=size)
    except TypeError as exc:
        raise RuntimeError(
            "Pillow terlalu lama: scalable fallback font tidak tersedia. "
            "Gunakan Pillow==11.1.0 dari requirements.txt."
        ) from exc
    _FONT_CACHE[key] = fnt
    return fnt


def fit_font(draw, text, max_width, start_size, min_size=28, bold=True, stroke=0):
    text = str(text)
    for size in range(int(start_size), int(min_size) - 1, -1):
        fnt = font(size, bold)
        bb = draw.textbbox((0, 0), text, font=fnt, stroke_width=stroke)
        if bb[2] - bb[0] <= max_width:
            return fnt
    return font(min_size, bold)


def center_text(draw, box, text, fnt, fill=WHITE, stroke=0, stroke_fill=BLACK):
    x1, y1, x2, y2 = box
    text = str(text)
    bb = draw.textbbox((0, 0), text, font=fnt, stroke_width=stroke)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    # Koreksi bbox kiri/atas penting untuk font FreeType yang punya bearing negatif.
    x = x1 + (x2 - x1 - w) / 2 - bb[0]
    y = y1 + (y2 - y1 - h) / 2 - bb[1]
    draw.text((x, y), text, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


def rounded_panel(draw, box, radius=18, fill=PANEL, outline=GOLD_DARK, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_search_icon(draw, cx, cy, r=18, color=GOLD_BRIGHT, width=5):
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=color, width=width)
    draw.line((cx+r-2, cy+r-2, cx+r+15, cy+r+15), fill=color, width=width)


def draw_gold_label(draw, box, label):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=15, fill=GOLD, outline=GOLD_BRIGHT, width=2)
    # sisi kanan diluruskan agar menyatu dengan panel angka
    draw.rectangle((x2 - 16, y1, x2, y2), fill=GOLD)
    fnt = fit_font(draw, label, x2 - x1 - 24, 54, 38, stroke=1)
    center_text(draw, box, label, fnt, BLACK, 1, (90, 60, 0))


def draw_label_value(draw, box, label, value, label_size, value_size, value_min):
    x1, y1, x2, y2 = box
    rounded_panel(draw, box, 16, PANEL, GOLD_DARK, 2)
    label_h = 58
    split = y1 + label_h
    draw.line((x1, split, x2, split), fill=GOLD_DARK, width=2)
    center_text(draw, (x1, y1, x2, split), label, font(label_size), GOLD_BRIGHT, 1, BLACK)
    # nilai dibuat tebal dengan stroke 2; fit hanya dilakukan sampai batas minimum besar.
    fnt = fit_font(draw, value, x2 - x1 - 20, value_size, value_min, stroke=2)
    center_text(draw, (x1 + 5, split, x2 - 5, y2), value, fnt, WHITE, 2, BLACK)


def create_poster(data):
    """Poster 1080x1350: besar, tebal, rapat, dan terbaca jelas di Telegram/HP."""
    validate_prediction_data(data)
    if not LOGO_FILE.exists():
        raise FileNotFoundError(f"Logo OMTOGEL tidak ditemukan: {LOGO_FILE}")

    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Background hitam-metallic halus.
    for y in range(H):
        d = abs(y - H * 0.50) / (H * 0.50)
        shade = max(3, min(14, int(13 - 8 * d)))
        draw.line((0, y, W, y), fill=(shade, shade + 1, shade + 2))

    # Garis sudut emas/silver.
    for offset, col, wd in ((0, GOLD_BRIGHT, 2), (17, (110, 86, 36), 1), (30, SILVER_DARK, 1)):
        draw.line((offset, offset, 132, 132), fill=col, width=wd)
        draw.line((W-offset, offset, W-132, 132), fill=col, width=wd)
        draw.line((offset, H-offset, 132, H-132), fill=col, width=wd)
        draw.line((W-offset, H-offset, W-132, H-132), fill=col, width=wd)

    # Logo OMTOGEL.
    with Image.open(LOGO_FILE) as src:
        logo = src.convert("RGBA")
        alpha = logo.getchannel("A")
        bbox = alpha.getbbox()
        if bbox:
            logo = logo.crop(bbox)
        logo.thumbnail((710, 130), Image.Resampling.LANCZOS)
        img.paste(logo, ((W - logo.width) // 2, 18), logo)

    # Judul besar dan tebal.
    title_f = fit_font(draw, "PREDIKSI TOGEL", 960, 92, 74, stroke=2)
    center_text(draw, (40, 142, W-40, 242), "PREDIKSI TOGEL", title_f, WHITE, 2, BLACK)

    # Pasaran + tanggal.
    rounded_panel(draw, (36, 250, 1044, 394), 20, PANEL_2, GOLD_DARK, 2)
    market_f = fit_font(draw, data["pasaran"], 930, 76, 52, stroke=2)
    center_text(draw, (64, 258, 1016, 332), data["pasaran"], market_f, WHITE, 2, BLACK)
    dt = data["result_dt"]
    date_text = f"{HARI_ID[dt.strftime('%A')]}, {dt.day:02d} {BULAN_ID[dt.month]} {dt.year}"
    date_f = fit_font(draw, date_text, 800, 44, 36, stroke=1)
    center_text(draw, (130, 334, 950, 390), date_text, date_f, GOLD_BRIGHT, 1, BLACK)

    # BBFS / AI / CB / CM.
    y1, y2 = 412, 582
    margin, gap = 36, 8
    colw = (W - 2 * margin - 3 * gap) // 4
    fields = [
        ("BBFS", data["bbfs"], 72, 46),
        ("AI", data["ai"], 76, 50),
        ("CB", data["cb"], 72, 48),
        ("CM", data["cm"], 62, 42),
    ]
    for i, (label, value, val_size, val_min) in enumerate(fields):
        x1 = margin + i * (colw + gap)
        draw_label_value(draw, (x1, y1, x1 + colw, y2), label, value, 42, val_size, val_min)

    # 4D / 3D / 2D dibuat paling menonjol.
    rows = [
        ("4D BB", data["d4"], 62, 46),
        ("3D BB", data["d3"], 50, 36),
        ("2D BB", data["d2"], 46, 31),
    ]
    row_y = 598
    row_h = 108
    row_gap = 8
    label_w = 195
    for idx, (label, value, start_size, min_size) in enumerate(rows):
        top = row_y + idx * (row_h + row_gap)
        bottom = top + row_h
        rounded_panel(draw, (36, top, 1044, bottom), 16, PANEL, GOLD_DARK, 2)
        draw_gold_label(draw, (36, top, 36 + label_w, bottom), label)
        vf = fit_font(draw, value, 1044 - (36 + label_w) - 30, start_size, min_size, stroke=2)
        center_text(draw, (36 + label_w + 12, top, 1032, bottom), value, vf, WHITE, 2, BLACK)

    # SHIO tanpa karakter Unicode yang bisa menjadi kotak di Railway.
    sy1, sy2 = 946, 1072
    rounded_panel(draw, (36, sy1, 1044, sy2), 16, PANEL, GOLD_DARK, 2)
    center_text(draw, (330, sy1 + 2, 750, sy1 + 54), "SHIO", font(42), GOLD_BRIGHT, 1, BLACK)
    shio_f = fit_font(draw, data["shio"], 620, 74, 58, stroke=2)
    center_text(draw, (230, sy1 + 42, 850, sy2 - 4), data["shio"], shio_f, WHITE, 2, BLACK)
    # Ornamen geometris sederhana, tidak bergantung glyph/font.
    for cx in (132, 948):
        cy = (sy1 + sy2) // 2
        r = 34
        pts = [(cx, cy-r), (cx+r, cy), (cx, cy+r), (cx-r, cy)]
        draw.polygon(pts, outline=GOLD_BRIGHT)
        draw.polygon([(cx, cy-r+10), (cx+r-10, cy), (cx, cy+r-10), (cx-r+10, cy)], outline=SILVER)

    # TWIN / ANGKA PANAS.
    draw_label_value(draw, (36, 1088, 532, 1222), "TWIN", data["twin"], 42, 78, 60)
    draw_label_value(draw, (548, 1088, 1044, 1222), "ANGKA PANAS", data["hot"], 38, 88, 68)

    # Footer besar dan tebal.
    rounded_panel(draw, (68, 1238, 1012, 1324), 22, PANEL_2, GOLD_DARK, 2)
    draw_search_icon(draw, 116, 1280, 17, GOLD_BRIGHT, 5)
    draw_search_icon(draw, 964, 1280, 17, GOLD_BRIGHT, 5)
    footer = "CARI KAMI DI GOOGLE : OMTOGEL"
    footer_f = fit_font(draw, footer, 780, 43, 34, stroke=1)
    center_text(draw, (155, 1238, 925, 1324), footer, footer_f, WHITE, 1, BLACK)

    safe_market = "".join(c if c.isalnum() else "_" for c in data["pasaran"]).strip("_")
    out = OUTPUT_DIR / f"prediksi_{data['result_dt'].date().isoformat()}_{safe_market}_{POSTER_VERSION}.png"
    tmp = out.with_suffix(".tmp.png")
    img.save(tmp, "PNG", optimize=True)
    os.replace(tmp, out)
    return out
