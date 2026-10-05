"""Daily Ramayan short: Hindi TTS (edge-tts, free) + Pexels footage + ffmpeg + Devanagari captions."""
import asyncio, json, os, random, subprocess, datetime, requests, edge_tts

W, H = 1080, 1920
day = (datetime.date.today() - datetime.date(2026, 10, 6)).days
stories = json.load(open("stories.json", encoding="utf-8"))
st = stories[day % len(stories)]
os.makedirs("out", exist_ok=True)

async def tts():
    c = edge_tts.Communicate(st["text"], "hi-IN-MadhurNeural", rate="-5%")
    with open("out/voice.mp3", "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
asyncio.run(tts())

def dur(p):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]).decode())
D = dur("out/voice.mp3") + 0.6

words = st["text"].split()
chunks = [" ".join(words[i:i+4]) for i in range(0, len(words), 4)]
per = D / len(chunks)
def t(s):
    return f"{int(s//3600)}:{int(s%3600//60):02d}:{s%60:05.2f}"
ass = f"""[Script Info]
PlayResX: {W}
PlayResY: {H}
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BorderStyle,Outline,Alignment,MarginV
Style: D,Noto Sans Devanagari,78,&H00FFFFFF,&H00000000,1,6,2,420
[Events]
Format: Layer,Start,End,Style,Text
""" + "\n".join(f"Dialogue: 0,{t(i*per)},{t((i+1)*per)},D,{c}" for i, c in enumerate(chunks))
open("out/cap.ass", "w", encoding="utf-8").write(ass)

r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": os.environ["PEXELS_KEY"]},
                 params={"query": st["query"], "orientation": "portrait", "per_page": 15}, timeout=30).json()
vid = random.choice(r["videos"]); credit = vid["user"]["name"]
f = max(vid["video_files"], key=lambda x: min(x["width"], x["height"]) if x["width"] < 1300 else 0)
open("out/bg.mp4", "wb").write(requests.get(f["link"], timeout=120).content)

subprocess.check_call(["ffmpeg","-y","-stream_loop","-1","-i","out/bg.mp4","-i","out/voice.mp3","-t",f"{D:.2f}",
  "-vf",f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},eq=brightness=-0.08,subtitles=out/cap.ass",
  "-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-shortest","-pix_fmt","yuv420p","out/video.mp4"])
json.dump({"title": f"{st['title']} | Ramayan Katha #Shorts",
           "description": f"Roz ek Ramayan katha. Footage: {credit} / Pexels. #ramayan #shorts #jaishreeram"},
          open("out/meta.json", "w"), ensure_ascii=False)
print("done", D)
