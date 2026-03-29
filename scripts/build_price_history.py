"""
Build 90-day price history for all commodities from AgMarkNet.
Correlates with weather data from Open-Meteo archive API.
Stores analysis as JSON in GCS bucket and locally.

Usage: python scripts/build_price_history.py
"""

import asyncio
import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from google.cloud import storage

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("AGMARKNET_API_KEY", "")
GCS_BUCKET = "kisanmind-cache"
GCS_PREFIX = "price-history"
LOCAL_DIR = Path(__file__).resolve().parent.parent / "data" / "price_history"

AGMARKNET_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"

# Major agricultural regions (lat, lon, name) for weather correlation
AGRICULTURAL_REGIONS = [
    (28.6, 77.2, "Delhi-NCR"),
    (26.9, 75.8, "Rajasthan"),
    (23.2, 72.6, "Gujarat"),
    (19.1, 73.0, "Maharashtra"),
    (15.4, 75.0, "Karnataka"),
    (13.1, 80.3, "Tamil Nadu"),
    (17.4, 78.5, "Telangana"),
    (22.6, 88.4, "West Bengal"),
    (26.8, 81.0, "Uttar Pradesh"),
    (25.6, 85.1, "Bihar"),
    (21.2, 81.1, "Chhattisgarh"),
    (23.3, 85.3, "Jharkhand"),
    (20.9, 85.1, "Odisha"),
    (31.1, 77.2, "Himachal Pradesh"),
    (30.7, 76.8, "Punjab-Haryana"),
]

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


