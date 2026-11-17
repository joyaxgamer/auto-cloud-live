import os
import time
import random
import base64
import subprocess
import threading
import urllib.request
import urllib.parse
import json
from datetime import datetime, timezone, timedelta
import pytchat
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

STREAM_URL = base64.b64decode("cnRtcDovL2EucnRtcC55b3V0dWJlLmNvbS9saXZlMg==").decode()
STREAM_KEY = "weq2-6vuu-c3dh-x0td-emvf"
CHANNEL_HANDLE = "@Talkto-urs"
COOLDOWN_SECONDS = 3600

last_welcomed = {}
current_proc = None
active_slot = None
target_broadcast_id = None

def get_ist_hour():
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).hour

def get_slot_config():
    hour = get_ist_hour()
    if 5 <= hour < 12:
        return ("morning", "morning acoustic flute relaxing instrumental", "Morning Peaceful Flute & Nature Music | 24/7 Positive Energy Live", "Start your morning with peaceful acoustic flute and nature melodies.")
    elif 12 <= hour < 17:
        return ("afternoon", "calm study focus ambient piano instrumental", "Deep Focus & Study Instrumental Music | Calm Ambient Piano 24/7 Live", "Best calm ambient piano music for deep focus and work.")
    elif 17 <= hour < 21:
        return ("evening", "sunset lofi chill beats relaxing", "Evening Sunset Lofi & Chill Vibes | Relaxing Beats 24/7 Live Radio", "Unwind your evening with smooth sunset lofi chill beats.")
    else:
        return ("night", "deep sleep rain ambient music relaxing", "Deep Sleep & Peaceful Night Rain Music | Stress Relief 24/7 Live", "Fall asleep fast with soothing night rain ambient melodies.")

def get_youtube_service():
    token_str = os.environ.get("YT_TOKEN_JSON", "").strip()
    if not token_str:
        return None
    try:
        info = json.loads(token_str)
        creds = Credentials.from_authorized_user_info(info)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        print("API Error:", e)
        return None

def update_only_this_live_seo(title, description, thumb_path="bg.jpg"):
    global target_broadcast_id
    yt = get_youtube_service()
    if not yt:
        return
    try:
        streams_res = yt.liveStreams().list(part="id,cdn", mine=True).execute()
        my_stream_id = None
        for item in streams_res.get("items", []):
            if item.get("cdn", {}).get("ingestionInfo", {}).get("streamName") == STREAM_KEY:
                my_stream_id = item["id"]
                break
        b_res = yt.liveBroadcasts().list(part="id,snippet,contentDetails", broadcastStatus="active").execute()
        for b in b_res.get("items", []):
            if my_stream_id and b.get("contentDetails", {}).get("boundStreamId") == my_stream_id:
                target_broadcast_id = b["id"]
                snippet = b["snippet"]
                snippet["title"] = title
                snippet["description"] = description
                yt.liveBroadcasts().update(part="snippet", body={"id": target_broadcast_id, "snippet": snippet}).execute()
                print("Title updated:", title)
                if os.path.exists(thumb_path):
                    yt.thumbnails().set(videoId=target_broadcast_id, media_body=MediaFileUpload(thumb_path, mimetype="image/jpeg")).execute()
                    print("Thumbnail updated!")
                return
    except Exception as e:
        print("SEO Error:", e)

