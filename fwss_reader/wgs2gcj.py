from xyconvert import wgs2gcj
import numpy as np
import pandas as pd


df = pd.read_csv('loca_20260613.csv')
wgs = df.to_numpy()
gcj = wgs2gcj(wgs)

df = pd.DataFrame(gcj, columns=df.columns)
df.to_csv('loca_20260613_gcj.csv', index=False, float_format='%.7f')