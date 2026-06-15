import json
import os
import glob

PARISHES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parishes")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macau_parishes.json")


def merge_geojson():
    merged = {"type": "FeatureCollection", "features": []}

    for path in sorted(glob.glob(os.path.join(PARISHES_DIR, "*.json"))):
        name = os.path.splitext(os.path.basename(path))[0]
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for feature in data.get("features", []):
            feature.setdefault("properties", {})
            feature["properties"].setdefault("parish", name)
            merged["features"].append(feature)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)

    print(f"Merged {len(merged['features'])} features into {OUTPUT_FILE}")


if __name__ == "__main__":
    merge_geojson()
