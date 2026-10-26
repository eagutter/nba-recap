"""Fetch Motion Station uploads, preferring YouTube's official Data API.

Optional secret: YOUTUBE_API_KEY (store as a GitHub Actions repository secret).
Without it, use the public YouTube RSS feed (which can intermittently 404).
Preserve the last valid videos.json if both sources fail. Requires Python stdlib only.
"""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

CHANNEL_ID = "UCLd4dSmXdrJykO_hgOzbfPw"  # @motionstation4342
RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
API_BASE = "https://www.googleapis.com/youtube/v3/"
OUTPUT = Path(__file__).with_name("videos.json")
ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MAX_VIDEOS = 350
RETENTION_DAYS = 23


def fetch_json(url):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_youtube_api(api_key):
    """Read the channel's uploads playlist, not a search (low quota usage)."""
    def api_call(endpoint, **params):
        params["key"] = api_key
        return fetch_json(API_BASE + endpoint + "?" + urllib.parse.urlencode(params))

    channels = api_call("channels", part="contentDetails", id=CHANNEL_ID)
    items = channels.get("items", [])
    if not items:
        raise ValueError("YouTube API did not return the Motion Station channel")
    playlist_id = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not playlist_id:
        raise ValueError("YouTube API did not return an uploads playlist")

    result = api_call("playlistItems", part="snippet,contentDetails", playlistId=playlist_id, maxResults=50)
    videos = []
    for item in result.get("items", []):
        snippet = item.get("snippet", {})
        details = item.get("contentDetails", {})
        video_id = details.get("videoId") or snippet.get("resourceId", {}).get("videoId")
        title = snippet.get("title")
        published = details.get("videoPublishedAt") or snippet.get("publishedAt")
        if video_id and title and published and title not in ("Private video", "Deleted video"):
            videos.append({"id": video_id, "title": title, "published": published})
    if not videos:
        raise ValueError("YouTube API returned no public uploads")
    return videos


def fetch_rss():
    request = urllib.request.Request(RSS_URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; PersonalNBARecap/1.0)",
        "Accept": "application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())
    videos = []
    for entry in root.findall(f"{ATOM}entry"):
        video_id = entry.findtext(f"{YT}videoId")
        title = entry.findtext(f"{ATOM}title")
        published = entry.findtext(f"{ATOM}published")
        if video_id and title and published:
            videos.append({"id": video_id, "title": title, "published": published})
    if not videos:
        raise ValueError("YouTube RSS contained no usable video entries")
    return videos


def read_existing():
    if not OUTPUT.exists():
        return [], None
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        videos = data.get("videos", [])
        return (videos if isinstance(videos, list) else []), data.get("updated_at")
    except (ValueError, OSError, AttributeError, TypeError):
        return [], None


def collect_videos(api_key, sleep=time.sleep):
    if api_key:
        for attempt in range(2):
            try:
                videos = fetch_youtube_api(api_key)
                print(f"Source: official YouTube Data API; fetched {len(videos)} uploads", flush=True)
                return videos
            except (OSError, ValueError, KeyError) as exc:
                print(f"YouTube API attempt {attempt + 1}/2 failed: {exc}", flush=True)
                if attempt == 0:
                    sleep(4)
    else:
        print("No YOUTUBE_API_KEY secret configured; using RSS (less reliable)", flush=True)

    for attempt in range(3):
        try:
            videos = fetch_rss()
            print(f"Source: YouTube RSS; fetched {len(videos)} uploads", flush=True)
            return videos
        except (OSError, ET.ParseError, ValueError) as exc:
            print(f"YouTube RSS attempt {attempt + 1}/3 failed: {exc}", flush=True)
            if attempt < 2:
                sleep((4, 10)[attempt])
    return None


def merge_videos(old_videos, new_videos, now):
    unique = {
        v["id"]: v for v in old_videos + new_videos
        if isinstance(v, dict) and isinstance(v.get("id"), str)
    }
    cutoff = now - timedelta(days=RETENTION_DAYS)
    saved = []
    for video in unique.values():
        try:
            published = datetime.fromisoformat(video["published"].replace("Z", "+00:00"))
            if published.tzinfo is not None and published >= cutoff:
                saved.append(video)
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    return sorted(saved, key=lambda v: v["published"], reverse=True)[:MAX_VIDEOS]


def main():
    old, previous_update = read_existing()
    fresh = collect_videos(os.environ.get("YOUTUBE_API_KEY", "").strip())
    if fresh is None:
        if old:
            print("::warning title=Highlights are stale::YouTube API/RSS unavailable; "
                  "retaining existing videos.json. Check the configured YouTube API key.", flush=True)
            return
        raise RuntimeError("Could not fetch YouTube uploads and videos.json has no previous entries")

    now = datetime.now(timezone.utc)
    videos = merge_videos(old, fresh, now)
    if not videos:
        raise RuntimeError("No valid recent uploads; leaving videos.json unchanged")
    try:
        last_update = datetime.fromisoformat(previous_update.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        last_update = now - timedelta(days=40)
    changed = videos != old or now - last_update > timedelta(days=21)
    updated_at = now.isoformat(timespec="seconds") if changed else previous_update
    if changed:
        OUTPUT.write_text(json.dumps({"channel": "Motion Station", "updated_at": updated_at,
                                      "videos": videos}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(videos)} recent uploads; changed: {changed}", flush=True)


if __name__ == "__main__":
    main()
