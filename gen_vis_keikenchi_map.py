import csv
import sys
import os
import json
import argparse
import re
import warnings
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, Patch
import matplotlib.font_manager as fm
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union
from shapely import STRtree
import pandas as pd
from tqdm import tqdm
import numpy as np
import cartopy.crs as ccrs
from collections import defaultdict
from importlib.metadata import version
from packaging.version import parse
from fwss_reader.fwss_reader import extract_fwss_date, find_latest_fwss, read_fwss



csv.field_size_limit(sys.maxsize)
type_colors = ['#e84c3d', '#d58337', '#f3c218', '#30cc70', '#3598db'] # lived, stayed, visited, alighted, passed
LABEL_ORDER = ['lived', 'stayed', 'visited', 'alighted', 'passed']

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

# 跨 180 度经线的区域在 GeoJSON 里被切成东(接近 +180)、西(接近 -180)两半，
# 西半部分经度为负。把经度小于该阈值的点整体 +360，使其接到东半球后面，
# 这样不可避免的分割线就从 180 度挪到了数据自然边界(约 -168.97 度)。
ANTIMERIDIAN_WRAP_LON = -167

def unwrap_lon(lon):
    """把越过 180 度经线、被切到西半球(经度 < 阈值)的经度整体 +360。
    对已经是正经度的点无影响，且幂等(重复调用结果不变)。"""
    lon = np.asarray(lon, dtype=float)
    return np.where(lon < ANTIMERIDIAN_WRAP_LON, lon + 360.0, lon)
    # return lon

def unwrap_coords(coords):
    """对 [(lon, lat), ...] 坐标列表做经度展开"""
    return [(float(unwrap_lon(lon)), lat) for lon, lat in coords]

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
                        p = make_valid_polygon(unwrap_coords(block))
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
    if sampling > 0:
        print(f"加载了 {n_points} 个点，抽样为 {n_points_sampling} 个点，坐标系{points_type}")
    else:
        print(f"加载了 {n_points} 个点，坐标系{points_type}")
    
    return [points_df, points_type]


def read_points_coordinates(coordinates):
    """把 FWSS 解析出的 (longitude, latitude) 坐标转换为轨迹点数据。"""
    points_df = pd.DataFrame(coordinates, columns=['longitude', 'latitude'])
    print(f"加载了 {len(points_df)} 个点，坐标系WGS")
    return [points_df, 'WGS']


def read_points_fwss(fwss_file):
    """直接读取 FWSS，不创建中间 loca CSV。"""
    print(f"读取 FWSS: {fwss_file}")
    return read_points_coordinates(read_fwss(str(fwss_file)))


def _match_target(ext_path, target):
    """target按空格分割后，每个部分须出现在ext_path的空格分割列表中"""
    parts = target.split()
    ext_parts = ext_path.split()
    return all(part in ext_parts for part in parts)


