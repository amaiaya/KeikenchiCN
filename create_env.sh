#!/usr/bin/env bash
conda create -n geo python=3.12 matplotlib shapely pandas tqdm numpy geopandas folium contextily -c conda-forge -y && conda run -n geo pip install xyconvert