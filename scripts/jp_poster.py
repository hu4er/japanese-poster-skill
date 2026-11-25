#!/usr/bin/env python3
"""
jp_poster.py - Japanese-style poster generator.

Deterministic PIL-based renderer producing editable, high-resolution posters
in five Japanese design archetypes (A-E). See references/style-guide.md.

Usage:
    python3 jp_poster.py --config spec.json --out poster.png
    python3 jp_poster.py --preset A --title "静静醒来" --out a.png
    python3 jp_poster.py --preset C --title "入口即化" --image food.jpg --out c.png

Config JSON example:
{
  "archetype": "A",
  "size": [900, 1200],
  "bg": "#F6F3EC",
  "title": "静静醒来",
  "subtitle": "A QUIET MORNING",
  "body": ["木与纸的", "作品展", "静静醒来"],
  "footer": "2026.09.22 - 09.29",
  "accent": "#C8A45C",
  "motifs": ["ensou", "dots"],
  "image": "/path/to/photo.jpg",   # optional, used by archetype C/E
  "seed": 42
}
"""

import argparse
import json
import math
import os
import random
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

# ---------------------------------------------------------------------------
# Font registry (macOS system fonts; graceful fallback to DejaVu)
# ---------------------------------------------------------------------------

# Two font tables: Japanese (Hiragino) and Chinese (Songti / PingFang).
# The active table is chosen per-poster by detect_language() in build(), so the
# poster's TEXT LANGUAGE always follows the user's original wording while the
# Japanese-style layout, palette and motifs are preserved.
FONT_FILES_JA = {
    "mincho":   "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
    "mincho_b": "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
    "gothic":   "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
    "gothic_b": "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
    "maru":     "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc",
    "pingfang": "/System/Library/Fonts/PingFang.ttc",
    "serif":    "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
    "sans":     "/System/Library/Fonts/HelveticaNeue.ttc",
}
FONT_INDEX_JA = {
    "mincho": 0, "mincho_b": 2, "gothic": 0, "gothic_b": 0,
    "maru": 1, "pingfang": 2, "serif": 0, "sans": 0,
}
FONT_FILES_ZH = {
    "mincho":   "/System/Library/Fonts/Supplemental/Songti.ttc",
    "mincho_b": "/System/Library/Fonts/Supplemental/Songti.ttc",
    "gothic":   "/System/Library/Fonts/PingFang.ttc",
    "gothic_b": "/System/Library/Fonts/PingFang.ttc",
    "maru":     "/System/Library/Fonts/PingFang.ttc",
    "pingfang": "/System/Library/Fonts/PingFang.ttc",
    "serif":    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "sans":     "/System/Library/Fonts/HelveticaNeue.ttc",
}
FONT_INDEX_ZH = {
    "mincho": 3, "mincho_b": 1, "gothic": 2, "gothic_b": 8,
    "maru": 2, "pingfang": 2, "serif": 6, "sans": 0,
}
FONT_CACHE = {}
LANG = "ja"  # set per poster by detect_language() in build()


def detect_language(texts):
    """Detect the language of poster copy: 'ja' (kana present), 'zh' (Han only), or 'latin'."""
    s = "".join(str(t) for t in texts if t)
    if any(0x3040 <= ord(c) <= 0x30FF for c in s):   # hiragana / katakana
        return "ja"
    if any(0x3400 <= ord(c) <= 0x9FFF for c in s):   # CJK ideographs
        return "zh"
    return "latin"


def set_language(lang):
    global LANG
    LANG = lang if lang in ("ja", "zh") else "ja"


def font(name, size):
    key = (LANG, name, size)
    if key in FONT_CACHE:
        return FONT_CACHE[key]
    files = FONT_FILES_ZH if LANG == "zh" else FONT_FILES_JA
    index = FONT_INDEX_ZH if LANG == "zh" else FONT_INDEX_JA
    path = files.get(name, files["gothic"])
    idx = index.get(name, 0)
    try:
        f = ImageFont.truetype(path, size, index=idx)
    except Exception:
        f = ImageFont.load_default()
    FONT_CACHE[key] = f
    return f


def auto_font(text, name, size):
    """Pick a CJK-capable font when the text contains Chinese/Japanese chars."""
    if any(ord(ch) > 0x2000 for ch in str(text)):
        return font("mincho", size)
    return font(name, size)


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

def hexrgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgba(hex_color, alpha=255):
    return (*hexrgb(hex_color), alpha)


def mix(c1, c2, t):
    a, b = hexrgb(c1), hexrgb(c2)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------------------
# Paper texture
# ---------------------------------------------------------------------------

def paper_texture(size, base="#F6F3EC", seed=0, strength=9, fibers=70):
    """Return an RGB image with subtle washi-paper grain and fibers."""
    rnd = random.Random(seed)
    w, h = size
    base_rgb = hexrgb(base)
    noise = Image.effect_noise(size, strength).convert("L")
    # Map noise into a narrow high range (236..255) so multiply only
    # gently darkens the paper, keeping the ivory base light.
    noise = noise.point(lambda v: 236 + int((v % 20) * 0.9))
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    img = ImageChops.multiply(Image.new("RGB", size, base_rgb), noise_rgb)
    d = ImageDraw.Draw(img, "RGBA")
    fiber_color = (*base_rgb, 26)
    for _ in range(fibers):
        x = rnd.randint(0, w)
        y = rnd.randint(0, h)
        length = rnd.randint(12, 70)
        ang = rnd.uniform(-0.35, 0.35) + (math.pi / 2 if rnd.random() < 0.5 else 0)
        x2 = x + int(math.cos(ang) * length)
        y2 = y + int(math.sin(ang) * length)
        d.line([(x, y), (x2, y2)], fill=fiber_color, width=1)
    return img


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def is_latin(ch):
    o = ord(ch)
    return (o < 128) or (0xFF01 <= o <= 0xFF5E)


