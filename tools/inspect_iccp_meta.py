"""检视 ICCP 洞穴元数据、logger 映射与数据覆盖度，为外部效度验证定方案。"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import xarray as xr

warnings.filterwarnings("ignore")

NC = "code/data/raw/iccp/extracted/israel_caves-2025.nc"


def s(v) -> str:
    a = np.asarray(v)
    if a.dtype.kind in "OUS":
        return str(a.item()) if a.ndim == 0 else " ".join(str(x) for x in a.ravel() if str(x) != "nan")
    return str(a)


def main() -> None:
    ds = xr.open_dataset(NC, engine="h5netcdf")

    print("=" * 78)
    print("洞穴元数据")
    print("=" * 78)
    caves = pd.DataFrame({
        "cave": ds["cave"].values,
        "name": [s(x) for x in ds["Cave_Name"].values],
        "region": [s(x) for x in ds["Region"].values],
        "lat": ds["Latitude"].values,
        "lon": ds["Longitude"].values,
        "elev": ds["Elevation"].values,
        "len_m": ds["Total_Length"].values,
        "ent_w": ds["Main_Entrance_Width"].values,
        "ent_h": ds["Main_Entrance_Height"].values,
        "env": [s(x)[:34] for x in ds["Current_Environment"].values],
        "litho": [s(x)[:30] for x in ds["Lithostratigraphy"].values],
    })
    print(caves.to_string(index=False))

    print("\n" + "=" * 78)
    print("logger -> cave 映射 与 数据覆盖")
    print("=" * 78)
    mapping = np.asarray(ds["logger_cave_mapping"].values)
    T = np.asarray(ds["Temperature"].values)
    RH = np.asarray(ds["Relative_Humidity"].values)
    lz = np.asarray(ds["Lighting_Zone"].values)

    rows = []
    for li in range(mapping.shape[1]):
        col = mapping[:, li]
        ci = int(np.argmax(col)) if col.sum() > 0 else -1
        t = T[li]
        rh = RH[li]
        rows.append({
            "logger": li + 1,
            "cave": ci + 1 if ci >= 0 else None,
            "name": caves.loc[ci, "name"] if ci >= 0 else "",
            "light_zone": s(lz[li])[:16],
            "T_valid": int(np.isfinite(t).sum()),
            "RH_valid": int(np.isfinite(rh).sum()),
            "T_mean_C": round(float(np.nanmean(t)) - 273.15, 2),
            "T_min_C": round(float(np.nanmin(t)) - 273.15, 2),
            "T_max_C": round(float(np.nanmax(t)) - 273.15, 2),
            "RH_mean": round(float(np.nanmean(rh)), 1),
            "RH_min": round(float(np.nanmin(rh)), 1),
            "RH_max": round(float(np.nanmax(rh)), 1),
        })
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    print("\n时间范围:", str(ds["time"].values[0])[:19], "->", str(ds["time"].values[-1])[:19])
    print("总小时数:", ds.sizes["time"])
    ds.close()


if __name__ == "__main__":
    main()
