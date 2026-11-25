---
name: japanese-poster
display_name: 日式海报生成器
display_name_en: Japanese Poster Generator
description: 一键生成日式风格海报，支持极简留白、传统纹样、和食美食、前卫排版、手绘诗意五种版式，文案跟随用户原文，输出高清PNG。适用于日式海报、和风海报、日系排版海报、美食海报、展览海报等需求。
description_zh: 一句话主题即可生成日式风格海报，含五种版式；文案不翻译成日文，中文输入就输出中文海报，呈现竖排文字、和纸肌理、朱印与传统纹样。
description_en: Generate Japanese-style posters from one topic with five layouts. Copy follows your original language, with vertical typography, washi texture, seals and traditional motifs, output as high-resolution PNG.
examples_zh:
- 用日式海报 skill 生成一张超市主题的海报
- 做一个极简留白风格的展览海报，标题是花与纸
- 用和食风格生成美食海报，标题是入口即化
examples_en:
- Generate a Japanese poster about picking up a child in the rain
- Make a minimal Japanese exhibition poster titled Ma
- Create a Japanese food poster for fried chicken
version: 1.0.0
author: humeiping
---


# Japanese Poster Generator

Generate authentic Japanese-style posters with correct vertical typography, washi-paper texture, seals (朱印), and traditional motifs — deterministic, reproducible, and one-click.

## When to Use

- User requests a Japanese / 和风 / 日式 poster, 海报, 招贴, or 展陈设计.
- User wants a poster in a Japanese aesthetic (minimal, wabi-sabi, traditional, food/wagashi, avant-garde, hand-drawn).
- User references Japanese poster design, 日式排版, 和风配色, or wants to emulate the style of Japanese graphic design.

## Core Workflow

### Step 1: Understand the request
Extract from the user's message:
- **主题/标题** (title text) — the single most important phrase.
- **用途** (use case) — food, event/exhibition, brand/shop, poem/art, product.
- **副标题/正文/落款** (subtitle, body lines, footer info) if provided.
- **偏好** — style archetype, colors, whether to include a photo.

**Language rule (important):** Poster copy follows the user's original wording. Do NOT translate the user's text into Japanese — Chinese input stays Chinese, English stays English. The "Japanese style" refers only to the visual language (layout, palette, motifs, vertical typesetting), not the text language. If the user writes in Chinese, write all poster copy in Chinese; if in Japanese, use Japanese. When filling in copy for an underspecified topic, match the language of the user's message. Keep phrases short and evocative.

### Step 2: Choose a style archetype
Read `references/style-guide.md` for the full grammar. Pick one of five archetypes:

| Archetype | Best for | Letter |
|-----------|----------|--------|
| 极简留白 Minimal Ma | exhibitions, poems, quiet/zen topics | `A` |
| 传统纹样 Traditional | shops, brands, festivals, craft | `B` |
| 和食/和菓子美食 Food | restaurants, wagashi, Japan food | `C` |
| 前卫排版 Avant-garde | bold events, theater, design statements | `D` |
| 手绘诗意 Hand-drawn | art, music, literary, emotional | `E` |

Default mapping by topic: food→`C`, exhibition/event→`A` or `D`, brand/shop→`B`, poem/art/music→`E`. When unsure, ask briefly which style they prefer, or generate `A` as the safest default.

### Step 3: Generate the poster
Use `scripts/jp_poster.py`. It runs on macOS with system fonts and PIL; no external services needed.

**Quick one-liner:**
```bash
python3 <skill-dir>/scripts/jp_poster.py \
  --preset A --title "朝に起きる。" \
  --subtitle "Context 21.8" --footer "2013.9.22 - 9.29" \
  --out /absolute/path/poster.png
```

**Full control via JSON config:**
```bash
python3 <skill-dir>/scripts/jp_poster.py --config spec.json --out poster.png
```
Config fields: `archetype` (A-E), `size` [w,h] (default [900,1200]), `bg`, `accent`, `ink`, `title`, `subtitle`, `body` (array of short vertical lines), `footer`, `title_font` (mincho/mincho_b/gothic/gothic_b/maru), `image` (optional photo path, used in C/E), `seed` (for reproducible motifs). Archetype B additionally accepts `side_left`, `side_right` (short vertical side captions) and `seal_text1`, `seal_text2` (single characters for the two seals). All archetypes accept `seal_text` (single character for the seal). Optional `language`: `zh` or `ja` to force a font family; otherwise it is auto-detected from the copy (kana→ja, Hanzi→zh). The script renders Chinese copy with Songti/PingFang and Japanese copy with Hiragino, so text language always follows the user's original wording.

For food posters (C) with a real food photo, pass `--image /path/to/photo.jpg`; the script clips it into a soft cloud frame. Without a photo, it draws a stylized wagashi illustration by default; set `dish: "fried_chicken"` to draw golden karaage-style fried chicken nuggets instead (good for fried chicken / snack / casual food themes).

Archetype E supports a `scene` field: default `botanical` draws a flowering branch with a bird; `scene: "rain_pickup"` draws a rainy-day scene (rain strokes, umbrella, adult + child silhouettes holding hands, puddles) — ideal for parenting/school/emotional everyday themes. E also accepts `seal_text` (single character for the seal, default `唄`).

### Step 4: Verify the output
Open the generated PNG with the image viewer. Confirm:
- Vertical text is upright, legible, not overflowing the frame.
- No tofu boxes (□□□) from unsupported glyphs.
- Elements don't overlap; there is clear negative space.
- Colors match the chosen palette.
If anything is wrong, adjust the config (font, size, text length) and regenerate. Short titles render best — keep titles under ~8 characters per vertical column.

### Step 5: Deliver
Present the PNG to the user with the image viewer tool. Briefly state the archetype and palette used. Offer to regenerate with adjustments (different style, colors, or text).

## Advanced: AI-generated illustration backgrounds

For archetype `E` or `D` when the user wants rich hand-drawn/watercolor/embroidery artwork rather than the built-in line art, the deterministic script handles layout but cannot draw complex illustration. In that case, generate a background image with an image-generation tool, then feed it as `--image` to archetype `E` (it composites into the watercolor field). Prompt recipe:

```
Minimal Japanese poster background, washi paper texture, [subject: delicate
ink-and-watercolor illustration], vast negative space, soft muted palette
(off-white #F5F1E8, ink gray, one accent color), no text, no letters,
vertical composition, wabi-sabi aesthetic, hand-drawn, subtle grain —
poster background only, flat, print design, no文字
```

Important: generate the background **without text**, then let `jp_poster.py` render the typography — this guarantees correct Japanese/Chinese glyphs, which image generators cannot reliably produce.

## Bundled Resources

- `references/style-guide.md` — full style grammar: 5 archetypes, palettes, fonts, motifs, layout ratios, pitfalls. Load it when choosing styles or tuning output.
- `scripts/jp_poster.py` — the generator. Contains a motif library (sakura, seigaiha, asanoha, ensō, seal, mon, fan, brush strokes), vertical text renderer, and 5 layout functions.
- `scripts/generate.py` — thin convenience wrapper (same CLI, resolves skill path automatically).
- `assets/` — reserved for user-supplied reference photos or logos to composite into posters.

## Notes

- The script is deterministic with a fixed `seed`; the same seed/config always produces the same poster.
- Recommended output size 900×1200 (3:4). For print, raise to 1800×2400.
- All text passed to the script must be plain strings; avoid emoji (renders as monochrome boxes).
- Fonts depend on macOS system fonts (Hiragino). On non-macOS systems, the script falls back to default fonts; typography may degrade.
