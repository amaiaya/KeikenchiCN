import numpy as np
import pandas as pd
from xyconvert import gcj2wgs, wgs2gcj
from tqdm import tqdm


def parse_polygon(polygon_str):
    """解析为 (group_lengths, coords_list)，空值返回 None。"""
    if pd.isna(polygon_str) or str(polygon_str).strip() == "":
        return None
    group_lengths, coords = [], []
    for g in str(polygon_str).split(";"):
        pts = [p for p in g.split(",") if p.strip() != ""]
        group_lengths.append(len(pts))
        for p in pts:
            lng, lat = p.strip().split()
            coords.append((float(lng), float(lat)))
    return group_lengths, coords


input_path, output_path = "china_mainland_boundaries_gcj.csv", "china_mainland_boundaries_wgs.csv"
df = pd.read_csv(input_path)

# 1. 一次性解析所有行，记录每行结构
all_coords = []
row_meta = []  # 每行: (是否有效, group_lengths, 该行点数)
for s in tqdm(df["polygon"]):
    parsed = parse_polygon(s)
    if parsed is None or len(parsed[1]) == 0:
        row_meta.append((False, None, 0))
    else:
        group_lengths, coords = parsed
        row_meta.append((True, group_lengths, len(coords)))
        all_coords.extend(coords)

# 2. 整个文件只调用一次 gcj2wgs
big = np.array(all_coords, dtype=float)   # 约 300 万 × 2
wgs = gcj2wgs(big)

# 3. 按结构还原成字符串
results, idx = [], 0
orig = df["polygon"].tolist()
for i, (valid, group_lengths, n) in tqdm(enumerate(row_meta)):
    if not valid:
        results.append(orig[i])
        continue
    block = wgs[idx: idx + n]
    idx += n
    out_groups, k = [], 0
    for cnt in group_lengths:
        pts = [f"{block[k+j][0]:.6f} {block[k+j][1]:.6f}" for j in range(cnt)]
        k += cnt
        out_groups.append(",".join(pts))
    results.append(";".join(out_groups))

df["polygon"] = results
df.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"已保存到 {output_path}")
