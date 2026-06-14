#!/usr/bin/env python3
"""
FWSS文件解析器 - 提取Fog of World快照文件中的地理坐标

该程序解析.fwss文件（ZIP格式），提取所有访问过的地理位置，
并将其转换为经纬度坐标。

用法:
    python fwss_parser.py <fwss文件路径>
"""

import zipfile
import zlib
import struct
import math
from pathlib import Path
from typing import List, Tuple, Iterator
import sys


# 常量定义（来自TypeScript源码）
MAP_WIDTH = 512
TILE_WIDTH = 128  # 2^7
TILE_HEADER_SIZE = TILE_WIDTH * TILE_WIDTH * 2  # 32768 bytes
BLOCK_BITMAP_SIZE = 512
BLOCK_EXTRA_DATA = 3
BLOCK_SIZE = BLOCK_BITMAP_SIZE + BLOCK_EXTRA_DATA
BITMAP_WIDTH = 64  # 2^6

# 文件名解码
FILENAME_MASK1 = "olhwjsktri"
FILENAME_ENCODING = {char: idx for idx, char in enumerate(FILENAME_MASK1)}


def decode_fow_tile_filename(filename: str) -> int:
    """
    解码FOW tile文件名，获取tile ID

    Args:
        filename: tile文件名（不含路径）

    Returns:
        tile ID
    """
    # 文件名格式: [4个字符的MD5前缀][编码的数字][2个字符的校验和]
    # 我们只需要中间的编码部分
    encoded_id = filename[4:-2]

    # 解码数字
    decoded_digits = [str(FILENAME_ENCODING[char]) for char in encoded_id]
    tile_id = int(''.join(decoded_digits))

    return tile_id


def tile_id_to_xy(tile_id: int) -> Tuple[int, int]:
    """
    将tile ID转换为tile坐标

    Args:
        tile_id: tile ID

    Returns:
        (x, y) tile坐标
    """
    x = tile_id % MAP_WIDTH
    y = tile_id // MAP_WIDTH
    return x, y


def xy_to_lnglat(x: float, y: float) -> Tuple[float, float]:
    """
    将归一化的tile坐标转换为经纬度（Web墨卡托投影）

    Args:
        x: X坐标 (0-512范围)
        y: Y坐标 (0-512范围)

    Returns:
        (经度, 纬度) 元组
    """
    # 经度计算
    lng = (x / 512) * 360 - 180

    # 纬度计算（反向Web墨卡托投影）
    lat = math.atan(math.sinh(math.pi - (2 * math.pi * y) / 512)) * 180 / math.pi

    return lng, lat


def parse_tile_data(data: bytes) -> List[Tuple[int, int, bytes]]:
    """
    解析tile数据，提取所有blocks

    Args:
        data: 压缩的tile数据

    Returns:
        List of (block_x, block_y, bitmap) tuples
    """
    # 解压数据
    decompressed = zlib.decompress(data)

    # 读取header (16384个uint16值)
    header_data = decompressed[:TILE_HEADER_SIZE]
    header = struct.unpack(f'<{TILE_WIDTH * TILE_WIDTH}H', header_data)

    blocks = []

    # 遍历header，找到所有有效的blocks
    for i, block_idx in enumerate(header):
        if block_idx > 0:
            block_x = i % TILE_WIDTH
            block_y = i // TILE_WIDTH

            # 计算block数据的偏移量
            start_offset = TILE_HEADER_SIZE + (block_idx - 1) * BLOCK_SIZE
            end_offset = start_offset + BLOCK_BITMAP_SIZE

            # 提取bitmap数据（不包括extra data）
            bitmap = decompressed[start_offset:end_offset]

            blocks.append((block_x, block_y, bitmap))

    return blocks


