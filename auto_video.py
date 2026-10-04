"""
Credit-free fallback video generator (vertical 1080x1920, for Shorts/Reels).
Reads script.txt (one scene per line) and writes output.mp4
"""
import asyncio
import textwrap

import edge_tts
from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    TextClip,
    concatenate_videoclips,
)

W, H = 1080, 1920
VOICE = "en-US-AriaNeural"  # Hindi voice: "hi-IN-SwaraNeural"
FONT = "DejaVu-Sans-Bold"   # For Hindi text use a Devanagari font, e.g. "Noto-Sans-Devanagari"
COLORS = [(20, 30, 70), (60, 20, 80), (10, 70, 80), (80, 30, 40)]


async def make_voice(text: str, path: str) -> None:
    await edge_tts.Communicate(text, VOICE).save(path)


def build(lines, out="output.mp4"):
    asyncio.run(make_voice(" ".join(lines), "voice.mp3"))
    audio = AudioFileClip("voice.mp3")
    per_scene = audio.duration / len(lines)

    scenes = []
    for i, line in enumerate(lines):
        bg = ColorClip((W, H), color=COLORS[i % len(COLORS)], duration=per_scene)
        txt = (
            TextClip(textwrap.fill(line, 22), fontsize=80, color="white", font=FONT)
            .set_position("center")
            .set_duration(per_scene)
            .crossfadein(0.4)
        )
        scenes.append(CompositeVideoClip([bg, txt]))

    video = concatenate_videoclips(scenes).set_audio(audio)
    video.write_videofile(out, fps=24, codec="libx264", audio_codec="aac")


if __name__ == "__main__":
    with open("script.txt", encoding="utf-8") as f:
        scene_lines = [l.strip() for l in f if l.strip()]
    build(scene_lines)
