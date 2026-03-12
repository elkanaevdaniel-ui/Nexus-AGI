"""
image_gen.py  —  Visual image generation for LinkedIn posts

Style rotates daily (FORGE overhaul v2.0 — NO TEXT IN IMAGES):
  Mon(0) = photorealistic        — Ultra-cinematic, dramatic, dark
  Tue(1) = anime                 — Studio Ghibli / high-quality anime
  Wed(2) = dark_fantasy          — Epic fantasy, magic, dark atmosphere
  Thu(3) = neon_noir             — Rain-soaked cyberpunk detective noir
  Fri(4) = hyperrealistic_3d     — Unreal Engine 5 quality 3D renders
  Sat(5) = cinematic_concept_art — Movie poster concept art, painterly
  Sun(6) = golden_hour_realism   — Warm golden light, aspirational

Rules:
  - ABSOLUTELY NO text, words, letters, labels, numbers in images
  - Images tell visual STORIES, not infographics
  - Every image must match the post topic with a SCENE

Public API:
    generate_image(title, content='', post_id=0, url='', force_style=None,
                   post_text='') -> str (path)
"""

import base64
import io
import logging
import math
import os
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import GOOGLE_API_KEY, OUTPUT_DIR

log = logging.getLogger(__name__)

_OUTPUT = Path(OUTPUT_DIR)
_OUTPUT.mkdir(parents=True, exist_ok=True)

# ── Daily style rotation ───────────────────────────────────────────────────────
DAILY_STYLES = {
    0: "photorealistic",       # Monday   — Ultra-cinematic dark photography
    1: "anime",                # Tuesday  — Studio Ghibli / high-quality anime
    2: "dark_fantasy",         # Wednesday — Epic dark fantasy landscapes
    3: "neon_noir",            # Thursday — Rain-soaked neon cyberpunk noir
    4: "hyperrealistic_3d",    # Friday   — Unreal Engine 5 quality renders
    5: "cinematic_concept_art",# Saturday — Movie poster concept art
    6: "golden_hour_realism",  # Sunday   — Warm golden aspirational realism
}

# All styles (including extras for manual /style command)
ALL_STYLES = list(DAILY_STYLES.values()) + ["cartoon", "cyberpunk"]


def _get_style(force_style=None):
    if force_style:
        if force_style == "random":
            return random.choice(ALL_STYLES)
        return force_style.lower().replace("-", "_")
    return DAILY_STYLES[datetime.now().weekday()]


def _strip_post_text(post_text: str) -> str:
    """Strip hashtags, URLs, emojis from post text for clean illustration prompt."""
    import re
    text = re.sub(r'http\S+|www\.\S+', '', post_text)
    text = re.sub(r'#\w+', '', text)
    text = re.sub(r'[\U00010000-\U0010ffff\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]', '', text)
    text = re.sub(r'Resources:[\s\S]*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:600]


def _generate_creative_scene_via_llm(post_summary: str) -> str | None:
    """Use LLM to generate a unique, creative visual scene description.

    Tries OpenRouter first, falls back to Gemini text generation.
    Returns a scene description string or None if all methods fail.
    """
    system = (
        "You are a premium visual director for editorial photography and illustration. "
        "Given a short article summary, you create ONE unique visual scene description "
        "for an image generator. Your scenes are NEVER cliché — no glowing brains, "
        "no floating blue network nodes, no binary code rain, no generic hooded hackers. "
        "Instead you use visual METAPHORS: architectural spaces, natural phenomena, "
        "physical objects, real-world environments, abstract geometry, or cinematic moments "
        "that CONCEPTUALLY represent the idea. Think like a top advertising creative director."
    )
    user = (
        f"Create a visual scene for this article:\n\n\"{post_summary}\"\n\n"
        "Requirements:\n"
        "- ONE paragraph, 2-4 sentences max\n"
        "- Describe a concrete, filmable SCENE (what is in frame, lighting, mood)\n"
        "- Use a fresh visual metaphor — NOT literal tech imagery\n"
        "- Think: editorial photography, architectural visualization, product photography, "
        "fine art, nature macro, minimalist design\n"
        "- AVOID: glowing brains, network nodes, binary code, hooded figures at computers, "
        "digital vaults, fish hooks, generic SOC rooms, floating holographic UIs\n"
        "- Output ONLY the scene description, nothing else"
    )

    # Try OpenRouter first
    try:
        from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL
        import requests as _req

        if OPENROUTER_API_KEY:
            resp = _req.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 1.0,
                    "max_tokens": 250,
                },
                timeout=30,
            )
            resp.raise_for_status()
            scene = resp.json()["choices"][0]["message"]["content"].strip()
            if scene:
                log.info("LLM-generated scene (OpenRouter): %s", scene[:120])
                return scene
    except Exception as exc:
        log.warning("OpenRouter scene generation failed: %s", exc)

    # Fallback to Gemini text generation
    try:
        from google import genai
        from google.genai import types

        if not GOOGLE_API_KEY:
            return None

        client = genai.Client(api_key=GOOGLE_API_KEY)
        prompt = f"{system}\n\n{user}"
        for _model in ["gemini-2.5-flash", "gemini-1.5-flash"]:
            try:
                response = client.models.generate_content(
                    model=_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=1.0,
                        max_output_tokens=250,
                    ),
                )
                scene = response.text.strip()
                if scene:
                    log.info("LLM-generated scene (%s): %s", _model, scene[:120])
                    return scene
            except Exception as _exc:
                log.warning("Gemini scene (%s) failed: %s", _model, _exc)
                continue
    except Exception as exc:
        log.warning("Gemini scene generation setup failed: %s", exc)

    return None