def bitmap_to_pixels(bitmap: bytes) -> List[Tuple[int, int]]:
    """
    将bitmap转换为像素坐标列表

    Args:
        bitmap: 512字节的bitmap数据 (64x64 pixels)

    Returns:
        List of (pixel_x, pixel_y) tuples
    """
    pixels = []

    # bitmap是64x64像素，每行8个字节
    for y in range(BITMAP_WIDTH):
        for byte_idx in range(8):  # 每行8个字节
            byte_offset = y * 8 + byte_idx
            byte_val = bitmap[byte_offset]

            # 检查这个字节的每一位
            for bit_idx in range(8):
                if byte_val & (1 << (7 - bit_idx)):
                    pixel_x = byte_idx * 8 + bit_idx
                    pixel_y = y
                    pixels.append((pixel_x, pixel_y))

    return pixels


def extract_coordinates_from_fwss(fwss_path: str) -> Iterator[Tuple[float, float]]:
    """
    从fwss文件中提取所有地理坐标

    Args:
        fwss_path: fwss文件路径

    Yields:
        (经度, 纬度) 元组
    """
    with zipfile.ZipFile(fwss_path, 'r') as zf:
        # 查找所有bitmap tile文件（在Model/*/目录下）
        bitmap_files = [
            name for name in zf.namelist()
            if name.lower().startswith('model/*/') and '/' == name[-1:] == False
        ]

        print(f"找到 {len(bitmap_files)} 个tile文件")

        for file_path in bitmap_files:
            # 提取文件名
            filename = Path(file_path).name
            if not filename:
                continue

            try:
                # 解码tile ID和坐标
                tile_id = decode_fow_tile_filename(filename)
                tile_x, tile_y = tile_id_to_xy(tile_id)

                # 读取并解析tile数据
                tile_data = zf.read(file_path)
                blocks = parse_tile_data(tile_data)

                print(f"  Tile ({tile_x}, {tile_y}): {len(blocks)} blocks")

                # 遍历每个block
                for block_x, block_y, bitmap in blocks:
                    # 提取bitmap中的像素
                    pixels = bitmap_to_pixels(bitmap)

                    # 将每个像素转换为全局坐标，然后转换为经纬度
                    for pixel_x, pixel_y in pixels:
                        # 计算全局像素坐标
                        global_x = (tile_x * TILE_WIDTH * BITMAP_WIDTH +
                                   block_x * BITMAP_WIDTH + pixel_x)
                        global_y = (tile_y * TILE_WIDTH * BITMAP_WIDTH +
                                   block_y * BITMAP_WIDTH + pixel_y)

                        # 转换为tile坐标系 (0-512)
                        norm_x = global_x / (TILE_WIDTH * BITMAP_WIDTH)
                        norm_y = global_y / (TILE_WIDTH * BITMAP_WIDTH)

                        # 转换为经纬度
                        lng, lat = xy_to_lnglat(norm_x, norm_y)

                        yield lng, lat

            except Exception as e:
                print(f"  警告: 解析文件 {filename} 时出错: {e}")
                continue


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python fwss_parser.py <fwss文件路径> [输出文件.csv]")
        print("\n如果不指定输出文件，将打印到标准输出")
        sys.exit(1)

    fwss_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    if not Path(fwss_path).exists():
        print(f"错误: 文件不存在: {fwss_path}")
        sys.exit(1)

    print(f"正在解析文件: {fwss_path}\n")

    # 提取坐标
    coordinates = list(extract_coordinates_from_fwss(fwss_path))

    print(f"\n共提取到 {len(coordinates)} 个坐标点")

    # 输出结果
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("longitude,latitude\n")
            for lng, lat in coordinates:
                f.write(f"{lng:.8f},{lat:.8f}\n")
        print(f"\n坐标已保存到: {output_path}")
    else:
        print("\n前10个坐标示例:")
        print("经度,纬度")
        for i, (lng, lat) in enumerate(coordinates[:10]):
            print(f"{lng:.8f},{lat:.8f}")

        if len(coordinates) > 10:
            print(f"... (还有 {len(coordinates) - 10} 个坐标)")

    # 计算统计信息
    if coordinates:
        lngs = [coord[0] for coord in coordinates]
        lats = [coord[1] for coord in coordinates]

        print(f"\n统计信息:")
        print(f"  经度范围: {min(lngs):.6f} ~ {max(lngs):.6f}")
        print(f"  纬度范围: {min(lats):.6f} ~ {max(lats):.6f}")


if __name__ == '__main__':
    main()
