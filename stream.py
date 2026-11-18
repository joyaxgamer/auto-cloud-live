import os, time, random, subprocess, threading, urllib.request, urllib.parse, json
from datetime import datetime, timezone, timedelta
import pytchat
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# ========================================================
# आसान कंट्रोल बॉक्स (जब चाहें यहाँ से समय, आवाज़ या टेक्स्ट बदलें)
# ========================================================
IMAGE_CHANGE_SECONDS = 600   # हर 10 मिनट (600 सेकंड) में बैकग्राउंड फोटो बदलेगी
MUSIC_VOLUME = 1.0           # संगीत की आवाज़ (2.2 = दोगुनी तेज़ और साफ़ आवाज़)
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
        return (
            "morning",
            "peaceful flute acoustic guitar morning instrumental music",
            "PEACEFUL MORNING • BOOST ENERGY • FRESH START",
            "Morning Peaceful Flute & Nature Music | 24/7 Positive Energy Live",
            "Start your morning with peaceful flute melodies and positive vibes.\n#MorningMusic #BoostEnergy #RelaxingLive"
        )
    elif 12 <= h < 17:
        return (
            "afternoon",
            "soft solo piano relaxing study instrumental music",
            "DEEP FOCUS • STUDY & WORK • CALM MIND",
            "Deep Focus & Study Instrumental Music | Calm Ambient Piano 24/7 Live",
            "Best calm ambient piano for deep focus, reading, and work.\n#StudyMusic #FocusLive #AmbientPiano"
        )
    elif 17 <= h < 21:
        return (
            "evening",
            "chillhop lofi beats relaxing guitar instrumental",
            "EVENING CHILL • SUNSET LOFI • RELAXING VIBES",
            "Evening Sunset Lofi & Chill Vibes | Relaxing Beats 24/7 Live",
            "Unwind your evening with smooth sunset lofi chill beats and guitar.\n#EveningChill #LofiLive #SunsetVibes"
        )
    else:
        return (
            "night",
            "deep sleep soft piano ambient meditation instrumental",
            "DEEP SLEEP • PEACEFUL NIGHT • STRESS RELIEF",
            "Deep Sleep & Peaceful Night Rain Music | Stress Relief 24/7 Live",
            "Fall asleep fast with soothing night rain and deep sleep ambient melodies.\n#SleepMusic #NightRain #DeepSleepLive"
        )

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

def create_stylish_thumbnail(base_img="bg.jpg", out_thumb="stylish_thumb.jpg", slot_name="LIVE", tagline="24/7 LIVE STREAM"):
    try:
        img = Image.open(base_img).convert("RGB").resize((1280, 720))
        img = ImageEnhance.Brightness(img).enhance(0.55)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        draw = ImageDraw.Draw(img)

        draw.rectangle([(15, 15), (1265, 705)], outline="#FFD700", width=8)

        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f_big = ImageFont.truetype(font_path, 76)
        f_med = ImageFont.truetype(font_path, 42)
        f_small = ImageFont.truetype(font_path, 30)

        headings = {
            "morning": ("MORNING PEACEFUL", "FLUTE & NATURE VIBES"),
            "afternoon": ("DEEP FOCUS & STUDY", "CALM AMBIENT PIANO"),
            "evening": ("EVENING SUNSET", "LOFI & CHILL BEATS"),
            "night": ("DEEP SLEEP MUSIC", "PEACEFUL NIGHT RAIN")
        }
        line1, line2 = headings.get(slot_name, ("24/7 RELAXING", "INSTRUMENTAL MUSIC"))

        draw.rectangle([(60, 50), (310, 110)], fill="#E50914")
        draw.text((75, 63), "● 24/7 LIVE", fill="white", font=f_small)
        draw.text((920, 63), CHANNEL_DISPLAY, fill="#FFD700", font=f_med)

        draw.text((74, 264), line1, fill="black", font=f_big)
        draw.text((70, 260), line1, fill="#FFD700", font=f_big)

        draw.text((74, 364), line2, fill="black", font=f_big)
        draw.text((70, 360), line2, fill="white", font=f_big)

        draw.rectangle([(60, 560), (1080, 620)], fill=(0, 0, 0))
        draw.text((75, 575), tagline, fill="#00E676", font=f_small)

        img.save(out_thumb, "JPEG", quality=95)
        return out_thumb
    except Exception as e:
        log(f"Thumbnail design note: {e}")
        return base_img

def update_only_this_live_seo(title, description, thumb_path="bg.jpg", tagline="24/7 LIVE STREAM"):
    global target_broadcast_id
    yt = get_youtube_service()
    if not yt:
        return

    designed_thumb = create_stylish_thumbnail(thumb_path, "stylish_thumb.jpg", active_slot, tagline)

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
import shutil

