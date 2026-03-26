# Commit and Push — PressRadar.me

PressRadar uses **direct commits to `main`** — no feature branches or PRs. Changes are auto-deployed via GitHub Pages.

---

## Before doing anything

```bash
pwd
git remote -v
git branch
git status
git diff --stat
```

Confirm:
- We are in the `pressradar` repository
- We are on the `main` branch
- The remote is `origin` pointing to `adgibs/pressradar`
- The diff shows only the expected changes

If anything looks wrong, **stop and ask** before proceeding.

---

## Steps

1. **Stage specific files** (never `git add -A` — avoid committing secrets or cache files):
   ```bash
   git add <file1> <file2> ...
   ```
   Common file groups:
   - **HTML pages:** `index.html ukraine.html east-asia.html africa.html europe.html south-asia.html americas.html`
   - **Shared code:** `css/style.css js/app.js`
   - **Backend:** `fetch_news.py`
   - **Config:** `.github/workflows/update-news.yml CLAUDE.md`

2. **Write a commit message:**
   - Imperative mood, present tense
   - ✅ `Add clickable AI briefing bullets to filter sidebar`
   - ✅ `Fix regex escape error in AI summary injection`
   - ❌ `fixed stuff`, `WIP`, `update`
   - If multiple logical changes, split into separate commits.

3. **Commit:**
   ```bash
   git commit -m "<message>"
   ```

4. **Push to GitHub:**

   **Option A — Cowork VM (preferred when PAT is configured):**
   If a GitHub PAT with `Contents` + `Workflows` scope is configured on the git remote, push directly:
   ```bash
   git push
   ```
   The PAT is set per-session via:
   ```bash
   git remote set-url origin https://adgibs:<PAT>@github.com/adgibs/pressradar.git
   ```

   **Option B — Mac push script:**
   A `push.sh` script is included in the repo root. Run from Terminal:
   ```bash
   cd "/Users/andrew/0. Swift Coding/pressradar" && bash push.sh
   ```
   It handles pull-rebase, stash, and push automatically.

   **Option C — Manual Mac push:**
   ```bash
   cd "/Users/andrew/0. Swift Coding/pressradar" && git pull --rebase && git push
   ```
   If you get "unstaged changes" errors:
   ```bash
   git stash && git pull --rebase && git push && git stash pop
   ```

5. **Trigger a workflow run** (if fetch_news.py or AI logic changed):
   > Go to **GitHub → Actions → Update PressRadar News → Run workflow**
   > Or wait for the next hourly cron run.

---

## Rules

- **Always commit to `main`** — no feature branches or PRs for this project.
- **Never use `git add -A`** — stage specific files to avoid committing `__pycache__/`, `.env`, or other junk.
- **The VM can push if a PAT is configured** on the git remote. Otherwise instruct the user to push from their Mac or use `push.sh`.
- **After pushing**, remind the user to trigger a workflow run if `fetch_news.py` changed.
- If there are merge conflicts from the auto-update bot, use `git stash && git pull --rebase && git push && git stash pop`.
- **Never commit** `.env`, `__pycache__/`, or API keys.

---

## Files the GitHub Actions workflow auto-commits

The hourly workflow (`update-news.yml`) only stages HTML files:
```bash
git add index.html ukraine.html east-asia.html africa.html europe.html south-asia.html americas.html
```
It does NOT commit `css/style.css`, `js/app.js`, or `fetch_news.py` — those must be committed manually.
