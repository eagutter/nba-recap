"""Collect Motion Station game highlights and official NBA Nightly Recaps.

Uses the YouTube Data API when YOUTUBE_API_KEY is configured and falls back
on the public RSS feed if unavailable. Keeps the uploads playlist ID in the
existing videos.json file, checking the channel API once every 24 hours.
No additional GitHub workflow or scheduled job is needed.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re
import json
import os
from pathlib import Path
import time
import urllib.error
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
    url = API_BASE + endpoint + "?" + urllib.parse.urlencode(params)
    # Retry transient errors without exposing the API key in logs.
    # Search has its own quota; use just one request per run for recovery.
    attempts = 1 if endpoint == "search" else 3
    for attempt in range(attempts):
        try:
            return fetch_json(url)
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt + 1 == attempts:
                raise
            print(f"YouTube {endpoint}: HTTP {exc.code}; retrying", flush=True)
        except (OSError, ValueError):
            if attempt + 1 == attempts:
                raise
            print(f"YouTube {endpoint}: transient request failure; retrying", flush=True)
        time.sleep(2 ** (attempt + 1))


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


# The official NBA YouTube channel, separate from Motion Station.
NBA_CHANNEL_ID = "UCWJ2lWNubArHWmf3FIHbfcQ"
NBA_RETENTION_DAYS = 23
NBA_MAX_PLAYLIST_PAGES = 8  # Enough for a full regular-season recap playlist.
NBA_MAX_DISCOVERY_PAGES = 20
NBA_MAX_UPLOAD_PAGES = 20  # Bounded fallback/backfill if the playlist is unavailable.
MONTHS = {name: n for n, name in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"), 1)}
MONTHS.update({name[:3]: n for name, n in list(MONTHS.items())})
MONTHS["sept"] = 9
TITLE_RE = re.compile(
    r"^NBA(?:['’]s)?\s+Nightly\s+Recap\s*(?:[|:–—-]\s*)?"
    r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})\s*$", re.I)
VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}\Z")


def recap_date(title):
    """Use the game date printed in the title, not the upload date."""
    m = TITLE_RE.fullmatch(title.strip()) if isinstance(title, str) else None
    if not m:
        return None
    try:
        return date(int(m[3]), MONTHS[m[1].lower()], int(m[2]))
    except (ValueError, KeyError):
        return None


def nba_game_today(now):
    return now.astimezone(ZoneInfo("America/New_York")).date()


def season_label(now):
    today = nba_game_today(now)
    start = today.year if today.month >= 7 else today.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def recap_record(item, now, curated=False):
    snippet = item.get("snippet", {})
    details = item.get("contentDetails", {})
    owner = snippet.get("videoOwnerChannelId")
    # For curated playlists require the video itself to belong to @NBA.
    # The uploads playlist is already restricted to that channel.
    if (curated and owner != NBA_CHANNEL_ID) or (owner and owner != NBA_CHANNEL_ID):
        return None
    title = snippet.get("title", "")
    day = recap_date(title)
    video_id = details.get("videoId") or snippet.get("resourceId", {}).get("videoId")
    published = details.get("videoPublishedAt") or snippet.get("publishedAt")
    if (not day or not isinstance(video_id, str) or not VIDEO_ID_RE.fullmatch(video_id)
            or not parse_time(published)):
        return None
    today = nba_game_today(now)
    if not today - timedelta(days=NBA_RETENTION_DAYS) <= day <= today:
        return None
    return day.isoformat(), {"id": video_id, "title": title, "published": published}


def discover_nba_playlists(api_key, now, old_cache):
    """Find the official uploads playlist and the current season's recap playlist."""
    result = api_call(api_key, "channels", part="contentDetails", id=NBA_CHANNEL_ID)
    channels = result.get("items", [])
    if not channels or channels[0].get("id") != NBA_CHANNEL_ID:
        raise ValueError("Official NBA channel not returned")
    uploads = channels[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    if not isinstance(uploads, str) or not uploads:
        raise ValueError("Official NBA uploads playlist not returned")
    season = season_label(now)
    token = None
    found = None
    try:
        for _ in range(NBA_MAX_DISCOVERY_PAGES):
            args = dict(part="snippet", channelId=NBA_CHANNEL_ID, maxResults=50)
            if token:
                args["pageToken"] = token
            result = api_call(api_key, "playlists", **args)
            for item in result.get("items", []):
                snippet = item.get("snippet", {})
                title = str(snippet.get("title", "")).lower().replace("–", "-").replace("—", "-")
                if (snippet.get("channelId") == NBA_CHANNEL_ID and "nightly recap" in title
                        and season in title and isinstance(item.get("id"), str)):
                    found = item["id"]
                    break
            token = result.get("nextPageToken")
            if found or not token:
                break
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"::warning title=NBA playlist discovery::Using uploads fallback ({type(exc).__name__})", flush=True)
        # Keep a previously verified seasonal playlist on temporary discovery errors.
        if old_cache.get("season") == season:
            found = old_cache.get("recap_playlist_id")
    print(f"Official NBA channel verified; season {season}; recap playlist {'found' if found else 'not found (uploads fallback)'}", flush=True)
    return {"uploads_playlist_id": uploads, "recap_playlist_id": found,
            "season": season, "checked_at": now.isoformat(timespec="seconds"),
            "backfill_at": old_cache.get("backfill_at")}


