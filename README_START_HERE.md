# FranchiseIQ — Complete Codebase (v6.6)

## v6.6 — Render deployment readiness

**Short answer: it wasn't quite ready, and now it is — with a few things
you need to know about Render specifically, not just this codebase.**

**Two real gaps found and fixed:**
1. `backend/Dockerfile` never copied the `amenities/` or `competitor/`
   folders into the image at all. Deploying as-is would have hit the exact
   same `FileNotFoundError` you saw locally before those folders existed —
   just in the cloud, much harder to debug from a Render log stream.
2. `docker/docker-compose.yml` in this bundle had somehow reverted to a
   version from before the auth/database work in this conversation — no
   Postgres service, none of the JWT/database env vars. Rewritten from
   scratch with everything correctly wired.
3. `frontend/Dockerfile` had no way to receive `VITE_API_URL` — Vite bakes
   that value into the JS bundle at **build time**, not container-run
   time, so the old Dockerfile silently ignored any value passed via
   `docker-compose`'s `environment:` block. Fixed with a proper `ARG`.

**Added:** a real `render.yaml` (Blueprint) with a managed Postgres
database, an auto-generated `JWT_SECRET_KEY` (Render generates and stores
a real secret for you — you can't accidentally leave the insecure default
in place), and every env var this app actually needs.

**Three things about Render itself, not this code, worth knowing before
you commit to it (checked against Render's current docs, July 2026):**
- **Free PostgreSQL expires 30 days after creation**, then a 14-day grace
  period, then Render hard-deletes it with no warning. Fine for a demo;
  if you want your saved prediction-run history to actually persist,
  upgrade the database to a paid instance (from ~$6/mo) before relying on
  it for anything real.
- **Free web services spin down after 15 minutes of inactivity** — the
  first request after that takes 30-60 seconds to wake back up. Normal
  for a free-tier demo, not something to be alarmed by.
- **`users.json` is baked into the Docker image at build time** (it's part
  of `backend/`, copied via `COPY backend/ .`). Editing it locally and
  seeing changes take effect immediately is a *local dev* convenience —
  on Render, adding/removing a user means: edit `backend/users.json` →
  commit → push → Render auto-redeploys. That's not a bug, just a
  different mental model for a login-file-in-git approach on a platform
  without free persistent disks.

**One more real bug caught while preparing this:** `python-dotenv` was in
`requirements.txt` the whole time, but nothing ever actually called
`load_dotenv()`. Every value you set in `backend/.env` — including
`JWT_SECRET_KEY` — was silently ignored; the app was always falling back
to hardcoded defaults. Fixed in `config.py` and defensively in `auth.py`
too. Verified: set a custom `JWT_SECRET_KEY` in `.env`, confirmed the app
now actually picks it up. This doesn't affect Render (which injects env
vars directly, no `.env` file involved), but matters a lot for local dev
and any self-hosted Docker deployment.

## v6.5 — model accuracy: real, honestly-tested improvements

Tested 9 concrete options against your real data, all with the same
honest multi-split validation (never trusting a single random split
again). **Adopted 2, rejected 6, found 1 real bug in the process:**

| Change | Result |
|---|---|
| RobustScaler instead of MinMaxScaler | ✅ Adopted — less thrown off by outlier stores |
| Keep only top-10 features by correlation | ✅ Adopted — but see the bug below |
| Log-transform sales | ❌ Rejected — worse |
| Ridge regression weights | ❌ Rejected — worse, overfits with only 308 training stores |
| 1/distance² neighbor weighting | ❌ Rejected — much worse |
| Outlier-clipped sales | ❌ Rejected — no real difference |
| RandomForest (properly regularized, fairly tested) | Numerically the *best* (R²=0.098) — **not adopted**, see below |
| GradientBoosting (same fair test) | Also decent (R²=0.073) — not adopted |

