# -*- coding: utf-8 -*-
"""
make_qr.py — توليد رمز QR لرابط المنصة بعد نشرها (لشريحة العرض الحيّ الاحتياطي).

    python mirwa/make_qr.py https://your-app.streamlit.app

يحفظ الصورة في mirwa/screenshots/app_qr.png
"""
import sys
from pathlib import Path
import qrcode

OUT = Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(exist_ok=True)


def make(url: str, path: Path):
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=12, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0a2d6e", back_color="white")
    img.save(path)
    print("saved", path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("الاستخدام: python mirwa/make_qr.py <رابط التطبيق>")
        sys.exit(1)
    make(sys.argv[1].strip(), OUT / "app_qr.png")
