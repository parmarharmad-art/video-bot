"""Daily Ramayan short: Hindi TTS (edge-tts, female Swara) + story-specific public-domain paintings (Wikimedia Commons) with zoom + synced Devanagari captions."""
import asyncio, json, os, random, re, shutil, subprocess, sys, datetime, requests, edge_tts

W, H = 1080, 1920
today = datetime.date.today()
day = (today - datetime.date(2026, 10, 6)).days
stories = json.load(open("stories.json", encoding="utf-8"))
st = stories[day % len(stories)]
os.makedirs("out", exist_ok=True)
random.seed(today.toordinal())
print("story:", st["title"], flush=True)

async def tts_once():
    c = edge_tts.Communicate(st["text"], "hi-IN-SwaraNeural", rate="-5%")
    with open("out/voice.mp3", "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])

ok = False
for attempt in range(4):
    try:
        asyncio.run(asyncio.wait_for(tts_once(), timeout=90))
        if os.path.getsize("out/voice.mp3") > 5000:
            ok = True; break
    except Exception as e:
        print("tts attempt", attempt, "failed:", repr(e), flush=True)
if not ok:
    sys.exit("TTS failed after retries")

def dur(p):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p], timeout=60).decode())
D = dur("out/voice.mp3") + 0.4

# ---- captions: 3-word chunks, timed by character weight (+ pause after punctuation)
words = st["text"].split()
chunks = [" ".join(words[i:i+3]) for i in range(0, len(words), 3)]
weights = [len(c) + (8 if re.search(r"[।!?…,]$", c) else 0) for c in chunks]
total = sum(weights)
LEAD = 0.15
def t(s):
    return f"{int(s//3600)}:{int(s%3600//60):02d}:{s%60:05.2f}"
ev, cur = [], LEAD
for c, w in zip(chunks, weights):
    span = (D - LEAD - 0.3) * w / total
    ev.append(f"Dialogue: 0,{t(cur)},{t(cur+span)},D,{c}")
    cur += span
ass = f"""[Script Info]
PlayResX: {W}
PlayResY: {H}
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BorderStyle,Outline,Alignment,MarginV
Style: D,Noto Sans Devanagari,84,&H00FFFFFF,&H00000000,1,6,2,260
[Events]
Format: Layer,Start,End,Style,Text
""" + "\n".join(ev)
open("out/cap.ass", "w", encoding="utf-8").write(ass)

Q = {
 4:("Sita Rama bow Janaka swayamvar",["sita","bow","swayamvar","janaka"]),
 5:("Parashurama Rama bow",["parashur","parasur","bhargava"]),
 6:("Kaikeyi Dasharatha Rama exile",["kaikeyi","dasharatha","dashrath","manthara"]),
 7:("Rama Sita Lakshmana exile forest",["exile","forest","vanavasa","departure"]),
 8:("Rama Guha Ganges boat",["guha","ganges","ganga","boat"]),
 9:("Bharata Rama sandals Chitrakuta",["bharata","bharat","sandals","paduka","chitrakut"]),
 10:("Shurpanakha Rama Lakshmana",["shurpanakha","surpanakha","sarpanakha"]),
 11:("Maricha golden deer Sita",["maricha","marica","deer"]),
 12:("Ravana Sita abduction",["ravana","abduct","sita"]),
 13:("Jatayu Ravana Sita",["jatayu"]),
 14:("Shabari Rama",["shabari","sabari","shavari"]),
 15:("Hanuman meets Rama Lakshmana",["hanuman","rama"]),
 16:("Sugriva Vali Rama",["sugriva","vali","bali"]),
 17:("Sampati vulture Ramayana",["sampati","vulture"]),
 18:("Hanuman leaps ocean Lanka",["hanuman","ocean","leap"]),
 19:("Hanuman burns Lanka",["lanka","hanuman"]),
 20:("Vibhishana Rama",["vibhishana","bibhishana"]),
 21:("Rama bridge Lanka setu",["bridge","setu","nala"]),
 22:("Angada Ravana court",["angada","angad"]),
 23:("Kumbhakarna Ramayana",["kumbhakarna","kumbhkaran"]),
 24:("Hanuman sanjeevani mountain Lakshmana",["sanjeevani","sanjivani","mountain","laxmana","lakshmana"]),
 25:("Indrajit Meghnada Lakshmana",["indrajit","meghnad","meghanada"]),
 26:("Mandodari Ravana",["mandodari"]),
 27:("Rama kills Ravana battle Lanka",["ravana","battle","lanka"]),
 28:("Sita agni pariksha fire",["agni","fire","sita"]),
 29:("Rama Sita return Ayodhya Pushpaka",["ayodhya","pushpaka","return","coronation"]),
 30:("Urmila Lakshmana",["urmila"]),
 31:("Lava Kusha Valmiki",["lava","kusha","valmiki"]),
}
m = re.search(r"Episode (\d+)", st["title"])
ep = int(m.group(1)) if m else 0
search_q, keys = Q.get(ep, (st["title"].split(" - ")[0], [st["title"].split()[0].lower()]))

