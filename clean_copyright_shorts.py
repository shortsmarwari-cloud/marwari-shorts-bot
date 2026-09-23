import os
import time
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Scope required to inspect and delete/update videos on your YouTube channel
SCOPES = ["https://www.googleapis.com/auth/youtube"]

def get_youtube_service():
    """Initializes Google OAuth credentials with management permissions."""
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

def batch_clean_copyright_shorts(auto_delete=True):
    """
    Scans all uploaded Shorts/videos on your YouTube channel.
    If YouTube flagged or rejected a video due to copyright/Content ID,
    it automatically deletes or sets it to Private.
    """
    youtube = get_youtube_service()

    # 1. Retrieve your channel's 'Uploads' playlist ID
    print("🔍 Fetching channel upload records...")
    ch_response = youtube.channels().list(mine=True, part="contentDetails").execute()
    
    if not ch_response.get("items"):
        print("❌ Could not find channel details. Check your token.json or credentials.")
        return

    uploads_playlist_id = ch_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # 2. Collect all uploaded video IDs across pages
    video_ids = []
    next_page_token = None

    while True:
        playlist_req = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part="contentDetails",
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        for item in playlist_req.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])

        next_page_token = playlist_req.get("nextPageToken")
        if not next_page_token:
            break

    print(f"📊 Total videos found on channel: {len(video_ids)}")
    
    if not video_ids:
        print("No uploaded videos found.")
        return

    # 3. Inspect video status in batches of 50
    flagged_videos = []

    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i+50]
        videos_req = youtube.videos().list(
            part="snippet,status",
            id=",".join(batch_ids)
        ).execute()

        for video in videos_req.get("items", []):
            vid_id = video["id"]
            title = video["snippet"]["title"]
            status = video.get("status", {})
            
            upload_status = status.get("uploadStatus")
            rejection_reason = status.get("rejectionReason")

            # Check if YouTube Content ID blocked or rejected the video
            if upload_status == "rejected" or rejection_reason is not None:
                print(f"🚨 FLAG DETECTED: '{title}' (ID: {vid_id}) | Reason: {rejection_reason}")
                flagged_videos.append((vid_id, title))

    # 4. Action step: Clean up flagged videos
    if not flagged_videos:
        print("✅ Scan complete! No rejected or copyright-blocked videos were found on your channel.")
        return

    print(f"\n⚠️ Found {len(flagged_videos)} video(s) with copyright/upload issues.")

    for vid_id, title in flagged_videos:
        if auto_delete:
            print(f"🗑️ Automatically deleting flagged video: '{title}' ({vid_id})...")
            try:
                youtube.videos().delete(id=vid_id).execute()
                print("✅ Successfully deleted from YouTube.")
            except Exception as e:
                print(f"❌ Failed to delete video {vid_id}: {e}")
        else:
            print(f"🔒 Setting flagged video to PRIVATE: '{title}' ({vid_id})...")
            try:
                youtube.videos().update(
                    part="status",
                    body={"id": vid_id, "status": {"privacyStatus": "private"}}
                ).execute()
                print("✅ Changed status to Private.")
            except Exception as e:
                print(f"❌ Failed to update video status {vid_id}: {e}")

if __name__ == "__main__":
    # Set auto_delete=True to permanently remove flagged videos,
    # or set auto_delete=False to just mark them as Private.
    batch_clean_copyright_shorts(auto_delete=True)