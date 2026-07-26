import json

with open('state_history.jsonl') as f:
    lines = f.readlines()
print(f'Total state writes: {len(lines)}')

# Show last entry
last = json.loads(lines[-1])
z = last.get('zone', {})
e = last.get('energy', {})
w = last.get('weather', {})
d = last.get('decision', {})
r = last.get('reasoning', '')
print(f'Zone: temp={z.get("temperature_c"):.2f} PMV={z.get("pmv"):.2f}')
print(f'Energy: total_W={e.get("total_w",0):.1f}')
print(f'Decision: heating={d.get("heating_sp")} cooling={d.get("cooling_sp")}')
print(f'Reasoning: {r[:150]}')

# Show first few and last few decisions
decisions = []
for l in lines:
    entry = json.loads(l)
    d = entry.get('decision', {})
    z = entry.get('zone', {})
    r = entry.get('reasoning', '')
    decisions.append((d.get('heating_sp'), d.get('cooling_sp'), z.get('pmv'), r[:60] if r else ''))

print()
print('Decision sequence (first 8):')
for hs, cs, pmv, reason in decisions[:8]:
    print(f'  heat={hs} cool={cs} PMV={pmv:.3f} | {reason}')

print()
print('Decision sequence (last 8):')
for hs, cs, pmv, reason in decisions[-8:]:
    print(f'  heat={hs} cool={cs} PMV={pmv:.3f} | {reason}')
