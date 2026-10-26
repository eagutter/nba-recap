# NBA Recap — seven game-day history

A thin, transparent NBA scores strip for a [TablissNG](https://addons.mozilla.org/en-GB/firefox/addon/tablissng/) Firefox new-tab page, hosted on GitHub Pages.

**Live widget:** https://eagutter.github.io/nba-recap/

## How to use

- Shows the **latest fully completed NBA game day** by default (US Eastern dates).
- Use the **‹ / › buttons on either side of the date/status label** to visit the previous or next completed game day. Up to **seven game days** are available, skipping days without games. The widget searches up to 21 calendar days back, so off-season gaps may show fewer.
- Each matchup links **directly to Motion Station's YouTube recap when a verified match is available**. Unlinked cards mean no matching recap has been collected yet.
- On nights with many games, the cards stay in **one row**, with a thin horizontal scrollbar. The background outside the cards is transparent.
- Refreshing the page resets to the latest day; automatic 15-minute refreshes preserve your currently selected day.

## Set up on a new computer/browser

1. Install [TablissNG for Firefox](https://addons.mozilla.org/en-GB/firefox/addon/tablissng/).
2. Open a new tab and add a **Custom HTML** widget.
3. Paste the code below into that widget and position it where you like:

   ```html
   <div style="position:relative;left:50%;width:100vw;transform:translateX(-50%);background:transparent;">
     <iframe
       src="https://eagutter.github.io/nba-recap/"
       title="NBA Recap"
       scrolling="no"
       style="display:block;width:100%;height:180px;margin:0;padding:0;border:0;background:transparent;overflow:hidden;"
     ></iframe>
   </div>
   ```

The site is already hosted. No Python, local server, or GitHub setup is needed on each new computer.

## Updating this repository

- `index.html`: all visual styling, seven-day navigation, ESPN scores and highlight matching.
- `update_highlights.py`: downloads recent Motion Station upload IDs/titles; prefers YouTube Data API v3, falls back to RSS, and preserves last good data when neither is available.
- `videos.json`: generated video cache. Now limited to **23 days / 350 videos**, appropriate for the 21-day score lookback plus upload-date margin. Never hand-edit this file.
- `.github/workflows/update-highlights.yml`: scheduled updates, roughly every three hours, and GitHub Pages deployment.

To publish a change, commit updated files to `main`, then verify the **Update NBA highlights and publish page** workflow finishes successfully in the [Actions tab](https://github.com/eagutter/nba-recap/actions). **Settings → Pages → Source** should remain **GitHub Actions**.

## Motion Station API setup (repository owner only)

GitHub Actions can access YouTube Data API v3 using a repository secret named `YOUTUBE_API_KEY` (never store the key in the repository). Create a restricted key in [Google Cloud Console](https://console.cloud.google.com/) after enabling YouTube Data API v3; add it under **Settings → Secrets and variables → Actions**. The workflow must pass the secret to the updater's `YOUTUBE_API_KEY` environment variable. Without a key it falls back to the YouTube RSS feed, which has been intermittently unavailable.

Check the job log for `Source: official YouTube Data API` to confirm new videos are being retrieved. A green workflow run can also mean it reused old videos after an upstream failure; check the log and `videos.json`'s latest dates when links are missing.

## Troubleshooting

- **Old version after a commit:** Wait for deployment to succeed. Then open https://eagutter.github.io/nba-recap/ and press **Ctrl+Shift+R**. If TablissNG still caches it, append `?v=5` to the iframe `src` URL.
- **Missing scores:** ESPN's unofficial public scoreboard endpoint may be unavailable. The widget checks only fully finished days.
- **Missing recap:** Motion Station may not have posted it, or the video may not have been collected/matched yet. Look for recent entries in `videos.json` and verify GitHub Actions logs.
- **Can't see all cards:** Use the slim horizontal scrollbar. Cards do not wrap onto a second row.
- **No arrows:** Refresh to the latest HTML and ensure the whole 180px-high iframe is visible in TablissNG.
