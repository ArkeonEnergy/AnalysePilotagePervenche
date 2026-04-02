from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd
from influxdb_client import InfluxDBClient
from influxdb_client.client.query_api import QueryApi
import pytz

# Optional: override via env vars to avoid hardcoding secrets
DEFAULT_INFLUX_URL = os.getenv("INFLUX_URL", "https://eu-central-1-1.aws.cloud2.influxdata.com")
DEFAULT_INFLUX_TOKEN = os.getenv(
    "INFLUX_TOKEN",
    "asV9ER3o1xmKTQMjTT_km59aDFlhgvwXolZXeEvnvZde_F2BQEjbdqAfKiMN-71UNuSHLqlTJLNoT2ueNr-gzg==",
)
DEFAULT_INFLUX_ORG = os.getenv("INFLUX_ORG", "Pervenches")
DEFAULT_INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "AllData")


@dataclass
class InfluxConfig:
    url: str = DEFAULT_INFLUX_URL
    token: str = DEFAULT_INFLUX_TOKEN
    org: str = DEFAULT_INFLUX_ORG
    bucket: str = DEFAULT_INFLUX_BUCKET


class AcquisitionError(Exception):
    pass


def build_flux_query(
    bucket: str,
    start_time: str,
    stop_time: str,
    use_specific_fields: bool,
    fields: Optional[Sequence[str]] = None,
    measurement: Optional[str] = None,
    data_step: str = "1h",
) -> str:
    """Build the Flux query string based on the requested mode."""
    if use_specific_fields:
        if not fields:
            raise ValueError("fields must be provided when use_specific_fields is True")
        fields_filter = " or ".join([f'r["_field"] == "{field}"' for field in fields])
        filter_condition = fields_filter
    else:
        if not measurement:
            raise ValueError("measurement must be provided when use_specific_fields is False")
        filter_condition = f'r._measurement == "{measurement}"'

    # Convert France timezone (CET/CEST) to UTC for InfluxDB
    france_tz = pytz.timezone("Europe/Paris")
    start_dt = pd.to_datetime(start_time).replace(tzinfo=france_tz).astimezone(pytz.UTC)
    stop_dt = pd.to_datetime(stop_time).replace(tzinfo=france_tz).astimezone(pytz.UTC)
    
    start_time_utc = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    stop_time_utc = stop_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return (
        f'from(bucket: "{bucket}") '
        f'|> range(start: {start_time_utc}, stop: {stop_time_utc})'
        f'|> filter(fn: (r) => {filter_condition})'
        f'|> drop(columns: ["_measurement", "result", "table", "_start", "_stop"])'
        f'|> aggregateWindow(every: {data_step}, fn: last, createEmpty: false)'
        f'|> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")'
        f'|> timeShift(duration: 1h)'
        f'|> timeShift(duration: -1m)'
        f'|> yield(name: "pivoted")'
    )


def _validate_fields(fields: Optional[Sequence[str]]) -> List[str]:
    if fields is None or len(fields) == 0:
        raise ValueError("fields are required when use_specific_fields is True")
    if not all(isinstance(field, str) for field in fields):
        raise ValueError("all fields must be strings")
    cleaned = [field.strip() for field in fields]
    if not all(cleaned):
        raise ValueError("fields cannot be empty or whitespace")
    return cleaned


def _validate_dates(start_date: str, end_date: str) -> Tuple[pd.Timestamp, pd.Timestamp]:
    try:
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("invalid date format; expected YYYY-MM-DD") from exc
    if start_dt >= end_dt:
        raise ValueError("start_date must be before end_date")
    return start_dt, end_dt


def process_period(
    query_api: QueryApi,
    bucket: str,
    start_time: str,
    stop_time: str,
    use_specific_fields: bool,
    fields: Optional[Sequence[str]],
    measurement: Optional[str],
    data_step: str,
    period_name: str,
) -> Optional[pd.DataFrame]:
    """Fetch data for a single period (hour/day)."""
    flux_query = build_flux_query(
        bucket=bucket,
        start_time=start_time,
        stop_time=stop_time,
        use_specific_fields=use_specific_fields,
        fields=fields,
        measurement=measurement,
        data_step=data_step,
    )
    df_period = query_api.query_data_frame(flux_query)
    df_period = df_period.loc[:, ~df_period.columns.str.startswith("result")]

    if df_period.empty:
        return None
    return df_period

