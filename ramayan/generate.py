"""Daily Ramayan short: Hindi TTS (edge-tts) + public-domain Ramayana paintings (Wikimedia Commons, no key) with slow zoom animation + Devanagari captions.
Falls back to an animated gradient if no images can be fetched."""
import asyncio, json, os, random, re, shutil, subprocess, datetime, requests, edge_tts

W, H = 1080, 1920
today = datetime.date.today()
day = (today - datetime.date(2026, 10, 6)).days
stories = json.load(open("stories.json", encoding="utf-8"))
st = stories[day % len(stories)]
os.makedirs("out", exist_ok=True)
random.seed(today.toordinal())

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

# ---- captions
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
Style: D,Noto Sans Devanagari,78,&H00FFFFFF,&H00000000,1,6,2,260
[Events]
Format: Layer,Start,End,Style,Text
""" + "\n".join(f"Dialogue: 0,{t(i*per)},{t((i+1)*per)},D,{c}" for i, c in enumerate(chunks))
open("out/cap.ass", "w", encoding="utf-8").write(ass)

# ---- images from Wikimedia Commons (public domain only)
UA = {"User-Agent": "RamayanDailyBot/1.0 (personal educational channel)"}
def search(q):
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
            "action":"query","generator":"search","gsrsearch":q+" filetype:bitmap","gsrnamespace":6,"gsrlimit":40,
            "prop":"imageinfo","iiprop":"url|extmetadata|size","iiurlwidth":1280,"format":"json"}).json()
        out = []
        for p in r.get("query", {}).get("pages", {}).values():
            ii = p["imageinfo"][0]
            lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
            if ("public domain" in lic.lower() or lic.upper().startswith("PD") or "cc0" in lic.lower()) and ii.get("width", 0) >= 600 and ii.get("thumburl"):
                out.append((p["title"], ii["thumburl"]))
        return out
    except Exception as e:
        print("commons search failed:", e); return []

N = max(3, min(8, int(D // 4) + 1))
kw = st["title"].split()[0]
cands = search(f"{kw} Ramayana painting")
for q in ("Ramayana painting", "Mewar Ramayana miniature", "Ramayana miniature painting India"):
    if len(cands) >= N: break
    for c in search(q):
        if c not in cands: cands.append(c)
random.shuffle(cands)

clips, credits = [], []
seg = D / N
for title, url in cands:
    if len(clips) >= N: break
    try:
        i = len(clips)
        img = f"out/img{i}.jpg"
        open(img, "wb").write(requests.get(url, headers=UA, timeout=60).content)
        out = f"out/clip{i}.mp4"
        zin = i % 2 == 0
        grow = f"1080*(1+0.08*t/{seg:.2f})" if zin else f"1080*(1.08-0.08*t/{seg:.2f})"
        fc = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:5,eq=brightness=-0.15[bg];"
              f"[b]scale=w='{grow}':h=-2:eval=frame[fg];[bg][fg]overlay=x=(W-w)/2:y=(H-h)/2-120,format=yuv420p")
        subprocess.check_call(["ffmpeg","-y","-loop","1","-framerate","30","-t",f"{seg:.2f}","-i",img,"-filter_complex",fc,
                               "-an","-c:v","libx264","-preset","veryfast","-crf","23","-pix_fmt","yuv420p",out])
        clips.append(out); credits.append(re.sub(r"^File:", "", title))
    except Exception as e:
        print("clip failed, skipping:", e)

if clips:
    open("out/list.txt", "w").write("".join(f"file '{os.path.basename(c)}'\n" for c in clips))
    src = ["-f","concat","-safe","0","-i","out/list.txt"]
    vf = "subtitles=out/cap.ass"
else:
    print("no images, using gradient fallback")
    src = ["-f","lavfi","-i",f"gradients=s={W}x{H}:c0=0x2b1200:c1=0xff9933:c2=0x7a1f00:x0=540:y0=0:x1=540:y1=1920:speed=0.03:d={D:.2f}:r=30"]
    vf = "format=yuv420p,subtitles=out/cap.ass"

subprocess.check_call(["ffmpeg","-y",*src,"-i","out/voice.mp3","-t",f"{D:.2f}","-vf",vf,
  "-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-shortest","-pix_fmt","yuv420p","out/video.mp4"])

desc = "Roz ek Ramayan katha. #ramayan #shorts #jaishreeram"
if credits:
    desc += "\nImages (public domain, Wikimedia Commons): " + "; ".join(credits[:6])
json.dump({"title": f"{st['title']} | Ramayan Katha #Shorts", "description": desc},
          open("out/meta.json", "w"), ensure_ascii=False)
print("done", D, "images:", len(clips))

# ---- publish latest.mp4 to the repo so Zapier can fetch it via a fixed public URL
try:
    shutil.copy("out/video.mp4", "latest.mp4")
    shutil.copy("out/meta.json", "latest.json")
    run = lambda *a: subprocess.run(a, check=False)
    run("git", "config", "user.name", "bot")
    run("git", "config", "user.email", "bot@users.noreply.github.com")
    run("git", "add", "latest.mp4", "latest.json")
    run("git", "commit", "-m", "daily video")
    run("git", "pull", "--rebase")
    p = subprocess.run(["git", "push"], check=False)
    print("push exit code:", p.returncode)
except Exception as e:
    print("publish step failed:", e)
