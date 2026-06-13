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


csv.field_size_limit(sys.maxsize)

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

def visualize_with_points(csv_file, points_df, output_dir='.',
                          lon_col=None, lat_col=None, show_points=True, file_name='县级可视化.png'):
    """
    csv_file: 行政区CSV
    points_df: 两列的DataFrame，分别是经度和纬度
    lon_col, lat_col: 经度/纬度列名，若为None则默认取前两列
    show_points: 是否把点也画出来
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 取出点坐标
    if lon_col is None or lat_col is None:
        lon_col, lat_col = points_df.columns[0], points_df.columns[1]
    lons = points_df[lon_col].astype(float).tolist()
    lats = points_df[lat_col].astype(float).tolist()
    pts = [Point(lo, la) for lo, la in zip(lons, lats)]
    
    print(f"加载了 {len(pts)} 个点")
    
    # 第一步：读取所有行政区，构造合并后的多边形
    print("读取行政区...")
    admin_regions = []  # 每个元素: {'geom': merged_polygon, 'row': row_data}
    
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
    
    print(f"加载了 {len(admin_regions)} 个行政区")
    
    # 第二步：构建空间索引（STRtree）
    print("构建空间索引...")
    geoms = [r['geom'] for r in admin_regions]
    tree = STRtree(geoms)
    
    # 第三步：快速查询每个点落在哪些行政区里
    print("查询点所在行政区...")
    has_point = set()  # 含点的行政区索引集合
    
    for i, pt in enumerate(pts):
        if (i + 1) % 10000 == 0:
            print(f"  已处理 {i+1}/{len(pts)} 个点")
        # query返回可能相交的候选多边形索引
        candidates = tree.query(pt)
        for idx in candidates:
            # 精确判断点是否在多边形内
            if geoms[idx].contains(pt):
                has_point.add(idx)
    
    print(f"共 {len(has_point)} 个行政区含点")
    
    # 第四步：绘图
    print("绘制地图...")
    fig, ax = plt.subplots(figsize=(45, 36))
    
    green_patches = []
    for idx, region in enumerate(admin_regions):
        geom = region['geom']
        
        if idx in has_point:
            # 绿色填充
            green_patches.extend(
                geom_to_mpl_patches(geom, facecolor='green',
                                   edgecolor='none', alpha=0.5)
            )
        
        # 黑色边界
        plot_geom_boundary(ax, geom, color='black', lw=0.8)
    
    # 添加绿色填充
    if green_patches:
        pc = PatchCollection(green_patches, match_original=True, zorder=0)
        ax.add_collection(pc)
    
    # 画点
    if show_points:
        ax.scatter(lons, lats, s=0.5, color='red', zorder=5, alpha=0.6)
    
    ax.set_aspect('equal')
    # ax.set_xlabel('经度', fontsize=12)
    # ax.set_ylabel('纬度', fontsize=12)
    # ax.set_title(f'行政区边界 (deep=2)，含点的行政区已涂绿\n'
    #              f'共{len(admin_regions)}个行政区，{len(has_point)}个含点', fontsize=14)
    ax.grid(False)
    plt.tight_layout()
    out = os.path.join(output_dir, file_name)
    plt.savefig(out, dpi=300, bbox_inches='tight')
    
    print(f"已保存: {out}")
    plt.show()


if __name__ == '__main__':    
    csv_file = 'border_data/ok_geo.csv'
    points_df = pd.read_csv('read_fwss/loca_20260613.csv')  # 替换为你的df来源
    points_df = points_df.iloc[::500]
    
    visualize_with_points(csv_file, points_df,
                          lon_col=None, lat_col=None,
                          show_points=True, file_name='县级可视化_轨迹点.png')