def get_data(
    start_date: str,
    end_date: str,
    fields: Optional[Sequence[str]] = None,
    use_specific_fields: bool = True,
    output_dir: str | Path = "./data",
    query_mode: str = "daily",
    data_step: str = "1h",
    measurement: Optional[str] = None,
    influx: InfluxConfig = InfluxConfig(),
) -> pd.DataFrame:
    """Retrieve data from InfluxDB between two dates and write to CSV.

    Returns the combined DataFrame for the requested range.
    """
    start_dt, end_dt = _validate_dates(start_date, end_date)

    if use_specific_fields:
        fields = _validate_fields(fields)
    else:
        if measurement is None:
            measurement = influx.bucket

    output_dir = Path(output_dir)
    output_filename = f"data_{influx.bucket}_{start_date}_to_{end_date}.csv"

    if query_mode.lower() == "hourly":
        date_range = pd.date_range(start=start_dt, end=end_dt, freq="H")
        period_name = "hour"
    else:
        date_range = pd.date_range(start=start_dt, end=end_dt, freq="D")
        period_name = "day"

    client = InfluxDBClient(url=influx.url, token=influx.token, org=influx.org)
    query_api = client.query_api()

    df_list: List[pd.DataFrame] = []
    for current_time in date_range:
        if query_mode.lower() == "hourly":
            start_time = current_time.strftime("%Y-%m-%dT%H:00:00Z")
            stop_time = (current_time + pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H:00:00Z")
        else:
            start_time = current_time.strftime("%Y-%m-%dT00:00:00Z")
            stop_time = (current_time + pd.Timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")

        df_period = process_period(
            query_api=query_api,
            bucket=influx.bucket,
            start_time=start_time,
            stop_time=stop_time,
            use_specific_fields=use_specific_fields,
            fields=fields,
            measurement=measurement,
            data_step=data_step,
            period_name=period_name,
        )
        if df_period is not None:
            df_list.append(df_period)

    if not df_list:
        return pd.DataFrame()

    df_final = pd.concat(df_list, ignore_index=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(output_dir / output_filename, index=False)
    return df_final


def process_multiple_intervals(
    date_intervals: Sequence[Dict[str, str]],
    fields: Optional[Sequence[str]] = None,
    use_specific_fields: bool = True,
    output_dir: str | Path = "./data",
    query_mode: str = "daily",
    data_step: str = "1h",
    measurement: Optional[str] = None,
    influx: InfluxConfig = InfluxConfig(),
) -> List[Dict[str, object]]:
    """Process multiple date intervals and return a list of results."""
    results: List[Dict[str, object]] = []
    for interval in date_intervals:
        start_date = interval["start_date"]
        end_date = interval["end_date"]
        description = interval.get("description", f"{start_date} to {end_date}")

        try:
            df_result = get_data(
                start_date=start_date,
                end_date=end_date,
                fields=fields,
                use_specific_fields=use_specific_fields,
                output_dir=output_dir,
                query_mode=query_mode,
                data_step=data_step,
                measurement=measurement,
                influx=influx,
            )
            results.append(
                {
                    "interval": interval,
                    "dataframe": df_result,
                    "success": True,
                    "error": None,
                    "rows": len(df_result),
                    "description": description,
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "interval": interval,
                    "dataframe": None,
                    "success": False,
                    "error": str(exc),
                    "rows": 0,
                    "description": description,
                }
            )
    return results


def _write_metadata(
    output_dir: Path,
    combined_filename: str,
    combined_filepath: Path,
    df_combined: pd.DataFrame,
    date_intervals: Sequence[Dict[str, str]],
    results: Sequence[Dict[str, object]],
    use_specific_fields: bool,
    query_mode: str,
    data_step: str,
    fields: Optional[Sequence[str]],
) -> Path:
    metadata = {
        "generation_info": {
            "created_at": datetime.now().isoformat(),
            "description": "Metadata for InfluxDB acquisition",
        },
        "configuration": {
            "output_dir": str(output_dir),
            "query_mode": query_mode,
            "data_step": data_step,
            "use_specific_fields": use_specific_fields,
            "fields": list(fields) if fields is not None else "ALL_FIELDS",
        },
        "intervals": [
            {
                "description": res["description"],
                "start_date": res["interval"]["start_date"],
                "end_date": res["interval"]["end_date"],
                "success": res["success"],
                "error": res["error"],
                "rows_count": res["rows"],
            }
            for res in results
        ],
        "combined_file": {
            "filename": combined_filename,
            "filepath": str(combined_filepath),
            "total_rows": len(df_combined),
            "columns": list(df_combined.columns),
        },
    }

    metadata_filename = combined_filename.replace("data_", "metadata_", 1).replace(".csv", ".json")
    metadata_filepath = output_dir / metadata_filename
    with metadata_filepath.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False)
    return metadata_filepath


def run_acquisition(
    date_intervals: Sequence[Dict[str, str]],
    fields: Optional[Sequence[str]] = None,
    use_specific_fields: bool = True,
    output_dir: str | Path = "./data",
    query_mode: str = "daily",
    data_step: str = "1h",
    measurement: Optional[str] = None,
    influx: InfluxConfig = InfluxConfig(),
) -> Dict[str, object]:
    """High-level helper: fetch multiple intervals, combine, and emit metadata."""
    output_dir = Path(output_dir)
    results = process_multiple_intervals(
        date_intervals=date_intervals,
        fields=fields,
        use_specific_fields=use_specific_fields,
        output_dir=output_dir,
        query_mode=query_mode,
        data_step=data_step,
        measurement=measurement,
        influx=influx,
    )

    successful_dfs = [r["dataframe"] for r in results if r["success"] and r["dataframe"] is not None and not r["dataframe"].empty]
    if not successful_dfs:
        return {"results": results, "combined": None, "metadata_file": None}

    df_combined = pd.concat(successful_dfs, ignore_index=True)
    df_combined = df_combined.sort_values("_time").reset_index(drop=True)

    all_start_dates = [interval["start_date"] for interval in date_intervals]
    all_end_dates = [interval["end_date"] for interval in date_intervals]
    combined_filename = f"data_{influx.bucket}_combined_{min(all_start_dates)}_to_{max(all_end_dates)}.csv"
    combined_filepath = output_dir / combined_filename

    output_dir.mkdir(parents=True, exist_ok=True)
    df_combined.to_csv(combined_filepath, index=False)

    metadata_file = _write_metadata(
        output_dir=output_dir,
        combined_filename=combined_filename,
        combined_filepath=combined_filepath,
        df_combined=df_combined,
        date_intervals=date_intervals,
        results=results,
        use_specific_fields=use_specific_fields,
        query_mode=query_mode,
        data_step=data_step,
        fields=fields,
    )

    return {
        "results": results,
        "combined": combined_filepath,
        "metadata_file": metadata_file,
        "rows": len(df_combined),
    }


if __name__ == "__main__":
    example_intervals = [
        {
            "start_date": "2025-11-16",
            "end_date": "2025-11-23",
            "description": "Example interval",
        }
    ]
    run_acquisition(
        date_intervals=example_intervals,
        fields=[
            "sharky_energy",
            "TT_ext",
            "RH_ext",
            "price",
            "DIS2_CHD_A_TT1",
            "DIS2_CHD_R_TT1",
            "Pchd_flow",
            "DIS_VRD_retour_position_opt",
            "DIS_CH_A_TT1",
            "DIS_CH_R_TT1",
            "DIS_BEL_energy_heating",
            "PAC1_energy",
            "PAC2_energy",
            "SKID_energy",
            "PAC1_power",
            "PAC2_power",
            "PAC1_cond_inlet",
            "PAC1_cond_outlet",
            "PAC1_modstatus",
            "PAC2_cond_inlet",
            "PAC2_cond_outlet",
            "PAC2_modstatus",
            "PAC1_user_pump",
            "PAC2_user_pump",
            "PAC1_domestic_pump",
            "PAC2_domestic_pump",
            "PAC1_general_alarm2",
            "PAC2_general_alarm2",
        ],
        use_specific_fields=True,
        output_dir="../data",
        query_mode="daily",
        data_step="1m",
    )
