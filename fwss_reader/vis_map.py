import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from folium.plugins import FastMarkerCluster
from tqdm import tqdm
import contextily as ctx
from matplotlib import pyplot as plt

# 读取CSV
df = pd.read_csv('loca_20260613.csv')
df = df.iloc[::100]

# 转换为GeoDataFrame
# m = folium.Map(location=[df['latitude'].mean(), df['longitude'].mean()], zoom_start=10)
# FastMarkerCluster(data=df[['latitude', 'longitude']].values.tolist()).add_to(m)
# m.save('map_cluster.html')

gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df['longitude'], df['latitude']),
    crs='EPSG:4326'
).to_crs(epsg=3857)

ax = gdf.plot(figsize=(12, 10), markersize=2, alpha=0.5, color='red')
ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)
ax.set_axis_off()
plt.savefig('map_with_basemap.png', dpi=200, bbox_inches='tight')