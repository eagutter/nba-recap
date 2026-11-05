"""Collect recent Motion Station uploads for the NBA Recap widget.

Uses the YouTube Data API when YOUTUBE_API_KEY is configured and falls back
on the public RSS feed if unavailable. Keeps the uploads playlist ID in the
existing videos.json file, checking the channel API once every 24 hours.
No additional GitHub workflow or scheduled job is needed.
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
CHANNEL_CHECK_INTERVAL = timedelta(hours=24)


def fetch_json(url):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def parse_time(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def api_call(api_key, endpoint, **params):
    params["key"] = api_key
    return fetch_json(API_BASE + endpoint + "?" + urllib.parse.urlencode(params))


def fetch_channel_playlist(api_key):
    channels = api_call(api_key, "channels", part="contentDetails", id=CHANNEL_ID)
    items = channels.get("items", [])
    if not items or items[0].get("id") != CHANNEL_ID:
        raise ValueError("YouTube API did not return the expected Motion Station channel")
    playlist_id = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not isinstance(playlist_id, str) or not playlist_id:
        raise ValueError("YouTube API did not return an uploads playlist")
    return playlist_id


def fetch_youtube_api(api_key, existing_cache, now):
    """Fetch 50 uploads; refresh the saved playlist ID at most daily.

    If the cached playlist ever stops working, refresh channel details
    immediately and retry, rather than waiting for the next daily check.
    """
    cache = existing_cache.copy() if isinstance(existing_cache, dict) else {}
    playlist_id = cache.get("uploads_playlist_id")
    if not isinstance(playlist_id, str) or not playlist_id:
        playlist_id = None
    last_check = parse_time(cache.get("checked_at"))
    due = (not playlist_id or not last_check or now - last_check >= CHANNEL_CHECK_INTERVAL)
    checked_channel = False

    if due:
        try:
            latest_playlist_id = fetch_channel_playlist(api_key)
            if playlist_id and latest_playlist_id != playlist_id:
                print("Motion Station uploads playlist changed; updating cache", flush=True)
            playlist_id = latest_playlist_id
            cache = {"uploads_playlist_id": playlist_id,
                     "checked_at": now.isoformat(timespec="seconds")}
            checked_channel = True
            print("Channel metadata checked; uploads playlist ID verified", flush=True)
        except (OSError, ValueError, KeyError) as exc:
            if not playlist_id:
                raise
            print(f"::warning title=Channel check failed::Using cached uploads playlist ID ({type(exc).__name__})", flush=True)
            # Leave checked_at unchanged, so the next run tries again.

    def list_uploads(pid):
        return api_call(api_key, "playlistItems", part="snippet,contentDetails",
                        playlistId=pid, maxResults=50)

    try:
        result = list_uploads(playlist_id)
    except (OSError, ValueError, KeyError):
        if checked_channel:
            raise
        # A cached playlist might have changed before its 24-hour check.
        latest_playlist_id = fetch_channel_playlist(api_key)
        cache = {"uploads_playlist_id": latest_playlist_id,
                 "checked_at": now.isoformat(timespec="seconds")}
        print("Cached playlist lookup failed; refreshed channel and retrying", flush=True)
        result = list_uploads(latest_playlist_id)

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
    return videos, cache


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
        return [], None, {}
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        videos = data.get("videos", [])
        cache = data.get("channel_cache", {})
        return (videos if isinstance(videos, list) else []), data.get("updated_at"), (cache if isinstance(cache, dict) else {})
    except (ValueError, OSError, AttributeError, TypeError):
        return [], None, {}


def collect_videos(api_key, existing_cache, now, sleep=time.sleep):
    if api_key:
        for attempt in range(2):
            try:
                videos, new_cache = fetch_youtube_api(api_key, existing_cache, now)
                print(f"Source: official YouTube Data API; fetched {len(videos)} uploads", flush=True)
                return videos, new_cache
            except (OSError, ValueError, KeyError) as exc:
                print(f"YouTube API attempt {attempt + 1}/2 failed: {type(exc).__name__}", flush=True)
                if attempt == 0:
                    sleep(4)
    else:
        print("No YOUTUBE_API_KEY secret configured; using RSS (less reliable)", flush=True)

    for attempt in range(3):
        try:
            videos = fetch_rss()
            print(f"Source: YouTube RSS; fetched {len(videos)} uploads", flush=True)
            return videos, existing_cache
        except (OSError, ET.ParseError, ValueError) as exc:
            print(f"YouTube RSS attempt {attempt + 1}/3 failed: {exc}", flush=True)
            if attempt < 2:
                sleep((4, 10)[attempt])
    return None, existing_cache


def merge_videos(old_videos, new_videos, now):
    unique = {
        video["id"]: video for video in old_videos + new_videos
        if isinstance(video, dict) and isinstance(video.get("id"), str)
    }
    cutoff = now - timedelta(days=RETENTION_DAYS)
    saved = []
    for video in unique.values():
        published = parse_time(video.get("published"))
        if published is not None and published >= cutoff:
            saved.append(video)
    return sorted(saved, key=lambda video: video["published"], reverse=True)[:MAX_VIDEOS]


def main():
    now = datetime.now(timezone.utc)
    old, previous_update, old_cache = read_existing()
    fresh, new_cache = collect_videos(os.environ.get("YOUTUBE_API_KEY", "").strip(), old_cache, now)

    if fresh is None:
        if old:
            print("::warning title=Highlights are stale::YouTube API/RSS unavailable; retaining existing videos.json.", flush=True)
            return
        raise RuntimeError("Could not fetch YouTube uploads and videos.json has no previous entries")

    videos = merge_videos(old, fresh, now)
    if not videos:
        raise RuntimeError("No valid recent uploads; leaving videos.json unchanged")

    last_update = parse_time(previous_update) or now - timedelta(days=40)
    changed = (videos != old or new_cache != old_cache
               or now - last_update > timedelta(days=21))
    updated_at = now.isoformat(timespec="seconds") if changed else previous_update

    if changed:
        data = {"channel": "Motion Station", "updated_at": updated_at, "videos": videos}
        if new_cache:
            data["channel_cache"] = new_cache
        OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(videos)} recent uploads; changed: {changed}", flush=True)


if __name__ == "__main__":
    main()
