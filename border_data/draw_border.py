import csv
import matplotlib.pyplot as plt
import numpy as np
import sys

# 增加CSV字段大小限制
csv.field_size_limit(sys.maxsize)

def parse_polygon(polygon_str):
    """解析polygon字符串为坐标列表（支持多个区块）
    返回区块列表，每个区块是一个坐标列表
    """
    if not polygon_str or polygon_str.strip() == '':
        return []
    
    blocks = []
    # 先按分号拆分成多个区块（飞地、分块）
    parts = polygon_str.split(';')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        coords = []
        # 每个区块再按逗号拆分坐标点
        points = part.split(',')
        for point in points:
            point = point.strip()
            if point:
                try:
                    lon, lat = point.split()
                    coords.append([float(lon), float(lat)])
                except:
                    continue
        
        if len(coords) > 1:
            blocks.append(coords)
    
    return blocks

def plot_administrative_boundaries(csv_file):
    """绘制行政区边界"""
    # 读取CSV文件
    all_blocks = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # if row['name'] not in ['新星市'] and '哈密市' not in row['ext_path']:
            if row['name'] not in ['伊州区']:
                continue
            if row['deep'] == '2':  # 只处理deep=2的行政区
                polygon_str = row['polygon']
                blocks = parse_polygon(polygon_str)
                if blocks:
                    all_blocks.extend(blocks)
                    # total_points = sum(len(b) for b in blocks)
                    # block_info = f"，{len(blocks)} 个区块" if len(blocks) > 1 else ""
                    # print(f"已加载: {row['name']}, 坐标点数: {total_points}{block_info}")
    
    print(f"\n总共加载了 {len(all_blocks)} 个边界区块")
    
    # 创建图形
    fig, ax = plt.subplots(figsize=(15, 12))
    
    # 绘制所有边界区块
    for block in all_blocks:
        if len(block) > 1:
            block_array = np.array(block)
            ax.plot(block_array[:, 0], block_array[:, 1], 
                   color='black', linewidth=0.8)
    
    # 设置图形属性
    ax.set_aspect('equal')
    # ax.set_xlabel('经度', fontsize=12)
    # ax.set_ylabel('纬度', fontsize=12)
    # ax.set_title('行政区边界 (deep=2)', fontsize=14)
    
    # 移除网格
    ax.grid(False)
    
    plt.tight_layout()
    plt.savefig('administrative_boundaries.png', dpi=300, bbox_inches='tight')
    print("\n地图已保存为: administrative_boundaries.png")
    # plt.show()

if __name__ == '__main__':
    # 替换为你的CSV文件路径
    csv_file = 'ok_geo_modi.csv'
    plot_administrative_boundaries(csv_file)