def fetch_online_songs(query, slot_name="morning", folder="songs"):
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        try: os.remove(os.path.join(folder, f))
        except: pass

    # आपकी GitHub Release (v1.0) से सीधे आपके अपलोड किए हुए गाने डाउनलोड करना
    try:
        api_h = "api." + "github.com"
        rel_url = f"https://{api_h}/repos/joyaxgamer/auto-cloud-live/releases/tags/v1.0"
        req = urllib.request.Request(rel_url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        assets = data.get("assets", [])

        # केवल मौजूदा स्लॉट (morning, afternoon, evening, night) के गाने ही चुनना
        matched = [
            a for a in assets
            if a.get("name", "").lower().endswith(".mp3")
            and a.get("name", "").lower().startswith(slot_name.lower())
        ]

        # बैकअप: यदि किसी स्लॉट की फाइल न मिले तो Release के कोई भी mp3 उठा लेना
        if not matched:
            matched = [a for a in assets if a.get("name", "").lower().endswith(".mp3")]

        matched.sort(key=lambda x: x.get("name", ""))

        for idx, asset in enumerate(matched):
            dl_url = asset.get("browser_download_url")
            orig_name = asset.get("name")
            save_path = os.path.join(folder, f"track_{idx}.mp3")
            urllib.request.urlretrieve(dl_url, save_path)
            log(f"Loaded From Release [{slot_name.upper()}] #{idx+1}: {orig_name}")
    except Exception as e:
        log(f"Release song load note: {e}")

    # अंतिम सुरक्षा: यदि Release अभी न बनी हो तो मधुर हार्मोनिक कॉर्ड्स चलाना
    if len(os.listdir(folder)) == 0:
        log("Waiting for v1.0 release songs, playing soft harmonic chords...")
        melody_filter = (
            "aevalsrc='0.15*sin(2*PI*261.63*t)+0.12*sin(2*PI*329.63*t)+0.12*sin(2*PI*392.00*t)'"
            ":s=44100:d=300,afade=t=in:st=0:d=4,afade=t=out:st=296:d=4"
        )
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", melody_filter,
            "-b:a", "192k", os.path.join(folder, "melody.mp3")
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def fetch_multiple_images(folder="pics", count=12):
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        try: os.remove(os.path.join(folder, f))
        except: pass

    downloaded = 0
    try:
        b_host = "www." + "bing.com"
        bing_api = f"https://{b_host}/HPImageArchive.aspx?format=js&idx=0&n=8&mkt=en-US"
        req = urllib.request.Request(bing_api, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        for item in data.get("images", []):
            if downloaded >= count:
                break
            img_path = item.get("url", "")
            if img_path:
                full_url = f"https://{b_host}{img_path}"
                out_img = os.path.join(folder, f"pic_{downloaded}.jpg")
                urllib.request.urlretrieve(full_url, out_img)
                if os.path.exists(out_img) and os.path.getsize(out_img) > 15000:
                    with Image.open(out_img) as im:
                        im.convert("RGB").resize((1280, 720)).save(out_img, "JPEG", quality=92)
                    log(f"Bing HD Nature Photo Saved: {downloaded+1}")
                    downloaded += 1
    except Exception as e:
        log(f"Bing photo note: {e}")

    nature_seeds = {
        "morning": list((10, 11, 13, 14, 15, 16, 17, 28, 29)),
        "afternoon": list((18, 19, 24, 25, 37, 42, 48, 54, 57)),
        "evening": list((65, 70, 74, 82, 84, 88, 92, 103, 110)),
        "night": list((116, 120, 124, 128, 134, 141, 145, 152, 160))
    }
    seeds = nature_seeds.get(active_slot, list((10, 11, 13, 14, 15)))
    random.shuffle(seeds)

    pic_host = "picsum." + "photos"
    for s in seeds:
        if downloaded >= count:
            break
        out_img = os.path.join(folder, f"pic_{downloaded}.jpg")
        try:
            url = f"https://{pic_host}/id/{s}/1280/720"
            req_img = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_img, timeout=15) as r, open(out_img, "wb") as out_f:
                out_f.write(r.read())
            if os.path.exists(out_img) and os.path.getsize(out_img) > 15000:
                log(f"Curated Nature Photo Saved: {downloaded+1} (ID {s})")
                downloaded += 1
        except Exception:
            pass

    if os.path.exists(os.path.join(folder, "pic_0.jpg")):
        subprocess.run(["cp", os.path.join(folder, "pic_0.jpg"), "bg.jpg"])
        subprocess.run(["cp", os.path.join(folder, "pic_0.jpg"), "live_bg.jpg"])

def build_song_playlist():
    s_files = [os.path.abspath(os.path.join("songs", f)) for f in os.listdir("songs") if f.endswith(".mp3")]
    with open("playlist.txt", "w", encoding="utf-8") as f:
        for _ in range(50):
            random.shuffle(s_files)
            for p in s_files: f.write(f"file '{p}'\n")

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
        new_slot, _, _, _, _ = get_slot_config()
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
    f2 = f"[1:a]volume={MUSIC_VOLUME},asplit=2[aout][awaves];[awaves]showwaves=s=1280x50:mode=line:rate=24:colors=white@0.4[waves];[bg][waves]overlay=0:H-50[with_waves];"
    f3 = f"[with_waves]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{CHANNEL_DISPLAY}  •  24/7 LIVE':fontcolor=white@0.9:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=10:x=25:y=25,"
    f4 = f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{TICKER_TEXT}':fontcolor=white@0.85:fontsize=24:box=1:boxcolor=black@0.45:boxborderw=8:x=w-mod(t*95\\,w+tw):y=h-92,"
    f5 = "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:textfile=welcome.txt:reload=1:fontcolor=yellow:fontsize=34:box=1:boxcolor=black@0.75:boxborderw=12:x=w-mod(t*180\\,w+tw):y=h-145[vout]"
    filter_complex = f1 + f2 + f3 + f4 + f5

    while True:
        slot, song_q, tagline, yt_title, yt_desc = get_slot_config()
        active_slot = slot
        log(f"Starting upgraded slot: {slot.upper()}")
        fetch_online_songs(song_q, slot)
        fetch_multiple_images("pics", 12)
        build_song_playlist()

        threading.Thread(target=update_only_this_live_seo, args=(yt_title, yt_desc, "bg.jpg", tagline), daemon=True).start()

        cmd = [
            "ffmpeg", "-re",
            "-f", "image2", "-loop", "1", "-r", "24", "-i", "live_bg.jpg",
            "-f", "concat", "-safe", "0", "-stream_loop", "-1", "-i", "playlist.txt",
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "1800k",
            "-maxrate", "1800k", "-bufsize", "3600k", "-pix_fmt", "yuv420p",
            "-g", "48", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
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
