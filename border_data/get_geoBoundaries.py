import csv
import sys
import os
import glob
import urllib.request
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
        path_list = [props['shapeGroup'].replace(' ','-'), props['shapeName'].replace(' ','-')]
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
        path_list = [props['shapeGroup'].replace(' ','-'), props['shapeName'].replace(' ','-')]
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


def download_geoboundaries(iso3, outdir):
    """Query the geoBoundaries API for the given ISO3 code and download all
    GeoJSON files into outdir.

    Args:
        iso3 (str): three-letter country code
        outdir (str): directory to download GeoJSON files into

    Returns:
        list of str: paths to the downloaded GeoJSON files
    """
    api_url = f'https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ALL/'
    print(f'Querying {api_url}')
    with urllib.request.urlopen(api_url) as resp:
        meta = json.load(resp)

    os.makedirs(outdir, exist_ok=True)

    downloaded = []
    for entry in meta:
        url = entry.get('gjDownloadURL')
        if not url:
            continue
        filename = os.path.basename(url)
        dest = os.path.join(outdir, filename)
        print(f'Downloading {url} -> {dest}')
        urllib.request.urlretrieve(url, dest)
        downloaded.append(dest)

    return downloaded


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python get_geoBoundaries.py XXX')
        sys.exit(1)
    iso3 = sys.argv[1]
    outdir = iso3

    download_geoboundaries(iso3, outdir)

    # 对下载目录内所有 geojson 文件执行原有的 CSV 生成逻辑
    geojson_files = sorted(
        glob.glob(os.path.join(outdir, '*.geojson')) +
        glob.glob(os.path.join(outdir, '*.json'))
    )
    if not geojson_files:
        print(f'No GeoJSON files found in {outdir}')
        sys.exit(1)

    for path in geojson_files:
        items = read_geojson(path)
        if not items:
            print(f'No geometries loaded from {path}, skipping')
            continue
        name_ISO = items[0][0]['shapeGroup']
        shape_type = items[0][0]['shapeType']
        print(f'Loaded {len(items)} geometries from {path}')
        outpath = os.path.join(outdir, f'{name_ISO}_{shape_type}_boundaries_wgs.csv')
        export_boundaries_csv(items, outpath)