# ---------------------------------------------------------------------------
# Fetch all AgMarkNet records (paginated)
# ---------------------------------------------------------------------------
async def fetch_all_agmarknet_records(client: httpx.AsyncClient) -> list[dict]:
    """Fetch all available records from AgMarkNet API, paginating with offset."""
    all_records = []
    offset = 0
    batch_size = 1000
    max_records = 50000  # safety limit

    while offset < max_records:
        params = {
            "api-key": API_KEY,
            "format": "json",
            "limit": batch_size,
            "offset": offset,
        }
        try:
            resp = await client.get(AGMARKNET_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("records", [])
            if not records:
                break
            all_records.extend(records)
            print(f"  Fetched {len(all_records)} records (offset={offset})...")
            offset += batch_size
        except Exception as e:
            print(f"  Fetch failed at offset={offset}: {e}")
            break

    return all_records


def parse_date(date_str: str) -> datetime | None:
    """Parse DD/MM/YYYY date format from AgMarkNet."""
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y")
    except (ValueError, AttributeError):
        return None


def filter_recent_records(records: list[dict], days: int = 90) -> list[dict]:
    """Filter records to only those within the last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    filtered = []
    for r in records:
        dt = parse_date(r.get("arrival_date", ""))
        if dt and dt >= cutoff:
            r["_parsed_date"] = dt
            filtered.append(r)
    return filtered


def safe_float(val) -> float | None:
    """Safely convert a value to float."""
    try:
        v = float(val)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Build price time series per commodity
# ---------------------------------------------------------------------------
def build_commodity_timeseries(records: list[dict]) -> dict[str, list[dict]]:
    """Group records by commodity and build daily price series."""
    by_commodity: dict[str, dict[str, list]] = {}

    for r in records:
        commodity = r.get("commodity", "").strip()
        if not commodity:
            continue

        dt = r.get("_parsed_date")
        if not dt:
            continue

        date_str = dt.strftime("%Y-%m-%d")
        modal = safe_float(r.get("modal_price"))
        min_p = safe_float(r.get("min_price"))
        max_p = safe_float(r.get("max_price"))

        if modal is None:
            continue

        if commodity not in by_commodity:
            by_commodity[commodity] = {}

        if date_str not in by_commodity[commodity]:
            by_commodity[commodity][date_str] = []

        by_commodity[commodity][date_str].append({
            "modal": modal,
            "min": min_p or modal,
            "max": max_p or modal,
            "state": r.get("state", ""),
            "market": r.get("market", ""),
        })

    # Convert to sorted daily price list
    result = {}
    for commodity, date_dict in by_commodity.items():
        daily = []
        for date_str in sorted(date_dict.keys()):
            entries = date_dict[date_str]
            prices = [e["modal"] for e in entries]
            mins = [e["min"] for e in entries]
            maxs = [e["max"] for e in entries]
            daily.append({
                "date": date_str,
                "avg_price": round(sum(prices) / len(prices)),
                "min_price": round(min(mins)),
                "max_price": round(max(maxs)),
                "num_mandis": len(entries),
            })
        result[commodity] = daily

    return result


# ---------------------------------------------------------------------------
# Moving averages and volatility
# ---------------------------------------------------------------------------
def compute_moving_average(daily_prices: list[dict], window: int) -> list[dict]:
    """Compute moving average of avg_price over a window."""
    result = []
    prices = [d["avg_price"] for d in daily_prices]
    for i in range(len(prices)):
        start = max(0, i - window + 1)
        window_prices = prices[start:i + 1]
        result.append({
            "date": daily_prices[i]["date"],
            "value": round(sum(window_prices) / len(window_prices)),
        })
    return result


def compute_volatility(daily_prices: list[dict], window: int) -> float:
    """Compute price volatility (coefficient of variation) over the last N days."""
    prices = [d["avg_price"] for d in daily_prices[-window:]]
    if len(prices) < 2:
        return 0.0
    avg = sum(prices) / len(prices)
    if avg == 0:
        return 0.0
    variance = sum((p - avg) ** 2 for p in prices) / len(prices)
    std_dev = math.sqrt(variance)
    return round(std_dev / avg, 4)


def detect_trend(daily_prices: list[dict]) -> tuple[str, str]:
    """Detect current price trend and momentum."""
    if len(daily_prices) < 3:
        return "insufficient_data", "unknown"

    recent = daily_prices[-7:] if len(daily_prices) >= 7 else daily_prices[-3:]
    first_avg = sum(d["avg_price"] for d in recent[:len(recent) // 2]) / max(len(recent) // 2, 1)
    second_avg = sum(d["avg_price"] for d in recent[len(recent) // 2:]) / max(len(recent) - len(recent) // 2, 1)

    if first_avg == 0:
        return "stable", "weak"

    change_pct = (second_avg - first_avg) / first_avg * 100

    if change_pct > 5:
        trend = "rising"
    elif change_pct < -5:
        trend = "falling"
    else:
        trend = "stable"

    momentum = "strong" if abs(change_pct) > 10 else ("moderate" if abs(change_pct) > 3 else "weak")
    return trend, momentum


def compute_sell_timing(daily_prices: list[dict], trend: str, momentum: str, volatility_7d: float) -> str:
    """Determine sell timing signal based on trend, momentum, and volatility."""
    if len(daily_prices) < 3:
        return "unknown"

    prices = [d["avg_price"] for d in daily_prices]
    avg_90d = sum(prices) / len(prices)
    current = prices[-1]

    # Price above 90-day average and falling -> sell now
    if current > avg_90d * 1.05 and trend == "falling":
        return "sell_now"

    # Price above average and rising -> wait for peak
    if current > avg_90d * 1.05 and trend == "rising":
        return "wait_3_days"

    # Price below average and rising -> hold
    if current < avg_90d * 0.95 and trend == "rising":
        return "hold"

    # High volatility -> sell in batches
    if volatility_7d > 0.15:
        return "sell_now"

    # Price near average, stable -> sell now (no advantage in waiting)
    if trend == "stable":
        return "sell_now"

    # Falling below average -> sell now to minimize loss
    if trend == "falling":
        return "sell_now"

    return "wait_3_days"


# ---------------------------------------------------------------------------
# Weather correlation
# ---------------------------------------------------------------------------
async def fetch_historical_weather(client: httpx.AsyncClient, days: int = 90) -> dict:
    """Fetch historical weather for major agricultural regions from Open-Meteo archive API."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    start_date = cutoff.strftime("%Y-%m-%d")
    end_date = datetime.utcnow().strftime("%Y-%m-%d")

    all_weather: dict[str, list] = {}  # date -> list of weather observations

    for lat, lon, region_name in AGRICULTURAL_REGIONS:
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum",
            "timezone": "Asia/Kolkata",
        }
        try:
            resp = await client.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            daily = data.get("daily", {})
            dates = daily.get("time", [])
            temp_max = daily.get("temperature_2m_max", [])
            temp_min = daily.get("temperature_2m_min", [])
            precip = daily.get("precipitation_sum", [])
            rain = daily.get("rain_sum", [])

            for i, date in enumerate(dates):
                if date not in all_weather:
                    all_weather[date] = []
                all_weather[date].append({
                    "region": region_name,
                    "temp_max": temp_max[i] if i < len(temp_max) else None,
                    "temp_min": temp_min[i] if i < len(temp_min) else None,
                    "precipitation": precip[i] if i < len(precip) else None,
                    "rain": rain[i] if i < len(rain) else None,
                })

            print(f"  Weather fetched for {region_name}")
        except Exception as e:
            print(f"  Weather fetch failed for {region_name}: {e}")

    # Aggregate to daily national averages
    daily_weather = {}
    for date, observations in sorted(all_weather.items()):
        temps_max = [o["temp_max"] for o in observations if o["temp_max"] is not None]
        temps_min = [o["temp_min"] for o in observations if o["temp_min"] is not None]
        precips = [o["precipitation"] for o in observations if o["precipitation"] is not None]
        rains = [o["rain"] for o in observations if o["rain"] is not None]

        daily_weather[date] = {
            "avg_temp_max": round(sum(temps_max) / len(temps_max), 1) if temps_max else None,
            "avg_temp_min": round(sum(temps_min) / len(temps_min), 1) if temps_min else None,
            "avg_precipitation": round(sum(precips) / len(precips), 1) if precips else 0,
            "total_rain_regions": sum(1 for r in rains if r and r > 5),
            "heavy_rain_regions": sum(1 for r in rains if r and r > 20),
            "heat_wave": any(t > 40 for t in temps_max) if temps_max else False,
            "cold_snap": any(t < 5 for t in temps_min) if temps_min else False,
        }

    return daily_weather


