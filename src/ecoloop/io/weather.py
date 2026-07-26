"""Weather helper using EPW file (simulation-clock aware)."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from ecoloop.config import EPW_PATH

_epw_cache: list[tuple[datetime, float]] = []


def load_epw(epw_path: Path | None = None) -> list[tuple[datetime, float]]:
    """Load EPW dry-bulb temperatures into cache."""
    global _epw_cache
    if _epw_cache:
        return _epw_cache

    path = Path(epw_path or EPW_PATH)
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        # Skip 8 header rows
        for _ in range(8):
            next(reader, None)
        for row in reader:
            if len(row) < 8:
                continue
            try:
                year = int(row[0])
                month = int(row[1])
                day = int(row[2])
                hour = int(row[3]) - 1  # EPW hour 1-24 -> 0-23
                db = float(row[6])
                dt = datetime(year, month, day, hour)
                _epw_cache.append((dt, db))
            except (ValueError, IndexError):
                continue
    return _epw_cache


def get_weather_lookahead(
    hours_ahead: int = 6,
    epw_path: Path | None = None,
    reference_time: datetime | None = None,
) -> dict:
    """Get current + future temperatures from EPW at the simulation clock."""
    data = load_epw(epw_path)
    if not data:
        return {"error": "EPW not loaded", "future_temps": [], "current_temp": None}

    # Prefer simulation clock; never silently use wall-clock "now" for control
    if reference_time is None:
        return {
            "error": "no simulation reference_time",
            "future_temps": [],
            "current_temp": None,
        }

    # Match on month/day/hour (EPW years often differ from sim year)
    target_key = (reference_time.month, reference_time.day, reference_time.hour)
    nearest_idx = 0
    best = None
    for i, (dt, _temp) in enumerate(data):
        key = (dt.month, dt.day, dt.hour)
        # absolute hour-of-year distance
        dist = abs(
            (key[0] - target_key[0]) * 744
            + (key[1] - target_key[1]) * 24
            + (key[2] - target_key[2])
        )
        if best is None or dist < best:
            best = dist
            nearest_idx = i
            if dist == 0:
                break

    current_temp = data[nearest_idx][1]
    start = nearest_idx + 1
    end = min(start + hours_ahead, len(data))
    future_temps = [data[i][1] for i in range(start, end)]

    return {
        "current_temp": current_temp,
        "future_temps": future_temps,
        "reference": reference_time.isoformat(timespec="hours"),
        "matched_epw": data[nearest_idx][0].isoformat(timespec="hours"),
    }


if __name__ == "__main__":
    w = get_weather_lookahead(3, reference_time=datetime(2009, 7, 1, 12))
    print(w)
