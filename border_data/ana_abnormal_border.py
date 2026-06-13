import csv
import math
import sys
import os
import matplotlib.pyplot as plt
import numpy as np

# 增加CSV字段大小限制
csv.field_size_limit(sys.maxsize)

def parse_polygon(polygon_str):
    """解析polygon字符串为区块列表，每个区块是一个坐标列表"""
    if not polygon_str or polygon_str.strip() == '':
        return []
    
    blocks = []
    parts = polygon_str.split(';')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        coords = []
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
def distance(p1, p2):
    """计算两点之间的欧氏距离（基于经纬度坐标）"""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def sanitize_filename(name):
    return name.strip()

def visualize_abnormal_rows(csv_file, threshold, output_dir='visual_abnormal'):
    """
    可视化所有存在可疑跳变的行，每行保存一张图到output_dir
    threshold: 距离阈值，超过此值认为是可疑跳变
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    suspicious_count = 0
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):  # start=2因为有header
            if row['deep'] != '2':
                continue
            
            blocks = parse_polygon(row['polygon'])
            if not blocks:
                continue
            
            # 检测该行所有可疑跳变
            problems = []  # 每个元素: (block_index, point_index, dist, from_point, to_point)
            for bi, block in enumerate(blocks):
                for i in range(len(block) - 1):
                    d = distance(block[i], block[i + 1])
                    if d > threshold:
                        problems.append((bi, i, d, block[i], block[i + 1]))
            
            if not problems:
                continue
            
            suspicious_count += 1
            row_id = row.get('id', '')
            row_name = row.get('name', '')
            
            # 创建图形
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # 绘制所有边界区块（黑色）
            for block in blocks:
                if len(block) > 1:
                    arr = np.array(block)
                    ax.plot(arr[:, 0], arr[:, 1], color='black', linewidth=0.8, zorder=1)
            
            # 高亮可疑跳变（红色线段 + 端点标记）
            for (bi, i, d, p_from, p_to) in problems:
                ax.plot([p_from[0], p_to[0]], [p_from[1], p_to[1]],
                        color='red', linewidth=1.5, zorder=2)
                ax.scatter([p_from[0], p_to[0]], [p_from[1], p_to[1]],
                           color='red', s=30, zorder=3)
            
            # 设置图形属性
            ax.set_aspect('equal')
            # ax.set_xlabel('经度', fontsize=12)
            # ax.set_ylabel('纬度', fontsize=12)
            # ax.set_title(f'行{line_num} id={row_id} name={row_name}\n'
            #              f'共 {len(problems)} 处可疑跳变 (红色标记)', fontsize=12)
            ax.grid(False)
            
            plt.tight_layout()
            
            # 文件名：行号_id_名称
            safe_name = sanitize_filename(row_name)
            filename = f"line{line_num}_id{sanitize_filename(str(row_id))}_{safe_name}.png"
            filepath = os.path.join(output_dir, filename)
            plt.savefig(filepath, dpi=200, bbox_inches='tight')
            plt.close(fig)  # 关闭图形释放内存
            
            # print(f"已保存: {filepath}  (可疑跳变 {len(problems)} 处)")
    
    print(f"\n共可视化 {suspicious_count} 个可疑行，保存在 '{output_dir}' 目录")

if __name__ == '__main__':
    csv_file = 'ok_geo.csv'
    
    # 设置为你确定的阈值（根据上一步的距离分布分析结果）
    threshold = 0.2  # 请替换为你认为合理的阈值
    
    visualize_abnormal_rows(csv_file, threshold)
