#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从国家名提取二级行政区边界 -> GeoJSON
依赖:
    pip install requests shapely pycountry
外部工具:
    cosmogony (已编译), 路径通过 --cosmogony 指定
    可选: osmium (本脚本未强依赖)
"""

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict

import requests

try:
    import pycountry
except ImportError:
    pycountry = None


GEOFABRIK_INDEX = "https://download.geofabrik.de/index-v1-nogeom.json"


# ----------------------------------------------------------------------
# 1. 根据国家名在 Geofabrik 找到下载链接
# ----------------------------------------------------------------------
def find_geofabrik_url(country_name: str):
    """
    在 Geofabrik 的索引中按名称模糊匹配国家，返回 .osm.pbf 的下载 URL。
    Geofabrik 提供一个 GeoJSON 索引，feature 的 properties 含 name / urls。
    """
    print(f"[*] 正在获取 Geofabrik 索引 ...")
    resp = requests.get(GEOFABRIK_INDEX, timeout=60)
    resp.raise_for_status()
    index = resp.json()

    # 收集候选 (name, iso, pbf_url)
    candidates = []
    for feat in index.get("features", []):
        props = feat.get("properties", {})
        name = props.get("name", "")
        urls = props.get("urls", {})
        pbf = urls.get("pbf")
        if not pbf:
            continue
        iso = props.get("iso3166-1:alpha2") or props.get("iso3166-2") or ""
        candidates.append((name, iso, pbf))

    q = country_name.strip().lower()

    # 先尝试用 pycountry 把中文/各种写法统一到英文名 + ISO 码
    aliases = {q}
    if pycountry:
        try:
            c = pycountry.countries.lookup(country_name)
            aliases.add(c.name.lower())
            if hasattr(c, "common_name"):
                aliases.add(c.common_name.lower())
            aliases.add(c.alpha_2.lower())
        except LookupError:
            pass

    # 精确匹配优先，其次包含匹配
    exact = [c for c in candidates if c[0].lower() in aliases]
    if exact:
        return _pick(exact, country_name)

    contains = [c for c in candidates
                if any(a in c[0].lower() or c[0].lower() in a for a in aliases)]
    if contains:
        return _pick(contains, country_name)

    raise ValueError(
        f"在 Geofabrik 中找不到 '{country_name}'。"
        f"请尝试用英文国家名（如 'Kazakhstan'）。"
    )


def _pick(candidates, query):
    """从多个候选里选一个，并打印供用户确认。"""
    # 选 name 最短的（通常是国家本身而非其子区域）
    candidates.sort(key=lambda c: len(c[0]))
    name, iso, url = candidates[0]
    print(f"[*] 匹配到: {name} ({iso})  ->  {url}")
    return url


# ----------------------------------------------------------------------
# 2. 下载 pbf
# ----------------------------------------------------------------------
def download(url: str, dest: str):
    print(f"[*] 下载 {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = done * 100 // total
                    print(f"\r    {done >> 20} / {total >> 20} MB ({pct}%)",
                          end="", flush=True)
        print()
    print(f"[*] 已保存到 {dest}")


# ----------------------------------------------------------------------
# 3. 运行 cosmogony
# ----------------------------------------------------------------------
def run_cosmogony(cosmogony_bin: str, pbf_path: str, out_jsonl_gz: str):
    cmd = [cosmogony_bin, "-i", pbf_path, "-o", out_jsonl_gz]
    print(f"[*] 运行: {' '.join(cmd)}")
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise RuntimeError("cosmogony 运行失败")
    print(f"[*] cosmogony 输出: {out_jsonl_gz}")


# ----------------------------------------------------------------------
# 4. 解析 jsonl(.gz) 中的 zones
# ----------------------------------------------------------------------
def iter_zones(jsonl_path: str):
    opener = gzip.open if jsonl_path.endswith(".gz") else open
    with opener(jsonl_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            # cosmogony 每行可能是 {"zone": {...}} 也可能直接是 zone
            yield obj.get("zone", obj)


def load_zones(jsonl_path: str):
    """读入所有 zone，建立 id -> zone 的索引。"""
    zones = {}
    for z in iter_zones(jsonl_path):
        zid = z.get("id")
        if zid is not None:
            zones[zid] = z
    print(f"[*] 共读取 {len(zones)} 个区域")
    return zones


def inspect(zones):
    """打印各 admin_level / zone_type 的统计，帮助用户决定提取哪一级。"""
    by_level = Counter()
    by_type = Counter()
    for z in zones.values():
        by_level[z.get("admin_level")] += 1
        by_type[z.get("zone_type")] += 1
    print("\n=== admin_level 统计 ===")
    for k in sorted(by_level, key=lambda x: (x is None, x)):
        print(f"  admin_level={k}: {by_level[k]}")
    print("=== zone_type 统计 ===")
    for k, v in by_type.most_common():
        print(f"  {k}: {v}")
    print()


# ----------------------------------------------------------------------
# 5. 提取二级行政区 + 一级行政区名称
# ----------------------------------------------------------------------
def get_name(z):
    """优先用 name，其次 labels 里的某个语言。"""
    if z.get("name"):
        return z["name"]
    labels = z.get("labels") or {}
    for v in labels.values():
        if v:
            return v
    return None


def find_ancestor_by_level(zones, zone, target_level):
    """沿 parent 链向上找到指定 admin_level 的祖先。"""
    seen = set()
    cur = zone
    while cur is not None:
        cid = cur.get("id")
        if cid in seen:
            break
        seen.add(cid)
        if cur.get("admin_level") == target_level and cur is not zone:
            return cur
        parent_id = cur.get("parent")
        cur = zones.get(parent_id)
    return None


def build_geojson(zones, level2, level1):
    """
    提取 admin_level == level2 的区域作为二级行政区，
    并向上查找 admin_level == level1 的祖先作为一级行政区。
    """
    features = []
    skipped_no_geom = 0
    for z in zones.values():
        if z.get("admin_level") != level2:
            continue
        geom = z.get("geometry")
        if not geom:
            skipped_no_geom += 1
            continue

        l2_name = get_name(z)
        ancestor = find_ancestor_by_level(zones, z, level1)
        l1_name = get_name(ancestor) if ancestor else None

        props = {
            "admin2_name": l2_name,
            "admin1_name": l1_name,
            "admin_level": z.get("admin_level"),
            "zone_type": z.get("zone_type"),
            "osm_id": z.get("osm_id"),
            "cosmogony_id": z.get("id"),
        }
        # 把多语言名也带上（可选）
        if z.get("labels"):
            props["labels"] = z["labels"]

        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": geom,
        })

    if skipped_no_geom:
        print(f"[!] {skipped_no_geom} 个区域因缺少 geometry 被跳过")
    print(f"[*] 提取到 {len(features)} 个二级行政区")
    return {"type": "FeatureCollection", "features": features}


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="从国家名提取二级行政区边界为 GeoJSON")
    ap.add_argument("country", help="国家名 (建议英文, 如 Kazakhstan)")
    ap.add_argument("-o", "--output", default=None,
                    help="输出 GeoJSON 路径 (默认 <country>_admin2.geojson)")
    ap.add_argument("--cosmogony", default="cosmogony",
                    help="cosmogony 可执行文件路径")
    ap.add_argument("--level2", type=int, default=6,
                    help="二级行政区对应的 admin_level")
    ap.add_argument("--level1", type=int, default=4,
                    help="一级行政区对应的 admin_level")
    ap.add_argument("--inspect", action="store_true",
                    help="只打印各层级统计, 不输出 GeoJSON")
    ap.add_argument("--keep-pbf", default=None,
                    help="若提供路径则直接使用该 pbf, 不下载")
    args = ap.parse_args()

    output = args.output or f"{args.country.replace(' ', '_')}_admin2.geojson"

    # 用临时目录存放中间文件，结束后整体删除
    workdir = tempfile.mkdtemp(prefix="cosmogony_", dir="/mnt/d/Temp")
    print(f"[*] 工作目录: {workdir}")

    try:
        # 1) 准备 pbf
        if args.keep_pbf:
            pbf_path = args.keep_pbf
        else:
            url = find_geofabrik_url(args.country)
            pbf_path = os.path.join(workdir, "country.osm.pbf")
            download(url, pbf_path)

        # 2) cosmogony
        jsonl_gz = os.path.join(workdir, "cosmogony.jsonl.gz")
        run_cosmogony(args.cosmogony, pbf_path, jsonl_gz)

        # 3) 解析
        zones = load_zones(jsonl_gz)

        if args.inspect:
            inspect(zones)
            return

        inspect(zones)  # 也顺便打印一下供核对

        # 4) 构建 geojson
        fc = build_geojson(zones, args.level2, args.level1)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False)
        print(f"[✓] 已生成: {output}")

    finally:
        # 5) 清理中间文件
        shutil.rmtree(workdir, ignore_errors=True)
        print(f"[*] 已清理临时目录")


if __name__ == "__main__":
    main()