def draw_vertical(draw, text, x, y, fnt, fill, line_h=None, tracking=1.0,
                  align="left", latin_rotate=True):
    """Draw vertical text (CJK upright, Latin rotated 90° CW). Returns bottom y."""
    if line_h is None:
        line_h = int(fnt.size * 1.35)
    cy = y
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            cy += line_h
            i += 1
            continue
        # collect latin run
        if is_latin(ch) and latin_rotate:
            j = i
            run = ""
            while j < len(text) and is_latin(text[j]) and text[j] != "\n":
                run += text[j]
                j += 1
            bbox = draw.textbbox((0, 0), run, font=fnt)
            rw = bbox[2] - bbox[0]
            rh = bbox[3] - bbox[1]
            layer = Image.new("RGBA", (max(rh + 6, 1), max(rw + 6, 1)), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.text((3 - bbox[0], 3 - bbox[1]), run, font=fnt, fill=fill)
            rot = layer.rotate(-90, expand=True)
            px = x - (rot.width - line_h) // 2 if align == "center" else x
            draw.bitmap((int(px), int(cy)), rot)
            cy += rw + tracking
            i = j
            continue
        # CJK char, upright
        bbox = draw.textbbox((0, 0), ch, font=fnt)
        cw = bbox[2] - bbox[0]
        cx = x - cw // 2 if align == "center" else x
        # punctuation nudged to upper-right of cell
        dx, dy = 0, 0
        if ch in "。、」，！？：；」』）":
            dx = int(fnt.size * 0.18)
            dy = int(fnt.size * 0.05)
        draw.text((cx + dx, cy + dy - bbox[1]), ch, font=fnt, fill=fill)
        cy += line_h * tracking
        i += 1
    return cy


def draw_tracking(draw, xy, text, fnt, fill, tracking=2, direction="ltr"):
    """Draw text with manual letter spacing (horizontal). Returns width used."""
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=fnt) if text else (0, 0, 0, 0)
    total = 0
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        w = draw.textbbox((0, 0), ch, font=fnt)[2]
        x += w + tracking
        total += w + tracking
    return total - tracking if text else 0


def center_text(draw, y, text, fnt, fill, canvas_w, tracking=2):
    widths = []
    for ch in text:
        widths.append(draw.textbbox((0, 0), ch, font=fnt)[2] + tracking)
    total = sum(widths) - tracking if widths else 0
    x = (canvas_w - total) / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += w
    return total


# ---------------------------------------------------------------------------
# Motifs
# ---------------------------------------------------------------------------

def sakura(draw, cx, cy, r, color, petals=5, seed=0, alpha=255):
    fill = (*hexrgb(color), alpha) if isinstance(color, str) else color
    for k in range(petals):
        ang = 2 * math.pi * k / petals - math.pi / 2
        # Rounded petal with a small V-notch at the outer tip (sakura signature)
        pr = max(r * 0.62, 3)
        local = []
        for t in range(13):
            a = math.pi * t / 12                     # 0..pi across the petal width
            px = -math.cos(a) * pr * 0.62            # base -> tip direction
            py = math.sin(a) * pr * 0.72             # half-width
            notch = 1 - 0.22 * (abs(px) / pr > 0.75 and abs(py) < pr * 0.16)
            local.append((px * notch, py))
        rot = math.degrees(ang) + 90
        ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        ox, oy = cx + math.cos(ang) * r * 0.5, cy + math.sin(ang) * r * 0.5
        pts = [(ox + px * ca - py * sa, oy + px * sa + py * ca) for px, py in local]
        draw.polygon(pts, fill=fill)
    draw.ellipse([cx - r * 0.17, cy - r * 0.17, cx + r * 0.17, cy + r * 0.17],
                 fill=(*hexrgb("#F6E7B8"), alpha))


def seigaiha(draw, x, y, w, h, color, alpha=90, rows=5, cols=8):
    """青海波 concentric wave scales."""
    c = (*hexrgb(color), alpha)
    rw = w / cols
    rh = h / rows
    for row in range(rows):
        for col in range(cols):
            ox = x + col * rw + (rw / 2 if row % 2 else 0)
            oy = y + row * rh
            for k in range(4):
                rr = rw * (0.22 + 0.14 * k)
                draw.arc([ox - rr, oy - rr, ox + rr, oy + rr], 180, 360, fill=c, width=2)


def asanoha(draw, x, y, size, color, alpha=60):
    """Simplified hemp-leaf hex grid."""
    c = (*hexrgb(color), alpha)
    s = size
    hh = math.sqrt(3) * s
    for row in range(-1, 10):
        for col in range(-1, 12):
            cx = x + col * s * 1.5
            cy = y + row * hh + (hh / 2 if col % 2 else 0)
            pts = [(cx + s * math.cos(math.pi / 3 * k),
                    cy + s * math.sin(math.pi / 3 * k)) for k in range(6)]
            draw.line(pts + [pts[0]], fill=c, width=1)
            for k in range(0, 6, 2):
                draw.line([pts[k], pts[(k + 3) % 6]], fill=c, width=1)


