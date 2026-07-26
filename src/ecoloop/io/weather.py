"""Weather helper using EPW file."""

import csv
import os
from datetime import datetime
from pathlib import Path

from src.ecoloop.config import EPW_PATH


_epw_cache = []


def load_epw(epw_path: Path = None) -> list[tuple[datetime, float]]:
    """Load EPW dry-bulb temperatures into cache."""
    global _epw_cache
    if _epw_cache:
        return _epw_cache

    path = Path(epw_path or EPW_PATH)
    if not path.exists():
        return []

    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
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


def get_weather_lookahead(hours_ahead: int = 6, epw_path: Path = None,
                          reference_time: datetime = None) -> dict:
    """Get current + future temperatures from EPW."""
    data = load_epw(epw_path)
    if not data:
        return {"error": "EPW not loaded", "future_temps": []}

    now = reference_time or datetime.now()

    # Find nearest timestamp
    nearest_idx = min(range(len(data)),
                      key=lambda i: abs((data[i][0] - now).total_seconds()))

    current_temp = data[nearest_idx][1]
    start = nearest_idx + 1
    end = min(start + hours_ahead, len(data))
    future_temps = [data[i][1] for i in range(start, end)]

    return {
        "current_temp": current_temp,
        "future_temps": future_temps,
    }


if __name__ == "__main__":
    # Quick test
    w = get_weather_lookahead(3, reference_time=datetime(2026, 7, 1, 12))
    print(w)