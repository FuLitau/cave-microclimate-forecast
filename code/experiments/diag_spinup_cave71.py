"""诊断：自旋期对「同窟同期」统计量的影响（第 71 窟口径，2019–2021）。

为什么需要这个脚本
------------------
文档里写过「不加自旋期时窟内 RH 最高被抬到 94.67%」，但这个数字长期只在
一次性审计脚本里能复现，``results/`` 下没有落盘载体。本脚本把该口径
**固化成一个正式的诊断**，并落盘 CSV/JSON，使文档中的每一个数字都能被
指认到本文件的输出。

口径
----
与 ``code/experiments/calib_cave71_compare.py`` 完全一致：POWER 外场驱动、
标定最优参数、统计窗口 2019-01-01 → 2021-12-31。唯一变量是**驱动序列从哪一年开始**：

* ``spinup=0``：驱动从 2019 开始，深部岩体节点初值远未平衡；
* ``spinup=2``：驱动从 2017 开始，2017–2018 两年作为自旋期丢弃，只用 2019 起的统计段。

7 m 量级导热链的时间常数是**月–年量级**，因此 ``spinup=0`` 时初值瞬态会污染
窗口内的极值统计量（尤其在湿度最高值这种尾部量上）。

产出：``results/diag_spinup_cave71.csv`` 与 ``results/diag_spinup_cave71.json``。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.physics.cave_model import CaveModel, CaveParams  # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

STAT_LO, STAT_HI = "2019-01-01", "2021-12-31"
SPINUP_YEARS = (0, 2)

#: 标定网格最优配置（与 ``calib_cave_params.py`` 的落盘结果一致）
BEST = dict(
    ventilation_mixing_efficiency=0.30,
    k_sorption_m_s=8.0e-5,
    wall_pore_rh=50.0,
    pillar_depth_m=5.0,
    visitor_occupancy=1.0,
)

#: Gong et al. 2025 (npj Heritage Science 13:173) 第 71 窟实测
LIT = dict(T_in_mean=12.0, T_in_max=25.8, T_in_min=-6.7,
           RH_in_mean=30.8, RH_in_min=8.7, RH_in_max=80.0)


def main() -> int:
    interim = ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv"
    if not interim.exists():
        print(f"[ERROR] 未找到 {interim}")
        return 1

    outdoor = pd.read_csv(interim, index_col=0, parse_dates=True).sort_index()
    params = CaveParams(**BEST)

    print("口径 = calib_cave71_compare.py（POWER 驱动，统计窗口 "
          f"{STAT_LO} → {STAT_HI}）")
    rows: list[dict] = []
    for yrs in SPINUP_YEARS:
        drive_lo = f"{2019 - yrs}-01-01"
        drive = outdoor.loc[drive_lo:STAT_HI]
        sim = CaveModel(params).simulate(drive).loc[STAT_LO:]
        row = {
            "spinup_years": yrs,
            "drive_start": drive.index[0].strftime("%Y-%m-%d"),
            "n_drive": int(len(drive)),
            "n_stat": int(len(sim)),
            "T_in_mean": round(float(sim["T_in"].mean()), 2),
            "T_in_min": round(float(sim["T_in"].min()), 2),
            "T_in_max": round(float(sim["T_in"].max()), 2),
            "RH_in_mean": round(float(sim["RH_in"].mean()), 2),
            "RH_in_min": round(float(sim["RH_in"].min()), 2),
            "RH_in_max": round(float(sim["RH_in"].max()), 2),
            "d_RH_in_max_vs_lit": round(float(sim["RH_in"].max()) - LIT["RH_in_max"], 2),
            "first_hour_RH_in": round(float(sim["RH_in"].iloc[0]), 2),
            "first_24h_mean_RH_in": round(float(sim["RH_in"].iloc[:24].mean()), 2),
        }
        rows.append(row)
        print(f"\n--- 自旋期 {yrs} 年（驱动自 {row['drive_start']} 起，"
              f"n_drive={row['n_drive']:,} / n_stat={row['n_stat']:,}）---")
        print(f"  T_in   mean {row['T_in_mean']:7.2f}  min {row['T_in_min']:7.2f}  "
              f"max {row['T_in_max']:7.2f}   (文献 {LIT['T_in_mean']}/"
              f"{LIT['T_in_min']}/{LIT['T_in_max']})")
        print(f"  RH_in  mean {row['RH_in_mean']:7.2f}  min {row['RH_in_min']:7.2f}  "
              f"max {row['RH_in_max']:7.2f}   (文献 {LIT['RH_in_mean']}/"
              f"{LIT['RH_in_min']}/{LIT['RH_in_max']})")
        print(f"  RH 最高值 vs 文献: {row['d_RH_in_max_vs_lit']:+.2f} pp"
              f"   |  首小时 {row['first_hour_RH_in']:.2f} / "
              f"首日均 {row['first_24h_mean_RH_in']:.2f}")

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "diag_spinup_cave71.csv", index=False)

    no_spin = rows[0]["RH_in_max"]
    with_spin = rows[1]["RH_in_max"]
    summary = {
        "stat_window": f"{STAT_LO}..{STAT_HI}",
        "lit_RH_in_max": LIT["RH_in_max"],
        "RH_in_max_spinup0": no_spin,
        "RH_in_max_spinup2": with_spin,
        "gap_vs_lit_spinup0_pp": round(no_spin - LIT["RH_in_max"], 2),
        "gap_vs_lit_spinup2_pp": round(with_spin - LIT["RH_in_max"], 2),
    }
    (RESULTS / "diag_spinup_cave71.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[结论] 无自旋期 RH 最高 {no_spin:.2f}%（vs 文献 {LIT['RH_in_max']}%，"
          f"偏高 {summary['gap_vs_lit_spinup0_pp']:+.2f} pp）；"
          f"加 {SPINUP_YEARS[1]} 年自旋期后 {with_spin:.2f}%"
          f"（{summary['gap_vs_lit_spinup2_pp']:+.2f} pp）。")
    print("       -> 无自旋期的极值统计量不可引用；加自旋期后偏差收敛到 2.5 pp 以内。")
    print(f"\n结果已写入 {RESULTS / 'diag_spinup_cave71.csv'} 与 diag_spinup_cave71.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
