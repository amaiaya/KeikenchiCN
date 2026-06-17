import csv
import sys
import os
import json
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, Patch
from matplotlib.collections import PatchCollection
import matplotlib.font_manager as fm
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union
from shapely import STRtree
import pandas as pd
from tqdm import tqdm
import numpy as np

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
    if sampling > 0:
        print(f"加载了 {n_points} 个点，抽样为 {n_points_sampling} 个点，坐标系{points_type}")
    else:
        print(f"加载了 {n_points} 个点，坐标系{points_type}")
    
    return [points_df, points_type]


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


def visualize_with_points(admin_regions, points_df, show_points=True, sampling=-1,
                          point_size=0.5, prefix_name='县级可视化', target_names=None,
                          ignore_names=None, points_within_only=True, fig_width=-1, format='jpg',
                          label_json=None, font_scale=1):
    base_file_names = [prefix_name, f'base-{admin_regions[1]}', f'path-{points_df[1]}']
    points_df = points_df[0]
    admin_regions_list = admin_regions[0]
    lon_col, lat_col = points_df.columns[0], points_df.columns[1]

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

    points_df = points_df[::sampling]
    print(f"抽样为 {len(points_df)} 个轨迹点")
    lons_all = points_df[lon_col].astype(float).to_numpy()
    lats_all = points_df[lat_col].astype(float).to_numpy()
    
    geoms = [r['geom'] for r in regions]
    tree = STRtree(geoms)
    has_point = set()
    lons, lats = [], []
    minx, miny, maxx, maxy = unary_union(geoms).bounds
    
    if target_names is not None:
        mask = (lons_all >= minx) & (lons_all <= maxx) & (lats_all >= miny) & (lats_all <= maxy)
        lons_cand, lats_cand = lons_all[mask], lats_all[mask]
        print(f"粗筛后剩 {len(lons_cand)}/{len(lons_all)} 个点")
    else:
        lons_cand, lats_cand = lons_all, lats_all
    
    n_in_areas = {}
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

    if target_names is None:
        out_csv_name = '_'.join(['经过县区名'] + base_file_names[1:]) + '.csv'
        has_point_names = [regions[idx]['row']['ext_path'] for idx in has_point]
        has_point_numbers = [n_in_areas.get(idx, 0) for idx in has_point]
        df = pd.DataFrame({'name': has_point_names, 'count': has_point_numbers})
        df.sort_values('name', inplace=True)
        df.to_csv(out_csv_name, index=False, encoding='utf-8')

    # 加载标签映射
    label_map = load_label_map(label_json, admin_regions_list) if label_json else []

    print("绘制地图...")
    pad_x = (maxx - minx) * 0.05
    pad_y = (maxy - miny) * 0.05
    x_range = (maxx + pad_x) - (minx - pad_x)
    y_merc_range = mercator_forward(maxy + pad_y) - mercator_forward(miny - pad_y)
    fig, ax = plt.subplots(figsize=(fig_width, fig_width * y_merc_range / x_range))
    colored_patches = []
    for idx, region in enumerate(regions):
        geom = region['geom']
        ext_path = region['row']['ext_path']
        json_label = _get_label_index(ext_path, label_map) if label_map else None

        if json_label is not None:
            # 出现在json中：按json标签着色（无论有没有点）
            color = type_colors[json_label]
            colored_patches.extend(geom_to_mpl_patches(geom, facecolor=color, edgecolor='none', alpha=1))
        elif idx in has_point:
            # 内部有点但未出现在json：默认passed颜色
            color = type_colors[LABEL_ORDER.index('passed')]
            colored_patches.extend(geom_to_mpl_patches(geom, facecolor=color, edgecolor='none', alpha=1))
        # 内部无点且不在json中：不着色
        plot_geom_boundary(ax, geom, color='black', lw=0.8)
    if colored_patches:
        ax.add_collection(PatchCollection(colored_patches, match_original=True, zorder=0))
    if show_points:
        if points_within_only:
            ax.scatter(lons, lats, s=point_size, color='red', zorder=5, alpha=0.6)
        else:
            ax.scatter(lons_all, lats_all, s=point_size, color='red', zorder=5, alpha=0.6)
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    ax.set_aspect('equal')
    ax.set_yscale('function', functions=(mercator_forward, mercator_inverse))
    ax.grid(False)

    # 图例：根据图片尺寸自动缩放字体
    legend_labels = ['住居（居住过）', '宿泊（住宿过）', '訪問（游玩过）', '接地（休息、换车等）', '通過（路过）', '未踏（没去过）']
    legend_colors = type_colors + ['#ffffff']
    legend_patches = [
        Patch(facecolor=color, edgecolor='black', linewidth=fig_width * 0.04 * font_scale,
              label=label)
        for color, label in zip(legend_colors, legend_labels)
    ]
    font_size = fig_width * 1.2 * font_scale
    font = fm.FontProperties(fname='SourceHanSansCN-Bold.otf', size=font_size)
    ax.legend(
        handles=legend_patches,
        # loc='lower right',
        fontsize=font_size,
        # framealpha=0.8,
        frameon=False,
        # edgecolor='black',
        handlelength=2.0,
        handleheight=1.2,
        borderpad=0.6,
        prop=font
    )

    fig.tight_layout()
    fig.savefig(file_name)
    print(f"已保存: {file_name}")
    plt.close(fig)


