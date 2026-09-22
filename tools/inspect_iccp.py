"""检视 ICCP NetCDF 数据集结构，判断能否用于跨气候区外部效度验证。"""
from __future__ import annotations

import numpy as np
import xarray as xr

NC = "code/data/raw/iccp/extracted/israel_caves-2025.nc"


def main() -> None:
    ds = xr.open_dataset(NC, engine="h5netcdf")
    print("=" * 72)
    print("维度")
    for k, v in ds.dims.items():
        print(f"  {k:22s} {v}")
    print("\n坐标")
    for k, c in ds.coords.items():
        vals = np.asarray(c.values)
        head = vals[:3]
        tail = vals[-2:]
        unit = c.attrs.get("units", "")
        print(f"  {k:22s} shape={vals.shape} {unit}")
        print(f"      head={head}  tail={tail}")
    print("\n数据变量")
    for k, v in ds.data_vars.items():
        print(f"  {k:22s} dims={v.dims} shape={v.shape} "
              f"units={v.attrs.get('units', '?')}")
        print(f"      long_name={str(v.attrs.get('long_name', ''))[:90]}")
    print("\n全局属性（选摘）")
    for k in list(ds.attrs)[:25]:
        print(f"  {k}: {str(ds.attrs[k])[:120]}")
    ds.close()


if __name__ == "__main__":
    main()
