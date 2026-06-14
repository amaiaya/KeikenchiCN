"""
FWSS Reader - 简化的fwss文件读取模块

提供简单的API来读取.fwss文件并返回所有地理坐标
"""

import zipfile
import zlib
import struct
import math
from pathlib import Path
from typing import List, Tuple


# 常量定义
MAP_WIDTH = 512
TILE_WIDTH = 128
TILE_HEADER_SIZE = TILE_WIDTH * TILE_WIDTH * 2
BLOCK_BITMAP_SIZE = 512
BLOCK_SIZE = BLOCK_BITMAP_SIZE + 3
BITMAP_WIDTH = 64

FILENAME_MASK1 = "olhwjsktri"
FILENAME_ENCODING = {char: idx for idx, char in enumerate(FILENAME_MASK1)}


def read_fwss(fwss_path: str) -> List[Tuple[float, float]]:
    """
    读取fwss文件，返回所有地理坐标点的经纬度

    Args:
        fwss_path: fwss文件的路径

    Returns:
        列表，每个元素是(经度, 纬度)元组

    Example:
        >>> coordinates = read_fwss("my_snapshot.fwss")
        >>> print(f"找到 {len(coordinates)} 个坐标点")
        >>> print(f"第一个点: 经度={coordinates[0][0]}, 纬度={coordinates[0][1]}")
    """
    coordinates = []

    with zipfile.ZipFile(fwss_path, 'r') as zf:
        # 查找所有bitmap tile文件
        bitmap_files = [
            name for name in zf.namelist()
            if name.lower().startswith('model/*/') and not name.endswith('/')
        ]

        for file_path in bitmap_files:
            filename = Path(file_path).name
            if not filename:
                continue

            try:
                # 解码文件名获取tile坐标
                tile_id = _decode_filename(filename)
                tile_x = tile_id % MAP_WIDTH
                tile_y = tile_id // MAP_WIDTH

                # 解析tile数据
                tile_data = zf.read(file_path)
                blocks = _parse_tile(tile_data)

                # 处理每个block
                for block_x, block_y, bitmap in blocks:
                    pixels = _bitmap_to_pixels(bitmap)

                    for pixel_x, pixel_y in pixels:
                        # 计算全局坐标
                        global_x = (tile_x * TILE_WIDTH * BITMAP_WIDTH +
                                   block_x * BITMAP_WIDTH + pixel_x)
                        global_y = (tile_y * TILE_WIDTH * BITMAP_WIDTH +
                                   block_y * BITMAP_WIDTH + pixel_y)

                        # 转换为经纬度
                        lng, lat = _xy_to_lnglat(
                            global_x / (TILE_WIDTH * BITMAP_WIDTH),
                            global_y / (TILE_WIDTH * BITMAP_WIDTH)
                        )

                        coordinates.append((lng, lat))

            except Exception as e:
                print(f"警告: 跳过文件 {filename}: {e}")
                continue

    return coordinates


def _decode_filename(filename: str) -> int:
    """解码tile文件名"""
    encoded_id = filename[4:-2]
    decoded_digits = [str(FILENAME_ENCODING[char]) for char in encoded_id]
    return int(''.join(decoded_digits))


def _parse_tile(data: bytes) -> List[Tuple[int, int, bytes]]:
    """解析tile数据"""
    decompressed = zlib.decompress(data)
    header_data = decompressed[:TILE_HEADER_SIZE]
    header = struct.unpack(f'<{TILE_WIDTH * TILE_WIDTH}H', header_data)

    blocks = []
    for i, block_idx in enumerate(header):
        if block_idx > 0:
            block_x = i % TILE_WIDTH
            block_y = i // TILE_WIDTH
            start_offset = TILE_HEADER_SIZE + (block_idx - 1) * BLOCK_SIZE
            bitmap = decompressed[start_offset:start_offset + BLOCK_BITMAP_SIZE]
            blocks.append((block_x, block_y, bitmap))

    return blocks


def _bitmap_to_pixels(bitmap: bytes) -> List[Tuple[int, int]]:
    """将bitmap转换为像素坐标"""
    pixels = []
    for y in range(BITMAP_WIDTH):
        for byte_idx in range(8):
            byte_val = bitmap[y * 8 + byte_idx]
            for bit_idx in range(8):
                if byte_val & (1 << (7 - bit_idx)):
                    pixels.append((byte_idx * 8 + bit_idx, y))
    return pixels


def _xy_to_lnglat(x: float, y: float) -> Tuple[float, float]:
    """坐标转经纬度（Web墨卡托投影）"""
    lng = (x / 512) * 360 - 180
    lat = math.atan(math.sinh(math.pi - (2 * math.pi * y) / 512)) * 180 / math.pi
    return lng, lat


if __name__ == '__main__':
    # 简单测试
    import sys
    if len(sys.argv) > 1:
        coords = read_fwss(sys.argv[1])
        print(f"共读取 {len(coords)} 个坐标点")
        if coords:
            print(f"前5个坐标:")
            for i, (lng, lat) in enumerate(coords[:5]):
                print(f"  {i+1}. ({lng:.6f}, {lat:.6f})")
                
        output_path = sys.argv[2] if len(sys.argv) > 2 else None

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("longitude,latitude\n")
                for lng, lat in coords:
                    f.write(f"{lng:.8f},{lat:.8f}\n")
    else:
        print("用法: python fwss_reader.py <fwss文件路径>")
