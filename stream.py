import os, time, random, subprocess, threading, urllib.request, urllib.parse, json
from datetime import datetime, timezone, timedelta
import pytchat
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# ========================================================
# आसान सेटिंग्स (जब चाहें यहाँ से समय या टेक्स्ट बदलें)
# ========================================================
IMAGE_CHANGE_SECONDS = 600   # फोटो बदलने का समय सेकंड में (300 = 5 मिनट, 600 = 10 मिनट, 900 = 15 मिनट)
CHANNEL_DISPLAY = "@Talkto-urs"
TICKER_TEXT = "SUBSCRIBE @Talkto-urs  •  Like & Share for 24/7 Relaxing Music  •  Stay Connected"
COOLDOWN_SECONDS = 3600      # 1 घंटे बाद दोबारा चैट वेलकम दिखाने के लिए

STREAM_HOST = "a.rtmp." + "youtube.com"
STREAM_URL = "rtmp://" + STREAM_HOST + "/live2"
STREAM_KEY = "weq2-6vuu-c3dh-x0td-emvf"

last_welcomed = {}
current_proc = None
active_slot = None
target_broadcast_id = None

def log(msg):
    print(msg, flush=True)

def get_ist_hour():
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).hour

def get_slot_config():
    h = get_ist_hour()
    if 5 <= h < 12:
        return ("morning", "morning acoustic flute relaxing instrumental",
                "Morning Peaceful Flute & Nature Music | 24/7 Positive Energy Live",
                "Start your morning with peaceful flute melodies.\n#MorningMusic #RelaxingLive")
    elif 12 <= h < 17:
        return ("afternoon", "calm study focus ambient piano instrumental",
                "Deep Focus & Study Instrumental Music | Calm Ambient Piano 24/7 Live",
                "Best calm ambient piano for deep focus and work.\n#StudyMusic #FocusLive")
    elif 17 <= h < 21:
        return ("evening", "sunset lofi chill beats relaxing",
                "Evening Sunset Lofi & Chill Vibes | Relaxing Beats 24/7 Live",
                "Unwind your evening with smooth sunset lofi chill beats.\n#EveningChill #LofiLive")
    else:
        return ("night", "deep sleep rain ambient music relaxing",
                "Deep Sleep & Peaceful Night Rain Music | Stress Relief 24/7 Live",
                "Fall asleep fast with soothing night rain melodies.\n#SleepMusic #NightRain")

def get_youtube_service():
    token_str = os.environ.get("YT_TOKEN_JSON", "").strip()
    if not token_str:
        return None
    try:
        creds = Credentials.from_authorized_user_info(json.loads(token_str))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        log(f"YouTube API Token Error: {e}")
        return None

def create_stylish_thumbnail(base_img="bg.jpg", out_thumb="stylish_thumb.jpg", slot_name="LIVE"):
    try:
        img = Image.open(base_img).convert("RGB").resize((1280, 720))
        # बैकग्राउंड को थोड़ा डार्क और सिनेमैटिक बनाना ताकि टेक्स्ट चमक कर दिखे
        img = ImageEnhance.Brightness(img).enhance(0.55)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        draw = ImageDraw.Draw(img)

        # चारों तरफ सुनहरा बॉर्डर
        draw.rectangle([15, 15, 1265, 705], outline="#FFD700", width=8)

        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f_big = ImageFont.truetype(font_path, 76)
        f_med = ImageFont.truetype(font_path, 42)
        f_small = ImageFont.truetype(font_path, 32)

        # समय के हिसाब से आकर्षक मुख्य हेडिंग
        headings = {
            "morning": ("MORNING PEACEFUL", "FLUTE & NATURE VIBES"),
            "afternoon": ("DEEP FOCUS & STUDY", "CALM AMBIENT PIANO"),
            "evening": ("EVENING SUNSET", "LOFI & CHILL BEATS"),
            "night": ("DEEP SLEEP MUSIC", "PEACEFUL NIGHT RAIN")
        }
        line1, line2 = headings.get(slot_name, ("24/7 RELAXING", "INSTRUMENTAL MUSIC"))

        # ऊपर लाल रंग का LIVE बैज
        draw.rectangle([50, 50, 290, 115], fill="#E50914")
        draw.text((75, 63), "● 24/7 LIVE", fill="white", font=f_small)

        # ऊपर दाईं तरफ चैनल का नाम
        draw.text((920, 63), CHANNEL_DISPLAY, fill="#FFD700", font=f_med)

        # बीच में बड़ा स्टाइलिश टाइटल (शैडो के साथ)
        draw.text((74, 264), line1, fill="black", font=f_big)
        draw.text((70, 260), line1, fill="#FFD700", font=f_big)

        draw.text((74, 364), line2, fill="black", font=f_big)
        draw.text((70, 360), line2, fill="white", font=f_big)

        # नीचे की पट्टी
        draw.rectangle([50, 560, 780, 625], fill=(0, 0, 0))
        draw.text((70, 573), "NO COPYRIGHT • RELAX • SLEEP • FOCUS", fill="#00E676", font=f_small)

        img.save(out_thumb, "JPEG", quality=95)
        return out_thumb
    except Exception as e:
        log(f"Thumbnail design note: {e}")
        return base_img

