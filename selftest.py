import json
from datetime import datetime
from pathlib import Path

import pytz
from PIL import Image
from poster import generate_prediction_data, create_poster, validate_prediction_data

BASE_DIR = Path(__file__).resolve().parent
TZ = pytz.timezone("Asia/Jakarta")

with open(BASE_DIR / "jadwal.json", "r", encoding="utf-8") as f:
    schedule = json.load(f)

assert schedule, "jadwal.json kosong"
errors = []
for market, hhmm in schedule.items():
    try:
        hh, mm = map(int, hhmm.split(":"))
        dt = TZ.localize(datetime(2026, 8, 18, hh, mm))
        d1 = generate_prediction_data(market, dt)
        d2 = generate_prediction_data(market, dt)
        assert d1["bbfs"] == d2["bbfs"], "generator tidak konsisten"
        assert d1["d4"] == d2["d4"], "generator tidak konsisten"
        validate_prediction_data(d1)
        path = create_poster(d1)
        assert path.exists() and path.stat().st_size > 10_000, "poster kosong/kecil"
        with Image.open(path) as im:
            assert im.size == (1080, 1350), f"ukuran poster salah: {im.size}"
            im.verify()
    except Exception as exc:
        errors.append(f"{market}: {exc}")

if errors:
    raise SystemExit("SELFTEST GAGAL:\n" + "\n".join(errors))

print(f"SELFTEST OK: {len(schedule)} pasaran, generator + validasi angka + poster semuanya lolos.")
