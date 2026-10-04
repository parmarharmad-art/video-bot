"""
Animated Hindi video generator (vertical 1080x1920, for Shorts/Reels).
Reads script.txt (one scene per line, Hindi/Devanagari) and writes output.mp4
- Natural Hindi voice (edge-tts), one voice clip per scene so text matches speech
- Animated gradient background, floating bubbles, text slide-in + fade
- Cartoon character that waves, blinks and moves its mouth with the voice
- Series mode: episodes.txt holds many episodes ("## 1", "## 2" ...); each one is rendered
  to videos/epNN.mp4 once (already-made episodes are skipped) and pushed to GitHub
- If the voice service fails, makes a silent video instead of crashing
"""
import asyncio
import glob
import math
import os
import shutil
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


S = 2                    # supersampling for smooth edges
CW, CH = 560, 760        # character canvas (local units)
CHAR_POS = (W // 2 - CW // 2, 1080)


def _s(v):
    return int(round(v * S))


def _blob(d, box, fill, outline=None, width=0):
    d.ellipse([_s(v) for v in box], fill=fill, outline=outline, width=_s(width) if width else 0)


def _limb(d, p1, p2, w, fill):
    d.line([_s(p1[0]), _s(p1[1]), _s(p2[0]), _s(p2[1])], fill=fill, width=_s(w))
    for x, y in (p1, p2):
        _blob(d, (x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill)


def draw_character(t, mouth):
    """Cute cartoon mascot: bobs, waves, blinks, and moves its mouth with the voice."""
    img = Image.new("RGBA", (CW * S, CH * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bob = 8 * math.sin(t * 3.0) - 10 * mouth
    skin, hair, shirt, pants = (255, 214, 170), (45, 32, 30), (255, 159, 67), (60, 70, 140)

    _blob(d, (110, 715, 450, 755), (0, 0, 0, 55))                       # ground shadow
    # legs and shoes
    _limb(d, (225, 620 + bob / 2), (225, 705), 56, pants)
    _limb(d, (335, 620 + bob / 2), (335, 705), 56, pants)
    _blob(d, (180, 690, 265, 725), (30, 30, 40))
    _blob(d, (295, 690, 380, 725), (30, 30, 40))
    # body
    d.rounded_rectangle([_s(150), _s(330 + bob), _s(410), _s(650 + bob / 2)],
                        radius=_s(80), fill=shirt)
    # left arm (down), right arm (waving)
    _limb(d, (160, 380 + bob), (105, 500 + bob), 46, shirt)
    _blob(d, (82, 485 + bob, 130, 533 + bob), skin)
    wave = math.sin(t * 5.0)
    hand = (455 + 18 * wave, 300 + bob - 30 * abs(wave))
    _limb(d, (400, 380 + bob), hand, 46, shirt)
    _blob(d, (hand[0] - 26, hand[1] - 26, hand[0] + 26, hand[1] + 26), skin)
    # head
    hy = 208 + bob
    _blob(d, (130, hy - 150, 430, hy + 150), skin)
    d.pieslice([_s(122), _s(hy - 162), _s(438), _s(hy + 120)], _s(0) + 190, 350, fill=hair)
    _blob(d, (250, hy - 185, 310, hy - 135), hair)                      # hair tuft
    # cheeks
    _blob(d, (150, hy + 30, 210, hy + 75), (255, 140, 140, 150))
    _blob(d, (350, hy + 30, 410, hy + 75), (255, 140, 140, 150))
    # eyes (blink every ~3.2 s)
    blink = (t % 3.2) < 0.14
    for ex in (215, 345):
        if blink:
            d.line([_s(ex - 24), _s(hy - 5), _s(ex + 24), _s(hy - 5)], fill=(40, 30, 30), width=_s(7))
        else:
            _blob(d, (ex - 30, hy - 38, ex + 30, hy + 22), (255, 255, 255), (40, 30, 30), 3)
            _blob(d, (ex - 14 + 4 * math.sin(t), hy - 22, ex + 14 + 4 * math.sin(t), hy + 8), (35, 25, 25))
            _blob(d, (ex - 6 + 4 * math.sin(t), hy - 18, ex + 2 + 4 * math.sin(t), hy - 10), (255, 255, 255))
    # eyebrows
    d.line([_s(185), _s(hy - 58 - 6 * mouth), _s(245), _s(hy - 62 - 6 * mouth)], fill=hair, width=_s(8))
    d.line([_s(315), _s(hy - 62 - 6 * mouth), _s(375), _s(hy - 58 - 6 * mouth)], fill=hair, width=_s(8))
    # mouth follows the voice
    my = hy + 85
    if mouth < 0.08:
        d.arc([_s(240), _s(my - 30), _s(320), _s(my + 20)], 20, 160, fill=(150, 40, 50), width=_s(7))
    else:
        mh = 14 + 58 * mouth
        _blob(d, (250, my - mh / 2 + 8, 310, my + mh / 2 + 8), (150, 40, 50))
        if mh > 40:
            _blob(d, (262, my + mh / 2 - 14, 298, my + mh / 2 + 6), (240, 110, 120))
    return img.resize((CW, CH), Image.LANCZOS)


def make_scene(text, idx, env=None):
    c1, c2 = PALETTES[idx % len(PALETTES)]
    bg = Image.fromarray(gradient(c1, c2)).convert("RGBA")
    layer = text_layer(text)
    lw, lh = layer.size
    tx, ty = (W - lw) // 2, max(140, 760 - lh)
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
        if env is not None and int(t * FPS) < len(env):
            mouth = float(env[int(t * FPS)])
        elif env is None:
            mouth = 0.25 + 0.25 * math.sin(t * 9)
        else:
            mouth = 0.0
        img.alpha_composite(draw_character(t, mouth), CHAR_POS)
        return np.array(img.convert("RGB"))

    return frame


def mouth_envelope(audio):
    """Mouth opening (0..1) for every video frame, from the loudness of the voice."""
    try:
        arr = audio.to_soundarray(fps=22050)
        mono = np.abs(arr).mean(axis=1) if arr.ndim > 1 else np.abs(arr)
        n = int(audio.duration * FPS) + 1
        win = int(22050 * 0.05)
        vals = []
        for i in range(n):
            c = int(i / FPS * 22050)
            seg = mono[max(0, c - win): c + win]
            vals.append(float(np.sqrt((seg ** 2).mean())) if len(seg) else 0.0)
        vals = np.array(vals)
        ref = np.percentile(vals, 95) or 1.0
        env = np.clip(vals / ref, 0, 1)
        return np.convolve(env, np.ones(3) / 3, mode="same")
    except Exception as e:
        print("Mouth sync failed:", e)
        return None


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
        clip = VideoClip(make_scene(line, i, mouth_envelope(audio) if audio else None), duration=dur)
        if audio:
            clip = clip.set_audio(audio)
        clips.append(clip)
    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(
        out, fps=FPS, codec="libx264", audio_codec="aac",
        ffmpeg_params=["-pix_fmt", "yuv420p"],
    )


def parse_episodes(path="episodes.txt"):
    eps, cur = {}, None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if not s:
                continue
            if s.startswith("## "):
                cur = int(s[3:].strip())
                eps[cur] = []
            elif cur is not None:
                eps[cur].append(s)
    return eps


def git_save(path, msg):
    """Commit and push a finished episode right away so nothing is lost if a later one fails."""
    ident = ["-c", "user.name=video-bot", "-c", "user.email=bot@users.noreply.github.com"]
    subprocess.run(["git", "add", path], check=False)
    subprocess.run(["git"] + ident + ["commit", "-m", msg], check=False)
    subprocess.run(["git", "push"], check=False)


if __name__ == "__main__":
    if os.path.exists("episodes.txt"):
        os.makedirs("videos", exist_ok=True)
        episodes = parse_episodes()
        last = None
        for n in sorted(episodes):
            out = f"videos/ep{n:02d}.mp4"
            if os.path.exists(out):
                print("Skip (already made):", out)
            else:
                print("Making", out)
                build(episodes[n], out)
                git_save(out, f"Episode {n}")
            last = out
        shutil.copy(last, "output.mp4")
    else:
        with open("script.txt", encoding="utf-8") as f:
            scene_lines = [l.strip() for l in f if l.strip()]
        build(scene_lines)
