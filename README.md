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

Open the **Settings** tab on the site. You can add or remove:

- job title keywords, grouped by role type (or add a whole new group),
- words that exclude a job,
- good signs and red flags in descriptions, with how much each counts,
- employers to watch (Greenhouse, Lever and Ashby company names),
- the alert score and how old a job can be.

Press **Save and refresh jobs**. The site commits `docs/config.json` to the repo and starts
a refresh, and new results appear in about two minutes.

To enable saving, create a fine grained GitHub token at
https://github.com/settings/personal-access-tokens/new, limited to this one repository,
with **Contents** and **Actions** both set to Read and write. Paste it in Settings. It is stored
only in that browser. You can also edit `docs/config.json` by hand.

## Resume tab

Paste your master resume once (format notes are on the page). Pick a listing, or paste any job
description, and press **Generate tailored resume**. It reorders your own bullets and skills so
the ones matching the job come first, shows words in the posting that your resume lacks, and
never adds anything. Then print or save as PDF, copy the text, or copy a ready made prompt to
have Claude do a deeper rewrite. The master resume is stored only in your browser.

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
- Run the tests with `python3 -I tests/test_scrape.py` and `node tests/resume.test.js`.
- The token lives in browser storage for the github.io address. Keep it fine grained and limited to this repo so a leak can do little.