if __name__ == '__main__':
    border_type = 'wgs'
    path_type = border_type
    border_data = read_base_border_csvs([
        f'border_data/mainland/china_mainland_boundaries_{border_type}.csv',
        f'border_data/hong_kong/hk_boundaries_{border_type}.csv',
        f'border_data/macau/mc_boundaries_{border_type}.csv',
        f'border_data/taiwan/taiwan_town_boundaries_{border_type}.csv',
        f'border_data/japan/japan_boundaries_{border_type}.csv',
        # f'border_data/vietnam/vn_1_boundaries_{border_type}.csv',
        # f'border_data/south_korea/sk_boundaries_{border_type}.csv',
        # f'border_data/north_korea/nk_boundaries_{border_type}.csv',
        # f'border_data/MNG/MNG_ADM2_boundaries_{border_type}.csv',
    ])
    path_data = read_points_csv(f'fwss_reader/loca_20260614_{path_type}.csv')
    label_json='add_labels/add_label_list_fullname.json'
    
    # china_provinces = [
    #     "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
    #     "江苏省", "浙江省", "安徽省", "福建省", "江西省",
    #     "山东省", "河南省", "湖北省", "湖南省", "广东省",
    #     "海南省", "四川省", "贵州省", "云南省", "陕西省",
    #     "甘肃省", "青海省", 
    #     "北京市", "天津市", "上海市", "重庆市", 
    #     "内蒙古自治区", "广西壮族自治区", "宁夏回族自治区", "新疆维吾尔自治区", "西藏自治区",
    #     "香港特别行政区", "澳门特别行政区", "臺灣省"
    # ]
    # for p in china_provinces:
    for p in ['山东省']:
        visualize_with_points(border_data, path_data, prefix_name='split_figs/县级可视化', show_points=True, fig_width=50, point_size=1.5, target_names=[p], label_json=label_json)
        visualize_with_points(border_data, path_data, prefix_name='split_figs/县级可视化', show_points=False, fig_width=50, point_size=1.5, target_names=[p], label_json=label_json)

    # visualize_with_points(border_data, path_data, show_points=False, fig_width=200, label_json=label_json, format='pdf')
    # visualize_with_points(border_data, path_data, show_points=False, fig_width=200, label_json=label_json, format='eps') # 体积太大
    visualize_with_points(border_data, path_data, show_points=False, fig_width=200, label_json=label_json, format='svg')
    visualize_with_points(border_data, path_data, show_points=True, fig_width=200, points_within_only=False, label_json=label_json, format='svg')
    # visualize_with_points(border_data, path_data, prefix_name='split_figs/县级可视化', show_points=True, fig_width=100, point_size=1.5, target_names=['广东省', '香港特別行政區', '澳門特別行政區'], label_json=label_json)

    # visualize_with_points(border_data, path_data, prefix_name='split_figs/县级可视化', show_points=True, target_names=['金門縣'])
    # visualize_with_points(border_data, path_data, prefix_name='split_figs/县级可视化', show_points=True, target_names=['金门县'])
    # visualize_with_points(border_data, path_data, prefix_name='split_figs/县级可视化', show_points=True, target_names=['連江縣'])
    # visualize_with_points(border_data, path_data, prefix_name='split_figs/县级可视化', show_points=True, target_names=['连江县'])
    # visualize_with_points(border_data, path_data, prefix_name='split_figs/县级可视化', show_points=True, target_names=['連江縣','连江县'])
    # visualize_with_points(border_data, path_data, prefix_name='split_figs/县级可视化', show_points=True, target_names=['金門縣','金门县'])
    
    
    # visualize_with_points(border_data, path_data, show_points=False, fig_width=100, target_names=['日本'], label_json=label_json)
    # tokyo_islands = ['大島支庁', '三宅支庁', '八丈支庁', '小笠原支庁', '東京都 所属不明地']
    # visualize_with_points(border_data, path_data, prefix_name='split_figs/县级可视化', show_points=False, target_names=['大阪府','兵庫県','愛知県','岐阜県','東京都','千葉県'], ignore_names=tokyo_islands, label_json=label_json, font_scale=0.7)
    
    
    # visualize_with_points(border_data, path_data, show_points=False, prefix_name='split_figs/县级可视化', fig_width=100, target_names=['Vietnam'])
