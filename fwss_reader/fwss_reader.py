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
import re
import argparse
import csv

# 常量定义
MAP_WIDTH = 512
TILE_WIDTH = 128
TILE_HEADER_SIZE = TILE_WIDTH * TILE_WIDTH * 2
BLOCK_BITMAP_SIZE = 512
BLOCK_SIZE = BLOCK_BITMAP_SIZE + 3
BITMAP_WIDTH = 64

FILENAME_MASK1 = "olhwjsktri"
FILENAME_ENCODING = {char: idx for idx, char in enumerate(FILENAME_MASK1)}
FWSS_TIMESTAMP_PATTERN = re.compile(r"(20\d{6}T\d{6}(?:[+-]\d{4})?)")
FWSS_DATE_PATTERN = re.compile(r"(20\d{6})")


def extract_fwss_date(fwss_path: str) -> str:
    """从快照文件名中提取 YYYYMMDD 日期。"""
    match = FWSS_TIMESTAMP_PATTERN.search(Path(fwss_path).name)
    if match:
        return match.group(1)[:8]
    match = FWSS_DATE_PATTERN.search(Path(fwss_path).name)
    if match:
        return match.group(1)
    raise ValueError(f"无法从文件名提取日期: {fwss_path}")


def find_latest_fwss(fwss_dir: str = None) -> Path:
    """按文件名中的快照时间戳选择最新的 .fwss 文件。"""
    directory = Path(fwss_dir) if fwss_dir else Path(__file__).with_name("fwss")
    candidates = [path for path in directory.glob("*.fwss") if path.is_file()]
    if not candidates:
        raise FileNotFoundError(f"{directory} 中没有找到 .fwss 文件")

    def sort_key(path: Path):
        timestamp = FWSS_TIMESTAMP_PATTERN.search(path.name)
        return (timestamp.group(1) if timestamp else "", path.stat().st_mtime, path.name)

    return max(candidates, key=sort_key)


def write_coordinates_csv(coordinates: List[Tuple[float, float]], output_path: str) -> Path:
    """把坐标列表写入 longitude,latitude CSV。"""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["longitude", "latitude"])
        writer.writerows((f"{lng:.8f}", f"{lat:.8f}") for lng, lat in coordinates)
    return output


def generate_latest_csv(fwss_dir: str = None, output_dir: str = None) -> Path:
    """读取最新快照，生成唯一的最新 loca CSV，并清理旧 loca CSV。"""
    latest_fwss = find_latest_fwss(fwss_dir)
    destination_dir = Path(output_dir) if output_dir else Path(__file__).parent
    date = extract_fwss_date(latest_fwss)
    output = destination_dir / f"loca_{date}_wgs.csv"

    print(f"读取最新 FWSS: {latest_fwss}")
    coordinates = read_fwss(str(latest_fwss))
    write_coordinates_csv(coordinates, output)

    for old_csv in destination_dir.glob("loca_*_wgs.csv"):
        if old_csv != output:
            old_csv.unlink()
            print(f"已删除旧轨迹 CSV: {old_csv}")
    print(f"坐标已保存到: {output}")
    return output


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
    parser = argparse.ArgumentParser(description="读取最新或指定的 FWSS 快照")
    parser.add_argument("fwss_file", nargs="?", help="指定 .fwss 文件；省略时自动选择最新文件")
    parser.add_argument("-o", "--output", help="输出 CSV 路径")
    args = parser.parse_args()

    if args.fwss_file:
        fwss_path = Path(args.fwss_file)
        date = extract_fwss_date(fwss_path)
        default_output_dir = fwss_path.parent.parent if fwss_path.parent.name == "fwss" else fwss_path.parent
        output = Path(args.output) if args.output else default_output_dir / f"loca_{date}_wgs.csv"
        coordinates = read_fwss(str(fwss_path))
        print(f"共读取 {len(coordinates)} 个坐标点")
        write_coordinates_csv(coordinates, output)
        print(f"坐标已保存到: {output}")
    else:
        generate_latest_csv()
