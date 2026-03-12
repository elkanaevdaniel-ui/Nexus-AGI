"""
video_gen.py  —  FFmpeg-based animated video generator for LinkedIn posts

FORGE division — NEXUS AGI HERALD component

Daily video style rotation:
  Mon(0) = ken_burns     — Slow zoom-in (Ken Burns effect)
  Tue(1) = pan_lr        — Pan left-to-right across image
  Wed(2) = zoom_fade     — Zoom out + fade
  Thu(3) = curtain_wipe  — Split reveal (curtain wipe)
  Fri(4) = glitch        — Glitch / digital distortion
  Sat(5) = film_grain    — Film grain + vignette
  Sun(6) = soft_fade     — Soft fade in/out loop

Public API:
    generate_video(image_path, post_id=0, duration=25,
                   force_style=None) -> str (path) or None
"""

import logging
import math
import os
import random
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR

log = logging.getLogger(__name__)

_VIDEO_DIR = Path(OUTPUT_DIR) / "videos"
_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DURATION = 25   # seconds
WIDTH  = 1200
HEIGHT = 628
FPS    = 30

# ── Daily style rotation ───────────────────────────────────────────────────────
DAILY_VIDEO_STYLES = {
    0: "ken_burns",    # Monday   — Slow zoom-in Ken Burns
    1: "pan_lr",       # Tuesday  — Pan left to right
    2: "zoom_fade",    # Wednesday — Zoom out + fade
    3: "curtain_wipe", # Thursday — Curtain split reveal
    4: "glitch",       # Friday   — Glitch/digital distortion
    5: "film_grain",   # Saturday — Film grain + vignette
    6: "soft_fade",    # Sunday   — Soft fade in/out loop
}
ALL_VIDEO_STYLES = list(DAILY_VIDEO_STYLES.values())


def _get_video_style(force_style=None):
    if force_style:
        if force_style == "random":
            return random.choice(ALL_VIDEO_STYLES)
        return force_style.lower()
    return DAILY_VIDEO_STYLES[datetime.now().weekday()]


