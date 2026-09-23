import os
import json
import time
import random
import numpy as np
import yt_dlp
import requests
from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip, TextClip, CompositeVideoClip
from pydub import AudioSegment
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
HISTORY_FILE = "upload_history.json"
CHANNEL_WATERMARK = "@MarwariShorts" # Change this to your channel name!

# --- 1. HISTORY & VIRAL DOWNLOAD HELPERS ---
def get_uploaded_videos():
    """Reads the history file to prevent duplicate uploads."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def mark_as_uploaded(video_id):
    """Saves the video ID to history after a successful upload."""
    history = get_uploaded_videos()
    history.append(video_id)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

def download_viral_marwari_video(search_query="Marwari funny comedy shorts", output_path="raw_marwari.mp4"):
    """Downloads a viral video that hasn't been uploaded before using cookies authentication."""
    history = get_uploaded_videos()
    print(f"Searching for viral videos (>100k views) for: {search_query}...")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': output_path,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,  # Cookie authentication enabled
        # Strictly filters for viral videos under 3 minutes
        'match_filter': yt_dlp.utils.match_filter_func("view_count >= 100000 & duration <= 180"),
        'rejecttitle': '(?i)copyright', 
        'noplaylist': True,
        'max_downloads': 10, # Check up to 10 videos to find a new one
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        results = ydl.extract_info(f"ytsearch15:{search_query}", download=False)
        if 'entries' in results:
            for entry in results['entries']:
                if entry and entry.get('id') not in history:
                    print(f"✅ Found viral video: {entry.get('title')} ({entry.get('view_count')} views)")
                    ydl.download([entry['webpage_url']])
                    return output_path, entry['id']
                    
    print("❌ No new viral videos found right now.")
    return None, None

def download_background_music(save_path="music/background.mp3"):
    """Downloads a clean, copyright-free background music track."""
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

# --- 2. VIDEO EDITING & HD QUALITY ENCODING ---
def find_loudest_moment(audio_path, duration=3):
    """Identifies peak audio to extract a 3-second hook."""
    audio = AudioSegment.from_file(audio_path)
    chunk_ms = 500
    loudness = [audio[i:i+chunk_ms].rms for i in range(0, len(audio)-chunk_ms, chunk_ms)]
    peak_chunk = np.argmax(loudness)
    start_time = max(0, (peak_chunk * chunk_ms) / 1000.0 - 1)
    return start_time, start_time + duration

def build_marwari_short(input_video_path="raw_marwari.mp4", music_path="music/background.mp3", output_path="final_short.mp4"):
    """Cuts 3-second hook, adds text overlays, crops to 9:16, exports in HD."""
    print("Processing video: Building 3-sec hook, adding text, formatting HD...")
    video = VideoFileClip(input_video_path)
    
    # 1. Extract temporary audio to find the funniest/loudest moment
    temp_audio = "temp.wav"
    video.audio.write_audiofile(temp_audio, logger=None)
    
    hook_start, hook_end = find_loudest_moment(temp_audio, duration=3)
    hook_clip = video.subclip(hook_start, min(hook_end, video.duration))
    
    # 2. Add "Wait for it..." Text to the Hook (Engagement Booster)
    try:
        hook_text = TextClip("Wait for it... 😂", fontsize=75, color='yellow', bg_color='black', font='Impact')
        hook_text = hook_text.set_position(('center', 'top')).set_duration(hook_clip.duration)
        hook_clip = CompositeVideoClip([hook_clip, hook_text])
    except Exception as e:
        print("⚠️ Text overlay skipped. Ensure ImageMagick is installed.")
        
    # 3. Get the main video and add a Watermark (Transformative Value)
    main_clip = video.subclip(max(0, hook_start - 2), min(video.duration, hook_start + 30))
    try:
        wm_text = TextClip(CHANNEL_WATERMARK, fontsize=40, color='white', font='Arial').set_opacity(0.6)
        wm_text = wm_text.set_position(('right', 'bottom')).set_duration(main_clip.duration)
        main_clip = CompositeVideoClip([main_clip, wm_text])
    except:
        pass

    # 4. Stitch together and Crop to 9:16 vertical
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
    
    # 5. Layer background music
    bg_music = AudioFileClip(music_path).volumex(0.10).subclip(0, final_video.duration)
    final_audio = CompositeAudioClip([final_video.audio.volumex(1.0), bg_music])
    final_video = final_video.set_audio(final_audio)
    
    # 6. Export HD
    final_video.write_videofile(
        output_path, 
        codec="libx264", 
        audio_codec="aac", 
        bitrate="6000k",       
        audio_bitrate="192k",  
        fps=30, 
        logger=None
    )
    
    if os.path.exists(temp_audio):
        os.remove(temp_audio)
        
    print(f"✅ HD Video created successfully: {output_path}")
    return output_path

# --- 3. YOUTUBE UPLOAD & COPYRIGHT SCAN ---
def get_youtube_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def safe_upload_and_check(video_file="final_short.mp4", title="Marwari Desi Comedy Joke 😂 #Shorts"):
    youtube = get_youtube_service()
    
    print("Uploading video as Private for Content ID checking...")
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
    print(f"Uploaded as Private. Video ID: {video_id}")
    
    print("Waiting 180 seconds for Content ID scanning...")
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
    # 1. Download video & save source ID
    raw_video, source_video_id = download_viral_marwari_video()
    
    if not raw_video:
        print("Pipeline stopped: No suitable videos found.")
        return

    # 2. Build the video
    music_file = download_background_music()
    short_file = build_marwari_short(raw_video, music_file)
    
    # 3. Upload & Check
    success = safe_upload_and_check(short_file)
    
    # 4. Save to history so we NEVER upload it again
    if success and source_video_id:
        mark_as_uploaded(source_video_id)
        print("✅ Added video to history.")

if __name__ == "__main__":
    run_pipeline()