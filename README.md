# NBA Recap

Compact NBA results for a Firefox/TablissNG new tab. Browse the latest seven fully completed NBA game days, skipping dates without games. Individual game cards link to Motion Station's short recaps. The centred **Nightly Recap** button links to the official NBA YouTube video for the selected date when available. No live games or upcoming fixtures.

**Live widget:** https://eagutter.github.io/nba-recap/

## Set up on another device or browser

1. Install [TablissNG for Firefox](https://addons.mozilla.org/en-GB/firefox/addon/tablissng/).
2. Open a new tab, enter TablissNG settings and add a **Custom HTML** widget.
3. Paste the following, save and position the widget:

```html
<div style="position:relative;left:50%;width:100vw;transform:translateX(-50%);background:transparent;">
  <iframe
    src="https://eagutter.github.io/nba-recap/"
    title="NBA Recap"
    scrolling="no"
    style="display:block;width:100%;height:200px;margin:0;padding:0;border:0;background:transparent;overflow:hidden;"
  ></iframe>
</div>
```

No new API key, GitHub repository, server or Python installation is needed on another device. Other new-tab extensions that support iframes may also work.

## Install the November 25 collection reliability update

1. Extract the ZIP. Open https://github.com/eagutter/nba-recap on the `main` branch.
2. At the repository root, select **Add file → Upload files**. Upload `update_highlights.py` and `README.md`, replacing their existing versions. Commit to `main`.
3. Navigate to `.github/workflows` in the repository. Select **Add file → Upload files**. Upload the replacement `update-highlights.yml` from the ZIP's `.github/workflows` directory. Commit to `main`.
4. Open https://github.com/eagutter/nba-recap/actions/workflows/update-highlights.yml and inspect the latest run. If none starts, click **Run workflow** (branch `main`).
5. Open its **Summary** and check the collection timestamp, source statuses and missing nightly recap dates. After Pages deploys, refresh https://eagutter.github.io/nba-recap/ or open a new tab.

Do **not** replace `videos.json`, change the API key or upload a new `index.html`. The existing centred layout and 200px iframe height are unchanged. The workflow must end up at `.github/workflows/update-highlights.yml`, not at the repository root.

## Using the widget

- Left arrow: older completed game day. Right arrow: newer completed game day. The latest completed day opens by default.
- Click a game card for its Motion Station recap when matched. Click **Nightly Recap** for the exact date's official NBA YouTube recap. The button is hidden until the correct video is available.
- Cards remain in a single row; use the horizontal scrollbar when necessary.

## Collection and publishing

- **Schedule:** every hour at :07, plus :22, :37 and :52 from 08:00 to 11:59, all in Europe/London time (GMT/BST automatically). This is 36 planned runs per ordinary day. Pushes to `main` and manual dispatches also trigger the workflow. GitHub may delay or drop scheduled runs. The updater is idempotent and the next run retries outstanding dates.
- **Scores:** ESPN's unofficial scoreboard endpoint. The widget checks up to 21 calendar days to find seven completed game days. The collector independently checks the same date window for expected nightly recaps.
- **Motion Station:** up to 50 latest uploads per request, daily channel metadata check, RSS fallback, at most 350 videos from the last 23 days.
- **Official NBA:** official channel uploads and seasonal playlist, daily metadata verification, historical backfill. Recaps are matched by the game date printed in the title, not upload date. Retention is 23 days plus the current Eastern date, one video per game date.
- **Recovery search:** if an expected date is still missing after playlist checks, one additional YouTube search restricted to the official NBA channel looks for missing recaps. It accepts only correctly dated Nightly Recap titles and the correct channel. Transient errors in ordinary API requests are retried; missing dates are rechecked on subsequent runs. If ESPN is unavailable, the search may check the previous two calendar dates without claiming games occurred.
- **Quota:** uses the same `YOUTUBE_API_KEY` repository secret. At most one search request per run, normally zero after the expected recaps have been found. Google currently documents a separate default daily allowance of 100 search.list calls and 10,000 units for other operations; manual and backup runs also count. Never put the API key in public files.
- **Diagnostics:** the Actions run summary reports the actual collection attempt time, whether either source failed, whether recovery search ran, and missing recap dates. A missing link after a successful check is not proof that the video has not been published. `updated_at` and `nightly_updated_at` in `videos.json` refer to data changes, not every check. Existing cached links are preserved on outages. The workflow can publish cached data with warnings rather than erase a working scoreboard.
- **Publishing:** Pages uses Settings → Pages → Source: GitHub Actions. Runs are serialised. Each checks out current `main` and publishes the resulting data, including on unchanged runs so a missed deployment can be recovered. No new JSON files are required.

## Optional independent scheduling backup

GitHub's cron trigger is best-effort, not a guarantee. If the hourly or morning runs are still missed, an independent scheduler can trigger the same workflow through GitHub's workflow dispatch REST API. It does not need the YouTube key or a separate collector.

For example, use https://cron-job.org/ to dispatch at 08:35 and 09:35 UK time. In GitHub create a fine-grained personal access token (Settings → Developer settings → Personal access tokens → Fine-grained tokens), limited to **only** `eagutter/nba-recap`, with repository **Actions: Read and write**. Choose a limited expiry and renew the token before it expires. The scheduler will hold this credential, so only do this if you trust it. Never commit it or share it in chat.

Configure a job (Europe/London timezone) with HTTP method POST, URL `https://api.github.com/repos/eagutter/nba-recap/actions/workflows/update-highlights.yml/dispatches`, body `{"ref":"main"}`, and request headers `Authorization: Bearer YOUR_TOKEN`, `Accept: application/vnd.github+json`, `Content-Type: application/json`, `X-GitHub-Api-Version: 2026-03-10`. Use the scheduler's private header field, not a query parameter. Test the job and verify a new manual-dispatch run in GitHub. Enable scheduler failure notifications. The backup dispatches do not guarantee GitHub runner availability, but avoid depending entirely on GitHub's cron trigger. Revoke the token if no longer needed.

## Troubleshooting

- **No scheduled run:** check Actions for the most recent run. Trigger Run workflow manually if needed. The schedule is not guaranteed by GitHub; see the optional independent backup above.
- **No Nightly Recap:** check the run summary for the selected game date. If the source was checked but the date is missing, the video may not have appeared in the YouTube API yet. If the date is present in `nightly_recaps` in `videos.json` but the button is absent, check deployment and refresh the browser. Check the official NBA channel directly: https://www.youtube.com/@NBA/videos.
- **Individual highlight missing:** inspect `videos.json` for the Motion Station video; missing entries point to collection or upload availability, present entries to matching or publishing.
- **Old page:** Ctrl+Shift+R on the live site, or add a version query parameter to the iframe URL.
- **Workflow failure:** open logs and confirm `YOUTUBE_API_KEY` is configured and Pages uses GitHub Actions. Do not expose keys in shared logs.
