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
import numpy as np

csv.field_size_limit(sys.maxsize)

def mercator_forward(lat):
    """
    纬度 -> 墨卡托尺度
    输入输出单位都用“度”，方便 Matplotlib 显示
    """
    lat = np.asarray(lat)
    lat = np.clip(lat, -85, 85)  # 避免接近极点发散
    return np.rad2deg(np.log(np.tan(np.pi / 4 + np.deg2rad(lat) / 2)))

def mercator_inverse(y):
    """
    墨卡托尺度 -> 纬度
    """
    return np.rad2deg(2 * np.arctan(np.exp(np.deg2rad(y))) - np.pi / 2)

def parse_polygon(polygon_str):
    """解析polygon字符串为区块列表，每个区块是一个坐标列表"""
    if not polygon_str or polygon_str.strip() == '':
        return []
    blocks = []
    for part in polygon_str.split(';'):
        part = part.strip()
        if not part:
            continue
        coords = []
        for point in part.split(','):
            point = point.strip()
            if point:
                try:
                    lon, lat = point.split()
                    coords.append((float(lon), float(lat)))
                except:
                    continue
        if len(coords) >= 3:
            blocks.append(coords)
    return blocks

def make_valid_polygon(coords):
    """从坐标构造Polygon，并尝试修复无效几何"""
    poly = Polygon(coords)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly

def geom_to_mpl_patches(geom, **kwargs):
    """把shapely几何转成matplotlib填充patch列表"""
    patches = []
    if geom.is_empty:
        return patches
    if geom.geom_type == 'Polygon':
        polys = [geom]
    elif geom.geom_type == 'MultiPolygon':
        polys = list(geom.geoms)
    else:
        return patches
    for poly in polys:
        ext = list(poly.exterior.coords)
        patches.append(MplPolygon(ext, closed=True, **kwargs))
    return patches

def plot_geom_boundary(ax, geom, color='black', lw=0.8):
    """绘制几何对象的边界"""
    if geom.is_empty:
        return
    if geom.geom_type == 'Polygon':
        polys = [geom]
    elif geom.geom_type == 'MultiPolygon':
        polys = list(geom.geoms)
    else:
        return
    for poly in polys:
        x, y = poly.exterior.xy
        ax.plot(x, y, color=color, linewidth=lw)
        for interior in poly.interiors:
            x, y = interior.xy
            ax.plot(x, y, color=color, linewidth=lw)


def read_base_border_csv(csv_file):
    print("读取行政区...")
    admin_regions = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['deep'] != '2':
                continue
            blocks = parse_polygon(row['polygon'])
            if not blocks:
                continue
            polys = []
            for block in blocks:
                try:
                    p = make_valid_polygon(block)
                    if not p.is_empty:
                        polys.append(p)
                except Exception:
                    continue
            if not polys:
                continue
            merged = unary_union(polys)
            admin_regions.append({'geom': merged, 'row': row})

    if 'gcj' in csv_file:
        base_type = 'GCJ'
    elif 'wgs' in csv_file:
         base_type = 'WGS'
    else:
        raise ValueError
    print(f"加载了 {len(admin_regions)} 个行政区，坐标系{base_type}")

    return [admin_regions, base_type]


def read_base_border_csvs(csv_files):
    print("读取行政区...")
    admin_regions = []
    for csv_file in csv_files:
        print("读取文件:", csv_file)
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['deep'] != '2':
                    continue
                blocks = parse_polygon(row['polygon'])
                if not blocks:
                    continue
                polys = []
                for block in blocks:
                    try:
                        p = make_valid_polygon(block)
                        if not p.is_empty:
                            polys.append(p)
                    except Exception:
                        continue
                if not polys:
                    continue
                merged = unary_union(polys)
                admin_regions.append({'geom': merged, 'row': row})

    if 'gcj' in csv_files[0]:
        base_type = 'GCJ'
    elif 'wgs' in csv_files[0]:
         base_type = 'WGS'
    else:
        raise ValueError
    print(f"加载了 {len(admin_regions)} 个行政区，坐标系{base_type}")

    return [admin_regions, base_type]


def read_points_csv(csv_file, sampling=-1):
    points_df = pd.read_csv(csv_file) # 'fwss_reader/loca_20260613_gcj.csv'
    n_points = len(points_df)
    if sampling > 0:
        points_df = points_df.iloc[::sampling]
    n_points_sampling = len(points_df)
    if 'gcj' in csv_file:
        points_type = 'GCJ'
    elif 'wgs' in csv_file:
        points_type = 'WGS'
    else:
        raise ValueError
    print(f"加载了 {n_points} 个点，抽样为 {n_points_sampling} 个点，坐标系{points_type}")
    
    return [points_df, points_type]


def _match_target(ext_path, target):
    """target按空格分割后，每个部分须出现在ext_path的空格分割列表中"""
    parts = target.split()
    ext_parts = ext_path.split()
    return all(part in ext_parts for part in parts)


