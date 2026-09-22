"""自旋期敏感性检查：只用 30 天暖启动，会不会污染 10 年标定统计量？

动机
----
`code/src/physics/cave_model.py::simulate` 的初值是**外场前 30 天均值**（第 470 行），
而 5 m 岩体导热链的时间常数是**月–年量级**。在做第 71 窟同期对照时发现：
不加自旋期，窟内 RH 最高被抬到 94.67%（实测 80.0%），**加 2 年自旋期后降到 82.50%**
——即 14.67 pp 的"高估"其实是**初值瞬态假象**。

于是必须回答：标定用的 10 年窗口（`calib_cave_params.py`，2010–2019）
是否也带有同样性质的偏差？本脚本用**同一套指标定义**（直接复用
`calib_cave_params` 的 `harmonic` / `daily_range_ratio` / `LIT_TARGETS`），
对比「无自旋（2010–2019 直接跑）」与「自旋 2 年后只统计 2010–2019」两组结果。

结论（2025 实测）
----------------
6 个标定目标中 5 个几乎不动（<0.4%），只有 **`annual_range_ratio_T` 由 0.529 降到 0.468**
（文献 0.559，相对变化 11.5%）——即不加自旋期会**掩盖**模型年阻尼过强的真实偏差。
因此 `calib_cave_params.py` 已改为默认带 2 年自旋期（可用 `CALIB_SPINUP_YEARS=0` 关闭）。

运行：python code/experiments/check_spinup_sensitivity.py
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / ".."))
sys.path.insert(0, str(_ROOT))

from src.physics.cave_model import CaveModel, CaveParams  # noqa: E402
from calib_cave_params import (  # noqa: E402
    LIT_TARGETS,
    daily_range_ratio,
    harmonic,
)

#: 标定得到的最优参数
BEST = dict(
    ventilation_mixing_efficiency=0.30,
    k_sorption_m_s=8.0e-5,
    wall_pore_rh=50.0,
    pillar_depth_m=5.0,
    visitor_occupancy=1.0,
)

EVAL_START, EVAL_END = "2010-01-01", "2019-12-31"
SPINUP_YEARS = 2


def stats(sim: pd.DataFrame, sim_closed: pd.DataFrame, sim_novisit: pd.DataFrame,
          outdoor_eval: pd.DataFrame) -> dict:
    """与 `calib_cave_params.evaluate` 同一套口径的统计量。"""
    a_out, p_out = harmonic(outdoor_eval["T2M"])
    a_in, p_in = harmonic(sim["T_in"])
    lag_rad = (p_out - p_in) % (2 * np.pi)

    day = sim.index.date
    pk_v = sim["RH_in"].groupby(day).max()
    pk_n = sim_novisit["RH_in"].groupby(day).max()

    tr = outdoor_eval["T2M"].max() - outdoor_eval["T2M"].min()
    hr = outdoor_eval["RH2M"].max() - outdoor_eval["RH2M"].min()

    return {
        # --- 6 个文献标定目标 ---
        "diurnal_ratio_open": daily_range_ratio(sim, outdoor_eval),
        "diurnal_ratio_closed": daily_range_ratio(sim_closed, outdoor_eval),
        "annual_range_ratio_T": float((sim["T_in"].max() - sim["T_in"].min()) / tr),
        "annual_range_ratio_RH": float((sim["RH_in"].max() - sim["RH_in"].min()) / hr),
        "RH_in_mean": float(sim["RH_in"].mean()),
        "visitor_RH_peak_gain": float((pk_v - pk_n).mean()),
        # --- 附加诊断 ---
        "_T_in_mean": float(sim["T_in"].mean()),
        "_T_in_min": float(sim["T_in"].min()),
        "_RH_in_min": float(sim["RH_in"].min()),
        "_RH_in_max": float(sim["RH_in"].max()),
        "_annual_lag_days": float(lag_rad / (2 * np.pi) * 365.25),
        "_annual_amp_ratio_T": float(a_in / a_out),
    }


def run(drive: pd.DataFrame, params: CaveParams) -> dict:
    """在 ``drive`` 上仿真，只对 EVAL_START–EVAL_END 统计。"""
    def sim_of(p: CaveParams) -> pd.DataFrame:
        return CaveModel(p).simulate(drive).loc[EVAL_START:EVAL_END]

    return stats(
        sim_of(params),
        sim_of(replace(params, force_door_closed=True)),
        sim_of(replace(params, visitor_occupancy=0.0)),
        drive.loc[EVAL_START:EVAL_END],
    )


def weighted_score(d: dict) -> float:
    """与 `calib_cave_params._score` 一致的加权归一化误差。"""
    w = {"diurnal_ratio_open": 2.0, "diurnal_ratio_closed": 1.5,
         "annual_range_ratio_T": 1.5, "annual_range_ratio_RH": 1.0,
         "RH_in_mean": 2.0, "visitor_RH_peak_gain": 1.0}
    return sum(wt * abs(d[k] - LIT_TARGETS[k][0]) / abs(LIT_TARGETS[k][0])
               for k, wt in w.items())


def main() -> int:
    interim = _ROOT / ".." / "data" / "interim" / "power_hourly_mogao_2001_2025.csv"
    allw = pd.read_csv(interim, index_col=0, parse_dates=True).sort_index()
    p = CaveParams(**BEST)

    print("跑 A（无自旋）：直接 2010–2019 ...")
    a = run(allw.loc[EVAL_START:EVAL_END].copy(), p)

    drive_start = f"{2010 - SPINUP_YEARS}-01-01"
    print(f"跑 B（自旋 {SPINUP_YEARS} 年）：{drive_start}–2019 驱动，只统计 2010–2019 ...")
    b = run(allw.loc[drive_start:EVAL_END].copy(), p)

    rows = [{"指标": k, "文献": tgt, "无自旋": round(a[k], 4),
             "自旋2年": round(b[k], 4), "变化": round(b[k] - a[k], 4)}
            for k, (tgt, _desc) in LIT_TARGETS.items()]
    rows += [{"指标": label, "文献": np.nan, "无自旋": round(a[k], 4),
              "自旋2年": round(b[k], 4), "变化": round(b[k] - a[k], 4)}
             for k, label in [("_T_in_mean", "窟内年均温"), ("_T_in_min", "窟内气温最低"),
                              ("_RH_in_min", "窟内 RH 最低"), ("_RH_in_max", "窟内 RH 最高"),
                              ("_annual_lag_days", "年周期滞后(天)"),
                              ("_annual_amp_ratio_T", "年振幅比 T")]]
    df = pd.DataFrame(rows)
    print("\n" + "=" * 84)
    print("自旋期敏感性：10 年标定窗口（2010–2019）")
    print("=" * 84)
    with pd.option_context("display.unicode.east_asian_width", True,
                           "display.max_colwidth", 32):
        print(df.to_string(index=False))

    sa, sb = weighted_score(a), weighted_score(b)
    max_rel = max(abs(b[k] - a[k]) / max(abs(a[k]), 1e-9) for k in LIT_TARGETS)
    worst = max(LIT_TARGETS, key=lambda k: abs(b[k] - a[k]) / max(abs(a[k]), 1e-9))

    print(f"\n加权归一化误差：无自旋 {sa:.3f} → 自旋 {SPINUP_YEARS} 年 {sb:.3f}")
    print(f"6 个标定目标的最大相对变化：{max_rel * 100:.2f}%（{worst}）")
    print("\n【判读】")
    if max_rel < 0.05:
        print("  → 标定目标受自旋期影响 < 5%，现有标定结论稳健，无需改动。")
    else:
        print(f"  → **{worst}** 受自旋期影响 {max_rel * 100:.1f}%，"
              "已把自旋期并入标定流程（`calib_cave_params.py` 默认 2 年）。")

    out = _ROOT / ".." / "results" / "spinup_sensitivity.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n已写入 {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