def scan_nba_playlist(api_key, playlist_id, now, pages, curated=False):
    """Scan pages without assuming a curated playlist is newest-first."""
    token = None
    records = {}
    cutoff = nba_game_today(now) - timedelta(days=NBA_RETENTION_DAYS + 2)
    finished = False
    for _ in range(pages):
        args = dict(part="snippet,contentDetails", playlistId=playlist_id, maxResults=50)
        if token:
            args["pageToken"] = token
        result = api_call(api_key, "playlistItems", **args)
        items = result.get("items")
        if not isinstance(items, list):
            raise ValueError("Unexpected NBA playlist response")
        dates = []
        for item in items:
            record = recap_record(item, now, curated=curated)
            if record:
                key, video = record
                if key not in records or parse_time(video["published"]) > parse_time(records[key]["published"]):
                    records[key] = video
            dt = parse_time(item.get("contentDetails", {}).get("videoPublishedAt") or
                            item.get("snippet", {}).get("publishedAt"))
            if dt:
                dates.append(dt.date())
        token = result.get("nextPageToken")
        if not token or (not curated and items and len(dates) == len(items) and max(dates) < cutoff):
            finished = True
            break
    return records, finished


def merge_recaps(old, new, now):
    today = nba_game_today(now)
    merged = {}
    for collection in (old, new):
        if not isinstance(collection, dict):
            continue
        for key, value in collection.items():
            if not isinstance(value, dict):
                continue
            day = recap_date(value.get("title"))
            if (not day or key != day.isoformat() or not today - timedelta(days=NBA_RETENTION_DAYS) <= day <= today
                    or not isinstance(value.get("id"), str) or not VIDEO_ID_RE.fullmatch(value["id"])
                    or not parse_time(value.get("published"))):
                continue
            if key not in merged or parse_time(value["published"]) >= parse_time(merged[key]["published"]):
                merged[key] = value
    return dict(sorted(merged.items(), reverse=True))