def correlate_weather_prices(daily_prices: list[dict], daily_weather: dict) -> dict:
    """Correlate price movements with weather events."""
    rain_impact_deltas = []
    heat_impact_deltas = []

    price_by_date = {d["date"]: d["avg_price"] for d in daily_prices}
    sorted_dates = sorted(price_by_date.keys())

    for date_str, weather in daily_weather.items():
        if date_str not in price_by_date:
            continue

        idx = sorted_dates.index(date_str) if date_str in sorted_dates else -1
        if idx < 0:
            continue

        # Check price change 1-3 days after weather event
        future_prices = []
        for offset in range(1, 4):
            if idx + offset < len(sorted_dates):
                future_date = sorted_dates[idx + offset]
                if future_date in price_by_date:
                    future_prices.append(price_by_date[future_date])

        if not future_prices:
            continue

        current_price = price_by_date[date_str]
        avg_future = sum(future_prices) / len(future_prices)
        if current_price == 0:
            continue
        pct_change = (avg_future - current_price) / current_price * 100

        # Heavy rain event
        if weather.get("heavy_rain_regions", 0) >= 3 or weather.get("avg_precipitation", 0) > 10:
            rain_impact_deltas.append(pct_change)

        # Heat wave event
        if weather.get("heat_wave"):
            heat_impact_deltas.append(pct_change)

    # Summarize
    rain_impact = "no data"
    if rain_impact_deltas:
        avg_rain = round(sum(rain_impact_deltas) / len(rain_impact_deltas), 1)
        direction = "rise" if avg_rain > 0 else "drop"
        rain_impact = f"prices {direction} {abs(avg_rain)}% within 3 days of heavy rain"

    heat_impact = "no data"
    if heat_impact_deltas:
        avg_heat = round(sum(heat_impact_deltas) / len(heat_impact_deltas), 1)
        direction = "rise" if avg_heat > 0 else "drop"
        heat_impact = f"prices {direction} {abs(avg_heat)}% during heat waves >40C"

    return {
        "rain_impact": rain_impact,
        "heat_impact": heat_impact,
        "rain_events_analyzed": len(rain_impact_deltas),
        "heat_events_analyzed": len(heat_impact_deltas),
    }


