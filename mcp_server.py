"""
MCP (Model Context Protocol) Server for the Eco-Loop Building Agent.
Exposes simulation tools over stdio for any MCP-compatible host.

Usage: python mcp_server.py
Communicates via JSON-RPC 2.0 over stdin/stdout.
"""

import json
import sys
import os
import csv
from datetime import datetime

TOOL_DEFINITIONS = [
    {
        "name": "get_zone_comfort",
        "description": "Get current zone temperature and PMV for a given zone",
        "inputSchema": {
            "type": "object",
            "properties": {
                "zone_id": {"type": "string", "description": "Zone name (e.g. SPACE1-1)"}
            },
            "required": ["zone_id"]
        }
    },
    {
        "name": "get_energy_metrics",
        "description": "Get current building energy consumption (instantaneous kW)",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_weather_forecast",
        "description": "Get current outdoor temperature and future forecast from EPW weather file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hours_ahead": {"type": "integer", "description": "Hours to look ahead (default 6)"}
            },
            "required": []
        }
    },
    {
        "name": "check_simulation_status",
        "description": "Check the EnergyPlus simulation log for errors or warnings",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "compute_setpoints",
        "description": "Recommend heating/cooling setpoints given current conditions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "zone_temp": {"type": "number", "description": "Current zone temperature (°C)"},
                "pmv": {"type": "number", "description": "Current Predicted Mean Vote"},
                "outdoor_temp": {"type": "number", "description": "Current outdoor temperature (°C)"},
                "future_temps": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Forecast outdoor temperatures for next hours"
                },
                "current_heating_sp": {"type": "number", "description": "Current heating setpoint"},
                "current_cooling_sp": {"type": "number", "description": "Current cooling setpoint"}
            },
            "required": ["zone_temp", "pmv", "outdoor_temp"]
        }
    },
]

# EPW data cache
_epw_cache = []

def _load_epw(epw_path=None):
    global _epw_cache
    if _epw_cache:
        return _epw_cache
    if epw_path is None:
        base = os.path.dirname(os.path.abspath(__file__))
        epw_path = os.path.join(base, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    if not os.path.exists(epw_path):
        return []
    with open(epw_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    for line in lines[8:]:
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(',')
        if len(parts) >= 7:
            try:
                year = int(parts[0])
                month = int(parts[1])
                day = int(parts[2])
                hour = int(parts[3]) - 1
                db = float(parts[6])
                _epw_cache.append((datetime(year, month, day, hour), db))
            except (ValueError, IndexError):
                continue
    return _epw_cache

def _read_state_file():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state_history.jsonl")
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        lines = [l.strip() for l in f if l.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])

def _handle_tool_call(name: str, args: dict) -> dict:
    if name == "get_zone_comfort":
        state = _read_state_file()
        zone = state.get("zone", {}) if state else {"error": "No simulation state available"}
        return zone

    elif name == "get_energy_metrics":
        state = _read_state_file()
        energy = state.get("energy", {}) if state else {"error": "No simulation state available"}
        return energy

    elif name == "get_weather_forecast":
        hours = args.get("hours_ahead", 6)
        data = _load_epw()
        if not data:
            return {"error": "EPW file not found"}
        now = datetime.now()
        nearest = min(data, key=lambda x: abs((x[0] - now).total_seconds()))
        idx = data.index(nearest)
        future = [float(data[i][1]) for i in range(idx + 1, min(idx + 1 + hours, len(data)))]
        return {"current_temp": float(nearest[1]), "future_temps": future}

    elif name == "check_simulation_status":
        base = os.path.dirname(os.path.abspath(__file__))
        for candidate in ["outputs/phase3_ems/eplusout.err",
                          "outputs/override/eplusout.err"]:
            path = os.path.join(base, candidate)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    errors = [l.strip() for l in f if any(w in l for w in ["FATAL", "SEVERE"])]
                return {"error_count": len(errors), "recent_errors": errors[-3:]}
        return {"error_count": 0, "recent_errors": []}

    elif name == "compute_setpoints":
        zone_temp = args.get("zone_temp", 21.0)
        pmv = args.get("pmv", 0.0)
        outdoor_temp = args.get("outdoor_temp", 10.0)
        future_temps = args.get("future_temps", [])
        current_hsp = args.get("current_heating_sp", 21.0)
        current_csp = args.get("current_cooling_sp", 24.0)

        suggested_hsp = current_hsp
        suggested_csp = current_csp

        if pmv < -0.5:
            suggested_hsp = min(24.0, current_hsp + 0.5)
        elif pmv > 0.5:
            suggested_csp = max(22.0, current_csp - 0.5)

        if future_temps and min(future_temps) < outdoor_temp - 5:
            suggested_hsp = min(24.0, suggested_hsp + 0.5)

        if suggested_csp < suggested_hsp + 2.0:
            suggested_csp = suggested_hsp + 2.0

        suggested_hsp = max(18.0, min(24.0, suggested_hsp))
        suggested_csp = max(22.0, min(28.0, suggested_csp))

        return {
            "heating_sp": round(suggested_hsp, 1),
            "cooling_sp": round(suggested_csp, 1),
            "reasoning": f"PMV={pmv:.2f}, outdoor={outdoor_temp}°C, "
                         f"adjusted from heat={current_hsp}/cool={current_csp}"
        }

    return {"error": f"Unknown tool: {name}"}

def _send(msg: dict):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

def main():
    _send({"jsonrpc": "2.0", "method": "initialized"})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "tools/list":
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOL_DEFINITIONS}
            })

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            result = _handle_tool_call(tool_name, tool_args)
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            })

        elif method == "initialize":
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "eco-loop-building-agent", "version": "1.0.0"}
                }
            })

        else:
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            })

if __name__ == "__main__":
    main()