def update_only_this_live_seo(title, description, thumb_path="bg.jpg"):
    global target_broadcast_id
    yt = get_youtube_service()
    if not yt:
        return

    designed_thumb = create_stylish_thumbnail(thumb_path, "stylish_thumb.jpg", active_slot)

    for attempt in range(6):
        time.sleep(15)
        try:
            streams_res = yt.liveStreams().list(part="id,cdn", mine=True).execute()
            my_stream_id = None
            for item in streams_res.get("items", []):
                if item.get("cdn", {}).get("ingestionInfo", {}).get("streamName") == STREAM_KEY:
                    my_stream_id = item["id"]
                    break

            b_res = yt.liveBroadcasts().list(part="id,snippet,contentDetails,status", mine=True, maxResults=10).execute()
            for b in b_res.get("items", []):
                bound_id = b.get("contentDetails", {}).get("boundStreamId")
                life_cycle = b.get("status", {}).get("lifeCycleStatus")
                if my_stream_id and bound_id == my_stream_id and life_cycle in ["live", "testing", "ready"]:
                    target_broadcast_id = b["id"]
                    snippet = b["snippet"]
                    snippet["title"] = title
                    snippet["description"] = description
                    yt.liveBroadcasts().update(part="snippet", body={"id": target_broadcast_id, "snippet": snippet}).execute()
                    
                    if os.path.exists(designed_thumb):
                        yt.thumbnails().set(
                            videoId=target_broadcast_id,
                            media_body=MediaFileUpload(designed_thumb, mimetype="image/jpeg")
                        ).execute()
                    log(f"SUCCESS: Stylish Thumbnail, Title & Description Updated -> {title}")
                    return
        except Exception as e:
            log(f"SEO Update Error: {e}")
def fetch_online_songs(query, folder="songs"):
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        try: os.remove(os.path.join(folder, f))
        except: pass
    try:
        arch_host = "archive" + ".org"
        q = urllib.parse.quote(f'({query}) AND mediatype:(audio) AND licenseurl:(*publicdomain* OR *zero*)')
        url = f"https://{arch_host}/advancedsearch.php?q={q}&fl[]=identifier&rows=30&page=1&output=json"
        docs = json.loads(urllib.request.urlopen(url, timeout=15).read().decode()).get("response", {}).get("docs", [])
        random.shuffle(docs)
        count = 0
        for doc in docs:
            if count >= 12: break
            ident = doc["identifier"]
            meta = json.loads(urllib.request.urlopen(f"https://{arch_host}/metadata/{ident}", timeout=10).read().decode())
            for fi in meta.get("files", []):
                fn = fi.get("name", "")
                if fn.lower().endswith(".mp3") and int(fi.get("size", 0)) < 15000000:
                    urllib.request.urlretrieve(f"https://{arch_host}/download/{ident}/{urllib.parse.quote(fn)}", os.path.join(folder, f"track_{count}.mp3"))
                    count += 1
                    break
    except Exception as e:
        log(f"Song fetch note: {e}")

    if len(os.listdir(folder)) == 0:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anoisesrc=c=pink:r=44100:a=0.04,aecho=0.8:0.88:60:0.4",
            "-t", "300", "-b:a", "128k", os.path.join(folder, "ambient_rain.mp3")
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def fetch_multiple_images(folder="pics", count=12):
    os.makedirs(folder, exist_ok=True)
    pic_host = "picsum" + ".photos"
    for i in range(count):
        out_img = os.path.join(folder, f"pic_{i}.jpg")
        try:
            seed = random.randint(1, 99999)
            urllib.request.urlretrieve(f"https://{pic_host}/seed/{seed}/1280/720", out_img)
        except Exception:
            pass
        if not os.path.exists(out_img) or os.path.getsize(out_img) < 5000:
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x16213e:s=1280x720:d=1", "-frames:v", "1", out_img], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(os.path.join(folder, "pic_0.jpg")):
        subprocess.run(["cp", os.path.join(folder, "pic_0.jpg"), "bg.jpg"])
        subprocess.run(["cp", os.path.join(folder, "pic_0.jpg"), "live_bg.jpg"])

