#!/usr/bin/env python3
"""Generate static/social-preview.jpg (1200x630) for Open Graph sharing."""

import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "social-preview.jpg")
LOGO = os.path.join(ROOT, "static", "pookies-logo.png")
FRAME = "/tmp/pookies-hero-frame.jpg"

W, H = 1200, 630
G_DARK = (25, 47, 25)
G_MID = (43, 82, 32)
AMBER = (196, 122, 42)
CREAM = (246, 241, 230)
WHITE = (255, 255, 255)


def crop_cover(img, target_w, target_h):
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))
    return img.resize((target_w, target_h), Image.Resampling.LANCZOS)


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def main():
    if os.path.isfile(FRAME):
        bg = crop_cover(Image.open(FRAME).convert("RGB"), W, H)
    else:
        bg = Image.new("RGB", (W, H), G_DARK)

    canvas = bg.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (*G_DARK, 165))
    canvas = Image.alpha_composite(canvas, overlay)

    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad)
    for y in range(H):
        alpha = int(40 + (y / H) * 90)
        grad_draw.line([(0, y), (W, y)], fill=(15, 40, 30, alpha))
    canvas = Image.alpha_composite(canvas, grad)

    draw = ImageDraw.Draw(canvas)

    serif_bold = load_font("/System/Library/Fonts/Supplemental/Georgia Bold.ttf", 72)
    serif_reg = load_font("/System/Library/Fonts/Supplemental/Georgia.ttf", 34)
    sans_med = load_font("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 26)
    sans_reg = load_font("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    sans_sm = load_font("/System/Library/Fonts/Supplemental/Arial.ttf", 20)

    logo = Image.open(LOGO).convert("RGBA")
    logo_h = 88
    logo_w = int(logo.width * (logo_h / logo.height))
    logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

    badge_pad = 14
    badge_w = logo_w + badge_pad * 2
    badge_h = logo_h + badge_pad * 2
    badge = Image.new("RGBA", (badge_w, badge_h), (*CREAM, 235))
    badge_draw = ImageDraw.Draw(badge)
    badge_draw.rounded_rectangle(
        (0, 0, badge_w - 1, badge_h - 1),
        radius=18,
        outline=(255, 255, 255, 70),
        width=2,
    )
    badge.paste(logo, (badge_pad, badge_pad), logo)

    x0, y0 = 72, 58
    canvas.paste(badge, (x0, y0), badge)

    text_x = x0
    title_y = y0 + badge_h + 36
    draw.text((text_x, title_y), "Pookie's Pet Care", font=serif_bold, fill=WHITE)
    draw.text(
        (text_x, title_y + 86),
        "Dog Walking · Drop-Ins · Overnight Care",
        font=serif_reg,
        fill=CREAM,
    )
    draw.text(
        (text_x, title_y + 142),
        "Registered LLC · 5.0 Google Rating · South Denver Metro",
        font=sans_reg,
        fill=(220, 230, 220),
    )

    pill_text = "Text or Call Chris"
    pill_bbox = draw.textbbox((0, 0), pill_text, font=sans_med)
    pill_w = pill_bbox[2] - pill_bbox[0] + 48
    pill_h = pill_bbox[3] - pill_bbox[1] + 28
    pill_x = text_x
    pill_y = title_y + 198
    draw.rounded_rectangle(
        (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
        radius=pill_h // 2,
        fill=AMBER,
    )
    draw.text(
        (pill_x + 24, pill_y + 12),
        pill_text,
        font=sans_med,
        fill=WHITE,
    )

    # subtle gold accent line
    draw.rounded_rectangle((72, H - 18, W - 72, H - 12), radius=3, fill=AMBER)

    canvas.convert("RGB").save(OUT, "JPEG", quality=92, optimize=True)
    print(f"Saved {OUT} ({W}x{H})")


if __name__ == "__main__":
    main()
