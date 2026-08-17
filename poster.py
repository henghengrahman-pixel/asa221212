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

    def split_values(text, sep=" - "):
        return text.split(sep)

    checks = [("d4", 4, 4), ("d3", 3, 7), ("d2", 2, 10)]
    for key, length, count in checks:
        values = split_values(data[key])
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


def fit_font(draw, text, max_width, start_size, min_size=18, bold=True):
    for size in range(start_size, min_size - 1, -2):
        fnt = font(size, bold)
        box = draw.textbbox((0, 0), text, font=fnt)
        if box[2] - box[0] <= max_width:
            return fnt
    return font(min_size, bold)


def center_text(draw, box, text, fnt, fill=(242, 242, 242), stroke=0, stroke_fill=(0, 0, 0)):
    x1, y1, x2, y2 = box
    bb = draw.textbbox((0, 0), text, font=fnt, stroke_width=stroke)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    x = x1 + (x2 - x1 - w) / 2
    y = y1 + (y2 - y1 - h) / 2 - bb[1]
    draw.text((x, y), text, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


def rounded_panel(draw, box, radius=18, fill=(8, 10, 12), outline=(180, 185, 190), width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_label_value(draw, x1, y1, x2, y2, label, value):
    rounded_panel(draw, (x1, y1, x2, y2), 15, (6, 8, 10), (180, 185, 190), 2)
    split = y1 + 58
    draw.line((x1, split, x2, split), fill=(90, 95, 100), width=1)
    center_text(draw, (x1, y1, x2, split), label, font(29), (220, 177, 74))
    value_font = fit_font(draw, value, x2 - x1 - 28, 42, 22)
    center_text(draw, (x1, split, x2, y2), value, value_font, (245, 245, 245))


def create_poster(data):
    validate_prediction_data(data)
    if not LOGO_FILE.exists():
        raise FileNotFoundError(f"Logo OMTOGEL tidak ditemukan: {LOGO_FILE}")

    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), (3, 4, 5))
    draw = ImageDraw.Draw(img)
    silver = (205, 210, 214)
    gold = (220, 177, 74)

    for y in range(0, H, 3):
        shade = int(4 + 10 * (1 - abs(y - H / 2) / (H / 2)))
        draw.rectangle((0, y, W, min(y + 2, H)), fill=(shade, shade + 1, shade + 2))

    for width, inset, tone in ((3, 0, silver), (1, 16, (90, 95, 100)), (1, 28, (55, 60, 65))):
        draw.line((inset, inset, 130, 130), fill=tone, width=width)
        draw.line((W - inset, inset, W - 130, 130), fill=tone, width=width)
        draw.line((inset, H - inset, 130, H - 130), fill=tone, width=width)
        draw.line((W - inset, H - inset, W - 130, H - 130), fill=tone, width=width)

    with Image.open(LOGO_FILE) as src:
        logo = src.convert("RGBA")
        alpha = logo.getchannel("A")
        bbox = alpha.getbbox()
        if bbox:
            logo = logo.crop(bbox)
        logo.thumbnail((760, 145), Image.Resampling.LANCZOS)
        img.paste(logo, ((W - logo.width) // 2, 32), logo)

    center_text(draw, (40, 175, 1040, 260), "PREDIKSI TOGEL", font(66), (238, 238, 238), 1, (90, 90, 90))

    rounded_panel(draw, (45, 275, 1035, 402), 18, (7, 9, 11), silver, 2)
    market_f = fit_font(draw, data["pasaran"], 900, 47, 28)
    center_text(draw, (70, 285, 1010, 345), data["pasaran"], market_f, (246, 246, 246))
    dt = data["result_dt"]
    date_text = f"{HARI_ID[dt.strftime('%A')]}, {dt.day:02d} {BULAN_ID[dt.month]} {dt.year}"
    center_text(draw, (70, 345, 1010, 394), date_text, font(27), gold)

    y1, y2 = 422, 572
    margin, gap = 45, 8
    colw = (W - 2 * margin - 3 * gap) // 4
    fields = [("BBFS", data["bbfs"]), ("AI", data["ai"]), ("CB", data["cb"]), ("CM", data["cm"])]
    for i, (label, value) in enumerate(fields):
        x1 = margin + i * (colw + gap)
        draw_label_value(draw, x1, y1, x1 + colw, y2, label, value)

    rows = [("4D BB", data["d4"]), ("3D BB", data["d3"]), ("2D BB", data["d2"])]
    row_y, row_h = 592, 112
    for idx, (label, value) in enumerate(rows):
        top = row_y + idx * (row_h + 10)
        rounded_panel(draw, (45, top, 1035, top + row_h), 16, (7, 9, 11), silver, 2)
        label_w = 205
        draw.rounded_rectangle((45, top, 45 + label_w, top + row_h), radius=16, fill=(205, 208, 210), outline=silver, width=1)
        draw.rectangle((45 + label_w - 16, top, 45 + label_w, top + row_h), fill=(205, 208, 210))
        center_text(draw, (45, top, 45 + label_w, top + row_h), label, font(38), (10, 10, 10))
        value_font = fit_font(draw, value, 1035 - (45 + label_w) - 35, 35 if label != "2D BB" else 30, 20)
        center_text(draw, (45 + label_w + 10, top, 1025, top + row_h), value, value_font, (242, 242, 242))

    sy1, sy2 = 954, 1075
    rounded_panel(draw, (45, sy1, 1035, sy2), 16, (7, 9, 11), silver, 2)
    center_text(draw, (180, sy1 + 8, 900, sy1 + 55), "SHIO", font(29), gold)
    center_text(draw, (180, sy1 + 45, 900, sy2 - 8), data["shio"], font(47), (246, 246, 246))
    center_text(draw, (65, sy1 + 15, 185, sy2 - 10), "◆", font(58), silver)
    center_text(draw, (895, sy1 + 15, 1015, sy2 - 10), "◆", font(58), silver)

    draw_label_value(draw, 45, 1092, 532, 1221, "TWIN", data["twin"])
    draw_label_value(draw, 548, 1092, 1035, 1221, "ANGKA PANAS", data["hot"])

    rounded_panel(draw, (75, 1247, 1005, 1319), 22, (8, 10, 12), (160, 165, 170), 2)
    footer = "CARI KAMI DI GOOGLE : OMTOGEL"
    footer_font = fit_font(draw, footer, 850, 31, 22)
    center_text(draw, (115, 1247, 965, 1319), footer, footer_font, (238, 238, 238))

    safe_market = "".join(c if c.isalnum() else "_" for c in data["pasaran"]).strip("_")
    out = OUTPUT_DIR / f"prediksi_{data['result_dt'].date().isoformat()}_{safe_market}.png"
    tmp = out.with_suffix(".tmp.png")
    img.save(tmp, "PNG", optimize=True)
    os.replace(tmp, out)
    return out