def collect_nightly(api_key, old_cache, old_recaps, now):
    """Poll the seasonal playlist and latest official uploads; backfill if needed."""
    if not api_key:
        print("::warning title=NBA Nightly Recap::YOUTUBE_API_KEY is required; preserving existing nightly recaps", flush=True)
        return None, old_cache
    cache = old_cache.copy() if isinstance(old_cache, dict) else {}
    checked = parse_time(cache.get("checked_at"))
    if (not cache.get("uploads_playlist_id") or not checked or now - checked >= CHANNEL_CHECK_INTERVAL
            or cache.get("season") != season_label(now)):
        try:
            cache = discover_nba_playlists(api_key, now, cache)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"::warning title=NBA channel check failed::{type(exc).__name__}; retaining cached metadata", flush=True)
    records = {}
    success = False
    complete = False
    pid = cache.get("recap_playlist_id") if cache.get("season") == season_label(now) else None
    if pid:
        try:
            records, complete = scan_nba_playlist(api_key, pid, now, NBA_MAX_PLAYLIST_PAGES, curated=True)
            success = True
            if not records:
                complete = False
                print("::warning title=NBA recap playlist::No recent official recaps found; checking uploads", flush=True)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"::warning title=NBA recap playlist failed::{type(exc).__name__}; checking uploads", flush=True)
            # Force rediscovery next run after a stale/invalid playlist.
            cache.pop("checked_at", None)
    # A fresh upload can arrive before it is added to the seasonal playlist.
    # Scan 2 recent upload pages each hour, and do a bounded daily backfill
    # when the curated playlist is unavailable or incomplete.
    last_backfill = parse_time(cache.get("backfill_at"))
    full_scan = not complete and (not old_recaps or not last_backfill or now - last_backfill >= CHANNEL_CHECK_INTERVAL)
    if cache.get("uploads_playlist_id"):
        try:
            more, exhausted = scan_nba_playlist(api_key, cache["uploads_playlist_id"], now,
                                                NBA_MAX_UPLOAD_PAGES if full_scan else 2)
            records = merge_recaps(records, more, now)
            success = True
            if full_scan:
                cache["backfill_at"] = now.isoformat(timespec="seconds")
                if not exhausted:
                    print("::warning title=NBA backfill limit::Reached bounded uploads scan; some older recaps may not be found", flush=True)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"::warning title=NBA uploads failed::{type(exc).__name__}; preserving saved recaps", flush=True)
            cache.pop("checked_at", None)
    if not success:
        return None, cache
    print(f"Official NBA Nightly Recap: {len(records)} recent game dates found", flush=True)
    return records, cache



ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


def completed_game_days(now):
    """Mirror the widget: seven fully completed Eastern game dates, up to 21 days back."""
    today = nba_game_today(now)
    start, end = today - timedelta(days=21), today - timedelta(days=1)
    url = ESPN_URL + "?" + urllib.parse.urlencode({
        "dates": f"{start:%Y%m%d}-{end:%Y%m%d}", "limit": 1000})
    result = fetch_json(url)
    if not isinstance(result.get("events"), list):
        raise ValueError("Unexpected ESPN scoreboard response")
    grouped = {}
    for event in result["events"]:
        tipoff = parse_time(event.get("date"))
        if tipoff is None:
            raise ValueError("Missing ESPN event date")
        day = tipoff.astimezone(ZoneInfo("America/New_York")).date()
        if not start <= day <= end:
            continue
        status = event.get("status", {}).get("type", {})
        competitions = event.get("competitions") or [{}]
        completed = status.get("completed") is True or competitions[0].get("status", {}).get("type", {}).get("completed") is True
        grouped.setdefault(day.isoformat(), []).append(completed)
    return sorted((day for day, games in grouped.items() if games and all(games)), reverse=True)[:7]


def search_missing_recaps(api_key, missing, now):
    """One channel-restricted search, only when a displayed date lacks a recap."""
    if not api_key or not missing:
        return {}
    oldest = date.fromisoformat(min(missing)) - timedelta(days=1)
    result = api_call(api_key, "search", part="snippet", channelId=NBA_CHANNEL_ID,
                      type="video", q="Nightly Recap", order="date", maxResults=50,
                      publishedAfter=oldest.isoformat() + "T00:00:00Z")
    items = result.get("items")
    if not isinstance(items, list):
        raise ValueError("Unexpected YouTube search response")
    found = {}
    for item in items:
        snippet = item.get("snippet", {})
        if snippet.get("channelId") != NBA_CHANNEL_ID or snippet.get("liveBroadcastContent") in ("live", "upcoming"):
            continue
        record = recap_record({"snippet": {**snippet, "videoOwnerChannelId": NBA_CHANNEL_ID},
                               "contentDetails": {"videoId": item.get("id", {}).get("videoId"),
                                                  "videoPublishedAt": snippet.get("publishedAt")}}, now, curated=True)
        if record and record[0] in missing:
            found = merge_recaps(found, dict([record]), now)
    return found


