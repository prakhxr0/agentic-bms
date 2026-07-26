import json

b = json.load(open("summer_baseline_1d_metrics.json"))
a = json.load(open("phase6_ai_1d_metrics.json"))

print("BASELINE: avg_pmv={:.3f} comfort={}% total_kwh={}".format(b["avg_pmv"], b["pmv_comfort_pct"], b["total_kwh"]))
print("AI:      avg_pmv={:.3f} comfort={}% total_kwh={}".format(a["avg_pmv"], a["pmv_comfort_pct"], a["total_kwh"]))
print()
print("Zone comparison:")
for z in sorted(b.get("zones", {}).keys()):
    bz = b["zones"][z]
    az = a["zones"][z]
    diff_pmv = az["avg_pmv"] - bz["avg_pmv"]
    diff_comfort = az["comfort_pct"] - bz["comfort_pct"]
    print("  {}: baseline PMV={:.3f} comfort={}% -> AI PMV={:.3f} comfort={}% (delta PMV={:.3f})".format(
        z, bz["avg_pmv"], bz["comfort_pct"], az["avg_pmv"], az["comfort_pct"], diff_pmv))