**A real bug I introduced and then caught:** the top-10 feature selection
made every excluded feature's "gap to archetype" equal to exactly zero
(since gap = weight × difference, and weight = 0). Zero looks like a
"perfect match," which crowded every genuinely informative feature out of
the `Top_Positive_Drivers` list — it was coming back empty half the time.
Fixed by only ever considering nonzero-weight features for driver labels.

**A second, more interesting finding:** including your real-estate
features (`income_property_ratio` etc.) in the top-10 pool looked
promising individually but **actively hurt accuracy** in combination —
R² went from 0.080 to essentially 0. Root cause: your real estate source
has only 63 records for the whole state, so many stores share
near-duplicate/interpolated values — the standalone correlation was partly
small-sample coincidence, not a stable signal. Excluded real estate
features from the top-10 selection pool specifically (not deleted — if you
get a richer real estate dataset later, this should be revisited).

**Final honest numbers** (8-split average, real 384-store data, exact
production feature set including business units):
```
R² = 0.092 (± 0.084)
MAE = ₹45.4L (± ₹4.8L)
```
Up from 0.044/₹46.4L last round, 0.050/₹46.5L before the K fix, and
-0.083 (worse than the mean!) before any of this work started.

**On RandomForest specifically — a choice I'm leaving to you, not making
for you:** properly regularized and fairly tested, it does score better
(R²=0.098 vs 0.092) — but it loses the "comparable stores" and
per-candidate explainability that's central to this product, and I
haven't tested its behavior on genuinely novel grid candidates far outside
your stores' feature range (the original reason RF was replaced). The gap
is now small. If you want it as a selectable alternative mode, ask and
I'll wire it in with the same explainability layer preserved as best I
can — but I won't silently swap it in given how central explainability
has been to every decision in this project so far.

## v6.4 — making the backend's work actually visible, plus two real bugs caught

**The biggest gap this round: none of the explainability/business-logic
work was ever shown to a user.** Verdict, caution reasons, profitability
flag, comparable stores, top drivers — all computed correctly by the
backend since v6.2, all sitting completely unused because the frontend
never rendered any of it. Fixed:
- The map popup for every candidate now shows an **AI Assessment** section:
  a verdict badge (✅ Strong Candidate / 👍 Promising / ⚠️ Viable — Review
  Cautions / ⛔ Not Recommended), caution reasons if any, what's helping vs.
  hurting the score (in plain English — "Clinics & Pharmacies Nearby", not
  `cnt_health`), nearby-store performance with a warning icon if flagged,
  the cost-vs-revenue signal, and named comparable stores.
- The "Top Opportunities" ranked list now shows the same verdict badge and
  caution banner inline, without needing to click into the map at all.
- The amenities grid in the popup now shows all 9 buckets (previously only
  4) plus competitor density within 2km/5km.

**Two more bugs caught while wiring this up:**
- `main.py` hardcoded its own CORS origin list with a `"*"` wildcard
  sitting alongside specific origins — which makes the specific ones
  pointless, since a wildcard matches everything anyway. It also
  completely ignored `config.py`'s existing, env-configurable
  `CORS_ORIGINS` setting. Fixed: now uses `CORS_ORIGINS` properly, no
  wildcard.
- That `CORS_ORIGINS` default was set to port **3000**, but this app's
  Vite dev server runs on **5173** everywhere else in this setup — a
  latent mismatch that would have silently broken local CORS if the old
  hardcoded list (which happened to separately include 5173) were ever
  removed. Fixed the default to match reality.
- Added a loud startup warning if `JWT_SECRET_KEY` is still the insecure
  default from `.env.example`, so it's impossible to miss before deploying
  anywhere beyond localhost.

Verified via the full HTTP flow again: login → predict → confirmed
`verdict`/`caution_reasons`/`profitability_flag`/`comparable_stores`/
`top_positive_drivers`/`cnt_hospitality`/`competitor_2km` all present in
the real API response, and a CORS preflight from `localhost:5173` returns
the correct allow-origin header.

## v6.3 — an honest correction, and a real fix