def recover_and_report(api_key, old, fresh, motion_ok, now):
    nightly = merge_recaps(old, fresh or {}, now)
    schedule_ok = True
    try:
        expected = completed_game_days(now)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        schedule_ok = False
        print(f"::warning title=ESPN completeness check unavailable::{type(exc).__name__}", flush=True)
        # Still attempt recovery for recent dates; do not claim these are game days.
        expected = [(nba_game_today(now) - timedelta(days=i)).isoformat() for i in (1, 2)]
    missing = [day for day in expected if day not in nightly]
    search_status = "Not needed"
    if missing:
        if not api_key:
            search_status = "Unavailable (missing API key)"
        else:
            try:
                recovered = search_missing_recaps(api_key, missing, now)
                nightly = merge_recaps(nightly, recovered, now)
                search_status = f"Completed; recovered {len(recovered)} recap(s)"
            except (OSError, ValueError, KeyError, TypeError) as exc:
                search_status = f"Failed ({type(exc).__name__})"
                print(f"::warning title=NBA recap recovery search::{search_status}", flush=True)
    missing = [day for day in expected if day not in nightly]
    summary = ["## NBA video collection", f"Checked (UTC): {now.isoformat(timespec='seconds')}",
               f"Motion Station: {'retrieved' if motion_ok else 'FAILED — using cached records'}",
               f"Official NBA playlist/uploads: {'retrieved' if fresh is not None else 'FAILED — using cached records'}",
               f"YouTube recovery search: {search_status}",
               f"Completed game dates: {', '.join(expected) or 'none'}" if schedule_ok else "Completed game dates: unverified (ESPN unavailable)",
               f"Missing nightly recaps: {', '.join(missing) or 'none'}" if schedule_ok else f"Unmatched recent dates (not verified game days): {', '.join(missing) or 'none'}"]
    if missing and schedule_ok:
        print("::warning title=Nightly recaps incomplete::" + ", ".join(missing) + "; will recheck next run. Not found does not prove unpublished.", flush=True)
    elif schedule_ok:
        print("All displayed completed game days have a nightly recap", flush=True)
    for line in summary:
        print(line, flush=True)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as out:
            out.write("\n\n".join(summary) + "\n")
    return nightly


def main():
    now = datetime.now(timezone.utc)
    # Keep the existing Motion Station JSON shape; nightly recaps are separate.
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")
    except (OSError, ValueError):
        # Never silently overwrite a corrupt cache.
        raise RuntimeError("Cannot read existing videos.json; leaving it unchanged") from None
    old = data.get("videos", [])
    if not isinstance(old, list):
        raise ValueError("Invalid existing Motion Station video list")
    old_cache = data.get("channel_cache", {})
    if not isinstance(old_cache, dict):
        old_cache = {}
    old_recaps = data.get("nightly_recaps", {})
    old_nba_cache = data.get("nba_channel_cache", {})
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    fresh, new_cache = collect_videos(api_key, old_cache, now)
    recaps, nba_cache = collect_nightly(api_key, old_nba_cache, old_recaps, now)
    if fresh is None:
        print("::warning title=Motion Station highlights stale::Keeping cached game highlights", flush=True)
        videos = old
    else:
        videos = merge_videos(old, fresh, now)
    if recaps is None:
        print("::warning title=Nightly recaps stale::Keeping cached official recaps", flush=True)
    nightly = recover_and_report(api_key, old_recaps, recaps, fresh is not None, now)
    if fresh is None and recaps is None and not old and not nightly:
        raise RuntimeError("Neither source available and no cached highlights exist")
    updated = dict(data)
    updated.update(channel="Motion Station", videos=videos, channel_cache=new_cache,
                   nightly_recaps=nightly, nba_channel_cache=nba_cache)
    if videos != old or (fresh is not None and not data.get("updated_at")):
        updated["updated_at"] = now.isoformat(timespec="seconds")
    if nightly != old_recaps or (recaps is not None and not data.get("nightly_updated_at")):
        updated["nightly_updated_at"] = now.isoformat(timespec="seconds")
    changed = updated != data
    if changed:
        tmp = OUTPUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(OUTPUT)
    print(f"Saved {len(videos)} Motion Station uploads and {len(nightly)} official nightly recaps; changed: {changed}", flush=True)


if __name__ == "__main__":
    main()