def build_song_playlist():
    s_files = [os.path.abspath(os.path.join("songs", f)) for f in os.listdir("songs") if f.endswith(".mp3")]
    with open("playlist.txt", "w", encoding="utf-8") as f:
        for _ in range(50):
            random.shuffle(s_files)
            for p in s_files: f.write(f"file '{p}'\n")

# हर IMAGE_CHANGE_SECONDS में बिना स्ट्रीम रोके बैकग्राउंड फोटो बदलने वाला थ्रेड
def image_rotator_loop():
    idx = 1
    while True:
        time.sleep(IMAGE_CHANGE_SECONDS)
        p_files = [os.path.join("pics", f) for f in os.listdir("pics") if f.endswith(".jpg")]
        if p_files:
            chosen = p_files[idx % len(p_files)]
            idx += 1
            subprocess.run(["cp", chosen, "temp_bg.jpg"])
            os.replace("temp_bg.jpg", "live_bg.jpg")
            log(f"Background image rotated -> {chosen}")

def set_welcome_text(msg):
    with open("welcome.txt", "w", encoding="utf-8") as f: f.write(msg)

def chat_listener():
    set_welcome_text(f"Welcome to {CHANNEL_DISPLAY}!")
    time.sleep(12)
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
            log(f"Slot changed ({active_slot} -> {new_slot})! Updating all media & SEO...")
            active_slot = new_slot
            if current_proc:
                current_proc.terminate()

def start_auto_cloud_live():
    global current_proc, active_slot
    rtmp_url = f"{STREAM_URL}/{STREAM_KEY}"
    set_welcome_text("")
    threading.Thread(target=chat_listener, daemon=True).start()
    threading.Thread(target=time_watcher, daemon=True).start()
    threading.Thread(target=image_rotator_loop, daemon=True).start()

    f1 = "[0:v]scale=1280:720,format=yuv420p[bg];"
    f2 = "[1:a]showwaves=s=1280x50:mode=line:rate=24:colors=white@0.4[waves];[bg][waves]overlay=0:H-50[with_waves];"
    f3 = f"[with_waves]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{CHANNEL_DISPLAY}  •  24/7 LIVE':fontcolor=white@0.9:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=10:x=25:y=25,"
    f4 = f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{TICKER_TEXT}':fontcolor=white@0.85:fontsize=24:box=1:boxcolor=black@0.45:boxborderw=8:x=w-mod(t*95\\,w+tw):y=h-92,"
    f5 = "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:textfile=welcome.txt:reload=1:fontcolor=yellow:fontsize=34:box=1:boxcolor=black@0.75:boxborderw=12:x=w-mod(t*180\\,w+tw):y=h-145[vout]"
    filter_complex = f1 + f2 + f3 + f4 + f5

    while True:
        slot, song_q, yt_title, yt_desc = get_slot_config()
        active_slot = slot
        log(f"Starting smooth slot: {slot.upper()}")
        fetch_online_songs(song_q)
        fetch_multiple_images("pics", 12)
        build_song_playlist()

        threading.Thread(target=update_only_this_live_seo, args=(yt_title, yt_desc, "bg.jpg"), daemon=True).start()

        cmd = [
            "ffmpeg", "-re",
            "-f", "image2", "-loop", "1", "-r", "24", "-i", "live_bg.jpg",
            "-f", "concat", "-safe", "0", "-stream_loop", "-1", "-i", "playlist.txt",
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "1800k",
            "-maxrate", "1800k", "-bufsize", "3600k", "-pix_fmt", "yuv420p",
            "-g", "48", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-f", "flv", rtmp_url
        ]
        try:
            current_proc = subprocess.Popen(cmd)
            current_proc.wait()
        except Exception as e:
            log(f"Stream reset: {e}")
        time.sleep(3)

if __name__ == "__main__":
    start_auto_cloud_live()