UA = {"User-Agent": "RamayanDailyBot/1.0 (personal educational channel)"}
def search(q):
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
            "action":"query","generator":"search","gsrsearch":q+" filetype:bitmap","gsrnamespace":6,"gsrlimit":50,
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
pool = []
for q in (search_q + " Ramayana", search_q, "Ramayana " + keys[0]):
    for c in search(q):
        if c not in pool: pool.append(c)
prio = [c for c in pool if any(k in c[0].lower() for k in keys) and any(w in c[0].lower() for w in ("ramayan","rama","sita","hanuman","ravan","lanka","laksh"))]
rest = [c for c in pool if c not in prio and ("ramayan" in c[0].lower() or "rama " in c[0].lower())]
if len(prio) < 3:
    for q in ("Ramayana painting", "Mewar Ramayana"):
        for c in search(q):
            if c not in rest and c not in prio and "ramayan" in c[0].lower(): rest.append(c)
random.shuffle(prio); random.shuffle(rest)
cands = prio + rest
print("episode", ep, "matched", len(prio), "fillers", len(rest), flush=True)

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
                               "-an","-c:v","libx264","-preset","veryfast","-crf","23","-pix_fmt","yuv420p",out], timeout=300)
        clips.append(out); credits.append(re.sub(r"^File:", "", title))
    except Exception as e:
        print("clip failed, skipping:", e, flush=True)

if clips:
    open("out/list.txt", "w").write("".join(f"file '{os.path.basename(c)}'\n" for c in clips))
    src = ["-f","concat","-safe","0","-i","out/list.txt"]
    vf = "subtitles=out/cap.ass"
else:
    print("no images, using gradient fallback")
    src = ["-f","lavfi","-i",f"gradients=s={W}x{H}:c0=0x2b1200:c1=0xff9933:c2=0x7a1f00:x0=540:y0=0:x1=540:y1=1920:speed=0.03:d={D:.2f}:r=30"]
    vf = "format=yuv420p,subtitles=out/cap.ass"

subprocess.check_call(["ffmpeg","-y",*src,"-i","out/voice.mp3","-t",f"{D:.2f}","-vf",vf,
  "-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-shortest","-pix_fmt","yuv420p","out/video.mp4"], timeout=600)

desc = "Roz ek Ramayan katha. #ramayan #shorts #jaishreeram"
if credits:
    desc += "\nImages (public domain, Wikimedia Commons): " + "; ".join(credits[:6])
json.dump({"title": f"{st['title']} | Ramayan Katha #Shorts"[:100], "description": desc},
          open("out/meta.json", "w"), ensure_ascii=False)
print("done", D, "images:", len(clips), flush=True)

# publish latest.mp4 / latest.json to the repo (never hang on prompts)
env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_EDITOR="true", GIT_SEQUENCE_EDITOR="true")
def git(*a):
    try:
        return subprocess.run(["git", *a], check=False, timeout=120, env=env).returncode
    except Exception as e:
        print("git", a, "failed:", e, flush=True); return 1
try:
    shutil.copy("out/video.mp4", "latest.mp4")
    shutil.copy("out/meta.json", "latest.json")
    git("config", "user.name", "bot")
    git("config", "user.email", "bot@users.noreply.github.com")
    git("add", "latest.mp4", "latest.json")
    git("commit", "-m", "daily video")
    for _ in range(3):
        git("pull", "--rebase", "--autostash")
        if git("push") == 0: print("push ok"); break
except Exception as e:
    print("publish step failed:", e, flush=True)
