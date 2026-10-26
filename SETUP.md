# NBA Recap v2 — upgrade instructions

This upgrades your existing `nba-recap` GitHub Pages repository. No new repository, YouTube API key, or paid hosting is needed.

## 1. Replace the widget and add the updater

1. Open your existing `nba-recap` repository on GitHub.
2. Click **Add file → Upload files**.
3. Drag in **index.html** and **update_highlights.py** from this package.
4. Commit the changes. If GitHub asks, confirm replacing the existing `index.html`.

## 2. Switch GitHub Pages to Actions

1. Open **Settings → Pages**.
2. Change **Build and deployment → Source** from **Deploy from a branch** to **GitHub Actions**.
3. You can skip any suggested starter workflow templates: the next step creates the right one.

This step matters: GitHub says automated commits using `GITHUB_TOKEN` do not trigger branch-based Pages builds.

## 3. Add the automated update and deploy workflow

1. Back in the repository **Code** tab, select **Add file → Create new file**.
2. In the filename box enter **.github/workflows/update-highlights.yml** (include the dots and slashes).
3. Open the matching file from this package in Notepad, then copy the entire contents into GitHub's editor.
4. Click **Commit changes** on the **main** branch.

The workflow collects the 15 latest public videos from the Motion Station RSS feed every three hours, merges them with previously collected videos, and deploys the page. It requires no API key. The feed only exposes 15 latest videos, so it is possible to miss an upload during unusually busy periods.

## 4. Verify the workflow

1. Open **Actions** on GitHub.
2. Select **Update NBA highlights and publish page**.
3. A run may have started automatically when you committed the workflow. If not, click **Run workflow → Run workflow**.
4. Open the run and check for a **green tick**.
5. Return to the Code tab and check that **videos.json** has appeared.
6. Visit your existing GitHub Pages site. Your address remains https://YOUR-USERNAME.github.io/nba-recap/.

If the run fails with a permission error while pushing videos.json, check **Settings → Actions → General → Workflow permissions**. Allow *Read and write permissions* if that setting is available, and rerun. The workflow itself also asks only for the permissions it needs.

## 5. Update TablissNG Custom HTML

Replace your old Custom HTML iframe with the text from **tablissng-iframe-v2.txt**, and replace `YOUR-USERNAME` with your actual GitHub username.

This makes the iframe span the page width while staying centred, without a filled rectangular background. The game cards remain the only dark elements.

## Expectations

- Completed games are shown for the last completed NBA game day.
- A card links directly to a Motion Station video **only if it has a confident match** from the collected video feed.
- A card with no match remains visible but is not clickable.
- Video matches may appear hours after games finish, depending on when the channel publishes them and when the scheduled updater runs.
- The layout was tested with two, eleven, and fifteen games at different desktop widths, but I couldn't test the live YouTube RSS response from this environment.