# ── Style art directions — all cinematic, NO text ──────────────────────────────
STYLE_ART_DIRECTION = {
    'photorealistic': (
        'Ultra-realistic cinematic photography, 8K IMAX quality, dramatic chiaroscuro lighting, '
        'shallow depth of field, anamorphic lens flare, movie still from a $200M thriller, '
        'deep shadows, hyper-detailed textures, photojournalism meets Hollywood cinematography'
    ),
    'anime': (
        'Premium Japanese anime illustration, Studio Ghibli meets Makoto Shinkai visual quality, '
        'lush detailed backgrounds, cinematic lighting, expressive atmospheric depth, '
        'beautiful color grading with rich saturated tones, hand-crafted cel animation aesthetic, '
        'epic composition worthy of a feature film still'
    ),
    'dark_fantasy': (
        'Epic dark fantasy digital painting, dramatic fantasy landscapes with ancient magic, '
        'sweeping vistas of dark mountains and lightning-split skies, mystical energy effects, '
        'painterly yet hyper-detailed in the style of top concept artists, '
        'deep purples, blacks, electric blues and ember oranges, cinematic grandeur'
    ),
    'neon_noir': (
        'Rain-soaked cyberpunk detective noir, neon signs reflecting in wet cobblestone streets, '
        'dense atmospheric fog, deep shadows cut by magenta and cyan neon, '
        'Blade Runner 2049 meets Sin City visual aesthetic, '
        'moody chiaroscuro, every raindrop individually lit, cinematic 2.39:1 widescreen'
    ),
    'hyperrealistic_3d': (
        'Photorealistic Unreal Engine 5 render, Nanite geometry detail, Lumen global illumination, '
        'physically-based rendering with perfect subsurface scattering, '
        '8K texture resolution, cinematic depth of field, ray-traced reflections, '
        'indistinguishable from reality, the highest-end real-time 3D art possible'
    ),
    'cinematic_concept_art': (
        'Epic movie poster concept art, painterly yet photorealistic, '
        'the visual development style of top Hollywood concept artists, '
        'bold heroic composition, dramatic rim lighting, sweeping scale, '
        'oil painting meets digital art, award-winning film concept illustration, '
        'rich color story with deep darks and brilliant highlights'
    ),
    'golden_hour_realism': (
        'Warm golden hour photography, long soft shadows, magical late-afternoon sunlight, '
        'optimistic and aspirational mood, professional and elegant settings bathed in gold, '
        'National Geographic meets corporate excellence photography, '
        'soft bokeh backgrounds, warm amber and honey tones, uplifting cinematic feel'
    ),
    'cartoon': (
        'Bold high-quality comic book illustration, thick confident ink outlines, '
        'vivid flat colors with dynamic shading, Marvel/DC graphic novel aesthetic, '
        'expressive dynamic composition, professional illustration quality'
    ),
    'cyberpunk': (
        'Cyberpunk dystopian scene, glowing magenta and cyan neon, '
        'ultra-dense futuristic city, holographic advertisements, rain and steam, '
        'Blade Runner meets Ghost in the Shell visual style, ultra-detailed'
    ),
}


