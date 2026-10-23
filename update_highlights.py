"""Update Motion Station game recaps from the public YouTube channel RSS feed.

Runs in GitHub Actions. Requires only the Python standard library.
- Retries transient YouTube failures.
- Leaves the last valid videos.json completely untouched if the feed is unavailable.
- Keeps up to 500 videos from the last 35 days.
- Fails only if there is no usable cached data (to avoid silently publishing nothing).
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
import urllib.request
import xml.etree.ElementTree as ET

CHANNEL_ID = "UCLd4dSmXdrJykO_hgOzbfPw"  # @motionstation4342
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
OUTPUT = Path(__file__).with_name("videos.json")
ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MAX_VIDEOS = 500
RETENTION_DAYS = 35


def read_existing():
    if not OUTPUT.exists():
        return [], None
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        videos = data.get("videos", [])
        if not isinstance(videos, list):
            return [], None
        return videos, data.get("updated_at")
    except (ValueError, OSError, AttributeError):
        return [], None


def download_feed():
    request = urllib.request.Request(FEED, headers={
        "User-Agent": "Mozilla/5.0 (compatible; PersonalNBARecap/1.0)",
        "Accept": "application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())

    found = []
    for entry in root.findall(f"{ATOM}entry"):
        video_id = entry.findtext(f"{YT}videoId")
        title = entry.findtext(f"{ATOM}title")
        published = entry.findtext(f"{ATOM}published")
        if video_id and title and published:
            found.append({"id": video_id, "title": title, "published": published})

    if not found:
        raise ValueError("YouTube RSS contained no usable video entries")
    return found


def main():
    earlier, previous_update = read_existing()

    found = None
    last_error = None
    for attempt in range(3):
        try:
            found = download_feed()
            break
        except (OSError, ET.ParseError, ValueError) as exc:
            last_error = exc
            print(f"YouTube RSS fetch attempt {attempt + 1}/3 failed: {exc}", flush=True)
            if attempt < 2:
                time.sleep((4, 10)[attempt])

    if found is None:
        if any(isinstance(v, dict) and v.get("id") for v in earlier):
            # No write: cached URLs remain published; next scheduled run retries.
            print(
                "::warning title=YouTube feed temporarily unavailable::"
                f"3 attempts failed ({str(last_error).replace(chr(10), ' ')}). "
                "Preserving existing videos.json; a later scheduled run will retry.",
                flush=True,
            )
            return
        raise RuntimeError(
            "Unable to download YouTube RSS after 3 attempts, "
            "and there is no previously saved highlights cache."
        ) from last_error

    unique = {
        video["id"]: video
        for video in earlier
        if isinstance(video, dict) and video.get("id")
    }
    unique.update({video["id"]: video for video in found})

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    videos = []
    for video in unique.values():
        try:
            uploaded = datetime.fromisoformat(video["published"].replace("Z", "+00:00"))
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        if uploaded >= cutoff:
            videos.append(video)
    videos.sort(key=lambda v: v["published"], reverse=True)
    videos = videos[:MAX_VIDEOS]

    # Refresh at least once every 21 days, even when no new videos arrive,
    # so GitHub doesn't disable scheduled workflows after prolonged inactivity.
    now = datetime.now(timezone.utc)
    try:
        last_updated = datetime.fromisoformat(previous_update.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        last_updated = now - timedelta(days=40)

    should_touch = (videos != earlier or now - last_updated > timedelta(days=21))
    updated_at = now.isoformat(timespec="seconds") if should_touch else previous_update
    output = {"channel": "Motion Station", "updated_at": updated_at, "videos": videos}
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Latest RSS: {len(found)} videos; saved total: {len(videos)}", flush=True)


if __name__ == "__main__":
    main()