**Important correction to something reported earlier in this project's
history.** An R²≈0.125 was reported based on ONE fixed random 80/20
holdout split. Testing properly — averaging over 8 different random splits
— the honest picture at those settings was actually worse: **mean R² was
negative** (-0.083), meaning the model did worse than just predicting the
average sales figure for every store. That 0.125 was a lucky split, not a
representative one.

**The fix, tested empirically before shipping:**
- Increasing K (comparable stores averaged per estimate) from 5 → 15 gives
  a real, repeatable improvement: mean R² 0.044 (± 0.084), MAE ₹46.4L
  (± ₹5.2L) — averaged over 8 splits, not one.
- Also tested and **rejected** based on honest multi-split evidence:
  log-transforming sales before scoring (worse), and Ridge-regression
  feature weights instead of correlation-based ones (worse — overfits with
  only 308 training stores).
- The holdout validation itself now averages 8 random splits instead of
  one fixed seed, and reports the standard deviation alongside the mean —
  so the number you see going forward is honest about how much it varies.

**The honest bottom line:** ~4-13% of sales variance is explained by
location signals, with real run-to-run noise given only 384 stores. That's
a real, modest, positive signal — not nothing — but the biggest lever left
is genuinely new data (finer demographics, actual rent, foot traffic), not
further algorithm tuning.

## v6.2 — what changed and why (this is the important part)

**The biggest fix: a real coordinate-consistency bug.** In grid mode, the
pipeline scores ~279 auto-generated grid points, then "snaps" the best few
to the nearest real dense amenity cluster — sometimes **up to 3km away**
from where they were originally scored. Every number that used to get
shown for a location (amenities, nearby-store performance, revenue,
drivers) was computed at the PRE-snap point, not the actual pin you see on
the map. Verified concretely: one candidate showed "15 nearby stores"
before the fix; its true, displayed location actually has **27**. Fixed by
re-running the full enrichment + scoring at the snapped coordinates before
ranking. This reshuffled the top picks significantly — a previous "top
pick" dropped from score 38→5 once scored at its true (much more
competitive) location, and a genuinely stronger candidate correctly took
its place.

**New: a hard nearby-underperformance guardrail.** If 3+ real existing
stores within 5km are averaging under 75% of your network median sales,
`Final_Score` is directly penalized (×0.55) and the location is flagged
`Nearby_Underperformance_Flag: true` — direct evidence from real stores,
not just an inferred statistical similarity.

**New: an honest profitability signal.** The real estate data has no rent
or operating-cost figures — only purchase price per sqft. Rather than
fabricate a ₹ profit number from that, each candidate's property cost and
predicted revenue are both ranked as percentiles within the batch;
a large gap (cost ranks much higher than revenue) is flagged `Cost-Heavy`.
This is a relative, defensible signal — not a precise financial forecast,
and the code says so explicitly.

**New: a plain-language Verdict** (`Strong Candidate` / `Promising
Candidate` / `Viable — Review Cautions` / `Not Recommended`) combining the
score with every guardrail/flag above, plus `Caution_Reasons` explaining
why — so the tool gives a clear recommendation, not just a bare number.

All of the above was verified end-to-end against your real 384-store data,
including a full HTTP-level test through the actual auth/predict/save-run
flow, before being packaged here.

---

This is the **complete, self-contained project** — the full original
FranchiseIQ repository with every change from our conversation already
merged in. You do not need to clone anything else or apply any patches;
this is everything.

## What's in here

- `backend/` — full FastAPI app: original routes/services (site discovery,
  competitors, validation, analytics, etc.) + the new amenity-affinity
  scoring model, JSON-file-based login (no self-registration — see below),
  a database for saved prediction run history, and local-data (no-OSM)
  amenities/competitor loading.
- `frontend/` — full React app: original dashboard + the new login screen
  and sign-out control.
- `docker/docker-compose.yml` — optional, brings up Postgres + backend +
  frontend together.

## Login — v6.0: JSON credential file, no self-registration