def _ffmpeg_available():
    """Check if FFmpeg is installed."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run_ffmpeg(args, label="ffmpeg"):
    """Run an FFmpeg command and return (success, stderr)."""
    cmd = ["ffmpeg", "-y"] + args
    log.debug("FFmpeg cmd [%s]: %s", label, " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            log.error("FFmpeg [%s] failed (rc=%d): %s",
                      label, result.returncode, result.stderr[-500:])
            return False, result.stderr
        return True, result.stderr
    except subprocess.TimeoutExpired:
        log.error("FFmpeg [%s] timed out", label)
        return False, "timeout"
    except Exception as exc:
        log.error("FFmpeg [%s] exception: %s", label, exc)
        return False, str(exc)


def _prepare_input_image(image_path, tmp_dir):
    """
    Ensure input image is exactly WIDTH x HEIGHT PNG.
    Returns path to prepared image.
    """
    prepared = os.path.join(tmp_dir, "input_prepared.png")
    ok, _ = _run_ffmpeg([
        "-i", image_path,
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
               f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
        "-frames:v", "1",
        prepared
    ], label="prepare")
    if ok and os.path.exists(prepared):
        return prepared
    return image_path  # fallback: use as-is


# ── Style builders — each returns (vf_filter, extra_input_args) ────────────────

def _build_ken_burns(image_path, duration, tmp_dir):
    """
    Slow zoom in from 100% → 115% over duration seconds.
    Uses zoompan filter.
    """
    total_frames = duration * FPS
    # zoompan: z=zoom, x/y=pan position, d=frame duration per step
    vf = (
        f"zoompan=z='min(zoom+0.0005,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={total_frames}:s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"fade=t=in:st=0:d=1.5,fade=t=out:st={duration-2}:d=2"
    )
    return vf


def _build_pan_lr(image_path, duration, tmp_dir):
    """
    Pan left to right across a wider-than-frame image.
    Scales image to 130% width, then pans.
    """
    wide_w = int(WIDTH * 1.3)
    total_frames = duration * FPS
    # x goes from 0 to (wide_w - WIDTH) over total_frames
    pan_distance = wide_w - WIDTH
    vf = (
        f"scale={wide_w}:{HEIGHT},"
        f"crop={WIDTH}:{HEIGHT}:'min(n/{total_frames}*{pan_distance},{pan_distance})':0,"
        f"fade=t=in:st=0:d=1.5,fade=t=out:st={duration-2}:d=2"
    )
    return vf


def _build_zoom_fade(image_path, duration, tmp_dir):
    """
    Zoom out effect: start at 120% crop, scale to full, fade in/out.
    Uses crop+scale instead of zoompan for FFmpeg compatibility.
    """
    # Start with cropped (zoomed-in) view and scale up = zoom-out effect
    # crop=W*0.83:H*0.83 gives 120% zoom, then scale back to full size
    crop_w = int(WIDTH * 0.83)
    crop_h = int(HEIGHT * 0.83)
    total_frames = duration * FPS
    # Animate crop size from small to full using scale2ref trick with fps
    # Simple: just use crop at fixed 110% then pan slightly = subtle zoom feel
    vf = (
        f"scale={int(WIDTH*1.2)}:{int(HEIGHT*1.2)},"
        f"crop='w={WIDTH}:h={HEIGHT}"
        f":x='({int(WIDTH*1.2)}-{WIDTH})/2*max(0,(1-n/{total_frames}))'"
        f":y='({int(HEIGHT*1.2)}-{HEIGHT})/2*max(0,(1-n/{total_frames}))',"
        f"scale={WIDTH}:{HEIGHT},setsar=1,"
        f"fade=t=in:st=0:d=2,fade=t=out:st={duration-2.5}:d=2.5"
    )
    return vf


def _build_curtain_wipe(image_path, duration, tmp_dir):
    """
    Curtain reveal — slow zoom in with dramatic fade in/out.
    Uses safe zoompan expression (no trig) for compatibility.
    """
    total_frames = duration * FPS
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,"
        f"zoompan=z='min(zoom+0.0003,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={total_frames}:s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"fade=t=in:st=0:d=3,fade=t=out:st={duration-2}:d=2"
    )
    return vf


def _build_glitch(image_path, duration, tmp_dir):
    """
    Digital glitch/distortion effect using noise + hue shift + scanlines.
    """
    vf = (
        # Add some chromatic aberration simulation via rgbashift
        f"rgbashift=rh=0:rv=0:gh=3:gv=0:bh=-3:bv=0,"
        # Add scanlines via drawgrid
        f"drawgrid=x=0:y=0:w=0:h=4:t=1:c=black@0.15,"
        # Noise for grittiness
        f"noise=c0s=8:c0f=t,"
        # Subtle hue oscillation
        f"hue=h='5*sin(2*PI*t/3)',"
        # Contrast boost
        f"eq=contrast=1.15:brightness=-0.02:saturation=1.3,"
        f"fade=t=in:st=0:d=0.5,fade=t=out:st={duration-1.5}:d=1.5,"
        f"scale={WIDTH}:{HEIGHT}"
    )
    return vf


def _build_film_grain(image_path, duration, tmp_dir):
    """
    Film grain + vignette effect for cinematic feel.
    """
    # Vignette via geq, grain via noise
    vf = (
        # Film grain noise
        f"noise=c0s=12:c0f=t+u,"
        # Vignette via lut — darken edges
        f"geq="
        f"lum='clip(lum(X,Y)*(1-0.6*pow(hypot(X-W/2,Y-H/2)/hypot(W/2,H/2),2.2)),0,255)'"
        f":cb='cb(X,Y)':cr='cr(X,Y)',"
        # Slight desaturation for aged look
        f"hue=s=0.75,"
        # Warm color grade
        f"colorbalance=rs=0.05:gs=0:bs=-0.05,"
        f"fade=t=in:st=0:d=1.5,fade=t=out:st={duration-2}:d=2,"
        f"scale={WIDTH}:{HEIGHT}"
    )
    return vf


def _build_soft_fade(image_path, duration, tmp_dir):
    """
    Gentle fade in, hold, fade out with warm color grade.
    Simple approach: scale to correct size, warm grade, fade in/out.
    """
    hold_start = 2.0
    hold_end   = duration - 2.5
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,"
        "setsar=1,"
        "colorbalance=rs=0.03:gs=0.01:bs=-0.02,"
        f"fade=t=in:st=0:d={hold_start},"
        f"fade=t=out:st={hold_end}:d=2.5"
    )
    return vf


# ── Style dispatcher ───────────────────────────────────────────────────────────

STYLE_BUILDERS = {
    "ken_burns":    _build_ken_burns,
    "pan_lr":       _build_pan_lr,
    "zoom_fade":    _build_zoom_fade,
    "curtain_wipe": _build_curtain_wipe,
    "glitch":       _build_glitch,
    "film_grain":   _build_film_grain,
    "soft_fade":    _build_soft_fade,
}


def generate_video(
    image_path: str,
    post_id: int = 0,
    duration: int = DEFAULT_DURATION,
    force_style: str = None,
) -> str | None:
    """
    Generate an animated MP4 video from a static image using FFmpeg.

    Args:
        image_path:   Path to the source PNG/JPG image (1200x628 recommended)
        post_id:      Post ID for filename
        duration:     Video duration in seconds (max 30)
        force_style:  Override daily style (or 'random')

    Returns:
        Absolute path to generated MP4, or None on failure
    """
    duration = min(max(duration, 10), 30)  # clamp 10-30 seconds

    if not _ffmpeg_available():
        log.error("FFmpeg not found. Install with: apt-get install -y ffmpeg")
        return None

    if not image_path or not os.path.exists(image_path):
        log.error("Image not found: %s", image_path)
        return None

    style = _get_video_style(force_style)
    log.info("generate_video post_id=%s style=%s duration=%ss", post_id, style, duration)

    out_path = _VIDEO_DIR / f"post_{post_id}_{style}.mp4"

    builder = STYLE_BUILDERS.get(style, STYLE_BUILDERS["ken_burns"])

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Prepare input image
        prepared_img = _prepare_input_image(image_path, tmp_dir)

        # Build the filter
        vf_filter = builder(prepared_img, duration, tmp_dir)

        # Build FFmpeg command
        ffmpeg_args = [
            "-loop", "1",                           # Loop the static image
            "-i", prepared_img,                     # Input image
            "-vf", vf_filter,                       # Video filter chain
            "-t", str(duration),                    # Duration
            "-r", str(FPS),                         # Frame rate
            "-c:v", "libx264",                      # H.264 codec
            "-preset", "medium",                    # Encoding speed/quality
            "-crf", "23",                           # Quality (lower=better)
            "-pix_fmt", "yuv420p",                  # Compatibility
            "-movflags", "+faststart",              # Web streaming optimization
            "-an",                                  # No audio (silent)
            str(out_path)
        ]

        ok, stderr = _run_ffmpeg(ffmpeg_args, label=style)

        if ok and out_path.exists():
            size_mb = out_path.stat().st_size / (1024 * 1024)
            log.info("Video generated (style=%s, %.1fMB): %s", style, size_mb, out_path)
            return str(out_path)
        else:
            log.error("Video generation failed for style=%s: %s", style, stderr[-300:])
            # Try fallback to simplest style
            if style != "soft_fade":
                log.info("Attempting fallback to soft_fade style")
                return generate_video(
                    image_path, post_id, duration, force_style="soft_fade"
                )
            return None


def get_today_video_style() -> str:
    """Return today's scheduled video style name."""
    return DAILY_VIDEO_STYLES[datetime.now().weekday()]


if __name__ == "__main__":
    # Quick test: generate a test video from the most recent post image
    import glob
    import sys

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    # Find a test image
    output_dir = Path(OUTPUT_DIR)
    images = sorted(glob.glob(str(output_dir / "post_*.png")))

    if not images:
        print("No test images found in output dir. Run bot first to generate images.")
        sys.exit(1)

    test_img = images[-1]  # Use most recent
    print(f"Test image: {test_img}")

    # Test all styles
    for style_name in ALL_VIDEO_STYLES:
        print(f"\nTesting style: {style_name}...")
        result = generate_video(
            image_path=test_img,
            post_id=999,
            duration=15,
            force_style=style_name
        )
        if result:
            size = os.path.getsize(result) / 1024
            print(f"  ✅ {style_name}: {result} ({size:.0f}KB)")
        else:
            print(f"  ❌ {style_name}: FAILED")
