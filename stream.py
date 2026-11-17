import os
import time
import random
import subprocess
import threading
import urllib.request
import urllib.parse
import json
from datetime import datetime, timezone, timedelta
import pytchat

# ==========================================
# आपकी नई लाइव स्ट्रीम की सेटिंग्स
# ==========================================
STREAM_URL = "rtmp://a.rtmp.youtube.com/live2"
STREAM_KEY = "f0uh-d2zd-c6ck-4guv-atux"
CHANNEL_HANDLE = "@Talkto-urs"
COOLDOWN_SECONDS = 3600

last_welcomed = {}
current_proc = None
active_slot = None

def get_ist_hour():
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).hour

def get_slot_config():
    hour = get_ist_hour()
    if 5 <= hour < 12:
        return "morning", "morning acoustic flute relaxing instrumental", "sunrise nature aesthetic wallpaper"
    elif 12 <= hour < 17:
        return "afternoon", "calm study focus ambient piano instrumental", "peaceful forest lake aesthetic"
    elif 17 <= hour < 21:
        return "evening", "sunset lofi chill beats relaxing", "sunset aesthetic sky clouds"
    else:
        return "night", "deep sleep rain ambient music relaxing", "night stars moon aesthetic"

def fetch_online_songs(query, folder="songs"):
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        try: os.remove(os.path.join(folder, f))
        except: pass

    print(f"🌐 ऑनलाइन नो-कॉपीराइट गाने खोजे जा रहे हैं: '{query}'...")
    try:
        q = urllib.parse.quote(f'({query}) AND mediatype:(audio) AND licenseurl:(*creativecommons* OR *publicdomain*)')
        search_url = f"https://archive.org{q}&fl[]=identifier&rows=15&page=1&output=json"
        req = urllib.request.urlopen(search_url, timeout=15)
        data = json.loads(req.read().decode())
        docs = data.get("response", {}).get("docs", [])
        random.shuffle(docs)

        downloaded = 0
        for doc in docs:
            if downloaded >= 5:
                break
            ident = doc["identifier"]
            meta_url = f"https://archive.org{ident}"
            meta = json.loads(urllib.request.urlopen(meta_url, timeout=10).read().decode())
            for f_info in meta.get("files", []):
                fname = f_info.get("name", "")
                if fname.lower().endswith(".mp3") and int(f_info.get("size", 0)) < 15000000:
                    dl_url = f"https://archive.org{ident}/{urllib.parse.quote(fname)}"
                    save_path = os.path.join(folder, f"track_{downloaded}.mp3")
                    urllib.request.urlretrieve(dl_url, save_path)
                    print(f"✅ गाना डाउनलोड हुआ: {fname}")
                    downloaded += 1
                    break
    except Exception as e:
        print(f"⚠️ ऑनलाइन गाना डाउनलोड करने में समस्या: {e}")

    if len(os.listdir(folder)) == 0:
        print("🌧️ बैकअप शांत बारिश का ऑडियो तैयार किया जा रहा है...")
        fallback_mp3 = os.path.join(folder, "rain_fallback.mp3")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=c=pink:r=44100:a=0.05",
            "-t", "300", "-b:a", "128k", fallback_mp3
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def fetch_online_image(query, out_img="bg.jpg"):
    print(f"🖼️ ऑनलाइन बैकग्राउंड फोटो डाउनलोड की जा रही है ({query})...")
    try:
        seed = random.randint(1, 10000)
        img_url = f"https://picsum.photos{seed}/1280/720"
        urllib.request.urlretrieve(img_url, out_img)
        if os.path.exists(out_img) and os.path.getsize(out_img) > 5000:
            print("✅ नई बैकग्राउंड फोटो सेट हो गई!")
            return
    except Exception as e:
        print(f"⚠️ फोटो डाउनलोड एरर: {e}")

    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1a1a2e:s=1280x720:d=1",
        "-frames:v", "1", out_img
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def build_playlist(folder="songs", list_file="playlist.txt"):
    files = [os.path.abspath(os.path.join(folder, f)) for f in os.listdir(folder) if f.endswith(".mp3")]
    random.shuffle(files)
    with open(list_file, "w", encoding="utf-8") as f:
        for _ in range(50):
            random.shuffle(files)
            for path in files:
                f.write(f"file '{path}'\n")

def set_welcome_text(msg):
    with open("welcome.txt", "w", encoding="utf-8") as f:
        f.write(msg)

def get_live_video_id():
    try:
        cmd = ["yt-dlp", "--get-id", "--playlist-items", "1", f"https://youtube.com{CHANNEL_HANDLE}/live"]
        res = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip().splitlines()
        for line in res:
            if len(line.strip()) == 11:
                return line.strip()
    except Exception:
        pass
    return None

def chat_listener():
    set_welcome_text("Auto Cloud Live Ready!")
    time.sleep(10)
    set_welcome_text("")
    while True:
        try:
            vid_id = get_live_video_id()
            if not vid_id:
                time.sleep(10)
                continue
            chat = pytchat.create(video_id=vid_id)
            time.sleep(3)
            if chat.is_alive():
                chat.get()
            while chat.is_alive():
                for c in chat.get().sync_items():
                    user = c.author.name
                    now = time.time()
                    prev_time = last_welcomed.get(user, 0)
                    if (now - prev_time) >= COOLDOWN_SECONDS:
                        last_welcomed[user] = now
                        label = f"Welcome {user}!" if prev_time == 0 else f"Welcome Back {user}!"
                        set_welcome_text(label)
                        time.sleep(8)
                        set_welcome_text("")
                time.sleep(1)
        except Exception:
            time.sleep(5)

def time_watcher():
    global current_proc, active_slot
    while True:
        time.sleep(60)
        new_slot, _, _ = get_slot_config()
        if active_slot and new_slot != active_slot:
            print(f"⏰ समय बदल गया ({active_slot} -> {new_slot})! नए ऑनलाइन गाने और फोटो लाए जा रहे हैं...")
            if current_proc:
                current_proc.terminate()

def start_auto_cloud_live():
    global current_proc, active_slot
    rtmp_url = f"{STREAM_URL}/{STREAM_KEY}"

    set_welcome_text("")
    threading.Thread(target=chat_listener, daemon=True).start()
    threading.Thread(target=time_watcher, daemon=True).start()

    vf_filter = (
        "scale=1280:720,format=yuv420p,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "textfile=welcome.txt:reload=1:fontcolor=yellow:fontsize=38:"
        "box=1:boxcolor=black@0.8:boxborderw=14:"
        "x=w-mod(t*190\\,w+tw):y=h-85"
    )

    while True:
        slot, song_query, img_query = get_slot_config()
        active_slot = slot
        print(f"🚀 नया स्लॉट शुरू हो रहा है: {slot.upper()}")

        fetch_online_songs(song_query)
        fetch_online_image(img_query)
        build_playlist()

        command = [
            "ffmpeg", "-re",
            "-loop", "1", "-i", "bg.jpg",
            "-f", "concat", "-safe", "0", "-stream_loop", "-1", "-i", "playlist.txt",
            "-vf", vf_filter,
            "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "1500k",
            "-maxrate", "1500k", "-bufsize", "3000k", "-pix_fmt", "yuv420p",
            "-g", "48", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-map", "0:v:0", "-map", "1:a:0",
            "-f", "flv", rtmp_url
        ]

        try:
            current_proc = subprocess.Popen(command)
            current_proc.wait()
        except Exception as e:
            print(f"स्ट्रीम रीसेट हुई: {e}")
        time.sleep(3)

if __name__ == "__main__":
    start_auto_cloud_live()