def load_label_map(label_json_path, admin_regions=None):
    """读取标签json，返回 ext_path分词集合 -> label_index 的映射列表"""
    with open(label_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    label_map = []  # list of (parts_set, label_index)
    for label_idx, label_name in enumerate(LABEL_ORDER):
        for fullname in data.get(label_name, []):
            parts = frozenset(fullname.split())
            label_map.append((parts, label_idx))

    if admin_regions is not None:
        all_ext_paths = [r['row']['ext_path'] for r in admin_regions]
        for label_idx, label_name in enumerate(LABEL_ORDER):
            for fullname in data.get(label_name, []):
                parts = frozenset(fullname.split())
                matched = any(parts <= set(ep.split()) for ep in all_ext_paths)
                if not matched:
                    print(f"[警告] 标签 '{label_name}' 中的名称 '{fullname}' 无法匹配任何行政区")

    return label_map


def _get_label_index(ext_path, label_map):
    """返回ext_path对应的label_index，未匹配返回None"""
    ext_parts = set(ext_path.split())
    for parts, label_idx in label_map:
        if parts <= ext_parts:
            return label_idx
    return None


def visualize_with_points(admin_regions, points_df=None, show_points=True, sampling=-1,
                          point_size=0.5, prefix_name='县级可视化', target_names=None,
                          ignore_names=None, points_within_only=True, fig_width=-1, format='jpg',
                          label_json=None, font_scale=1, hide_never=False, legend_loc='best', projection='m', draw_map=True,
                          output_csv=None):
    # 没有传入轨迹点时，禁用所有与点相关的操作
    has_points_df = points_df is not None
    if not has_points_df:
        show_points = False
    # points_df 与 label_json 都没有时，没有任何标签信息（全部未踏）
    has_labels = has_points_df or bool(label_json)

    base_file_names = [prefix_name, f'base-{admin_regions[1]}']
    if has_points_df:
        base_file_names.append(f'path-{points_df[1]}')
        points_df = points_df[0]
        lon_col, lat_col = points_df.columns[0], points_df.columns[1]

    admin_regions_list = admin_regions[0]

    if target_names is None:
        regions = admin_regions_list
        file_name = '_'.join(base_file_names)
        fig_width = 50 if fig_width < 0 else fig_width
        sampling = 100 if sampling < 0 else sampling
    else:
        regions = []
        for target in target_names:
            matched = [r for r in admin_regions_list
                       if _match_target(r['row']['ext_path'], target)
                       and not (ignore_names and any(_match_target(r['row']['ext_path'], ign) for ign in ignore_names))]
            if not matched:
                print(f"未找到匹配 '{target}' 的行政区")
            regions.extend(matched)
        if not regions:
            print("没有匹配到任何行政区，退出")
            return
        file_name = '_'.join(base_file_names + ['-'.join(target_names)])
        fig_width = 25 if fig_width < 0 else fig_width
        sampling = 10 if sampling < 0 else sampling

    if show_points:
        file_name += '_轨迹点'
    file_name = f'{file_name}.{format}'

    geoms = [r['geom'] for r in regions]

    # 轻量 bounds：遍历各 geom 的 bounds 取极值，避免 unary_union 的高开销
    minx = miny = float('inf')
    maxx = maxy = float('-inf')
    for g in geoms:
        gx0, gy0, gx1, gy1 = g.bounds
        if gx0 < minx: minx = gx0
        if gy0 < miny: miny = gy0
        if gx1 > maxx: maxx = gx1
        if gy1 > maxy: maxy = gy1

    has_point = set()
    lons, lats = [], []
    lons_all, lats_all = None, None
    n_in_areas = {}

    if has_points_df:
        points_df = points_df[::sampling]
        print(f"抽样为 {len(points_df)} 个轨迹点")
        lons_all = unwrap_lon(points_df[lon_col].astype(float).to_numpy())
        lats_all = points_df[lat_col].astype(float).to_numpy()

        tree = STRtree(geoms)

        if target_names is not None:
            mask = (lons_all >= minx) & (lons_all <= maxx) & (lats_all >= miny) & (lats_all <= maxy)
            lons_cand, lats_cand = lons_all[mask], lats_all[mask]
            print(f"粗筛后剩 {len(lons_cand)}/{len(lons_all)} 个点")
        else:
            lons_cand, lats_cand = lons_all, lats_all

        for lo, la in tqdm(zip(lons_cand, lats_cand), total=len(lons_cand)):
            pt = Point(lo, la)
            for idx in tree.query(pt):
                if geoms[idx].contains(pt):
                    has_point.add(idx)
                    lons.append(lo)
                    lats.append(la)
                    n_in_areas[idx] = n_in_areas.get(idx, 0) + 1
                    break

        print(f"共 {len(has_point)} 个行政区含点，{len(lons)} 个点落入")

    legend_labels = ['住居（居住过）', '宿泊（住宿过）', '訪問（游玩过）', '接地（休息、换车等）', '通過（路过）', '未踏（没去过）']
    NO_LABEL_INDEX = len(LABEL_ORDER)        # 5，未踏
    PASSED_INDEX = LABEL_ORDER.index('passed')

    if has_labels:
        # 加载标签映射
        label_map = load_label_map(label_json, admin_regions_list) if label_json else []

        # 为每个区域确定标签索引：json标签优先；其次区域内有点则默认 passed；否则未踏
        region_labels = []
        for idx, region in enumerate(regions):
            json_label = _get_label_index(region['row']['ext_path'], label_map) if label_map else None
            if json_label is not None:
                region_labels.append(json_label)
            elif idx in has_point:
                region_labels.append(PASSED_INDEX)
            else:
                region_labels.append(NO_LABEL_INDEX)

        label_counts = [region_labels.count(i) for i in range(len(legend_labels))]

        if target_names is None:
            # 标签短名
            short_labels = [lbl.split('（')[0] for lbl in legend_labels]
            out_csv_name = output_csv or ('_'.join(['经过县区名'] + base_file_names[1:]) + '.csv')
            out_rows = []
            for idx, region in enumerate(regions):
                lbl = region_labels[idx]
                if lbl == NO_LABEL_INDEX:
                    continue  # 未踏不输出
                out_rows.append({
                    'name': region['row']['ext_path'],
                    'count': n_in_areas.get(idx, 0),
                    'label': short_labels[lbl],
                })
            df = pd.DataFrame(out_rows, columns=['name', 'count', 'label'])
            df.sort_values('name', inplace=True)
            output_parent = Path(out_csv_name).parent
            if str(output_parent) != '.':
                output_parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(out_csv_name, index=False, encoding='utf-8')
    else:
        # 无任何标签信息：全部视为未踏
        region_labels = [NO_LABEL_INDEX] * len(regions)
        label_counts = [region_labels.count(i) for i in range(len(legend_labels))]

    level_weights = [5, 4, 3, 2, 1]
    world_level = sum(w * label_counts[i] for i, w in enumerate(level_weights))
    
    if draw_map:
        print("绘制地图...")
        pad_x = (maxx - minx) * 0.05
        pad_y = (maxy - miny) * 0.05
        # print(maxx,minx,maxy,miny)

        data_crs = ccrs.PlateCarree()
        central_lon = 11.03
        if projection == 'r':
            proj = ccrs.Robinson(central_longitude=central_lon)
        elif projection == 'm':
            proj = ccrs.Mercator(central_longitude=central_lon, min_latitude=-80, max_latitude=84)
        else:
            raise ValueError
        # Robinson 的有效经度范围是 central_longitude ± 180（这里约 [-168.97, 191.03]）。
        # 俄罗斯东端经度(unwrap 后约 191)已贴着上边界，加 padding 后会越界，
        # 被 cartopy 回绕到地图另一侧，导致投影范围横跨整个世界。
        # 这里把加 padding 后的经度夹到有效范围内。
        eps = 1e-6
        ext_minx = max(minx - pad_x, central_lon - 180 + eps)
        ext_maxx = min(maxx + pad_x, central_lon + 180 - eps)
        ext_miny = miny - pad_y
        ext_maxy = maxy + pad_y

        corners = proj.transform_points(
            data_crs,
            np.array([ext_minx, ext_maxx, ext_minx, ext_maxx]),
            np.array([ext_miny, ext_miny, ext_maxy, ext_maxy]),
        )
        x_range = corners[:, 0].max() - corners[:, 0].min()
        y_range = corners[:, 1].max() - corners[:, 1].min()

        fig, ax = plt.subplots(
            figsize=(fig_width, fig_width * y_range / x_range),
            subplot_kw={'projection': proj},
        )

        groups = defaultdict(list)
        for idx, region in enumerate(regions):
            lbl = region_labels[idx]
            fc = type_colors[lbl] if lbl != NO_LABEL_INDEX else 'none'
            groups[fc].append(region['geom'])
        for fc, geoms in groups.items():
            ax.add_geometries(geoms, crs=data_crs,
                            facecolor=fc, edgecolor='black', linewidth=0.8, zorder=0)

        if show_points:
            pts_lon, pts_lat = (lons, lats) if points_within_only else (lons_all, lats_all)
            ax.scatter(pts_lon, pts_lat, s=point_size, color='red',
                    zorder=5, alpha=0.6, transform=data_crs)

        ax.set_extent([ext_minx, ext_maxx, ext_miny, ext_maxy], crs=data_crs)
        ax.patch.set_visible(False)
        ax.spines['geo'].set_visible(False)
        ax.grid(False)

        if has_labels:
            legend_colors = type_colors + ['#ffffff']

            IDEO_SPACE = '　'
            label_width = max(len(lbl) for lbl in legend_labels)
            legend_texts = [
                f"{lbl.ljust(label_width, IDEO_SPACE)}{IDEO_SPACE}{str(cnt)} 个区域"
                for lbl, cnt in zip(legend_labels, label_counts)
            ]
            if hide_never:
                legend_texts[-1] = '未踏（没去过）'
            legend_patches = [
                Patch(facecolor=color, edgecolor='black', linewidth=fig_width * 0.04 * font_scale, label=text)
                for color, text in zip(legend_colors, legend_texts)
            ]
            font_size = fig_width * 1 * font_scale
            font = fm.FontProperties(fname='SourceHanSansCN-Bold.otf', size=font_size)
            title_font = fm.FontProperties(fname='SourceHanSansCN-Bold.otf', size=font_size * 1.3)
            legend = ax.legend(
                handles=legend_patches, fontsize=font_size, frameon=False,
                handlelength=2.0, handleheight=1.2, borderpad=0.6, prop=font,
                title=f"世界等级  {world_level}", loc=legend_loc,
            )
            legend.get_title().set_fontproperties(title_font)
            legend._legend_box.align = 'left'

        fig.tight_layout()
        fig.savefig(file_name)
        print(f"已保存: {file_name}")
        plt.close(fig)
    
    return [world_level] + label_counts


def require(pkg, min_ver):
    try:
        cur = version(pkg)
    except Exception as exc:
        warnings.warn(f"无法检查依赖 {pkg}: {exc}", RuntimeWarning)
        return False
    if parse(cur) < parse(min_ver):
        warnings.warn(
            f"{pkg} 版本较低: 当前 {cur}，建议 >= {min_ver}",
            RuntimeWarning,
        )
        return False
    return True


def check_env():
    require('shapely', '2.1.2')
    require('cartopy', '0.25.0')
    require('pyproj', '3.7.2')
    require('matplotlib', '3.10.9')
    require('numpy', '2.4.6')
    require('pandas', '3.0.3')
    

DATE_PATTERN = re.compile(r'(?<!\d)(20\d{6})(?!\d)')


def validate_date(date):
    if not DATE_PATTERN.fullmatch(date):
        raise ValueError(f"日期必须是 YYYYMMDD: {date}")
    return date


def date_from_loca_path(path):
    match = re.search(r'loca_(20\d{6})_', Path(path).name)
    return match.group(1) if match else None


def find_fwss_for_date(date, fwss_dir='fwss_reader/fwss'):
    matches = []
    for path in Path(fwss_dir).glob('*.fwss'):
        try:
            if extract_fwss_date(path) == date:
                matches.append(path)
        except ValueError:
            continue
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return max(matches, key=lambda path: path.stat().st_mtime)
    return None


def load_path_data(date=None, points_file=None, fwss_file=None):
    """优先读取显式输入；没有 loca CSV 时直接读取对应 FWSS。"""
    if points_file:
        path = Path(points_file)
        if not path.exists():
            raise FileNotFoundError(path)
        inferred_date = date_from_loca_path(path)
        resolved_date = date or inferred_date
        if not resolved_date:
            raise ValueError('CSV 文件名不含日期，请通过 --date 指定日期')
        return resolved_date, read_points_csv(str(path))

    if fwss_file:
        path = Path(fwss_file)
        if not path.exists():
            raise FileNotFoundError(path)
        return date or extract_fwss_date(path), read_points_fwss(path)

    if date:
        csv_path = Path(f'fwss_reader/loca_{date}_wgs.csv')
        if csv_path.exists():
            return date, read_points_csv(str(csv_path))
        snapshot = find_fwss_for_date(date)
        if snapshot:
            return date, read_points_fwss(snapshot)
        raise FileNotFoundError(f"找不到日期 {date} 的 loca CSV 或 FWSS 文件")

    snapshot = find_latest_fwss()
    return extract_fwss_date(snapshot), read_points_fwss(snapshot)


def read_border_data(border_type='wgs'):
    read_list = [
        f'border_data/mainland/china_mainland_boundaries_{border_type}.csv',
        f'border_data/hong_kong/hk_boundaries_{border_type}.csv',
        f'border_data/macau/mc_boundaries_{border_type}.csv',
        f'border_data/taiwan/taiwan_town_boundaries_{border_type}.csv',
        f'border_data/japan/japan_boundaries_{border_type}.csv',
    ]
    return read_base_border_csvs(read_list)


def discover_history_dates():
    csv_dates = {
        match.group(1)
        for path in Path('fwss_reader').glob('loca_*_wgs.csv')
        for match in [re.search(r'loca_(20\d{6})_wgs\.csv$', path.name)]
        if match
    }
    label_dates = {
        match.group(1)
        for path in Path('add_labels').glob('add_label_list_fullname_*.json')
        for match in [re.search(r'add_label_list_fullname_(20\d{6})\.json$', path.name)]
        if match
    }
    return sorted(csv_dates & label_dates)


def generate_history(border_data, history_dir='history'):
    dates = discover_history_dates()
    destination_dir = Path(history_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    pending_dates = [
        date for date in dates
        if not (destination_dir / f'经过县区名_base-WGS_path-WGS_{date}.csv').exists()
    ]
    if not pending_dates:
        print('history 已包含所有可重建的日期，无需更新。')
        return
    for date in pending_dates:
        _, path_data = load_path_data(date=date)
        destination = destination_dir / f'经过县区名_base-WGS_path-WGS_{date}.csv'
        visualize_with_points(
            border_data,
            path_data,
            show_points=False,
            fig_width=200,
            label_json=f'add_labels/add_label_list_fullname_{date}.json',
            format='jpg',
            legend_loc='lower left',
            sampling=10,
            draw_map=False,
            output_csv=str(destination),
        )
        print(f'历史结果已保存: {destination}')


def update_total_level(date, world_level, japan_level):
    total_level_path = Path('total_level.json')
    if total_level_path.exists():
        with total_level_path.open('r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = []
    new_item = {
        'date': int(date),
        'world': world_level,
        'china': (np.asarray(world_level) - np.asarray(japan_level)).tolist(),
        'japan': japan_level,
    }
    data = [item for item in data if item['date'] != new_item['date']]
    data.append(new_item)
    data.sort(key=lambda item: item['date'])
    with total_level_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def parse_args():
    parser = argparse.ArgumentParser(description='生成县区经验值地图和结果 CSV')
    parser.add_argument('date', nargs='?', help='日期 YYYYMMDD；省略时使用最新 FWSS')
    parser.add_argument('--date', dest='date_option', help='日期 YYYYMMDD（与位置参数二选一）')
    parser.add_argument('--points-file', help='直接指定 loca CSV')
    parser.add_argument('--fwss-file', help='直接指定 FWSS，不生成 loca 中间文件')
    parser.add_argument('--labels', help='直接指定 fullname 标签 JSON')
    parser.add_argument('--no-labels', '--ignore-labels', action='store_true', help='忽略已有标签，只生成初步 CSV')
    parser.add_argument('--history', action='store_true', help='根据已有日期 CSV 和 fullname JSON 更新 history')
    parser.add_argument('--no-map', action='store_true', help='只计算结果，不生成地图图片')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    check_env()
    if args.date and args.date_option:
        raise ValueError('日期只能通过位置参数或 --date 指定一次')
    date_argument = args.date or args.date_option
    if date_argument:
        date_argument = validate_date(date_argument)

    border_data = read_border_data()
    if args.history:
        generate_history(border_data)
        raise SystemExit(0)

    date, path_data = load_path_data(
        date=date_argument,
        points_file=args.points_file,
        fwss_file=args.fwss_file,
    )
    validate_date(date)

    if args.labels:
        label_json = Path(args.labels)
        if not label_json.exists():
            raise FileNotFoundError(label_json)
        label_json = str(label_json)
    elif args.no_labels:
        label_json = None
    else:
        default_label_json = Path(f'add_labels/add_label_list_fullname_{date}.json')
        label_json = str(default_label_json) if default_label_json.exists() else None
        if label_json is None:
            print(f'未找到 {default_label_json}，本次先生成未标注的初步 CSV。')

    preliminary = label_json is None
    if preliminary:
        visualize_with_points(
            border_data,
            path_data,
            show_points=False,
            fig_width=200,
            label_json=None,
            format='jpg',
            legend_loc='lower left',
            sampling=10,
            draw_map=False,
        )
        print('初步县区结果已生成，请运行 add_labels/resolve_full_names.py 生成标签 JSON。')
        raise SystemExit(0)

    world_level = visualize_with_points(
        border_data,
        path_data,
        show_points=False,
        fig_width=200,
        label_json=label_json,
        format='jpg',
        legend_loc='lower left',
        sampling=10,
        draw_map=not args.no_map,
    )
    japan_level = visualize_with_points(
        border_data,
        path_data,
        show_points=False,
        fig_width=100,
        target_names=['日本'],
        format='jpg',
        label_json=label_json,
        sampling=1,
        draw_map=False,
    )
    update_total_level(date, world_level, japan_level)
