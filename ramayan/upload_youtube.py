import json, os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
c = Credentials(None, refresh_token=os.environ["YT_REFRESH"], token_uri="https://oauth2.googleapis.com/token",
                client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
m = json.load(open("out/meta.json", encoding="utf-8"))
yt = build("youtube", "v3", credentials=c)
yt.videos().insert(part="snippet,status", body={"snippet": {"title": m["title"][:100], "description": m["description"], "categoryId": "24"},
  "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}},
  media_body=MediaFileUpload("out/video.mp4", resumable=True)).execute()
