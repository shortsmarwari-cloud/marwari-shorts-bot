import os
import json
import time
import random
import numpy as np
import yt_dlp
import requests
from PIL import Image, ImageDraw, ImageFont
# ✅ NEW (Works across MoviePy versions)
from moviepy.editor import (
    VideoFileClip,
    concatenate_videoclips,
    AudioFileClip,
    CompositeAudioClip,
    ImageClip,
    CompositeVideoClip
)
from pydub import AudioSegment
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
HISTORY_FILE = "upload_history.json"
CHANNEL_WATERMARK = "@MarwariShorts"

# --- PIL TEXT CREATION ---
def create_text_banner_pil(text, font_size=50, text_color="yellow", bg_color=(0, 0, 0, 180), width=1080):
    """Generates a text banner as a NumPy array using Pillow."""
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()

    dummy_img = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    padding_x = 20
    padding_y = 15
    canvas_w = width
    canvas_h = th + (padding_y * 2)

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    rect_x1 = (canvas_w - tw) / 2 - padding_x
    rect_y1 = padding_y / 2
    rect_x2 = (canvas_w + tw) / 2 + padding_x
    rect_y2 = canvas_h - (padding_y / 2)

    draw.rounded_rectangle([rect_x1, rect_y1, rect_x2, rect_y2], radius=12, fill=bg_color)

    text_x = (canvas_w - tw) / 2
    text_y = padding_y / 2
    draw.text((text_x, text_y), text, font=font, fill=text_color)

    return np.array(img)

# --- 1. HISTORY & VIRAL DOWNLOAD HELPERS ---
def get_uploaded_videos():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def mark_as_uploaded(video_id):
    history = get_uploaded_videos()
    history.append(video_id)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

def download_video_with_cobalt(video_url, output_path="raw_marwari.mp4"):
    """Downloads a YouTube video using Cobalt API endpoint."""
    cobalt_instances = [
        "https://api.cobalt.tools"
    ]

    # Fixed: Modern Cobalt API expects simple JSON payload
    payload = {
        "url": video_url
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    for instance in cobalt_instances:
        try:
            print(f"🌐 Requesting download stream from Cobalt API: {instance}...")
            res = requests.post(instance, json=payload, headers=headers, timeout=15)
            
            if res.status_code != 200:
                print(f"⚠️ Instance returned status code {res.status_code}: {res.text}")
                continue

            data = res.json()
            download_url = data.get("url")

            if not download_url and "picker" in data and len(data["picker"]) > 0:
                download_url = data["picker"][0].get("url")

            if download_url:
                print(f"📥 Downloading video stream...")
                video_res = requests.get(download_url, stream=True, timeout=60)
                if video_res.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in video_res.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
                    print(f"✅ Video saved successfully to {output_path}")
                    return True
        except Exception as e:
            print(f"⚠️ Cobalt instance error: {e}")

    return False

def download_viral_marwari_video(output_path="raw_marwari.mp4"):
    """Searches for viral videos, attempting Cobalt download first and falling back to yt-dlp."""
    history = get_uploaded_videos()

    search_queries = [
        "Marwari funny comedy shorts",
        "Rajasthani comedy shorts viral",
        "Marwari funny status shorts",
        "Marwari short video comedy",
        "Rajasthani funny jokes shorts"
    ]
    search_query = random.choice(search_queries)
    print(f"🔍 Searching viral videos for: '{search_query}'...")

    search_opts = {
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'quiet': True,
        'ignoreerrors': True,
    }

    with yt_dlp.YoutubeDL(search_opts) as ydl_search:
        try:
            results = ydl_search.extract_info(f"ytsearch50:{search_query}", download=False)
            if results and 'entries' in results:
                entries = [e for e in results['entries'] if e]
                random.shuffle(entries)

                for entry in entries:
                    video_id = entry.get('id')
                    video_url = entry.get('url') or f"https://www.youtube.com/watch?v={video_id}"

                    if not video_id or video_id in history:
                        continue

                    view_count = entry.get('view_count') or 0
                    if view_count and view_count < 30000:
                        continue

                    print(f"🎬 Found candidate video: {video_id}. Attempting Cobalt API...")
                    if download_video_with_cobalt(video_url, output_path):
                        return output_path, video_id

                    print(f"⚠️ Cobalt failed for {video_id}, falling back to direct yt-dlp...")
                    try:
                        ydl_dl_opts = {
                            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                            'outtmpl': output_path,
                            'quiet': True,
                        }
                        with yt_dlp.YoutubeDL(ydl_dl_opts) as ydl_dl:
                            ydl_dl.download([video_url])
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                            print(f"✅ Direct yt-dlp download succeeded.")
                            return output_path, video_id
                    except Exception as dl_err:
                        print(f"⚠️ Direct yt-dlp download failed: {dl_err}")

        except Exception as e:
            print(f"⚠️ Search error: {e}")

    print("❌ No new viral videos found right now.")
    return None, None

def download_background_music(save_path="music/background.mp3"):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    url = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Scheming%20Weasel%20faster.mp3"
    if not os.path.exists(save_path):
        print("Fetching background music...")
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
    return save_path

# --- 2. VIDEO EDITING & ENCODING ---
def find_loudest_moment(audio_path, duration=3):
    audio = AudioSegment.from_file(audio_path)
    chunk_ms = 500
    loudness = [audio[i:i+chunk_ms].rms for i in range(0, len(audio)-chunk_ms, chunk_ms)]
    if not loudness:
        return 0, duration
    peak_chunk = np.argmax(loudness)
    start_time = max(0, (peak_chunk * chunk_ms) / 1000.0 - 1)
    return start_time, start_time + duration

def build_marwari_short(input_video_path="raw_marwari.mp4", music_path="music/background.mp3", output_path="final_short.mp4"):
    print("🎬 Processing video: Building hook & cropping to 9:16...")
    video = VideoFileClip(input_video_path)

    temp_audio = "temp.wav"
    video.audio.write_audiofile(temp_audio, logger=None)

    hook_start, hook_end = find_loudest_moment(temp_audio, duration=3)
    hook_clip = video.subclip(hook_start, min(hook_end, video.duration))

    hook_img = create_text_banner_pil("Wait for it... 😂", font_size=55, text_color="yellow", bg_color=(0, 0, 0, 180), width=1080)
    hook_text = ImageClip(hook_img).set_position(('center', 120)).set_duration(hook_clip.duration)
    hook_clip = CompositeVideoClip([hook_clip, hook_text])

    main_clip = video.subclip(max(0, hook_start - 2), min(video.duration, hook_start + 30))
    wm_img = create_text_banner_pil(CHANNEL_WATERMARK, font_size=35, text_color="white", bg_color=(0, 0, 0, 120), width=1080)
    wm_text = ImageClip(wm_img).set_position(('center', 'bottom')).set_duration(main_clip.duration)
    main_clip = CompositeVideoClip([main_clip, wm_text])

    assembled = concatenate_videoclips([hook_clip, main_clip])

    w, h = assembled.size
    target_aspect = 9 / 16
    current_aspect = w / h

    if current_aspect > target_aspect:
        new_w = h * target_aspect
        x1 = (w - new_w) / 2
        cropped = assembled.crop(x1=x1, y1=0, width=new_w, height=h)
    else:
        new_h = w / target_aspect
        y1 = (h - new_h) / 2
        cropped = assembled.crop(x1=0, y1=y1, width=w, height=new_h)

    final_video = cropped.resize((1080, 1920))

    if os.path.exists(music_path):
        try:
            bg_music = AudioFileClip(music_path).volumex(0.10).subclip(0, final_video.duration)
            final_audio = CompositeAudioClip([final_video.audio.volumex(1.0), bg_music])
            final_video = final_video.set_audio(final_audio)
        except Exception as e:
            print(f"⚠️ Could not blend background music: {e}")

    final_video.write_videofile(
        output_path, 
        codec="libx264", 
        audio_codec="aac", 
        bitrate="6000k",        
        audio_bitrate="192k",  
        fps=30, 
        logger=None
    )

    video.close()
    final_video.close()
    if os.path.exists(temp_audio):
        os.remove(temp_audio)

    print(f"✅ HD Video created successfully: {output_path}")
    return output_path

# --- 3. YOUTUBE UPLOAD & COPYRIGHT SCAN ---
def get_youtube_service():
    creds = None

    if os.environ.get("TOKEN_JSON"):
        try:
            token_data = json.loads(os.environ["TOKEN_JSON"])
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            print(f"⚠️ Failed to parse TOKEN_JSON: {e}")

    if not creds and os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("client_secret.json"):
                raise FileNotFoundError("client_secret.json missing and no valid token found.")
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(host="127.0.0.1", port=8080)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)

