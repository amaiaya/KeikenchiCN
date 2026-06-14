# FWSS文件解析器

用于解析Fog of World应用的`.fwss`快照文件，提取其中的地理坐标（经纬度）。

## 实现原理

### FWSS文件结构

FWSS（Fog of World Snapshot）文件是一个ZIP压缩包，包含以下结构：

```
Snapshot.fwss (ZIP文件)
├── Model/*/        # 存放bitmap tiles（位图瓦片）
├── Model/#/        # 存放hash tiles和元数据
└── Model/~/        # 存放layer tiles（图层瓦片）
```

### 坐标系统

1. **全局坐标系统**：使用Web墨卡托投影（Web Mercator Projection）
2. **分层结构**：
   - 全球地图被分为 512×512 个tiles（瓦片）
   - 每个tile包含 128×128 个blocks（块）
   - 每个block包含 64×64 个pixels（像素点）
   - 每个像素代表一个地理位置点

3. **坐标转换**：
   ```
   像素坐标 → tile坐标 (0-512) → 经纬度
   
   经度 = (x / 512) * 360 - 180
   纬度 = atan(sinh(π - 2πy/512)) * 180/π
   ```

### 解析流程

1. **解压ZIP文件**：提取`Model/*/`目录下的所有bitmap文件
2. **解码文件名**：文件名经过特殊编码，需要解码为tile ID
3. **解析tile数据**：
   - 使用zlib解压缩tile数据
   - 读取header（前32768字节），包含block索引信息
   - 提取每个block的bitmap数据（512字节）
4. **解析bitmap**：每个字节的每一位代表一个像素是否被访问过
5. **坐标转换**：将像素坐标转换为全局坐标，再转换为经纬度

## 使用方法

### 方法1：命令行工具（详细版）

```bash
# 打印到标准输出
python fwss_parser.py your_snapshot.fwss

# 保存到CSV文件
python fwss_parser.py your_snapshot.fwss output.csv
```

**输出示例**：
```
正在解析文件: Snapshot-20260101T120000+0800.fwss

找到 156 个tile文件
  Tile (243, 105): 234 blocks
  Tile (243, 106): 189 blocks
  ...

共提取到 458932 个坐标点

统计信息:
  经度范围: 116.283450 ~ 116.512830
  纬度范围: 39.894560 ~ 40.023450

坐标已保存到: output.csv
```

### 方法2：作为Python模块使用（简洁版）

```python
from fwss_reader import read_fwss

# 读取fwss文件，获取所有坐标
coordinates = read_fwss("your_snapshot.fwss")

# coordinates是一个列表，每个元素是(经度, 纬度)元组
print(f"共有 {len(coordinates)} 个坐标点")

# 访问具体坐标
for lng, lat in coordinates[:10]:
    print(f"经度: {lng:.6f}, 纬度: {lat:.6f}")

# 示例：保存为GeoJSON格式
import json

geojson = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat]
            },
            "properties": {}
        }
        for lng, lat in coordinates
    ]
}

with open("output.geojson", "w") as f:
    json.dump(geojson, f)
```

### 方法3：可视化示例

使用matplotlib绘制坐标点：

```python
from fwss_reader import read_fwss
import matplotlib.pyplot as plt

# 读取坐标
coordinates = read_fwss("your_snapshot.fwss")

# 分离经纬度
lngs = [coord[0] for coord in coordinates]
lats = [coord[1] for coord in coordinates]

# 绘制散点图
plt.figure(figsize=(12, 8))
plt.scatter(lngs, lats, s=1, alpha=0.5)
plt.xlabel('经度 (Longitude)')
plt.ylabel('纬度 (Latitude)')
plt.title('Fog of World 访问位置')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('map.png', dpi=300)
plt.show()
```

使用folium创建交互式地图：

```python
from fwss_reader import read_fwss
import folium
from folium.plugins import HeatMap

# 读取坐标
coordinates = read_fwss("your_snapshot.fwss")

# 计算中心点
center_lat = sum(c[1] for c in coordinates) / len(coordinates)
center_lng = sum(c[0] for c in coordinates) / len(coordinates)

# 创建地图
m = folium.Map(location=[center_lat, center_lng], zoom_start=12)

# 添加热力图
heat_data = [[lat, lng] for lng, lat in coordinates]
HeatMap(heat_data, radius=10).add_to(m)

# 保存
m.save('heatmap.html')
print("热力图已保存到 heatmap.html")
```

## 文件说明

- **fwss_parser.py**：完整的命令行工具，带详细输出和统计信息
- **fwss_reader.py**：简洁的模块版本，适合在代码中导入使用

## 技术细节

### 文件名编码

Fog of World使用特殊的编码方式生成文件名：
```
格式: [MD5前缀(4字符)][编码的ID][校验和(2字符)]
编码字符集: "olhwjsktri" (对应数字0-9)
```

### Bitmap编码

每个block的bitmap是512字节（64×64像素）：
- 每行64像素 = 8字节
- 每个字节的位从高到低（bit 7到bit 0）代表8个连续像素
- 位值为1表示该位置被访问过

### 坐标精度

- 全局像素总数：512 × 128 × 64 = 4,194,304 像素/边
- 在赤道附近，每个像素约代表 10米 的精度

## 依赖

仅依赖Python标准库：
- `zipfile` - ZIP文件处理
- `zlib` - 数据解压缩
- `struct` - 二进制数据解析
- `math` - 数学计算

无需安装任何第三方包！

## 相关代码

原始实现位于：
- `fog-machine/editor/src/utils/FwssArchive.ts` - FWSS导入/导出
- `fog-machine/editor/src/utils/FogMap.ts` - 坐标转换
- `fog-machine/editor/src/utils/FowTile.ts` - Tile和Block数据结构

## 许可

与Fog of World项目使用相同的许可证。
