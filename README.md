# NBA Recap

A compact NBA recap strip for the Firefox new-tab page using **TablissNG**. Displays scores from the **most recent fully completed NBA game day**, with team logos and links to matching [Motion Station](https://www.youtube.com/@motionstation4342/videos) highlights when available. The cards stay on one row; on narrower screens, use the horizontal scrollbar.

**Live widget:** https://eagutter.github.io/nba-recap/

## Set up on a new device or browser

1. Install [TablissNG for Firefox](https://addons.mozilla.org/en-GB/firefox/addon/tablissng/), and open a new tab.
2. In TablissNG, add a **Custom HTML** widget.
3. Paste the following HTML, save, and position the widget on the new-tab page:

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

That's it! **You don't need to download this repository, run Python, or set up GitHub Pages again.** The site is already hosted; TablissNG just displays it.

If you use a different new-tab extension or browser, the requirement is an HTML widget that permits iframes (or an equivalent embedded web view). The above steps are for Firefox + TablissNG.

## Updating or troubleshooting

- **Change the design/logic:** edit `index.html`, commit to `main`, then check the **Actions** tab for a successful **Update NBA highlights and publish page** run. GitHub Pages should have **Settings → Pages → Source: GitHub Actions**.
- **Old version still appearing:** refresh [the live widget](https://eagutter.github.io/nba-recap/) with `Ctrl+Shift+R`. In TablissNG, temporarily change the iframe URL to `https://eagutter.github.io/nba-recap/?v=2` to bypass a cached copy (increment the `v` value for later updates).
- **Too many games for the screen:** drag the thin horizontal scrollbar beneath the cards (or use a horizontal touchpad gesture). The strip never wraps to a second row.
- **Missing highlight link:** `videos.json` contains recent Motion Station uploads, matched by teams, date, and score where possible. Unmatched games are displayed without a link; videos can appear later.
- **Automated updates:** `.github/workflows/update-highlights.yml` checks for new videos approximately every three hours, updates `videos.json`, and republishes the site. The updater prunes entries older than 35 days and caps the list at 500; it won't grow without bound.

Scores come from an unofficial ESPN scoreboard endpoint; if that service changes, the widget may need maintenance. The optional YouTube Data API key is stored privately in GitHub Actions; it is never placed in the public webpage.

## Maintainer: configure the reliable Motion Station feed

The public YouTube RSS endpoint sometimes returns HTTP 404, even for a valid channel. To keep Motion Station YouTube links current, the GitHub Action supports YouTube Data API v3 as the primary source, with RSS as the backup. The scores do not require this key.

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create/select a project.
2. Under **APIs & Services → Library**, enable **YouTube Data API v3**.
3. Under **APIs & Services → Credentials**, create an **API key**. Restrict it to the **YouTube Data API v3** under API restrictions. Avoid IP/application restrictions, because GitHub Actions runners do not use a fixed outbound IP.
4. Go to this repo's **Settings → Secrets and variables → Actions → New repository secret**. Name: `YOUTUBE_API_KEY`; value: your API key. Never put the key in a public file or README.
5. The workflow at `.github/workflows/update-highlights.yml` reads the secret for the `update_highlights.py` step. Go to **Actions → Update NBA highlights and publish page → Run workflow**.
6. Verify the run log says `Source: official YouTube Data API` and then check that `videos.json` contains recently uploaded videos. Opening the hosted widget should then show direct YouTube links whenever Motion Station has uploaded recaps for those games.

The updater requests a channel's uploads playlist rather than searching for individual games; this normally uses approximately two low-cost YouTube API requests per check. The script retains a rolling **35-day** history capped at **500 videos**.

If the API becomes unavailable, the workflow retries and falls back to RSS. If neither works, it issues a **GitHub Actions warning** and preserves the old `videos.json`, so the site continues to display scores without inventing links. Green/successful workflow runs do not necessarily mean new highlights were discovered: inspect the log and the latest `videos.json` date.