def _build_illustration_prompt(post_text: str, style: str, custom_prompt: str = "") -> str:
    """Build a pure visual scene prompt — absolutely NO text in image.

    If *custom_prompt* is provided it is used as-is for the scene.
    Otherwise the function tries LLM-based creative scene generation and
    only falls back to a simple topic-derived description when both are
    unavailable.
    """
    story = _strip_post_text(post_text)
    art = STYLE_ART_DIRECTION.get(style, STYLE_ART_DIRECTION['photorealistic'])

    # Priority: custom_prompt > LLM-generated > simple fallback
    if custom_prompt.strip():
        scene = custom_prompt.strip()
    else:
        scene = _generate_creative_scene_via_llm(story)
        if not scene:
            # Minimal fallback — just summarise the topic, let the image model
            # be creative rather than forcing a cliché scene.
            scene = (
                f"A clean, professional, visually striking editorial illustration "
                f"that conceptually represents: {story[:250]}. "
                f"Use a subtle visual metaphor — elegant architecture, natural "
                f"phenomena, or abstract geometry — NOT literal tech clichés."
            )

    prompt = (
        f"{art}. "
        f"Scene: {scene}. "
        "Composition: dramatic, immersive, premium editorial quality. "
        "16:9 landscape orientation, 1200x628 pixels. "
        "CRITICAL RULES — STRICTLY ENFORCE: "
        "NO text of any kind. NO words. NO letters. NO numbers. NO labels. "
        "NO captions. NO titles. NO watermarks. NO UI elements. NO infographic elements. "
        "PURE visual storytelling only — the image tells the story through visuals alone."
    )
    return prompt


# ── Gemini image generation ────────────────────────────────────────────────────

