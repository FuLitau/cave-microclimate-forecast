"""只读审计：统计 ICCP 原始 nc 里的洞窟数 / 记录仪数，并复现 validate_iccp.py 的筛选链。"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

warnings.filterwarnings("ignore")

NC = Path("code/data/raw/iccp/extracted/israel_caves-2025.nc")
MIN_VALID = 5000

ds = xr.open_dataset(NC, engine="h5netcdf")
print("=== 变量 ===")
for k, v in ds.variables.items():
    print(f"  {k}: dims={v.dims} shape={v.shape}")

names = [str(x) for x in np.asarray(ds["Cave_Name"].values, dtype=object)]
zones = [str(x) for x in np.asarray(ds["Lighting_Zone"].values, dtype=object)]
mapping = np.asarray(ds["logger_cave_mapping"].values)
T = np.asarray(ds["Temperature"].values) - 273.15
RH = np.asarray(ds["Relative_Humidity"].values)

print(f"\n=== 记录仪总数 len(zones) = {len(zones)} ===")
print(f"Cave_Name 数组长度 = {len(names)}")
uniq = sorted(set(names))
print(f"唯一洞名数 = {len(uniq)}: {uniq}")
print(f"唯一 Lighting_Zone 取值 = {sorted(set(zones))}")
print(f"logger_cave_mapping shape = {mapping.shape}")

logger_cave = {}
for li in range(mapping.shape[1]):
    col = mapping[:, li]
    logger_cave[li] = int(np.argmax(col)) if col.sum() > 0 else -1

valid = [li for li in range(len(zones))
         if np.isfinite(RH[li]).sum() >= MIN_VALID and np.isfinite(T[li]).sum() >= MIN_VALID]

print(f"\n=== 通过 MIN_VALID={MIN_VALID} 的记录仪数 = {len(valid)} ===")

# 每洞的记录仪分布（用 mapping 的 argmax 归洞，与 validate_iccp.py 一致）
print("\n=== 逐洞（ci+1 = 文档里的洞号）===")
print(f"{'cave':>4} {'name':<16} {'lg_total':>8} {'lg_valid':>8} {'Light':>6} {'Dark/Twi':>8} "
      f"{'maxlen_L':>9} {'maxlen_D':>9} {'n_pair':>7} {'进入统计':>8}  跳过原因")
rows = []
for ci in range(len(names)):
    lg_all = [li for li in range(len(zones)) if logger_cave[li] == ci]
    lg = [li for li in valid if logger_cave[li] == ci]
    light = [li for li in lg if zones[li] == "Light"]
    dark = [li for li in lg if zones[li] in ("Dark", "Twilight")]
    zc = pd.Series([zones[li] for li in lg_all]).value_counts().to_dict()
    reason = ""
    if not light or not dark:
        reason = f"无 Light 或 无 Dark/Twilight 记录仪（该洞 zone 分布={zc}）"
    n_pair = -1
    if light and dark:
        li_l = max(light, key=lambda i: np.isfinite(RH[i]).sum())
        li_d = max(dark, key=lambda i: np.isfinite(RH[i]).sum())
        Ln = int(np.isfinite(RH[li_l]).sum())
        Dn = int(np.isfinite(RH[li_d]).sum())
        n_pair = min(Ln, Dn)
        if n_pair < 2000:
            reason = f"配对有效样本 {n_pair} < 2000"
    nl = max([int(np.isfinite(RH[i]).sum()) for i in light], default=0)
    nd = max([int(np.isfinite(RH[i]).sum()) for i in dark], default=0)
    used = "是" if (light and dark and n_pair >= 2000) else "否"
    print(f"{ci+1:>4} {names[ci][:16]:<16} {len(lg_all):>8} {len(lg):>8} {len(light):>6} "
          f"{len(dark):>8} {nl:>9} {nd:>9} {n_pair:>7} {used:>8}  {reason}")
    rows.append((ci + 1, names[ci], used, reason))

print("\n=== 汇总 ===")
print("进入统计的洞（去掉 target_sd<0.5 之前）:", [r[0] for r in rows if r[2] == "是"])
print("从未进入的洞:", [(r[0], r[1], r[3]) for r in rows if r[2] == "否"])

# 各洞 Light/Dark 记录仪明细
print("\n=== 全部记录仪明细（logger 序号=数组下标+1）===")
for li in range(len(zones)):
    ok = np.isfinite(RH[li]).sum()
    print(f"  logger {li+1:>3}  cave={logger_cave[li]+1:>3}({names[logger_cave[li]][:14]:<14}) "
          f"zone={zones[li]:<9} n_RH={int(ok):>6} valid={li in valid}")
ds.close()
