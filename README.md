# Language Access Data Explorer

Internal data navigation tool for the 911 dispatch / language access research team.
The app loads the **de-identified study dataset from a private Google Sheet** (not from
files in this repo). Filters, charts, and CSV download of the current filtered view
all run against that sheet.

## Access model (important)

This GitHub repo can stay **public** — the study data is **not** in the repo.

Access is gated in two places:

1. **Google Sheet** — shared only with the research team + the app's service account
   (`sheets-reader@….iam.gserviceaccount.com`) as Viewer.
2. **Streamlit Cloud sharing** — the deployed app must be **restricted/private**, with
   only team emails allowed. If the Streamlit app is public, anyone with the link can
   see the data through the UI even though the Sheet itself is private.

Never commit `.streamlit/secrets.toml` or a service-account JSON key.

## Run locally

1. Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` and fill in the
   service-account fields + `sheet_id` / `worksheet`.
2. Share the Sheet with the service account email as Viewer.
3. `pip install -r requirements.txt && streamlit run app.py`

## What's on the dashboard

- **Stat cards:** total calls, interpreter use %, average interpreter connect time.
- **Filters:** call center, date range, interpreter used, language group, zip code, time of day.
- **Charts:** interpreter use, weekly volume, language groups, hang-ups, response/onscene
  times, jargon vs compliance, emotion validation, emergency type, connect times.
- **Filtered data table** with CSV download of the current filter view.

## Refreshing the data

Raw SPSS (`.sav`) stays offline / off-repo (see `.gitignore`). To refresh the Sheet:

```bash
python data/prep_data.py path/to/new_file.sav
```

That writes a local `data/calls.csv` (also gitignored). Re-import that CSV into the
Google Sheet tab (or overwrite the tab). The live app picks up changes on the next
cache refresh (about 5 minutes), or after a redeploy.

## Streamlit Cloud setup checklist

1. Deploy from this repo; paste the same secrets into **App settings → Secrets**.
2. Under **Sharing**, set the app to **restricted** and add team emails.
3. Confirm a logged-out / non-listed account cannot open the app.
