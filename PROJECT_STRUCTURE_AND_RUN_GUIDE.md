# FranchiseIQ v5.0 — Final Structure, Codes & Run Guide

Fully offline location-scoring product: amenity-affinity scoring (no RF
regression), your own local datasets (no OSM, no live Places API), JWT
login, and a Postgres/SQLite database for saved runs.

**Everything in this bundle has been run end-to-end against your actual
384-store dataset in a test environment — not just written, actually
executed, with a real bug found and fixed in the process (see §4).**

---

## 1. Final directory structure

```
Franchise_IQ/
├── backend/
│   ├── .env                          ← copy from .env.example, fill in JWT_SECRET_KEY
│   ├── requirements.txt              ← ← this bundle (osmnx removed)
│   ├── franchiseiq.db                ← auto-created on first run (SQLite)
│   └── app/
│       ├── main.py                   ← creates DB tables on startup
│       ├── __init__.py
│       ├── config.py                 ← ← this bundle (local data paths, no OSM by default)
│       ├── auth.py                   ← JWT + password hashing
│       ├── db/
│       │   ├── __init__.py
│       │   ├── database.py           ← SQLAlchemy engine/session (SQLite/Postgres)
│       │   └── models.py             ← User, PredictionRun tables
│       ├── models/
│       │   ├── __init__.py
│       │   ├── affinity_model.py     ← ← this bundle — THE scoring model
│       │   └── rf_model.py           ← untouched, kept only as reference
│       ├── routes/
│       │   ├── __init__.py           ← registers auth_routes + runs
│       │   ├── auth_routes.py        ← /auth/register, /auth/login, /auth/me
│       │   ├── runs.py               ← /runs — saved prediction history
│       │   ├── predict.py            ← now requires login
│       │   ├── results.py            ← now requires login
│       │   └── ...(all other existing route files — unchanged)
│       └── services/
│           ├── scoring_service.py    ← ← this bundle — competitor + no-OSM wiring
│           ├── amenities_service.py  ← ← this bundle — REWRITTEN, local file, no OSM
│           ├── local_competitor_service.py  ← ← this bundle — NEW
│           ├── demographics_service.py      ← ← this bundle — Income bug fix
│           └── ...(real_estate_service.py, clustering_service.py, etc. — unchanged)
│
├── data/
│   └── india/
│       ├── west_bengal/demographics.xlsx    ← from your data/ folder
│       └── odisha/demographics.xlsx
│
├── downloads/
│   ├── Mio_franchise_stores.xlsx     ← from your franchise_store/ folder
│   └── Mio_business_unit.xlsx        ← from your business_unit/ folder
│
├── real_estate_data/
│   └── WestBengal_RealEstate.xlsx    ← from your real_estate_data/ folder
│
├── amenities/                         ← NEW folder — put your raw file here
│   └── AmenitiesWB.csv                ← from your amenities/ folder, AS-IS
│
├── competitor/                        ← NEW folder — put your raw file here
│   └── Mio_competitor.xlsx            ← from your competitor/ folder, AS-IS
│
├── amenities_cache/                   ← auto-populated on first run (parsed
│                                          version of AmenitiesWB.csv, not OSM)
│
└── frontend/
    └── src/
        ├── App.jsx                    ← auth gate
        ├── context/AuthContext.jsx     ← NEW
        ├── pages/LoginPage.jsx         ← NEW
        ├── services/authApi.js         ← NEW
        ├── services/api.js             ← attaches JWT to requests
        └── components/Sidebar.jsx      ← sign-out button
```

**Every one of your six original folders now has a real, wired-in home.**
Nothing needs to be uploaded or fetched live — the whole pipeline runs from
local disk.

---

## 2. What actually changed vs the last message, and why

You said you don't want any live OSM fetching, and that you already have
all the data. So amenities and competitors are no longer live/optional —
they're now first-class local data sources, on the same footing as
demographics and real estate:

- **`amenities_service.py` — fully rewritten.** No `osmnx`, no network call
  of any kind. It reads `AmenitiesWB.csv` directly, parses the `Query`
  column (`"restaurant in Kolkata, West Bengal"` → category `restaurant`),
  and maps each row into one of **9** buckets (the original 7, plus 2 new
  ones — `hospitality` and `civic` — because your real data has hotels,
  police stations, and post offices that the old OSM-tag scheme never
  covered). Verified against your file: **44,144 amenity points parsed**,
  bucketed as `health: 15,424 · education: 8,588 · finance: 7,758 ·
  food: 6,145 · leisure: 3,255 · hospitality: 1,594 · civic: 1,380`.
  (`retail` and `transport` come back 0 — your CSV has no
  supermarket/mall/bus-station entries — the model handles that
  gracefully, that feature just gets ~0 weight automatically.)
- **`local_competitor_service.py` — new.** Loads `Mio_competitor.xlsx`
  (6,250 real competitor shops across 36 cities) and computes
  `Competitor_2km` / `Competitor_5km` for every store and candidate — a
  genuine market-saturation signal your old pipeline never had at all.
  Verified: it came out as the **#2 most important feature** in the model
  (right after `income_property_ratio`), which makes intuitive sense for a
  bakery/confectionery franchise.
- **`config.py` — OSM road/landuse fetch now OFF by default**
  (`ENABLE_OSM_GEO_FEATURES=false`). It's not deleted — if you ever want
  that extra signal later, flip the env var and install `osmnx` — but
  nothing in the default path makes a network call.

## 3. What the model actually learned from your real data

Running the full pipeline against your real 384 stores (verified, not
simulated), the top feature weights came out as:

| Rank | Feature | Weight | Direction |
|---|---|---|---|
| 1 | `income_property_ratio` | 0.105 | higher is better |
| 2 | `Competitor_2km` | 0.075 | **lower** is better |
| 3 | `cnt_health` | 0.067 | higher is better |
| 4 | `cnt_education` | 0.062 | higher is better |
| 5 | `cnt_food` | 0.061 | higher is better |

`model_metrics`: `r2_test ≈ 0.115`, `mae_test ≈ ₹53.5L`,
`validation: "knn_lookalike_holdout"`.

**Honest framing, not a sales pitch:** that MAE is in the same range as the
RF model's ~₹50L you started with. I want to be direct about that rather
than overclaiming — with this feature set, roughly ₹50L of unexplained
variance appears to be a real, current ceiling on "predict sales from
location signals alone" for this data (store execution, staff, local
marketing, and other unmeasured factors matter too). What genuinely did
improve:
- **R² is honestly reported** (0.115) instead of hidden behind a
  black-box RF number — you now know exactly how much location explains.
- **Every score comes with real comparable stores and named drivers** —
  something the RF regressor never gave you at all.
- **The revenue range is grounded in actual stores**, not a fabricated
  point estimate that can silently extrapolate to nonsense for a brand-new
  location.
- Adding `Competitor_2km`/`5km` gave the model a genuinely new, real signal
  it didn't have before (it ranked #2).

If you want to push MAE down further from here, the highest-leverage next
step is more/better features (foot traffic, rent, store manager tenure,
local competition intensity beyond just counts) rather than a different
model — the ceiling right now looks data-limited, not algorithm-limited.

## 4. Bugs found and fixed during testing

Two real bugs surfaced by actually running this — not just writing it:

**a) Scoring collapsed to 0.** `Final_Score` came back as 0.0 for every
single candidate. Root cause: the calibration anchor ("what similarity
counts as a 50") was computed from an aggregated median-feature-vector,
which sits artificially close to the top-performer archetype (each
dimension gets smoothed independently), while real individual stores are
naturally noisier and sit further away. That made the 0–100 scale wildly
oversensitive and clipped almost every real score to 0. **Fixed** by
anchoring on the *median of individual stores' own similarities* to the
archetype instead. Re-verified: scores now come back in a sane 18–39 range.

**b) Registration/login crashed entirely.** `passlib==1.7.4` combined with
an unpinned `bcrypt` installs `bcrypt` 5.x by default, which breaks
passlib's internal backend self-test with `ValueError: password cannot be
longer than 72 bytes`. Every `/auth/register` call would have failed in
production. **Fixed** by pinning `bcrypt==4.0.1` in `requirements.txt`.

Both fixes are verified in this bundle via a full HTTP-level test
(`TestClient`, real SQLite DB, real JWT) that exercised the entire flow:
register → login → 401-without-token → country/state selection → load
data → parse local amenities → run prediction (auth-protected) → save run
→ list runs → `/auth/me`. All 200s, real scores, real comparable stores.

---

## 5. Setup, step by step

```bash
# 1. Apply this bundle's files into your local clone at the paths shown
#    in §1, then place your six data folders' contents exactly as shown:
mkdir -p Franchise_IQ/downloads Franchise_IQ/real_estate_data
mkdir -p Franchise_IQ/amenities Franchise_IQ/competitor
cp franchise_store/Mio_franchise_stores.xlsx   Franchise_IQ/downloads/
cp business_unit/Mio_business_unit.xlsx        Franchise_IQ/downloads/
cp real_estate_data/WestBengal_RealEstate.xlsx Franchise_IQ/real_estate_data/
cp amenities/AmenitiesWB.csv                   Franchise_IQ/amenities/
cp competitor/Mio_competitor.xlsx              Franchise_IQ/competitor/
cp -r data/india                                Franchise_IQ/data/

# 2. Backend
cd Franchise_IQ/backend
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into .env as JWT_SECRET_KEY

uvicorn app.main:app --reload --port 8000
#   → creates franchiseiq.db automatically
#   → first /fetch_amenities call parses AmenitiesWB.csv (a few seconds,
#     not minutes — no network involved) and caches the parsed result

# 3. Frontend (separate terminal)
cd Franchise_IQ/frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Open `http://localhost:5173` → register → Country → West Bengal →
Load Preloaded → Fetch Amenities (fast, local parse) → Predict.

## 6. Running with Docker (includes Postgres)

```bash
cd Franchise_IQ/docker
docker compose up --build
```
Brings up Postgres + backend + frontend together with `DATABASE_URL` /
`JWT_SECRET_KEY` pre-wired (change the default password/secret before any
real deployment). Mount your `amenities/`, `competitor/`, `downloads/`,
`real_estate_data/`, and `data/` folders as volumes the same way
`docker-compose.yml` already mounts `data/`.

## 7. Sanity-check before you trust it

- Compare `Comparable_Stores` on a couple of predictions against locations
  you know well — do the named comparable stores actually make sense
  (nearby, similar neighbourhood)?
- Look at `top_positive_drivers` / `top_negative_drivers` per candidate —
  they should read as genuine business logic (e.g. "close to competitors,
  low health-amenity density" as negatives), not noise.
- `GET /api/amenities_status?...` will show the parsed bucket counts if you
  want to confirm the CSV parsed the way you expect.

## 8. One pre-existing issue, unrelated to this bundle

`app/routes/__init__.py` lists a `"chat"` module that doesn't exist
anywhere in the repo (`app/routes/chat.py` is missing). This was already
true in your original, unmodified codebase — not something introduced
here. It fails silently (logged as `router-import-failed`, app still
boots fine), but it means the `/api/chat` endpoint the frontend's
`ChatBot.jsx` expects isn't actually registered. Worth knowing about if
that chatbot panel doesn't respond — it's a separate, pre-existing gap.