def safe_upload_and_check(video_file="final_short.mp4", title="Marwari Desi Comedy Joke 😂 #Shorts"):
    youtube = get_youtube_service()

    print("📤 Uploading video as Private for Content ID checking...")
    body = {
        "snippet": {
            "title": title,
            "description": f"{title}\n\n#MarwariComedy #RajasthaniComedy #DesiJokes #Shorts #Comedy",
            "categoryId": "23"
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    response = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    video_id = response.get("id")
    print(f"✅ Uploaded as Private. Video ID: {video_id}")

    print("⏳ Waiting 180 seconds for Content ID scanning...")
    time.sleep(180)

    status_req = youtube.videos().list(part="status", id=video_id).execute()
    items = status_req.get("items", [])
    if items:
        upload_status = items[0].get("status", {}).get("uploadStatus")
        rejection_reason = items[0].get("status", {}).get("rejectionReason")

        if upload_status == "rejected":
            print(f"❌ Video rejected by YouTube! Reason: {rejection_reason}")
            return False

    print("✅ Copyright clear! Publishing video to Public...")
    youtube.videos().update(
        part="status",
        body={"id": video_id, "status": {"privacyStatus": "public"}}
    ).execute()
    print(f"🚀 Published successfully: https://youtube.com/shorts/{video_id}")
    return True

def run_pipeline():
    raw_video, source_video_id = download_viral_marwari_video()

    if not raw_video:
        print("Pipeline stopped: No suitable videos found.")
        return

    music_file = download_background_music()
    short_file = build_marwari_short(raw_video, music_file)

    success = safe_upload_and_check(short_file)

    if success and source_video_id:
        mark_as_uploaded(source_video_id)
        print("✅ Added video to history.")

if __name__ == "__main__":
    run_pipeline()