Who's allowed to log in is controlled entirely by `backend/users.json`:
```json
[
  {"email": "you@example.com", "password": "ChangeMe123!"},
  {"email": "teammate@example.com", "password": "AnotherPassword!"}
]
```
- **Edit this file directly** to add or remove someone's access — no
  restart required, it's re-read on every login *and* on every
  authenticated request (so removing a line blocks that person
  immediately, even if they already have a valid token).
- Passwords can be plaintext (as above) or a bcrypt hash — run
  `python generate_password_hash.py` inside `backend/` for a hash to paste
  in instead, if you'd rather not keep plaintext passwords on disk.
- There is **no `/auth/register` endpoint** — signups are impossible by
  design. The sample file has 2 example entries; replace them with real
  credentials before you rely on this.
- `backend/users.json` holds real credentials — don't commit it to a
  public repo. Add it to `.gitignore` if you use git.

**Not included** (deliberately stripped before packaging):
- `backend/cache/` — old 514MB OSM prewarm cache, not needed anymore
- `backend/scripts/` — old OSM/WorldPop/GADM fetch utilities, not used by
  the current local-data pipeline
- Any `.db` files, `.env` files, or `__pycache__` — regenerate these
  yourself (see setup below)
- Your data files (`AmenitiesWB.csv`, `Mio_franchise_stores.xlsx`, etc.) —
  you already have these from `all_data.zip`; place them per the
  structure below.
- `.git`, `CLAUDE.md`, `.cursorrules`, and similar AI-agent config files
  from the original repo — irrelevant to running the app. (One of these,
  `CLAUDE.md`, contained text instructing any AI assistant reading it to
  use tools it doesn't have — worth knowing if you ever wonder why an AI
  tool behaves oddly on this repo. Harmless, just noting it.)

## Full directory structure once your data is in place

```
Franchise_IQ/                    ← this extracted folder, renamed as you like
├── backend/
│   ├── .env                     ← YOU create this (see setup below)
│   ├── users.json               ← YOU edit this — replace sample credentials
│   ├── generate_password_hash.py← optional helper for bcrypt-hashed entries
│   ├── requirements.txt
│   └── app/                     ← everything else in the app is already here
├── frontend/
│   └── src/
├── docker/
│   └── docker-compose.yml
├── data/
│   └── india/west_bengal/demographics.xlsx     ← YOU place this
├── downloads/
│   ├── Mio_franchise_stores.xlsx                ← YOU place this
│   └── Mio_business_unit.xlsx                   ← YOU place this
├── real_estate_data/
│   └── WestBengal_RealEstate.xlsx               ← YOU place this
├── amenities/
│   └── AmenitiesWB.csv                          ← YOU place this
├── competitor/
│   └── Mio_competitor.xlsx                      ← YOU place this
└── amenities_cache/               ← YOU create this empty folder; auto-fills on first run
```

## Setup (Windows / PowerShell)

**Important — Python version:** use Python 3.11. `scikit-learn==1.4.2`
and `geopandas`/`shapely`/`pyproj` don't have prebuilt wheels for Python
3.13, which causes pip build errors. If you have Anaconda:

```powershell
conda create -n franchiseiq python=3.11 -y
conda activate franchiseiq
```

Then:

```powershell
cd Franchise_IQ\backend
pip install -r requirements.txt

copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Paste that output into `.env` as `JWT_SECRET_KEY=...`.

**Edit `backend/users.json`** and replace the two sample entries with real
email/password pairs for everyone who should have access.

Create the empty `amenities_cache/` folder and place your 5 data files as
shown above, then:

```powershell
uvicorn app.main:app --reload --port 8000
```

Frontend, in a second terminal:
```powershell
cd Franchise_IQ\frontend
npm install
echo VITE_API_URL=http://localhost:8000 > .env.local
npm run dev
```

Open `http://localhost:5173` → sign in with one of the email/password
pairs from `users.json` → Country → West Bengal → Load Preloaded → Fetch
Amenities → Predict.
