"""
Credit-free video generator (vertical 1080x1920, for Shorts/Reels).
Reads script.txt (one scene per line) and writes output.mp4
No ImageMagick needed. If the voice service fails, makes a silent video instead.
"""
import asyncio
import textwrap

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

W, H = 1080, 1920
VOICE = "en-US-AriaNeural"  # Hindi voice: "hi-IN-SwaraNeural"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
COLORS = [(20, 30, 70), (60, 20, 80), (10, 70, 80), (80, 30, 40)]
SILENT_SECONDS_PER_LINE = 4


def make_frame(text, color):
    img = Image.new("RGB", (W, H), color)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 76)
    wrapped = textwrap.fill(text, 24)
    box = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=14)
    tw, th = box[2] - box[0], box[3] - box[1]
    draw.multiline_text(
        ((W - tw) / 2, (H - th) / 2), wrapped, font=font,
        fill="white", align="center", spacing=14,
    )
    return np.array(img)


async def _voice(text, path):
    import edge_tts
    await edge_tts.Communicate(text, VOICE).save(path)


def make_voice(text, path="voice.mp3"):
    try:
        asyncio.run(_voice(text, path))
        return AudioFileClip(path)
    except Exception as e:
        print("Voice failed, making silent video:", e)
        return None


def build(lines, out="output.mp4"):
    audio = make_voice(" ".join(lines))
    total = audio.duration if audio else SILENT_SECONDS_PER_LINE * len(lines)
    per_scene = total / len(lines)

    clips = [
        ImageClip(make_frame(line, COLORS[i % len(COLORS)])).set_duration(per_scene)
        for i, line in enumerate(lines)
    ]
    video = concatenate_videoclips(clips, method="compose")
    if audio:
        video = video.set_audio(audio)
    video.write_videofile(
        out, fps=24, codec="libx264", audio_codec="aac",
        ffmpeg_params=["-pix_fmt", "yuv420p"],
    )


if __name__ == "__main__":
    with open("script.txt", encoding="utf-8") as f:
        scene_lines = [l.strip() for l in f if l.strip()]
    build(scene_lines)
