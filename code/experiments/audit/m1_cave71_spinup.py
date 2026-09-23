"""M1 定量核对：复刻 calib_cave71_compare.py 的口径（2019-2021 同窟同期），
对比「无自旋期」与「2 年自旋期」下窟内 RH 最高值。

纯只读：不写 results/，不修改任何仓库文件。
运行：python code/experiments/_audit_tmp/m1_cave71_spinup.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]  # code/
sys.path.insert(0, str(_ROOT))

from src.physics.cave_model import CaveModel, CaveParams  # noqa: E402

BEST = dict(
    ventilation_mixing_efficiency=0.30,
    k_sorption_m_s=8.0e-5,
    wall_pore_rh=50.0,
    pillar_depth_m=5.0,
    visitor_occupancy=1.0,
)
LIT = dict(T_in_mean=12.0, T_in_max=25.8, T_in_min=-6.7,
           RH_in_mean=30.8, RH_in_min=8.7, RH_in_max=80.0)


def main() -> int:
    interim = _ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv"
    oa = pd.read_csv(interim, index_col=0, parse_dates=True).sort_index()
    p = CaveParams(**BEST)

    print("口径 = calib_cave71_compare.py（POWER 驱动，统计窗口 2019-01-01→2021-12-31）")
    for yrs in (0, 2):
        drive = oa.loc[f"{2019 - yrs}-01-01":"2021-12-31"]
        sim = CaveModel(p).simulate(drive).loc["2019-01-01":]
        print(f"\n--- CALIB_SPINUP_YEARS={yrs} ---")
        print(f"  驱动窗口 {drive.index[0]:%Y-%m-%d} -> {drive.index[-1]:%Y-%m-%d} "
              f"n_drive={len(drive):,} n_stat={len(sim):,}")
        print(f"  T_in  mean {sim['T_in'].mean():7.2f}  min {sim['T_in'].min():7.2f}  "
              f"max {sim['T_in'].max():7.2f}   (lit {LIT['T_in_mean']}/{LIT['T_in_min']}/{LIT['T_in_max']})")
        print(f"  RH_in mean {sim['RH_in'].mean():7.2f}  min {sim['RH_in'].min():7.2f}  "
              f"max {sim['RH_in'].max():7.2f}   (lit {LIT['RH_in_mean']}/{LIT['RH_in_min']}/{LIT['RH_in_max']})")
        print(f"  差值 vs 文献: RHmax {sim['RH_in'].max() - LIT['RH_in_max']:+.2f} pp | "
              f"RHmean {sim['RH_in'].mean() - LIT['RH_in_mean']:+.2f} pp | "
              f"Tmin {sim['T_in'].min() - LIT['T_in_min']:+.2f} K")
        head = sim["RH_in"].head(24 * 20)
        print(f"  前 20 天 RH_in: 首小时 {head.iloc[0]:.2f} -> 首日均 {sim['RH_in'].iloc[:24].mean():.2f} "
              f"-> 20日均 {head.mean():.2f}; 全期前 0.1% 分位 {sim['RH_in'].quantile(0.001):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