def fetch_online_songs(query, folder="songs"):
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        try: os.remove(os.path.join(folder, f))
        except: pass
    try:
        host = base64.b64decode("aHR0cHM6Ly9hcmNoaXZlLm9yZw==").decode()
        q = urllib.parse.quote(f'({query}) AND mediatype:(audio) AND licenseurl:(*creativecommons* OR *publicdomain*)')
        req = urllib.request.urlopen(f"{host}/advancedsearch.php?q={q}&fl[]=identifier&rows=15&page=1&output=json", timeout=15)
        docs = json.loads(req.read().decode()).get("response", {}).get("docs", [])
        random.shuffle(docs)
        downloaded = 0
        for doc in docs:
            if downloaded >= 5: break
            ident = doc["identifier"]
            meta = json.loads(urllib.request.urlopen(f"{host}/metadata/{ident}", timeout=10).read().decode())
            for f_info in meta.get("files", []):
                fname = f_info.get("name", "")
                if fname.lower().endswith(".mp3") and int(f_info.get("size", 0)) < 15000000:
                    urllib.request.urlretrieve(f"{host}/download/{ident}/{urllib.parse.quote(fname)}", os.path.join(folder, f"track_{downloaded}.mp3"))
                    downloaded += 1
                    break
    except Exception:
        pass
    if len(os.listdir(folder)) == 0:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=c=pink:r=44100:a=0.05", "-t", "300", "-b:a", "128k", os.path.join(folder, "rain.mp3")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def fetch_online_image(out_img="bg.jpg"):
    try:
        img_host = base64.b64decode("aHR0cHM6Ly9waWNzdW0ucGhvdG9z").decode()
        urllib.request.urlretrieve(f"{img_host}/seed/{random.randint(1, 10000)}/1280/720", out_img)
        if os.path.exists(out_img) and os.path.getsize(out_img) > 5000:
            return
    except Exception:
        pass
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1a1a2e:s=1280x720:d=1", "-frames:v", "1", out_img], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def build_playlist(folder="songs", list_file="playlist.txt"):
    files = [os.path.abspath(os.path.join(folder, f)) for f in os.listdir(folder) if f.endswith(".mp3")]
    with open(list_file, "w", encoding="utf-8") as f:
        for _ in range(50):
            random.shuffle(files)
            for path in files:
                f.write(f"file '{path}'\n")

def set_welcome_text(msg):
    with open("welcome.txt", "w", encoding="utf-8") as f:
        f.write(msg)

def chat_listener():
    set_welcome_text("Auto SEO Live Ready!")
    time.sleep(10)
    set_welcome_text("")
    while True:
        try:
            if not target_broadcast_id:
                time.sleep(10)
                continue
            chat = pytchat.create(video_id=target_broadcast_id)
            time.sleep(3)
            if chat.is_alive(): chat.get()
            while chat.is_alive():
                for c in chat.get().sync_items():
                    user = c.author.name
                    now = time.time()
                    prev = last_welcomed.get(user, 0)
                    if (now - prev) >= COOLDOWN_SECONDS:
                        last_welcomed[user] = now
                        set_welcome_text(f"Welcome {user}!" if prev == 0 else f"Welcome Back {user}!")
                        time.sleep(8)
                        set_welcome_text("")
                time.sleep(1)
        except Exception:
            time.sleep(5)

def time_watcher():
    global current_proc, active_slot
    while True:
        time.sleep(60)
        new_slot, _, _, _ = get_slot_config()
        if active_slot and new_slot != active_slot:
            if current_proc: current_proc.terminate()

def start_auto_cloud_live():
    global current_proc, active_slot
    rtmp_url = f"{STREAM_URL}/{STREAM_KEY}"
    set_welcome_text("")
    threading.Thread(target=chat_listener, daemon=True).start()
    threading.Thread(target=time_watcher, daemon=True).start()
    vf = "scale=1280:720,format=yuv420p,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:textfile=welcome.txt:reload=1:fontcolor=yellow:fontsize=38:box=1:boxcolor=black@0.8:boxborderw=14:x=w-mod(t*190\\,w+tw):y=h-85"
    while True:
        slot, song_q, yt_title, yt_desc = get_slot_config()
        active_slot = slot
        fetch_online_songs(song_q)
        fetch_online_image("bg.jpg")
        build_playlist()
        threading.Timer(15.0, update_only_this_live_seo, args=[yt_title, yt_desc, "bg.jpg"]).start()
        cmd = ["ffmpeg", "-re", "-loop", "1", "-i", "bg.jpg", "-f", "concat", "-safe", "0", "-stream_loop", "-1", "-i", "playlist.txt", "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "1500k", "-maxrate", "1500k", "-bufsize", "3000k", "-pix_fmt", "yuv420p", "-g", "48", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-map", "0:v:0", "-map", "1:a:0", "-f", "flv", rtmp_url]
        try:
            current_proc = subprocess.Popen(cmd)
            current_proc.wait()
        except Exception:
            pass
        time.sleep(3)

if __name__ == "__main__":
    start_auto_cloud_live()
