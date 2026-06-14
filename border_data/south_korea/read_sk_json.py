import csv
import sys
import os
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union
from shapely import STRtree
import pandas as pd
from tqdm import tqdm
import json
from xyconvert import gcj2wgs, wgs2gcj
import numpy as np


def read_geojson(filepath):
    """Read a GeoJSON file and return a list of (properties, shapely geometry).

    Args:
        filepath (str): path to the .json/.geojson file

    Returns:
        list of tuples: [(properties_dict, shapely.geometry), ...]
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    items = []
    # support FeatureCollection or a plain Feature list
    features = []
    if isinstance(data, dict) and data.get('type') == 'FeatureCollection':
        features = data.get('features', [])
    elif isinstance(data, dict) and data.get('type') == 'Feature':
        features = [data]
    elif isinstance(data, list):
        features = data
    else:
        raise ValueError('Unsupported GeoJSON structure')

    for feat in features:
        props = feat.get('properties', {}) if isinstance(feat, dict) else {}
        geom = feat.get('geometry') if isinstance(feat, dict) else None
        if not geom:
            continue
        gtype = geom.get('type')
        coords = geom.get('coordinates')
        try:
            if gtype == 'Polygon':
                items.append((props, Polygon(coords[0])))
            elif gtype == 'MultiPolygon':
                polys = [Polygon(poly[0]) for poly in coords]
                items.append((props, MultiPolygon(polys)))
            else:
                # skip unsupported geometry types for now
                continue
        except Exception:
            # skip invalid geometries
            continue

    return items


def export_boundaries_csv(items, outpath):
    """Export boundary info to CSV with columns:
    id,pid,deep,name,ext_path,geo,polygon
    """
    rows = []
    for props, geom in items:
        path_list = ['韩国', props['name']]
        path_list = [p for p in path_list if p and p != 'null']
        name = path_list[-1]
        ext_path = ' '.join(path_list)
        # polygon: one polygon as "lon lat,lon lat,..."; multiple polygons separated by ;
        poly_parts = []
        if geom.geom_type == 'Polygon':
            coords = [(c[0], c[1]) for c in geom.exterior.coords]
            poly_parts.append(','.join(f"{lon} {lat}" for lon, lat in coords))
        elif geom.geom_type == 'MultiPolygon':
            for p in geom.geoms:
                coords = [(c[0], c[1]) for c in p.exterior.coords]
                poly_parts.append(','.join(f"{lon} {lat}" for lon, lat in coords))
        polygon = ';'.join(poly_parts)
        rows.append({'id': -1, 'pid': -1, 'deep': 2, 'name': name, 'ext_path': ext_path, 'geo': '', 'polygon': polygon})

    # write CSV
    with open(outpath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'pid', 'deep', 'name', 'ext_path', 'geo', 'polygon'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f'Exported {len(rows)} rows to {outpath}')


def convert_to_gcj_and_export(items, outpath_gcj):
    """Convert WGS coordinates to GCJ and export to CSV"""
    rows = []
    for props, geom in items:
        path_list = ['韩国', props['name']]
        path_list = [p for p in path_list if p and p != 'null']
        name = path_list[-1]
        ext_path = ' '.join(path_list)
        # polygon: convert to GCJ and format as "lon lat,lon lat,..."; multiple polygons separated by ;
        poly_parts = []
        if geom.geom_type == 'Polygon':
            coords = [(c[0], c[1]) for c in geom.exterior.coords]
            coords_array = np.array(coords)
            gcj_coords = wgs2gcj(coords_array)
            poly_parts.append(','.join(f"{lon} {lat}" for lon, lat in gcj_coords))
        elif geom.geom_type == 'MultiPolygon':
            for p in geom.geoms:
                coords = [(c[0], c[1]) for c in p.exterior.coords]
                coords_array = np.array(coords)
                gcj_coords = wgs2gcj(coords_array)
                poly_parts.append(','.join(f"{lon} {lat}" for lon, lat in gcj_coords))
        polygon = ';'.join(poly_parts)
        rows.append({'id': -1, 'pid': -1, 'deep': 2, 'name': name, 'ext_path': ext_path, 'geo': '', 'polygon': polygon})

    # write CSV
    with open(outpath_gcj, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'pid', 'deep', 'name', 'ext_path', 'geo', 'polygon'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f'Exported {len(rows)} rows to {outpath_gcj}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python read_jp_json.py path/to/file.geojson')
        sys.exit(1)
    path = sys.argv[1]
    items = read_geojson(path)
    print(f'Loaded {len(items)} geometries from {path}')
    export_boundaries_csv(items, 'sk_boundaries_wgs.csv')
    convert_to_gcj_and_export(items, 'sk_boundaries_gcj.csv')

    # 列出可选项，让用户挑选一个进行可视化
    for i, (props, geom) in enumerate(items):
        name = props['name_eng']
        print(f"[{i}] {name}")

    # 读取用户选择的索引（命令行参数优先）
    idx = None
    if len(sys.argv) >= 3:
        try:
            idx = int(sys.argv[2])
        except Exception:
            idx = None

    if idx is None:
        try:
            idx = int(input('请选择要可视化的索引编号: '))
        except Exception:
            print('无效输入，退出')
            sys.exit(1)

    if idx < 0 or idx >= len(items):
        print('索引超出范围')
        sys.exit(1)

    props, geom = items[idx]
    print(f'Visualizing index {idx}, properties: {props}')

    # 绘制几何形状（支持 Polygon / MultiPolygon）
    fig, ax = plt.subplots()
    patches = []
    if geom.geom_type == 'Polygon':
        x, y = geom.exterior.xy
        ax.fill(x, y, alpha=0.6, edgecolor='k')
    elif geom.geom_type == 'MultiPolygon':
        for poly in geom.geoms:
            x, y = poly.exterior.xy
            # ax.fill(x, y, alpha=0.6, edgecolor='k')
            ax.plot(x, y, color='k')
    else:
        print('不支持的几何类型，无法可视化')
        sys.exit(1)

    ax.set_aspect('equal')
    plt.show()

