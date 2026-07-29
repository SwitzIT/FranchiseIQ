FROM python:3.11-slim

WORKDIR /app

# System deps needed by geopandas/osmnx
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev gdal-bin libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend app code
COPY backend/ .

# Copy demographics, cache, and preloaded datasets from the root
COPY data/ ./data
COPY amenities_cache/ ./amenities_cache
COPY downloads/ ./downloads
COPY real_estate_data/ ./real_estate_data
# v6.6 — these two were missing entirely. Without them, the container has
# no local amenities/competitor source data and every /fetch_amenities
# call fails with FileNotFoundError, exactly like the local Windows setup
# did before those folders were created.
COPY amenities/ ./amenities
COPY competitor/ ./competitor

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