def generate_with_gemini(title, content, url, post_id, post_text="",
                         custom_prompt="", style="photorealistic"):
    """Generate illustrative image via Google Imagen/Gemini. Returns path or None."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        log.error("Import failed: %s", exc)
        return None

    if not GOOGLE_API_KEY:
        log.warning("GOOGLE_API_KEY not set")
        return None
    source_text = post_text if post_text.strip() else (title + ". " + content[:300])
    prompt = _build_illustration_prompt(source_text, style, custom_prompt=custom_prompt)
    log.info("Illustration prompt (style=%s): %s...", style, prompt[:120])

    client = genai.Client(api_key=GOOGLE_API_KEY)

    # ── Method 1: Imagen API (dedicated image generation) ──────────────
    imagen_models = [
        "imagen-4.0-generate-001",
        "imagen-4.0-fast-generate-001",
        "imagen-3.0-generate-002",
    ]
    for model_name in imagen_models:
        try:
            response = client.models.generate_images(
                model=model_name,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                ),
            )
            if response.generated_images:
                img_data = response.generated_images[0].image
                # img_data has .image_bytes attribute
                img = Image.open(io.BytesIO(img_data.image_bytes)).convert("RGBA")
                img = img.resize((1200, 628), Image.LANCZOS)
                out_path = _OUTPUT / f"post_{post_id}.png"
                img.convert("RGB").save(out_path)
                log.info("Imagen image saved via %s (style=%s): %s",
                         model_name, style, out_path)
                return str(out_path)
        except Exception as exc:
            log.warning("Imagen %s failed: %s", model_name, str(exc)[:150])
            continue

    # ── Method 2: Gemini native image generation (fallback) ────────────
    gemini_image_models = [
        "gemini-2.5-flash-image",
    ]
    for model_name in gemini_image_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"]
                ),
            )
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    img_bytes = base64.b64decode(part.inline_data.data)
                    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
                    img = img.resize((1200, 628), Image.LANCZOS)
                    out_path = _OUTPUT / f"post_{post_id}.png"
                    img.convert("RGB").save(out_path)
                    log.info("Gemini image saved via %s (style=%s): %s",
                             model_name, style, out_path)
                    return str(out_path)
        except Exception as exc:
            log.warning("Gemini %s failed: %s", model_name, str(exc)[:150])
            continue

    log.warning("All image generation models failed — using Pillow fallback")
    return None


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_image(title, content="", post_id=0, url="", force_style=None,
                   post_text="", custom_prompt=""):
    """
    Generate a LinkedIn post image.
    Tries Gemini first; falls back to enhanced Pillow.
    Returns absolute file path string.
    """
    # Skip image generation if post text is placeholder/failure content
    if post_text and "POST GENERATION FAILED" in post_text:
        log.warning("Skipping image generation — post text is placeholder content")
        return _create_pillow_fallback(title, content, post_id,
                                       _get_style(force_style))

    style = _get_style(force_style)
    log.info("generate_image post_id=%s style=%s", post_id, style)

    path = generate_with_gemini(title, content, url, post_id,
                                post_text=post_text,
                                custom_prompt=custom_prompt,
                                style=style)
    if path:
        return path

    log.info("Falling back to enhanced Pillow style=%s", style)
    return _create_pillow_fallback(title, content, post_id, style)


# ── Pillow fallback ────────────────────────────────────────────────────────────

STYLE_PALETTES = {
    'photorealistic':       {'bg': (5, 10, 25),   'accent': (220, 30, 30),   'glow': (0, 100, 200)},
    'anime':                {'bg': (10, 5, 30),   'accent': (255, 80, 180),  'glow': (80, 200, 255)},
    'dark_fantasy':         {'bg': (8, 5, 18),    'accent': (180, 60, 255),  'glow': (80, 20, 160)},
    'neon_noir':            {'bg': (4, 2, 12),    'accent': (255, 20, 120),  'glow': (0, 220, 255)},
    'hyperrealistic_3d':    {'bg': (5, 8, 22),    'accent': (0, 200, 255),   'glow': (180, 0, 255)},
    'cinematic_concept_art':{'bg': (10, 6, 4),    'accent': (220, 100, 20),  'glow': (255, 180, 40)},
    'golden_hour_realism':  {'bg': (30, 18, 5),   'accent': (255, 160, 20),  'glow': (255, 200, 80)},
    'cartoon':              {'bg': (20, 20, 60),  'accent': (255, 140, 0),   'glow': (50, 200, 100)},
    'cyberpunk':            {'bg': (5, 0, 20),    'accent': (255, 0, 100),   'glow': (0, 255, 200)},
}


def _get_font(size, bold=False):
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
            else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold
            else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf' if bold
            else '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _draw_energy_web(draw, cx, cy, radius, color, spokes=12, rings=6):
    """Draw an energy web / force field pattern."""
    for ring in range(1, rings + 1):
        r = radius * ring / rings
        pts = []
        for s in range(spokes):
            angle = math.pi * 2 * s / spokes - math.pi / 2
            pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        for i in range(len(pts)):
            alpha = int(160 * (1 - ring / rings) + 40)
            draw.line([pts[i], pts[(i + 1) % len(pts)]], fill=color + (alpha,), width=1)
    for s in range(spokes):
        angle = math.pi * 2 * s / spokes - math.pi / 2
        draw.line([(cx, cy),
                   (cx + radius * math.cos(angle), cy + radius * math.sin(angle))],
                  fill=color + (60,), width=1)


def _draw_particles(draw, w, h, color, count=80):
    """Draw floating particle dots for atmosphere."""
    rng = random.Random(42)
    for _ in range(count):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        r = rng.randint(1, 3)
        alpha = rng.randint(40, 180)
        draw.ellipse([x-r, y-r, x+r, y+r], fill=color + (alpha,))


def _draw_horizon_glow(draw, w, h, glow_color, y_pos=None):
    """Draw a glowing horizon line."""
    if y_pos is None:
        y_pos = int(h * 0.6)
    for offset in range(30, 0, -3):
        alpha = int(80 * (1 - offset / 30))
        draw.line([(0, y_pos + offset), (w, y_pos + offset)],
                  fill=glow_color + (alpha,), width=2)
        draw.line([(0, y_pos - offset), (w, y_pos - offset)],
                  fill=glow_color + (alpha,), width=2)
    draw.line([(0, y_pos), (w, y_pos)], fill=glow_color + (220,), width=2)


def _create_pillow_fallback(title, content, post_id, style):
    """Create a high-quality cinematic fallback image — PURE visuals, no text content."""
    W, H = 1200, 628
    pal = STYLE_PALETTES.get(style, STYLE_PALETTES['photorealistic'])
    bg, accent, glow = pal['bg'], pal['accent'], pal['glow']

    img = Image.new('RGBA', (W, H), bg + (255,))
    draw = ImageDraw.Draw(img)

    # Rich gradient background
    for y in range(H):
        t = y / H
        r = int(bg[0] * (1 - t * 0.3))
        g = int(bg[1] * (1 - t * 0.3))
        b = int(min(255, bg[2] * (1 + t * 0.4)))
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # Large atmospheric glow orbs
    glow_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    # Primary glow — top right
    for r in range(280, 0, -8):
        alpha = int(25 * (1 - r / 280))
        gd.ellipse([W - r - 50, -r, W - 50 + r, r * 2], fill=glow + (alpha,))
    # Secondary glow — bottom left
    for r in range(200, 0, -8):
        alpha = int(20 * (1 - r / 200))
        gd.ellipse([-r, H - r, r * 2, H + r], fill=accent + (alpha,))
    img = Image.alpha_composite(img, glow_layer)
    draw = ImageDraw.Draw(img)

    # Horizon glow line
    _draw_horizon_glow(draw, W, H, glow, y_pos=int(H * 0.58))

    # Central energy web
    _draw_energy_web(draw, W // 2, H // 2, min(W, H) // 2 - 20,
                    glow, spokes=16, rings=8)

    # Floating particles
    _draw_particles(draw, W, H, glow, count=120)
    _draw_particles(draw, W, H, accent, count=40)

    # Style-specific accent shapes
    if style == 'golden_hour_realism':
        # Sun rays
        sun_x, sun_y = int(W * 0.75), int(H * 0.25)
        for angle_deg in range(0, 360, 15):
            angle = math.radians(angle_deg)
            x2 = sun_x + int(math.cos(angle) * 200)
            y2 = sun_y + int(math.sin(angle) * 200)
            draw.line([(sun_x, sun_y), (x2, y2)], fill=accent + (30,), width=2)
        for r in range(60, 0, -5):
            alpha = int(200 * (1 - r / 60))
            draw.ellipse([sun_x-r, sun_y-r, sun_x+r, sun_y+r],
                         fill=accent + (alpha,))
    elif style in ('neon_noir', 'cyberpunk'):
        # Neon vertical lines (building silhouettes)
        rng = random.Random(7)
        for _ in range(20):
            x = rng.randint(0, W)
            bh = rng.randint(100, 400)
            bw = rng.randint(30, 80)
            draw.rectangle([x, H - bh, x + bw, H],
                           fill=(rng.randint(5, 20), rng.randint(5, 20),
                                 rng.randint(20, 50), 200))
            # Neon window lights
            for wy in range(H - bh + 10, H - 20, 20):
                for wx in range(x + 5, x + bw - 5, 12):
                    if rng.random() > 0.4:
                        wc = glow if rng.random() > 0.5 else accent
                        draw.rectangle([wx, wy, wx+6, wy+8], fill=wc + (180,))
    elif style == 'dark_fantasy':
        # Mountain silhouettes
        pts = [(0, H)]
        x = 0
        rng = random.Random(13)
        while x < W:
            x += rng.randint(40, 120)
            y = H - rng.randint(100, 380)
            pts.append((x, y))
        pts.append((W, H))
        draw.polygon(pts, fill=(6, 3, 14, 230))

    # Silhouette figure — the human element
    fig_x = int(W * 0.15)
    fig_y = int(H * 0.25)
    # Head
    draw.ellipse([fig_x + 28, fig_y, fig_x + 68, fig_y + 48],
                 fill=(10, 10, 20, 210))
    # Body
    draw.polygon([
        (fig_x, fig_y + 200), (fig_x + 96, fig_y + 200),
        (fig_x + 108, fig_y + 60), (fig_x + 72, fig_y + 46),
        (fig_x + 24, fig_y + 46), (fig_x - 12, fig_y + 60),
    ], fill=(8, 8, 18, 210))
    # Glowing eyes
    draw.ellipse([fig_x + 36, fig_y + 16, fig_x + 46, fig_y + 26],
                 fill=accent + (220,))
    draw.ellipse([fig_x + 52, fig_y + 16, fig_x + 62, fig_y + 26],
                 fill=accent + (220,))

    # Subtle vignette
    vignette = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for r in range(min(W, H) // 2, 0, -4):
        alpha = int(120 * (r / (min(W, H) // 2)))
        vd.ellipse([W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r],
                   outline=(0, 0, 0, max(0, 120 - alpha)))
    img = Image.alpha_composite(img, vignette)

    out_path = _OUTPUT / f"post_{post_id}.png"
    img.convert('RGB').save(out_path)
    log.info('Pillow fallback saved (style=%s): %s', style, out_path)
    return str(out_path)
