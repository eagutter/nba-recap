"""Update Motion Station's public YouTube uploads using its RSS feed.

No API key or third-party packages required. Run via GitHub Actions every 3 hours.
YouTube only exposes the 15 latest videos, so we keep earlier downloads.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

CHANNEL_ID = "UCLd4dSmXdrJykO_hgOzbfPw"  # @motionstation4342
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
OUTPUT = Path(__file__).with_name("videos.json")
ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"


def main():
    request = urllib.request.Request(FEED, headers={
        "User-Agent": "Mozilla/5.0 (compatible; PersonalNBARecap/1.0)",
        "Accept": "application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        rss = response.read()
    root = ET.fromstring(rss)
    found = []
    for entry in root.findall(f"{ATOM}entry"):
        video_id = entry.findtext(f"{YT}videoId")
        title = entry.findtext(f"{ATOM}title")
        published = entry.findtext(f"{ATOM}published")
        if video_id and title and published:
            found.append({"id": video_id, "title": title, "published": published})
    if not found:
        raise RuntimeError("YouTube RSS contained no videos; preserving existing data")

    # Merge instead of overwriting: the YouTube feed includes only 15 entries.
    earlier = []
    previous_update = None
    if OUTPUT.exists():
        try:
            old_data = json.loads(OUTPUT.read_text(encoding="utf-8"))
            earlier = old_data.get("videos", [])
            previous_update = old_data.get("updated_at")
        except (ValueError, OSError, AttributeError):
            earlier = []
    unique = {v["id"]: v for v in earlier if isinstance(v, dict) and v.get("id")}
    unique.update({v["id"]: v for v in found})
    cutoff = datetime.now(timezone.utc) - timedelta(days=35)
    videos = []
    for video in unique.values():
        try:
            uploaded = datetime.fromisoformat(video["published"].replace("Z", "+00:00"))
        except (ValueError, KeyError, TypeError):
            continue
        if uploaded >= cutoff:
            videos.append(video)
    videos.sort(key=lambda v: v["published"], reverse=True)
    # Minimise commits, but refresh once per 21 days in the offseason so
    # GitHub does not disable scheduled workflows after 60 inactive days.
    now = datetime.now(timezone.utc)
    try:
        last_updated = datetime.fromisoformat(previous_update.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        last_updated = now - timedelta(days=40)
    should_touch = (videos[:500] != earlier or
                    now - last_updated > timedelta(days=21))
    updated_at = now.isoformat(timespec="seconds") if should_touch else previous_update
    output = {"channel": "Motion Station", "updated_at": updated_at,
              "videos": videos[:500]}
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Latest RSS: {len(found)} videos; saved total: {len(videos[:500])}")


if __name__ == "__main__":
    main()
