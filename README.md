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

Scores come from an unofficial ESPN scoreboard endpoint; if that service changes, the widget may need maintenance. No personal API keys are required.
