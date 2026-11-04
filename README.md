# Job Radar

A free, self updating remote job board for your own search. A GitHub Action pulls
remote jobs every 6 hours from free public job APIs and employer career boards,
keeps only your target roles, scores each one for flexibility and fit, and
publishes the result as a static site on GitHub Pages. No server needed.

## Set up (about 5 minutes)

1. Create a **public** GitHub repository (free GitHub Pages needs a public repo) and
   push this folder to it.
2. In the repo go to **Settings, Pages**. Under Build and deployment choose
   **Deploy from a branch**, branch `main`, folder `/docs`. Save.
3. Go to the **Actions** tab, open **Refresh jobs**, and click **Run workflow**.
   (If Actions asks to be enabled, enable it.) After about a minute `docs/jobs.json`
   fills in. Your site is at `https://YOUR-USERNAME.github.io/YOUR-REPO/`.
4. Optional phone alerts: install the free **ntfy** app, subscribe to a hard to
   guess topic name, then add that name as a repository secret called `NTFY_TOPIC`
   (Settings, Secrets and variables, Actions). You get a push when a new job
   scores 65 or higher.

Cloudflare Pages works too: connect the repo and set the output directory to `docs`.
The Action still does the refreshing.

## Make it yours

Edit `config.json`:

- `roles`: title patterns per role group. Add or remove groups.
- `boards`: employer career boards to watch. Add the company slug from its job
  page URL, for example `boards.greenhouse.io/SLUG`, `jobs.lever.co/SLUG`, or
  `jobs.ashbyhq.com/SLUG`. This is the freshest source because it is the
  employer's own list. A wrong slug just fails quietly and shows a warning.
- `positive_terms` and `negative_terms`: the words that raise or lower a score.
  Defaults reward flexibility, async work and your HR systems, and penalize on
  call, 24/7 and crisis style language.
- `home_state`: roles limited to another state are hidden unless you tick the box.
- `max_age_days`, `notify_min_score`.

## Notes

- Your pipeline statuses (Saved, Applied and so on) are stored in your own browser,
  not in the repo. They do not sync between devices.
- The repo is public, so keep personal details (name, references, phone) out of it.
  The config only holds role keywords.
- GitHub pauses scheduled workflows after 60 days with no repo activity. If the
  board stops updating, click **Run workflow** once to wake it.
- Sources are public APIs and feeds that allow this kind of use. Remotive, Jobicy and
  We Work Remotely ask that you link back to the listing, which the site does. Please
  do not add sites that forbid scraping, such as LinkedIn, Indeed or FlexJobs.
- Run the tests with `python3 -I tests/test_scrape.py`.