def ichimatsu(draw, x, y, w, h, cell, c1, c2, alpha=45):
    a = (*hexrgb(c1), alpha)
    b = (*hexrgb(c2), alpha)
    for r in range(int(h // cell) + 1):
        for c in range(int(w // cell) + 1):
            col = a if (r + c) % 2 == 0 else b
            draw.rectangle([x + c * cell, y + r * cell,
                            x + (c + 1) * cell, y + (r + 1) * cell], fill=col)


def ensou(draw, cx, cy, r, color, width=6, seed=0, alpha=230, gap=0.12):
    """Hand-drawn brush circle with organic width variation."""
    c = (*hexrgb(color), alpha)
    rnd = random.Random(seed)
    steps = 90
    start = rnd.uniform(0, math.pi * 2)
    for k in range(steps):
        t = start + (1 - gap) * 2 * math.pi * k / steps
        t2 = start + (1 - gap) * 2 * math.pi * (k + 1) / steps
        jitter = rnd.uniform(-1.5, 1.5)
        w = max(1, int(width * (0.7 + 0.5 * math.sin(k / steps * math.pi))))
        draw.line([
            (cx + (r + jitter) * math.cos(t), cy + (r + jitter) * math.sin(t)),
            (cx + (r + jitter) * math.cos(t2), cy + (r + jitter) * math.sin(t2)),
        ], fill=c, width=w)


def brush_stroke(draw, points, color, width=10, alpha=230, seed=0):
    """Tapered calligraphic stroke along a polyline."""
    c = (*hexrgb(color), alpha)
    rnd = random.Random(seed)
    for k in range(len(points) - 1):
        x1, y1 = points[k]
        x2, y2 = points[k + 1]
        t = k / max(len(points) - 1, 1)
        w = max(1, int(width * math.sin(math.pi * t) + 1))
        jx, jy = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
        draw.line([(x1 + jx, y1 + jy), (x2 + jx, y2 + jy)], fill=c, width=w)


def wave_lines(draw, x, y, w, n=5, color="#1F3A5F", alpha=120, amp=8, step=18):
    c = (*hexrgb(color), alpha)
    for row in range(n):
        yy = y + row * step
        pts = [(xx, yy + amp * math.sin(xx / 28 + row * 0.7))
               for xx in range(x, x + w, 4)]
        draw.line(pts, fill=c, width=2)


def dot_grid(draw, x, y, cols, rows, gap, r, color, alpha=120):
    c = (*hexrgb(color), alpha)
    for i in range(cols):
        for j in range(rows):
            cx, cy = x + i * gap, y + j * gap
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)


def fan(draw, cx, cy, r, color, alpha=220, ribs=9, angle=70):
    """Folding fan (uchiwa/ougi) silhouette."""
    c = (*hexrgb(color), alpha)
    a0 = math.radians(90 - angle / 2)
    a1 = math.radians(90 + angle / 2)
    pts = [(cx, cy)]
    for k in range(17):
        a = a0 + (a1 - a0) * k / 16
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    draw.polygon(pts, fill=c)
    lc = (*hexrgb("#F6F3EC"), min(alpha + 20, 255))
    for k in range(ribs):
        a = a0 + (a1 - a0) * k / (ribs - 1)
        draw.line([(cx, cy), (cx + r * 0.94 * math.cos(a), cy + r * 0.94 * math.sin(a))],
                  fill=lc, width=1)


def seal(draw, x, y, size, text, color="#C0392B", seed=0, alpha=235,
         shape="square", fontname="mincho_b"):
    """Vermillion seal stamp (朱印)."""
    c = (*hexrgb(color), alpha)
    rnd = random.Random(seed)
    pad = max(2, size // 10)
    if shape == "circle":
        draw.ellipse([x, y, x + size, y + size], outline=c, width=max(2, size // 14))
    else:
        radius = size // 7
        draw.rounded_rectangle([x, y, x + size, y + size], radius=radius,
                               outline=c, width=max(2, size // 14))
    f = font(fontname, max(int(size * 0.78), 8))
    bbox = draw.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = x + (size - tw) / 2 - bbox[0]
    ty = y + (size - th) / 2 - bbox[1]
    draw.text((tx, ty), text, font=f, fill=c)
    # erode for stamp texture
    for _ in range(max(6, size // 2)):
        ex = rnd.randint(x + pad, x + size - pad)
        ey = rnd.randint(y + pad, y + size - pad)
        r = rnd.randint(1, max(2, size // 18))
        draw.ellipse([ex - r, ey - r, ex + r, ey + r],
                     fill=(*hexrgb("#F6F3EC"), 0))  # no-op on RGBA draw of base


def mon(draw, cx, cy, r, color="#1F3A5F", alpha=230):
    """Family-crest-like geometric mark (three circles + triangle)."""
    c = (*hexrgb(color), alpha)
    draw.ellipse([cx - r, cy - r * 0.55, cx - r * 0.1, cy + r * 0.55], fill=c)
    draw.ellipse([cx + r * 0.1, cy - r * 0.55, cx + r, cy + r * 0.55], fill=c)
    draw.polygon([(cx, cy - r), (cx - r * 0.62, cy + r * 0.5),
                  (cx + r * 0.62, cy + r * 0.5)], fill=c)


def cloud_shape(draw, box, color, alpha=255, seed=0):
    """Soft cloud/flower outline used as photo frame in food posters."""
    x0, y0, x1, y1 = box
    c = (*hexrgb(color), alpha) if isinstance(color, str) else color
    rnd = random.Random(seed)
    w, h = x1 - x0, y1 - y0
    cx, cy = x0 + w / 2, y0 + h / 2
    pts = []
    for k in range(48):
        a = 2 * math.pi * k / 48
        rr = 1 + 0.045 * math.sin(5 * a + 1) + 0.025 * math.sin(9 * a)
        px = cx + (w / 2) * rr * math.cos(a)
        py = cy + (h / 2) * rr * math.sin(a)
        pts.append((px, py))
    draw.polygon(pts, fill=c)
    return pts


def rain_lines(draw, x0, y0, x1, y1, color="#8FA6B8", alpha=90, seed=0,
               count=70, length=26, slant=0.35):
    """Fine slanting rain strokes filling a region."""
    rnd = random.Random(seed)
    c = (*hexrgb(color), alpha)
    for _ in range(count):
        x = rnd.randint(int(x0), int(x1))
        y = rnd.randint(int(y0), int(y1))
        ln = rnd.randint(int(length * 0.5), int(length * 1.5))
        draw.line([(x, y), (int(x - ln * slant), y + ln)], fill=c, width=1)


def umbrella(draw, cx, cy, r, color, ribs=8, alpha=235, seed=0):
    """Hand-drawn umbrella: domed canopy with scalloped hem and hooked handle."""
    c = (*hexrgb(color), alpha)
    edge = (*hexrgb("#F6F3EC"), min(alpha, 220))
    # dome (top half)
    draw.pieslice([cx - r, cy - r * 0.86, cx + r, cy + r * 0.86],
                  180, 360, fill=c)
    # scalloped hem: small downward bumps along the baseline
    seg = 2 * r / ribs
    for i in range(ribs):
        x0 = cx - r + i * seg
        draw.pieslice([x0, cy - 1, x0 + seg, cy + seg * 0.42], 0, 180, fill=c)
    # ribs
    for i in range(1, ribs):
        x = cx - r + i * seg
        draw.line([(cx, cy - r * 0.86), (x, cy + 2)], fill=edge, width=1)
    # shaft + hook
    draw.line([(cx, cy - r * 0.86), (cx, cy + r * 1.0)],
              fill=(*hexrgb(color), 235), width=max(2, r // 45))
    rnd = random.Random(seed)
    hook_r = r * 0.16
    draw.arc([cx - hook_r, cy + r * 0.7, cx + hook_r, cy + r * 1.05],
             0, 200, fill=c, width=max(2, r // 45))


def person(draw, x, ground_y, height, color, alpha=235, seed=0):
    """Simple hand-drawn standing figure silhouette (adult or child)."""
    c = (*hexrgb(color), alpha)
    hr = height * 0.115                 # head radius
    hy = ground_y - height + hr         # head center y
    # head
    draw.ellipse([x - hr, hy - hr, x + hr, hy + hr], fill=c)
    # coat / body trapezoid
    bw = height * 0.24
    draw.polygon([(x - bw * 0.46, hy + hr * 0.9),
                  (x + bw * 0.46, hy + hr * 0.9),
                  (x + bw * 0.66, ground_y - height * 0.06),
                  (x - bw * 0.66, ground_y - height * 0.06)], fill=c)
    # legs
    leg_h = height * 0.16
    lw = max(2, int(height * 0.045))
    draw.line([(x - bw * 0.28, ground_y - leg_h), (x - bw * 0.30, ground_y)],
              fill=c, width=lw)
    draw.line([(x + bw * 0.28, ground_y - leg_h), (x + bw * 0.30, ground_y)],
              fill=c, width=lw)


def fried_chicken(draw, cx, cy, r, seed=0, alpha=240):
    """Stylized karaage / fried-chicken pieces: golden craggy nuggets + parsley."""
    rnd = random.Random(seed)
    gold = ["#D9A441", "#C98A2E", "#E0B055", "#BE7C28"]
    dark = "#8A5A20"
    # a paper basket / plate
    draw.ellipse([cx - r * 1.05, cy - r * 0.72, cx + r * 1.05, cy + r * 0.82],
                 fill=(*hexrgb("#FBF6EA"), 235), outline=(*hexrgb(dark), 90), width=2)
    # craggy nuggets
    for k in range(6):
        ang = 2 * math.pi * k / 6 - math.pi / 2 + rnd.uniform(-0.2, 0.2)
        fx = cx + math.cos(ang) * r * (0.34 if k == 0 else 0.46)
        fy = cy + math.sin(ang) * r * (0.24 if k == 0 else 0.30)
        rr = r * (0.30 if k == 0 else rnd.uniform(0.23, 0.29))
        # irregular polygon for crispy edge
        pts = []
        for t in range(14):
            a = 2 * math.pi * t / 14
            jag = 1 + rnd.uniform(-0.16, 0.16)
            pts.append((fx + rr * jag * math.cos(a),
                        fy + rr * jag * math.sin(a) * 0.86))
        draw.polygon(pts, fill=(*hexrgb(gold[k % len(gold)]), alpha))
        # golden highlight + a few darker crispy specks
        draw.ellipse([fx - rr * 0.42, fy - rr * 0.46, fx + rr * 0.28, fy - rr * 0.02],
                     fill=(*hexrgb("#F2CE82"), 150))
        for _ in range(4):
            sx = fx + rnd.uniform(-rr * 0.6, rr * 0.6)
            sy = fy + rnd.uniform(-rr * 0.5, rr * 0.5)
            d0 = rnd.uniform(1.5, 3.5)
            draw.ellipse([sx - d0, sy - d0, sx + d0, sy + d0],
                         fill=(*hexrgb(dark), 110))
    # parsley flecks
    for _ in range(9):
        px = cx + rnd.uniform(-r * 0.85, r * 0.85)
        py = cy + rnd.uniform(-r * 0.5, r * 0.6)
        d0 = rnd.uniform(3, 6)
        draw.ellipse([px - d0, py - d0 * 0.6, px + d0, py + d0 * 0.6],
                     fill=(*hexrgb("#6E8B4A"), 210))


def puddles(draw, x0, y0, x1, y1, color="#9FB3C2", alpha=80, seed=0, count=4):
    """Shallow puddle ellipses with ripple rings on the ground."""
    rnd = random.Random(seed)
    c = (*hexrgb(color), alpha)
    for _ in range(count):
        px = rnd.randint(int(x0), int(x1))
        py = rnd.randint(int(y0), int(y1))
        pw = rnd.randint(30, 70)
        ph = rnd.randint(8, 16)
        draw.ellipse([px - pw, py - ph, px + pw, py + ph], outline=c, width=2)
        draw.ellipse([px - pw * 0.55, py - ph * 0.5, px + pw * 0.55, py + ph * 0.5],
                     outline=c, width=1)


def frame(draw, box, color, width=2, alpha=100, inset=0):
    c = (*hexrgb(color), alpha)
    x0, y0, x1, y1 = box
    draw.rectangle([x0 + inset, y0 + inset, x1 - inset, y1 - inset],
                   outline=c, width=width)


# ---------------------------------------------------------------------------
# Image compositing helper (for user photos in archetype C / E)
# ---------------------------------------------------------------------------

def paste_in_shape(base, image_path, box, shape="cloud", seed=0):
    """Paste a photo clipped to a soft shape. Returns modified base."""
    if not image_path or not os.path.exists(image_path):
        return base
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    photo = Image.open(image_path).convert("RGBA")
    # cover fit
    pr = photo.width / photo.height
    br = w / h
    if pr > br:
        nw = int(photo.height * br)
        photo = photo.crop(((photo.width - nw) // 2, 0, (photo.width + nw) // 2, photo.height))
    else:
        nh = int(photo.width / br)
        photo = photo.crop((0, (photo.height - nh) // 2, photo.width, (photo.height + nh) // 2))
    photo = photo.resize((w, h), Image.LANCZOS)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    if shape == "circle":
        md.ellipse([0, 0, w - 1, h - 1], fill=255)
    elif shape == "hexagon":
        pts = [(w * (0.25 + 0.5 * k / 2), h * (0.02 if k % 2 == 0 else 0.98))
               for k in range(4)]
        pts = [(w * 0.25, h * 0.02), (w * 0.75, h * 0.02), (w, h * 0.5),
               (w * 0.75, h * 0.98), (w * 0.25, h * 0.98), (0, h * 0.5)]
        md.polygon(pts, fill=255)
    else:  # cloud / flower
        rnd = random.Random(seed)
        pts = []
        for k in range(64):
            a = 2 * math.pi * k / 64
            rr = 1 + 0.04 * math.sin(5 * a + 1) + 0.02 * math.sin(9 * a)
            pts.append((w / 2 + (w / 2) * rr * math.cos(a),
                        h / 2 + (h / 2) * rr * math.sin(a)))
        md.polygon(pts, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    base.paste(photo, (x0, y0), mask)
    return base


# ---------------------------------------------------------------------------
# Default presets per archetype
# ---------------------------------------------------------------------------

PRESETS = {
    "A": {
        "bg": "#F6F3EC", "accent": "#C8A45C", "ink": "#2B2B2B",
        "title_font": "mincho", "motifs": ["ensou", "dots"],
        "subtitle": "A QUIET MORNING",
        "body": ["木与纸的", "作品展", "静静醒来"],
        "footer": "2026.09.22 - 09.29",
    },
    "B": {
        "bg": "#F3EDE0", "accent": "#C0392B", "ink": "#1F3A5F",
        "title_font": "mincho_b", "motifs": ["mon", "seigaiha", "seal"],
        "subtitle": "MARUHACHI MARKET  EST. 1978",
        "body": ["新鲜", "市场"],
        "footer": "丸八食品馆   No.1",
        "side_left": "丸八食品馆", "side_right": "果蔬 鲜肉 鲜鱼 日用",
        "seal_text1": "鲜", "seal_text2": "福",
    },
    "C": {
        "bg": "#F7F0E6", "accent": "#C0392B", "ink": "#8B4A3A",
        "title_font": "maru", "motifs": ["sakura", "cloud"],
        "subtitle": "La Figure",
        "body": ["轻轻化开", "在舌尖"],
        "footer": "可爱点心  780元",
    },
    "D": {
        "bg": "#FFFFFF", "accent": "#C2185B", "ink": "#1A1A1A",
        "title_font": "gothic_b", "motifs": ["line_art", "dots"],
        "subtitle": "JAPANESE TYPOGRAPHY",
        "body": ["漂着剧", "版式展"],
        "footer": "2018.11.23 FRI  19:00",
    },
    "E": {
        "bg": "#F5F1E8", "accent": "#4A7C59", "ink": "#4A4A4A",
        "title_font": "mincho_b", "motifs": ["botanical", "seal"],
        "subtitle": "A POETIC EVENING",
        "body": ["花色已逝", "余韵长存"],
        "footer": "第13回  公众征集作品展",
    },
}


# ---------------------------------------------------------------------------
# Layout renderers
# ---------------------------------------------------------------------------

def layout_A(img, cfg, rnd):
    """Minimal Ma - huge negative space, one vertical phrase, subtle circle."""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    ink, acc = hexrgb(cfg["ink"]), hexrgb(cfg["accent"])
    m = int(w * 0.10)

    # thin frame
    frame(d, (m, m, w - m, h - m), cfg["ink"], width=2, alpha=55)

    # one soft ensou upper-left area
    ensou(d, int(w * 0.38), int(h * 0.30), int(w * 0.16),
          cfg["accent"], width=3, seed=cfg["seed"], alpha=95)

    # scattered short lines / dots
    for k in range(7):
        x = rnd.randint(int(w * 0.45), int(w * 0.82))
        y = rnd.randint(int(h * 0.45), int(h * 0.80))
        ln = rnd.randint(10, 34)
        d.line([(x, y), (x + ln, y + rnd.randint(-6, 6))], fill=(*ink, 130), width=2)
    dot_grid(d, int(w * 0.60), int(h * 0.18), 3, 3, 16, 2, cfg["accent"], 120)

    # main vertical title on right
    tf = font(cfg["title_font"], int(w * 0.082))
    draw_vertical(d, cfg["title"], int(w * 0.82), int(h * 0.16), tf,
                  (*ink, 255), line_h=int(w * 0.11), tracking=1.12, align="center")

    # small vertical body columns
    bf = font("mincho", max(int(w * 0.024), 12))
    x = int(w * 0.68)
    for col in cfg.get("body", [])[:3]:
        draw_vertical(d, col, x, int(h * 0.55), bf, (*ink, 210),
                      line_h=int(w * 0.037), tracking=1.05, align="center")
        x -= int(w * 0.06)

    # subtitle small serif
    sf = font("serif", max(int(w * 0.022), 11))
    d.text((m + 4, int(h * 0.08)), cfg.get("subtitle", ""), font=sf, fill=(*ink, 180))

    # footer
    ff = font("serif", max(int(w * 0.019), 10))
    draw_tracking(d, (m + 4, h - m - int(h * 0.055)), cfg.get("footer", ""),
                  ff, (*ink, 190), tracking=2)
    seal(d, int(w * 0.82), h - m - int(w * 0.09), int(w * 0.075),
         cfg.get("seal_text", "间"), cfg["accent"], cfg["seed"] + 1,
         alpha=205, shape="circle")


def layout_B(img, cfg, rnd):
    """Traditional pattern - central title, surrounding motifs, seals."""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    ink, acc = hexrgb(cfg["ink"]), hexrgb(cfg["accent"])
    m = int(w * 0.08)

    seigaiha(d, int(w * 0.06), int(h * 0.78), int(w * 0.88), int(h * 0.16),
             cfg["ink"], alpha=42, rows=3, cols=10)
    frame(d, (m, m, w - m, h - m), cfg["accent"], width=3, alpha=120)
    frame(d, (m + 7, m + 7, w - m - 7, h - m - 7), cfg["ink"], width=1, alpha=55)

    # crest above title
    mon(d, int(w * 0.5), int(h * 0.14), int(w * 0.085), cfg["ink"], 235)

    # main vertical title (two columns, right-to-left)
    tf = font(cfg["title_font"], int(w * 0.115))
    cols = cfg.get("body", [cfg["title"]])
    x = int(w * 0.62)
    for col in cols[:2]:
        draw_vertical(d, col, x, int(h * 0.24), tf, (*ink, 255),
                      line_h=int(w * 0.135), tracking=1.05, align="center")
        x -= int(w * 0.15)

    # big title char on left area
    sf = font("mincho_b", int(w * 0.10))
    d.text((int(w * 0.14), int(h * 0.30)), cfg["title"][0] if cfg["title"] else "",
           font=sf, fill=(*hexrgb(cfg["accent"]), 240))

    # sakura accents
    for k in range(5):
        sx = rnd.randint(int(w * 0.12), int(w * 0.88))
        sy = rnd.choice([rnd.randint(int(h * 0.07), int(h * 0.18)),
                         rnd.randint(int(h * 0.70), int(h * 0.86))])
        sakura(d, sx, sy, rnd.randint(int(w * 0.018), int(w * 0.032)),
               cfg["accent"], seed=cfg["seed"] + k, alpha=200)

    # side vertical info (configurable; defaults preserve the classic shop look)
    infof = font("mincho", max(int(w * 0.022), 12))
    draw_vertical(d, cfg.get("side_left", "丸八食品馆"), int(w * 0.12), int(h * 0.40),
                  infof, (*ink, 200), line_h=int(w * 0.035), align="center")
    draw_vertical(d, cfg.get("side_right", "果蔬 鲜肉 鲜鱼 日用"), int(w * 0.90),
                  int(h * 0.30), infof, (*ink, 200), line_h=int(w * 0.035),
                  align="center")

    # seals (configurable single-char text)
    seal(d, int(w * 0.78), int(h * 0.74), int(w * 0.095),
         cfg.get("seal_text1", "报"), cfg["accent"], cfg["seed"] + 2, alpha=225)
    seal(d, int(w * 0.14), int(h * 0.61), int(w * 0.07),
         cfg.get("seal_text2", "福"), cfg["accent"], cfg["seed"] + 3,
         alpha=210, shape="circle")

    # footer marks
    ff = font("serif", max(int(w * 0.018), 10))
    draw_tracking(d, (m + 2, h - m - int(h * 0.045)), cfg.get("subtitle", ""),
                  ff, (*ink, 170), tracking=2)
    draw_tracking(d, (int(w * 0.60), h - m - int(h * 0.045)), cfg.get("footer", ""),
                  ff, (*ink, 170), tracking=1)


def layout_C(img, cfg, rnd):
    """Washoku / Wagashi - soft bg, cloud-framed hero, right vertical poem."""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    ink, acc = hexrgb(cfg["ink"]), hexrgb(cfg["accent"])
    m = int(w * 0.08)

    # background pattern
    seigaiha(d, 0, int(h * 0.72), w, int(h * 0.28), cfg["accent"], alpha=26,
             rows=4, cols=14)

    # hero shape
    box = (int(w * 0.10), int(h * 0.16), int(w * 0.68), int(h * 0.66))
    cloud_shape(d, box, mix(cfg["bg"], "#FFFFFF", 0.6), alpha=230, seed=cfg["seed"])
    if cfg.get("image"):
        paste_in_shape(img, cfg["image"], box, shape="cloud", seed=cfg["seed"])
        d = ImageDraw.Draw(img, "RGBA")
    else:
        pcx, pcy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        pr = min(box[2] - box[0], box[3] - box[1]) * 0.36
        if cfg.get("dish") == "fried_chicken":
            fried_chicken(d, pcx, pcy, pr, seed=cfg["seed"] + 20)
        else:
            # stylized food illustration: plate + wagashi balls
            d.ellipse([pcx - pr, pcy - pr, pcx + pr, pcy + pr],
                      fill=(*hexrgb("#FFFFFF"), 220), outline=(*ink, 60), width=2)
            colors = ["#8B4A3A", "#7A8B5A", "#C8A45C", "#D98A8A"]
            for k in range(4):
                a = 2 * math.pi * k / 4 - math.pi / 4
                fx = pcx + math.cos(a) * pr * 0.48
                fy = pcy + math.sin(a) * pr * 0.48
                rr = pr * 0.24
                d.ellipse([fx - rr, fy - rr, fx + rr, fy + rr],
                          fill=(*hexrgb(colors[k]), 235))
                d.ellipse([fx - rr * 0.4, fy - rr * 0.4, fx + rr * 0.4, fy + rr * 0.4],
                          fill=(*hexrgb("#F6F3EC"), 120))

    # right vertical poem
    pf = font(cfg["title_font"], int(w * 0.072))
    draw_vertical(d, cfg["title"], int(w * 0.86), int(h * 0.18), pf,
                  (*ink, 255), line_h=int(w * 0.10), tracking=1.15, align="center")
    bf = font("mincho", max(int(w * 0.026), 13))
    x = int(w * 0.71)
    for col in cfg.get("body", [])[:2]:
        draw_vertical(d, col, x, int(h * 0.38), bf, (*ink, 210),
                      line_h=int(w * 0.040), tracking=1.05, align="center")
        x -= int(w * 0.055)

    # sakura corners
    for k in range(3):
        sakura(d, rnd.randint(int(w * 0.08), int(w * 0.30)),
               rnd.choice([int(h * 0.10), int(h * 0.72)]),
               rnd.randint(int(w * 0.016), int(w * 0.026)), "#E8A9B5",
               seed=cfg["seed"] + k, alpha=190)

    # bottom info band
    d.rectangle([int(w * 0.08), int(h * 0.78), int(w * 0.92), int(h * 0.90)],
                fill=(*hexrgb("#FFFFFF"), 150))
    sf = font("serif", max(int(w * 0.023), 12))
    d.text((int(w * 0.11), int(h * 0.795)), cfg.get("subtitle", ""), font=sf,
           fill=(*ink, 190))
    ff = font("mincho", max(int(w * 0.026), 13))
    d.text((int(w * 0.11), int(h * 0.835)), cfg.get("footer", ""), font=ff,
           fill=(*ink, 225))
    seal(d, int(w * 0.83), int(h * 0.815), int(w * 0.065),
         cfg.get("seal_text", "果"), cfg["accent"],
         cfg["seed"] + 4, alpha=220)


def layout_D(img, cfg, rnd):
    """Avant-garde typography - huge type, diagonal rules, line art."""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    ink, acc = hexrgb(cfg["ink"]), hexrgb(cfg["accent"])

    # diagonal accent field
    d.polygon([(0, 0), (int(w * 0.62), 0), (0, int(h * 0.42))],
              fill=(*hexrgb(cfg["accent"]), 22))
    for k in range(9):
        y = int(h * 0.05) + k * int(h * 0.024)
        d.line([(0, y), (int(w * (0.48 - k * 0.035)), y - int(h * 0.03))],
               fill=(*acc, 28 + k * 6), width=2)

    # abstract line art (forest/branch motif)
    ox, oy = int(w * 0.10), int(h * 0.50)
    brush_stroke(d, [(ox, oy + 180), (ox + 20, oy + 90), (ox + 10, oy)],
                 "#1A1A1A", width=9, alpha=210, seed=cfg["seed"])
    for k in range(7):
        bx = ox + 10
        by = oy + 20 + k * 24
        ex = bx + rnd.choice([-1, 1]) * rnd.randint(40, 95)
        ey = by - rnd.randint(25, 60)
        brush_stroke(d, [(bx, by), ((bx + ex) / 2, (by + ey) / 2 - 12), (ex, ey)],
                     "#1A1A1A", width=4, alpha=180, seed=cfg["seed"] + k)
        d.ellipse([ex - 7, ey - 7, ex + 7, ey + 7], fill=(*acc, 190))

    # giant title - vertical stacked characters
    tf = font(cfg["title_font"], int(w * 0.15))
    draw_vertical(d, cfg["title"][:5], int(w * 0.80), int(h * 0.10), tf,
                  (*ink, 250), line_h=int(w * 0.17), tracking=1.0, align="center")

    # subtitle along left, small
    sf = font("gothic", max(int(w * 0.022), 12))
    draw_vertical(d, cfg.get("subtitle", ""), int(w * 0.09), int(h * 0.10), sf,
                  (*acc, 220), line_h=int(w * 0.034), align="center")

    # body text columns bottom-left
    bf = font("mincho", max(int(w * 0.025), 13))
    yy = int(h * 0.74)
    for col in cfg.get("body", [])[:2]:
        d.text((int(w * 0.10), yy), col, font=bf, fill=(*ink, 220))
        yy += int(h * 0.045)

    # footer
    ff = font("serif", max(int(w * 0.020), 11))
    draw_tracking(d, (int(w * 0.10), h - int(h * 0.075)), cfg.get("footer", ""),
                  ff, (*ink, 190), tracking=2)
    seal(d, int(w * 0.84), h - int(h * 0.10), int(w * 0.07),
         cfg.get("seal_text", "剧"), cfg["accent"],
         cfg["seed"] + 5, alpha=230, shape="circle")


def layout_E(img, cfg, rnd):
    """Hand-drawn poetic - botanical illustration, watercolor blooms."""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    ink, acc = hexrgb(cfg["ink"]), hexrgb(cfg["accent"])
    m = int(w * 0.10)

    # watercolor blooms
    for k in range(3):
        bx = rnd.randint(int(w * 0.15), int(w * 0.75))
        by = rnd.randint(int(h * 0.20), int(h * 0.70))
        br = rnd.randint(int(w * 0.12), int(w * 0.25))
        for ring in range(5):
            rr = br * (1 - ring * 0.16)
            d.ellipse([bx - rr, by - rr, bx + rr, by + rr],
                      fill=(*hexrgb(cfg["accent"]), 8))

    scene = cfg.get("scene", "botanical")
    if scene == "rain_pickup":
        # rainy-day scene: rain, umbrella, adult + child holding hands, puddles
        rain_lines(d, int(w * 0.08), int(h * 0.16), int(w * 0.66), int(h * 0.78),
                   "#8FA6B8", alpha=80, seed=cfg["seed"] + 11, count=90,
                   length=int(w * 0.035))
        puddles(d, int(w * 0.10), int(h * 0.80), int(w * 0.60), int(h * 0.88),
                "#9FB3C2", alpha=70, seed=cfg["seed"] + 12, count=4)
        ux, uy, ur = int(w * 0.36), int(h * 0.46), int(w * 0.20)
        umbrella(d, ux, uy, ur, "#6E8CA0", ribs=8, alpha=235, seed=cfg["seed"] + 13)
        # adult on the left, child on the right, sharing the umbrella
        gy = int(h * 0.80)
        person(d, int(w * 0.29), gy, int(h * 0.24), "#3F4A52",
               alpha=235, seed=cfg["seed"] + 14)
        person(d, int(w * 0.44), gy, int(h * 0.16), cfg["accent"],
               alpha=235, seed=cfg["seed"] + 15)
        # joined hands
        d.line([(int(w * 0.33), int(h * 0.68)), (int(w * 0.41), int(h * 0.72))],
               fill=(*hexrgb("#3F4A52"), 235), width=5)
    else:
        # botanical branch (default)
        ox, oy = int(w * 0.16), int(h * 0.86)
        brush_stroke(d, [(ox, oy), (ox + 60, oy - 140), (ox + 40, oy - 300),
                         (ox + 120, oy - 460)], "#4A4A4A", width=6, alpha=200,
                     seed=cfg["seed"])
        for k in range(6):
            by = oy - 90 - k * 62
            bx = ox + 50 + (k % 2) * 12
            ex = bx + rnd.choice([-1, 1]) * rnd.randint(45, 90)
            ey = by - rnd.randint(20, 45)
            brush_stroke(d, [(bx, by), (ex, ey)], "#4A4A4A", width=3, alpha=170,
                         seed=cfg["seed"] + k)
            sakura(d, ex, ey, rnd.randint(11, 20), "#E8A9B5", seed=cfg["seed"] + k,
                   alpha=200)
        # tiny bird
        bx, by = int(w * 0.60), int(h * 0.34)
        d.ellipse([bx - 16, by - 9, bx + 16, by + 9], fill=(*hexrgb("#C97B6B"), 210))
        d.polygon([(bx + 14, by), (bx + 30, by - 7), (bx + 14, by + 6)],
                  fill=(*hexrgb("#C97B6B"), 210))
        d.ellipse([bx + 9, by - 4, bx + 13, by], fill=(*ink, 220))

    # vertical poetic title
    tf = font(cfg["title_font"], int(w * 0.085))
    draw_vertical(d, cfg["title"], int(w * 0.86), int(h * 0.14), tf,
                  (*ink, 245), line_h=int(w * 0.12), tracking=1.12, align="center")
    bf = font("mincho", max(int(w * 0.026), 13))
    x = int(w * 0.72)
    for col in cfg.get("body", [])[:2]:
        draw_vertical(d, col, x, int(h * 0.30), bf, (*ink, 205),
                      line_h=int(w * 0.040), tracking=1.05, align="center")
        x -= int(w * 0.055)

    # seal + footer (seal text configurable)
    seal(d, int(w * 0.80), h - m - int(w * 0.10), int(w * 0.075),
         cfg.get("seal_text", "韵"), cfg["accent"], cfg["seed"] + 6, alpha=225)
    ff = font("serif", max(int(w * 0.020), 11))
    draw_tracking(d, (m + 2, h - m - int(h * 0.05)), cfg.get("footer", ""),
                  ff, (*ink, 180), tracking=2)
    sf = font("serif", max(int(w * 0.019), 10))
    d.text((m + 2, int(h * 0.06)), cfg.get("subtitle", ""), font=sf,
           fill=(*ink, 160))


RENDERERS = {"A": layout_A, "B": layout_B, "C": layout_C, "D": layout_D, "E": layout_E}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build(cfg, out_path):
    arch = str(cfg.get("archetype", "A")).upper()
    if arch not in RENDERERS:
        raise ValueError(f"Unknown archetype {arch}; choose from {list(RENDERERS)}")
    preset = PRESETS[arch]
    merged = dict(preset)
    merged.update({k: v for k, v in cfg.items() if v is not None})
    cfg = merged
    # Choose the font family from the actual poster copy so the text language
    # follows the user's original wording (Chinese -> Songti/PingFang,
    # Japanese -> Hiragino). An explicit `language` config overrides detection.
    copy = [cfg.get("title"), cfg.get("subtitle"), cfg.get("footer"),
            cfg.get("side_left"), cfg.get("side_right"), cfg.get("seal_text"),
            cfg.get("seal_text1"), cfg.get("seal_text2")]
    copy += list(cfg.get("body", []))
    lang = cfg.get("language") or detect_language(copy)
    set_language(lang)
    w, h = cfg.get("size", [900, 1200])
    seed = int(cfg.get("seed", 42))
    rnd = random.Random(seed)
    cfg["seed"] = seed

    img = paper_texture((w, h), cfg["bg"], seed=seed)
    RENDERERS[arch](img, cfg, rnd)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.convert("RGB").save(out_path, "PNG")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Generate a Japanese-style poster")
    ap.add_argument("--config", help="JSON config file")
    ap.add_argument("--preset", choices=list(RENDERERS), help="Archetype A-E")
    ap.add_argument("--title", help="Main title text")
    ap.add_argument("--subtitle", help="Small subtitle")
    ap.add_argument("--footer", help="Footer info")
    ap.add_argument("--body", nargs="*", help="Body text columns")
    ap.add_argument("--bg", help="Background hex color")
    ap.add_argument("--accent", help="Accent hex color")
    ap.add_argument("--image", help="Optional photo to composite (archetype C/E)")
    ap.add_argument("--size", nargs=2, type=int, metavar=("W", "H"))
    ap.add_argument("--seed", type=int)
    ap.add_argument("--out", default="poster.png")
    args = ap.parse_args()

    cfg = {}
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
    cli = {k: v for k, v in vars(args).items()
           if k not in ("config", "out") and v is not None}
    cfg.update(cli)
    if args.preset:
        cfg["archetype"] = args.preset
    if not cfg.get("archetype"):
        ap.error("Specify --preset A-E or an archetype in --config")

    path = build(cfg, args.out)
    print(json.dumps({"out": os.path.abspath(path), "archetype": cfg["archetype"],
                      "size": cfg.get("size", [900, 1200])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
