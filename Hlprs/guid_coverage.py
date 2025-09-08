import xml.etree.ElementTree as ET
import csv
from pathlib import Path

working_dir = Path(r"c:\Users\THOMPSON\Downloads\EHX\Working")
out_csv = working_dir / "guid_coverage.csv"
files = sorted(working_dir.glob("*.EHX"))

rows = []
for f in files:
    try:
        tree = ET.parse(str(f))
        root = tree.getroot()
    except Exception as e:
        rows.append({"file": f.name, "LevelGuid": "PARSE_ERROR", "BundleGuid": "PARSE_ERROR", "PanelGuid": "PARSE_ERROR", "BoardGuid": "PARSE_ERROR", "SubAssemblyGuid": "PARSE_ERROR"})
        continue
    def has(tag):
        return 1 if root.findall(f".//{tag}") else 0
    row = {
        "file": f.name,
        "LevelGuid": has("LevelGuid"),
        "BundleGuid": has("BundleGuid"),
        "PanelGuid": has("PanelGuid"),
        "BoardGuid": has("BoardGuid"),
        "SubAssemblyGuid": has("SubAssemblyGuid"),
    }
    rows.append(row)

with open(out_csv, "w", newline="", encoding="utf-8") as csvf:
    writer = csv.DictWriter(csvf, fieldnames=["file","LevelGuid","BundleGuid","PanelGuid","BoardGuid","SubAssemblyGuid"]) 
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {out_csv}")
# Print a summary count
summary = {"LevelGuid":0,"BundleGuid":0,"PanelGuid":0,"BoardGuid":0,"SubAssemblyGuid":0}
for r in rows:
    for k in summary.keys():
        if isinstance(r[k], int) and r[k] == 1:
            summary[k] += 1

print("GUID presence summary (files containing element):")
for k,v in summary.items():
    print(f"  {k}: {v} / {len(rows)}")
