import base64
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# --- Auth / OAuth2 ---
TOKEN_URL = "https://gw.ext.prod.api.enedis.fr:443/oauth2/v3/token"
CLIENT_ID = "LyKMEhtHjyankDtHG6fibsf0l2Ua"
CLIENT_SECRET = "sgIdP0naEG5_x9INE88SEIqc5B8a"

# --- API metering_data ---
API_BASE_URL = "https://gw.ext.prod.api.enedis.fr:443/mesures/v2"
RESOURCE_PATH = "/metering_data/consumption_load_curve"
DEFAULT_USAGE_POINT_ID = "30001940100942"


# =======================
# TOKEN
# =======================

def get_access_token_client_credentials() -> str:
    """Return an OAuth2 access_token via client_credentials."""
    data = {"grant_type": "client_credentials"}

    userpass = f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")
    basic_token = base64.b64encode(userpass).decode("ascii")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "python-linky-client/1.0",
        "Authorization": f"Basic {basic_token}",
        "Host": "gw.ext.prod.api.enedis.fr:443",
    }

    resp = requests.post(TOKEN_URL, data=data, headers=headers, timeout=15)
    resp.raise_for_status()

    payload = resp.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError(f"Missing access_token in /token response: {payload}")
    return access_token


# =======================
# DATA FETCH
# =======================

def get_consumption_load_curve(
    access_token: str,
    start: str,
    end: str,
    usage_point_id: str = DEFAULT_USAGE_POINT_ID,
) -> dict:
    """Call /metering_data/consumption_load_curve for [start, end). Max 7 days."""
    url = API_BASE_URL + RESOURCE_PATH

    params = {
        "usage_point_id": usage_point_id,
        "start": start,
        "end": end,
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": "python-linky-client/1.0",
    }

    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _split_into_chunks(start: date, end: date, max_days: int = 7) -> List[Tuple[date, date]]:
    chunks: List[Tuple[date, date]] = []
    current = start
    while current < end:
        chunk_end = min(current + timedelta(days=max_days), end)
        chunks.append((current, chunk_end))
        current = chunk_end
    return chunks


def _extract_meter_reading(payload: dict) -> Tuple[Optional[dict], List[dict]]:
    """
    Normalize API responses:
    - newer form: {"meter_reading": {..., "interval_reading": [...]}}
    - older form: {"usage_point": [{"meter_reading": {...}}]}
    Returns (meter_reading_without_intervals, interval_list)
    """
    if "meter_reading" in payload:
        meter = payload.get("meter_reading") or {}
        intervals = meter.get("interval_reading", []) or []
        meter = {k: v for k, v in meter.items() if k != "interval_reading"}
        return meter, intervals

    usage_points = payload.get("usage_point", [])
    if usage_points:
        meter = usage_points[0].get("meter_reading", {}) or {}
        intervals = meter.get("interval_reading", []) or []
        meter = {k: v for k, v in meter.items() if k != "interval_reading"}
        return meter, intervals

    return None, []


def fetch_consumption_range(
    start_date: str,
    end_date: str,
    usage_point_id: str = DEFAULT_USAGE_POINT_ID,
    output_dir: str | Path = "../data/ENEDIS",
) -> Dict[str, object]:
    """Fetch load curve over a range, splitting into 7-day chunks, and merge to one file.

    Dates use YYYY-MM-DD strings; start is inclusive, end is exclusive.
    Returns a dict with combined data and output file path.
    """
    start_dt = date.fromisoformat(start_date)
    end_dt = date.fromisoformat(end_date)
    if start_dt >= end_dt:
        raise ValueError("start_date must be before end_date")

    chunks = _split_into_chunks(start_dt, end_dt, max_days=7)
    token = get_access_token_client_credentials()

    combined_intervals: List[dict] = []
    base_meter: Optional[dict] = None
    raw_responses = []

    for chunk_start, chunk_end in chunks:
        payload = get_consumption_load_curve(
            access_token=token,
            start=chunk_start.isoformat(),
            end=chunk_end.isoformat(),
            usage_point_id=usage_point_id,
        )
        raw_responses.append(payload)

        meter_reading, intervals = _extract_meter_reading(payload)
        if meter_reading is not None and base_meter is None:
            base_meter = meter_reading
        combined_intervals.extend(intervals)

    combined_data: Dict[str, object]
    if base_meter is not None:
        meter_copy = dict(base_meter)
        meter_copy["interval_reading"] = combined_intervals
        meter_copy.setdefault("usage_point_id", usage_point_id)
        combined_data = {
            "meter_reading": meter_copy,
            "chunks": len(chunks),
            "start": start_date,
            "end": end_date,
        }
    else:
        combined_data = {
            "meter_reading": {},
            "chunks": len(chunks),
            "start": start_date,
            "end": end_date,
        }

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"metering_data_{start_date}_to_{end_date}.json"
    with filename.open("w", encoding="utf-8") as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)

    return {
        "data": combined_data,
        "file": filename,
        "raw_responses": raw_responses,
    }


# =======================
# MAIN (example)
# =======================

def main():
    start_str = "2026-01-05"
    end_str = "2026-01-12"  # exclusive
    result = fetch_consumption_range(start_str, end_str)
    print(f"Combined file written to: {result['file']}")
    meter = result["data"].get("meter_reading", {})
    intervals = meter.get("interval_reading", [])
    print(f"Total intervals: {len(intervals)}")
    for item in intervals[:5]:
        print(item)


if __name__ == "__main__":
    main()