# ---------------------------------------------------------------------------
# Build analysis for a single commodity
# ---------------------------------------------------------------------------
def build_commodity_analysis(
    commodity: str,
    daily_prices: list[dict],
    daily_weather: dict,
) -> dict:
    """Build full analysis object for a commodity."""
    if not daily_prices:
        return {}

    # Moving averages
    ma_7d = compute_moving_average(daily_prices, 7)
    ma_30d = compute_moving_average(daily_prices, 30)

    # Volatility
    vol_7d = compute_volatility(daily_prices, 7)
    vol_30d = compute_volatility(daily_prices, 30)

    # Price range
    all_prices = [d["avg_price"] for d in daily_prices]
    price_range = {
        "min": min(all_prices),
        "max": max(all_prices),
        "avg": round(sum(all_prices) / len(all_prices)),
    }

    # Trend & momentum
    trend, momentum = detect_trend(daily_prices)

    # Sell timing
    sell_timing = compute_sell_timing(daily_prices, trend, momentum, vol_7d)

    # Weather correlation
    weather_corr = correlate_weather_prices(daily_prices, daily_weather)

    return {
        "commodity": commodity,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "daily_prices": daily_prices,
        "moving_avg_7d": ma_7d,
        "moving_avg_30d": ma_30d,
        "volatility_7d": vol_7d,
        "volatility_30d": vol_30d,
        "price_range_90d": price_range,
        "weather_correlation": weather_corr,
        "prediction_signals": {
            "current_trend": trend,
            "momentum": momentum,
            "sell_timing": sell_timing,
        },
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def commodity_key(name: str) -> str:
    """Convert commodity name to file-safe key."""
    return name.lower().strip().replace(" ", "_").replace("(", "").replace(")", "")


def save_to_gcs(gcs_client: storage.Client, commodity: str, data: dict):
    """Upload commodity analysis to GCS."""
    key = commodity_key(commodity)
    blob_name = f"{GCS_PREFIX}/{key}.json"
    bucket = gcs_client.bucket(GCS_BUCKET)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(
        json.dumps(data, ensure_ascii=False),
        content_type="application/json",
    )
    blob.make_public()


def save_locally(commodity: str, data: dict):
    """Save commodity analysis to local file."""
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    key = commodity_key(commodity)
    filepath = LOCAL_DIR / f"{key}.json"
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    if not API_KEY:
        print("ERROR: AGMARKNET_API_KEY not set")
        sys.exit(1)

    print("=" * 60)
    print("KisanMind — 90-Day Price History Builder")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        # Step 1: Fetch all AgMarkNet records
        print("\nStep 1: Fetching all AgMarkNet records...")
        all_records = await fetch_all_agmarknet_records(client)
        print(f"  Total records fetched: {len(all_records)}")

        # Step 2: Filter to last 90 days
        print("\nStep 2: Filtering to last 90 days...")
        recent = filter_recent_records(all_records, days=90)
        print(f"  Records within 90 days: {len(recent)}")

        if not recent:
            print("WARNING: No records found within the last 90 days.")
            print("  Will process all available records instead.")
            recent = filter_recent_records(all_records, days=365)
            print(f"  Records within 365 days: {len(recent)}")

        # Step 3: Build per-commodity time series
        print("\nStep 3: Building commodity time series...")
        timeseries = build_commodity_timeseries(recent)
        print(f"  Commodities with price data: {len(timeseries)}")

        # Step 4: Fetch historical weather
        print("\nStep 4: Fetching 90-day historical weather from Open-Meteo...")
        daily_weather = await fetch_historical_weather(client, days=90)
        print(f"  Weather data for {len(daily_weather)} days")

    # Step 5: Build analysis for each commodity
    print("\nStep 5: Building analysis for each commodity...")
    gcs_client = storage.Client()
    saved_count = 0

    for commodity, daily_prices in sorted(timeseries.items()):
        if len(daily_prices) < 2:
            print(f"  [SKIP] {commodity}: only {len(daily_prices)} day(s) of data")
            continue

        analysis = build_commodity_analysis(commodity, daily_prices, daily_weather)

        # Save to GCS and locally
        try:
            save_to_gcs(gcs_client, commodity, analysis)
        except Exception as e:
            print(f"  [GCS ERR] {commodity}: {e}")

        save_locally(commodity, analysis)
        saved_count += 1

        trend = analysis["prediction_signals"]["current_trend"]
        days = len(daily_prices)
        sell = analysis["prediction_signals"]["sell_timing"]
        print(f"  [{days:>3}d] {commodity}: trend={trend}, sell={sell}")

    # Step 6: Save commodity index
    index = {
        "commodities": sorted(timeseries.keys()),
        "count": len(timeseries),
        "analyzed": saved_count,
        "built_at": datetime.utcnow().isoformat() + "Z",
    }
    try:
        bucket = gcs_client.bucket(GCS_BUCKET)
        blob = bucket.blob(f"{GCS_PREFIX}/index.json")
        blob.upload_from_string(json.dumps(index, ensure_ascii=False), content_type="application/json")
        blob.make_public()
    except Exception as e:
        print(f"  [GCS ERR] Index: {e}")

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    (LOCAL_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2))

    print(f"\nDone. Analyzed {saved_count}/{len(timeseries)} commodities.")
    print(f"  GCS: gs://{GCS_BUCKET}/{GCS_PREFIX}/")
    print(f"  Local: {LOCAL_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
