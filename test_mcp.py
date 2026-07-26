"""Quick test of the MCP server."""
import subprocess
import json

proc = subprocess.Popen(
    ["python", "mcp_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    cwd=r"C:\Users\prakh\Downloads\proj\eco-loop-building-agent",
)

# Read the first (initialized) message
first = proc.stdout.readline()
print(f"Initialized: {first.strip()[:100]}")

# Test 1: tools/list
proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}) + "\n")
proc.stdin.flush()
resp = proc.stdout.readline()
data = json.loads(resp)
print(f"tools/list response keys: {list(data.keys())}")
if "result" in data:
    tools = data["result"]["tools"]
    print(f"Tools: {len(tools)} defined")
    for t in tools:
        print(f"  - {t['name']}: {t['description'][:60]}")
else:
    print(f"Error/other: {json.dumps(data, indent=2)[:300]}")

# Test 2: tools/call for compute_setpoints
proc.stdin.write(json.dumps({
    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": {
        "name": "compute_setpoints",
        "arguments": {
            "zone_temp": 21.0,
            "pmv": -1.8,
            "outdoor_temp": 8.2,
            "future_temps": [7.4, 6.6, 5.8],
            "current_heating_sp": 21.0,
            "current_cooling_sp": 24.0
        }
    }
}) + "\n")
proc.stdin.flush()
resp = proc.stdout.readline()
data = json.loads(resp)
if "result" in data:
    text = data["result"]["content"][0]["text"]
    print(f"\nSetpoints: {text}")
else:
    print(f"\nError: {json.dumps(data, indent=2)[:300]}")

proc.terminate()
print("\nDone!")