def visualize_with_points(admin_regions, points_df, show_points=True, sampling=100,
                          point_size=0.5, prefix_name='县级可视化', target_names=None):
    base_file_names = [prefix_name, f'base-{admin_regions[1]}', f'path-{points_df[1]}']
    points_df = points_df[0]
    admin_regions_list = admin_regions[0]
    lon_col, lat_col = points_df.columns[0], points_df.columns[1]

    if target_names is None:
        # 全局概览模式
        out_csv_name = '_'.join(['经过县区名'] + base_file_names[1:]) + '.csv'
        file_name = '_'.join(base_file_names)
        if show_points:
            file_name += '_轨迹点'
        file_name += '.png'

        points_df = points_df[::sampling]
        lons = points_df[lon_col].astype(float).tolist()
        lats = points_df[lat_col].astype(float).tolist()

        geoms = [r['geom'] for r in admin_regions_list]
        tree = STRtree(geoms)
        has_point = set()
        print("筛选点...")
        for lo, la in tqdm(zip(lons, lats), total=len(lons)):
            pt = Point(lo, la)
            for idx in tree.query(pt):
                if geoms[idx].contains(pt):
                    has_point.add(idx)

        print(f"共 {len(has_point)} 个行政区含点")
        has_point_names = [admin_regions_list[idx]['row']['ext_path'] for idx in has_point]
        pd.DataFrame(has_point_names, columns=['name']).to_csv(out_csv_name, index=False, encoding='utf-8')

        print("绘制地图...")
        fig, ax = plt.subplots(figsize=(45, 36))
        green_patches = []
        for idx, region in enumerate(admin_regions_list):
            geom = region['geom']
            if idx in has_point:
                green_patches.extend(geom_to_mpl_patches(geom, facecolor='green', edgecolor='none', alpha=0.5))
            plot_geom_boundary(ax, geom, color='black', lw=0.8)
        if green_patches:
            ax.add_collection(PatchCollection(green_patches, match_original=True, zorder=0))
        if show_points:
            ax.scatter(lons, lats, s=point_size, color='red', zorder=5, alpha=0.6)
        ax.set_aspect('equal')
        ax.set_yscale('function', functions=(mercator_forward, mercator_inverse))
        ax.grid(False)
        fig.tight_layout()
        fig.savefig(file_name)
        print(f"已保存: {file_name}")
        plt.close(fig)
        return
    else:
        points_df = points_df[::10]

    # 把所有 target 匹配的行政区合并到一张图
    filtered_regions = []
    for target in target_names:
        matched = [r for r in admin_regions_list if _match_target(r['row']['ext_path'], target)]
        if not matched:
            print(f"未找到匹配 '{target}' 的行政区")
        filtered_regions.extend(matched)

    if not filtered_regions:
        print("没有匹配到任何行政区，退出")
        return

    label = '+'.join(target_names)
    file_name = '_'.join(base_file_names + [label])
    if show_points:
        file_name += '_轨迹点'
    file_name += '.png'

    geoms = [r['geom'] for r in filtered_regions]
    all_geom = unary_union(geoms)
    minx, miny, maxx, maxy = all_geom.bounds

    lons_all = points_df[lon_col].astype(float).to_numpy()
    lats_all = points_df[lat_col].astype(float).to_numpy()
    mask = (lons_all >= minx) & (lons_all <= maxx) & \
           (lats_all >= miny) & (lats_all <= maxy)
    lons_cand = lons_all[mask]
    lats_cand = lats_all[mask]
    print(f"  bbox粗筛后剩 {len(lons_cand)}/{len(lons_all)} 个点")

    print("筛选点...")
    tree = STRtree(geoms)
    lons, lats = [], []
    has_point = set()
    for lo, la in tqdm(zip(lons_cand, lats_cand), total=len(lons_cand)):
        pt = Point(lo, la)
        for idx in tree.query(pt):
            if geoms[idx].contains(pt):
                has_point.add(idx)
                lons.append(lo)
                lats.append(la)
                break
    print(f"目标行政区内共 {len(lons)} 个点")

    print("绘制地图...")
    fig, ax = plt.subplots(figsize=(15, 15))
    green_patches = []
    for idx, region in enumerate(filtered_regions):
        geom = region['geom']
        if idx in has_point:
            green_patches.extend(geom_to_mpl_patches(geom, facecolor='green', edgecolor='none', alpha=0.5))
        plot_geom_boundary(ax, geom, color='black', lw=0.8)
    if green_patches:
        ax.add_collection(PatchCollection(green_patches, match_original=True, zorder=0))
    if show_points:
        ax.scatter(lons, lats, s=point_size, color='red', zorder=5, alpha=0.6)
    pad_x = (maxx - minx) * 0.05
    pad_y = (maxy - miny) * 0.05
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    ax.set_aspect('equal')
    ax.set_yscale('function', functions=(mercator_forward, mercator_inverse))
    ax.grid(False)
    fig.tight_layout()
    fig.savefig(file_name)
    print(f"已保存: {file_name}")
    plt.close(fig)


if __name__ == '__main__':
    border_type = 'gcj'
    path_type = border_type
    # border_data = read_base_border_csv(f'border_data/ok_geo_{border_type}.csv')
    border_data = read_base_border_csvs([
        f'border_data/mainland/ok_geo_mainland_{border_type}.csv',
        f'border_data/taiwan/taiwan_boundaries_{border_type}.csv',
        f'border_data/japan/japan_boundaries_{border_type}.csv',
    ])
    path_data = read_points_csv(f'fwss_reader/loca_20260613_{path_type}.csv')

    # visualize_with_points(border_data, path_data, show_points=False)
    visualize_with_points(border_data, path_data, show_points=True, target_names=['大阪府'])
