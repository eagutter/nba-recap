# NBA Recap

Compact NBA results for a Firefox/TablissNG new tab. Shows the latest fully completed NBA game day and lets you browse the last seven completed game days (skipping dates without games). Individual cards link to Motion Station's short recaps when matched. The **Nightly Recap** button opens the official NBA YouTube channel's combined recap for the date displayed, when available. The Nightly Recap button is centred beneath the date picker. The date footer stays minimal; the scores stay in a single row, with horizontal scrolling on narrow screens.

**Live widget:** https://eagutter.github.io/nba-recap/

## Set up on another device or browser

1. Install [TablissNG for Firefox](https://addons.mozilla.org/en-GB/firefox/addon/tablissng/).
2. Open a new tab, enter TablissNG settings and add a **Custom HTML** widget.
3. Paste the following code, save and position the widget:

```html
<div style="position:relative;left:50%;width:100vw;transform:translateX(-50%);background:transparent;">
  <iframe
    src="https://eagutter.github.io/nba-recap/"
    title="NBA Recap"
    scrolling="no"
    style="display:block;width:100%;height:220px;margin:0;padding:0;border:0;background:transparent;overflow:hidden;"
  ></iframe>
</div>
```

No new GitHub repository, API key, Python installation or hosting setup is needed on a new device. Another new-tab extension may also work if it supports HTML iframes.

## Install the Nightly Recap update (existing repository)

1. Extract the update ZIP. Go to https://github.com/eagutter/nba-recap and open the root of the `main` branch.
2. Select **Add file → Upload files**. Upload the three files `index.html`, `update_highlights.py` and `README.md` together, replacing their current versions. Do **not** upload a blank or replacement `videos.json`; the updater migrates the existing cache automatically.
3. Click **Commit changes**, committing directly to `main`. The existing workflow should start automatically. The included `.github/workflows/update-highlights.yml` is a reference copy of the existing hourly workflow; it does not need replacing.
4. Open https://github.com/eagutter/nba-recap/actions and check the latest run of **Update NBA highlights and publish page**. The existing step named “Read Motion Station uploads” now collects both sources. Its log should include `Official NBA Nightly Recap: ... recent game dates found` and `Saved ... official nightly recaps`. A first run may take longer because it also discovers the seasonal playlist and backfills history. If no run starts, open the workflow and click **Run workflow**.
5. After a successful deployment, open https://eagutter.github.io/nba-recap/?v=nightly and test the Nightly Recap button for several dates. The link should open the exact date's official NBA video in a new tab. Refresh TablissNG; if stale, append `?v=nightly` to its iframe URL. Set the iframe height to `220px` (instead of `180px`) to leave room for the centred Nightly Recap button without clipping.

## Update the centred Nightly Recap layout

If the Nightly Recap update is already installed, replace only `index.html` and `README.md`, commit to `main`, then change the TablissNG iframe height from `180px` to `220px`. No Python, API key, or workflow changes are needed.

## Using the widget

- Left arrow: older completed game day. Right arrow: newer completed game day. The latest completed day opens by default.
- Click a game card to watch its Motion Station recap (if available).
- Click **Nightly Recap** to watch the combined official NBA recap for the selected date. The button is hidden until an exact date match exists; no search links or guesses.
- If games do not fit horizontally, use the thin scrollbar or a horizontal touchpad gesture.

## How updates work

- ESPN's unofficial scoreboard API supplies completed game scores. The widget checks up to 21 calendar days to find seven completed game days.
- GitHub Actions is scheduled at minute 7 of every hour (UTC) and on commits to `main`; scheduled runs can be delayed or missed by GitHub. A manual run is also available. Pages uses **Settings → Pages → Source: GitHub Actions**.
- The existing repository secret `YOUTUBE_API_KEY` supplies the YouTube Data API key for both channels. Never put the key in HTML, JSON, or a public source file.
- Motion Station: fetches up to 50 upload records per run; verifies its channel metadata daily and falls back to RSS when necessary. Retains up to 350 videos from the last 23 days.
- Official NBA: discovers the current season's Nightly Recap playlist from the verified @NBA channel and caches its IDs. It scans the playlist (bounded to eight pages), checks the latest two pages of official uploads for videos not yet added, and uses a bounded historical uploads scan if the playlist is unavailable. Metadata is rechecked daily. Only dated Nightly Recap titles are kept, one record per game date for the last 23 days (plus the current date). No videos are downloaded; only metadata and YouTube IDs are stored.
- The recap date comes from the title, not the upload timestamp. Official NBA and Motion Station data are stored separately in the same `videos.json` file. An unavailable source does not erase the other source's cached videos. A successful workflow can still report stale-source warnings; check its logs if links are missing.

## Troubleshooting

- **Nightly Recap absent:** check whether the official NBA channel has posted the selected date's recap; then inspect `nightly_recaps` in `videos.json` and the latest Action log. Trigger a manual run if necessary. The first live run verifies playlist discovery with your API key.
- **Individual game missing:** check the Motion Station entry in `videos.json`; the original team/date/score matcher is unchanged.
- **Old page:** use Ctrl+Shift+R on the live site; add or increment a query parameter in the iframe URL.
- **Workflow failed:** open its logs. Verify the `YOUTUBE_API_KEY` secret and that Pages uses GitHub Actions. Do not expose your API key when sharing a log.
