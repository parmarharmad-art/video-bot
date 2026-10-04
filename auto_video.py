"""
Animated Hindi video generator (vertical 1080x1920, for Shorts/Reels).
Reads script.txt (one scene per line, Hindi/Devanagari) and writes output.mp4
- Natural Hindi voice (edge-tts), one voice clip per scene so text matches speech
- Animated gradient background, floating bubbles, text slide-in + fade
- If the voice service fails, makes a silent video instead of crashing
"""
import asyncio
import glob
import math
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import AudioFileClip, VideoClip, concatenate_videoclips

W, H = 1080, 1920
FPS = 24
VOICE = "hi-IN-SwaraNeural"   # male voice: "hi-IN-MadhurNeural"
RATE = "-5%"                  # slightly slower = more natural
FONT_SIZE = 84
SILENT_SECONDS = 4.0

PALETTES = [
    ((106, 17, 203), (37, 117, 252)),
    ((255, 65, 108), (255, 75, 43)),
    ((0, 153, 153), (0, 60, 130)),
    ((197, 67, 163), (79, 38, 131)),
]
CIRCLES = [  # base_x, base_y, radius, speed, phase
    (180, 400, 140, 40, 0.0), (860, 900, 200, 55, 1.3), (300, 1400, 110, 35, 2.1),
    (780, 1650, 160, 48, 0.7), (540, 150, 90, 30, 3.0),
]


def find_font():
    pats = [
        "/usr/share/fonts/**/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/**/NotoSansDevanagari*Bold*.ttf",
        "/usr/share/fonts/**/NotoSansDevanagari*.ttf",
        "/usr/share/fonts/**/Lohit-Devanagari.ttf",
    ]
    for p in pats:
        found = glob.glob(p, recursive=True)
        if found:
            return found[0]
    return None


def ensure_fonts():
    if find_font():
        return
    print("Installing Hindi fonts...")
    subprocess.run(
        "sudo apt-get update -qq && "
        "sudo apt-get install -y -qq fonts-noto-core libraqm0 libfribidi0",
        shell=True, check=False,
    )


def load_font(size):
    path = find_font() or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.truetype(path, size)


def gradient(c1, c2):
    t = np.linspace(0, 1, H)[:, None, None]
    g = np.array(c1) * (1 - t) + np.array(c2) * t
    return np.repeat(g, W, axis=1).astype(np.uint8)


def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def text_layer(text):
    font = load_font(FONT_SIZE)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lines = wrap(probe, text, font, W - 200)
    line_h = int(FONT_SIZE * 1.55)
    lw, lh = W - 120, line_h * len(lines) + 40
    layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, line in enumerate(lines):
        x = (lw - d.textlength(line, font=font)) / 2
        y = 20 + i * line_h
        d.text((x + 4, y + 5), line, font=font, fill=(0, 0, 0, 110))  # shadow
        d.text((x, y), line, font=font, fill=(255, 255, 255, 255))
    return layer


def make_scene(text, idx):
    c1, c2 = PALETTES[idx % len(PALETTES)]
    bg = Image.fromarray(gradient(c1, c2)).convert("RGBA")
    layer = text_layer(text)
    lw, lh = layer.size
    tx, ty = (W - lw) // 2, (H - lh) // 2
    alpha = layer.getchannel("A")

    def frame(t):
        img = bg.copy()
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for bx, by, r, sp, ph in CIRCLES:
            x = bx + 70 * math.sin(t * 0.7 + ph)
            y = (by - t * sp) % (H + 2 * r) - r
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 38))
        # accent line grows under the text
        p = min(1.0, t / 0.9)
        half = int(160 * (1 - (1 - p) ** 3))
        d.rounded_rectangle((W // 2 - half, ty + lh + 30, W // 2 + half, ty + lh + 42),
                            radius=6, fill=(255, 255, 255, 220))
        img = Image.alpha_composite(img, ov)
        # text slides up + fades in
        e = 1 - (1 - min(1.0, t / 0.7)) ** 3
        lay = layer.copy()
        lay.putalpha(alpha.point(lambda v: int(v * e)))
        img.alpha_composite(lay, (tx, ty + int((1 - e) * 80)))
        return np.array(img.convert("RGB"))

    return frame


async def _tts(text, path):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(path)


def voice_for(line, i):
    path = f"voice_{i}.mp3"
    try:
        asyncio.run(_tts(line, path))
        return AudioFileClip(path)
    except Exception as e:
        print("Voice failed for scene", i, "->", e)
        return None


def build(lines, out="output.mp4"):
    ensure_fonts()
    clips = []
    for i, line in enumerate(lines):
        audio = voice_for(line, i)
        dur = audio.duration + 0.6 if audio else SILENT_SECONDS
        clip = VideoClip(make_scene(line, i), duration=dur)
        if audio:
            clip = clip.set_audio(audio)
        clips.append(clip)
    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(
        out, fps=FPS, codec="libx264", audio_codec="aac",
        ffmpeg_params=["-pix_fmt", "yuv420p"],
    )


if __name__ == "__main__":
    with open("script.txt", encoding="utf-8") as f:
        scene_lines = [l.strip() for l in f if l.strip()]
    build(scene_lines)
