import csv
import os
from datetime import datetime, timedelta

# Global EMS context (set by plugin)
_ems_state = None
_exchange = None
_handles = {}

def set_ems_context(state, exchange, handles=None):
    global _ems_state, _exchange, _handles
    _ems_state = state
    _exchange = exchange
    if handles:
        _handles.update(handles)

def get_zone_state(zone_id="SPACE1-1"):
    if _exchange is None or not _handles:
        return {"error": "EMS not initialized"}
    h_temp = _handles.get(f"{zone_id}_temp")
    h_pmv = _handles.get(f"{zone_id}_pmv")
    if h_temp in (-1, None) or h_pmv in (-1, None):
        return {"zone": zone_id, "error": "sensor handles not available"}
    try:
        temp = _exchange.get_variable_value(_ems_state, h_temp)
        pmv = _exchange.get_variable_value(_ems_state, h_pmv)
        return {"zone": zone_id, "temperature_c": temp, "pmv": pmv}
    except Exception as e:
        return {"zone": zone_id, "error": str(e)}

def get_energy_metrics():
    if _exchange is None or not _handles:
        return {"cumulative_j": 0.0}
    h_bldg = _handles.get("Electricity:Building")
    h_hvac = _handles.get("Electricity:HVAC")
    print(f"[DEBUG] get_energy_metrics: handles bldg={h_bldg} hvac={h_hvac}", flush=True)
    if h_bldg in (-1, None) or h_hvac in (-1, None):
        return {"cumulative_j": 0.0}
    try:
        bldg_val = _exchange.get_meter_value(_ems_state, h_bldg)
        hvac_val = _exchange.get_meter_value(_ems_state, h_hvac)
        total_w = bldg_val + hvac_val
        print(f"[DEBUG] get_energy_metrics: bldg={bldg_val} hvac={hvac_val} total_W={total_w}", flush=True)
        return {"total_w": total_w, "building_w": bldg_val, "hvac_w": hvac_val}
    except Exception as e:
        print(f"[DEBUG] get_energy_metrics exception: {e}", flush=True)
        return {"error": str(e)}

# Simple EPW loader without pandas
_epw_data = []  # list of (dt, db_temp)

def load_epw_forecast(epw_path):
    global _epw_data
    if _epw_data:
        return _epw_data
    if not os.path.exists(epw_path):
        return []
    # EPW format: skip 8 header lines
    with open(epw_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    # Find the start of data: line after headers that starts with a year digit
    data_lines = []
    for line in lines[8:]:  # Skip 8 EPW header lines
        stripped = line.strip()
        if stripped:
            data_lines.append(stripped)
    if len(data_lines) < 1:
        return []
    for line in data_lines:
        parts = line.split(',')
        if len(parts) < 8:
            continue
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        hour = int(parts[3]) - 1  # Hour in range 1..24 => 0..23 for datetime
        db = float(parts[6])  # Dry bulb temperature (°C)
        try:
            dt = datetime(year, month, day, hour)
            _epw_data.append((dt, db))
        except:
            continue
    return _epw_data

def get_weather_lookahead(hours_ahead=6, epw_path=None):
    if epw_path is None:
        epw_path = os.environ.get("EPW_PATH")
    if epw_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        epw_path = os.path.join(base_dir, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    print(f"[DEBUG] get_weather_lookahead EPW path: {epw_path}  exists={os.path.exists(epw_path)}", flush=True)
    if not os.path.exists(epw_path):
        return {"error": f"EPW not found at {epw_path}", "future_temps": []}
    data = load_epw_forecast(epw_path)
    if not data:
        return {"error": "EPW load failed", "future_temps": []}
    now = datetime.now()
    nearest_idx = None
    min_diff = None
    # Find the EPW timestamp closest to now
    for i, (dt, _) in enumerate(data):
        diff = abs((dt - now).total_seconds())
        if min_diff is None or diff < min_diff:
            min_diff = diff
            nearest_idx = i
    if nearest_idx is None:
        return {"error": "no matching timestamp", "future_temps": []}
    current_temp = data[nearest_idx][1]
    start_idx = nearest_idx + 1
    end_idx = min(nearest_idx + hours_ahead + 1, len(data))
    future_temps = [float(data[i][1]) for i in range(start_idx, end_idx)]
    return {
        "current_temp": float(current_temp),
        "future_temps": future_temps
    }

def check_simulation_errors():
    err_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "baseline", "eplusout.err")
    if not os.path.exists(err_path):
        return {"new_errors": []}
    try:
        with open(err_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        errors = [l.strip() for l in lines if any(word in l for word in ["FATAL", "SEVERE"])]
        return {"new_errors": errors[-5:], "error_count": len(errors)}
    except Exception as e:
        return {"error": str(e), "new_errors": []}