"""
Refresh mandi price cache in GCS for ALL crops from AgMarkNet.
Fetches the full commodity list first, then caches each one.

Usage: python scripts/refresh_mandi_cache.py
"""

import json
import os
import sys
import requests
from datetime import datetime
from google.cloud import storage

API_KEY = os.environ.get("AGMARKNET_API_KEY", "")
BUCKET = "kisanmind-cache"
PREFIX = "mandi-prices"


def get_all_commodities() -> list[str]:
    """Fetch all unique commodity names from AgMarkNet."""
    url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    commodities = set()
    # Fetch in batches
    for offset in range(0, 10000, 1000):
        params = {
            "api-key": API_KEY,
            "format": "json",
            "limit": 1000,
            "offset": offset,
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("records", [])
            if not records:
                break
            for r in records:
                c = r.get("commodity", "")
                if c:
                    commodities.add(c)
        except Exception as e:
            print(f"  Batch offset={offset} failed: {e}")
            break
    return sorted(commodities)


def fetch_and_cache(crop_name: str, gcs_client: storage.Client) -> int:
    """Fetch all records for a crop from AgMarkNet and upload to GCS."""
    url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    params = {
        "api-key": API_KEY,
        "format": "json",
        "limit": 500,
        "filters[commodity]": crop_name,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        records = data.get("records", [])
        if not records:
            return 0

        cache_data = {
            "commodity": crop_name,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "total": len(records),
            "records": records,
        }

        file_key = crop_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
        blob_name = f"{PREFIX}/agmarknet_{file_key}.json"

        bucket = gcs_client.bucket(BUCKET)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(
            json.dumps(cache_data, ensure_ascii=False),
            content_type="application/json",
        )
        blob.make_public()

        print(f"  [{len(records):>3}] {crop_name} → {blob_name}")
        return len(records)

    except Exception as e:
        print(f"  [ERR] {crop_name}: {e}")
        return 0


def main():
    if not API_KEY:
        print("ERROR: AGMARKNET_API_KEY not set")
        sys.exit(1)

    print("Step 1: Fetching all commodity names from AgMarkNet...")
    all_crops = get_all_commodities()
    print(f"Found {len(all_crops)} unique commodities\n")

    print("Step 2: Caching each commodity to GCS...")
    gcs_client = storage.Client()
    total_records = 0
    cached_count = 0

    for crop in all_crops:
        count = fetch_and_cache(crop, gcs_client)
        total_records += count
        if count > 0:
            cached_count += 1

    # Also save the commodity index
    index_data = {
        "commodities": all_crops,
        "count": len(all_crops),
        "cached_at": datetime.utcnow().isoformat() + "Z",
    }
    bucket = gcs_client.bucket(BUCKET)
    blob = bucket.blob(f"{PREFIX}/commodity_index.json")
    blob.upload_from_string(json.dumps(index_data, ensure_ascii=False), content_type="application/json")
    blob.make_public()

    print(f"\nDone. {total_records} records cached for {cached_count}/{len(all_crops)} commodities.")
    print(f"Index saved to gs://{BUCKET}/{PREFIX}/commodity_index.json")


if __name__ == "__main__":
    main()
