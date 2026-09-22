"""用默认参数跑一次标定核对，确认窟内统计量落在文献约束内。

**本脚本必须带自旋期，否则结果不可引用。**
窟内物理模型是有记忆的：岩体导热的时间常数以月计，从评估窗口起点冷启动
等于让窟内状态从"任意初值"开始弛豫，窗口前几天到前一两年的窟内状态根本
还没进入物理轨道。实测影响是**把窟内 RH 极值整体抬高**——不带自旋期时
``annual_range_ratio_T`` 0.5291（带自旋期 0.4683）、``RH_in_max`` 90.41%
（带自旋期 82.50%），差 8 个百分点，足以让"与文献对照通过/不通过"翻面。

``experiments/calib_cave_params.py`` 的 ``evaluate(outdoor, params, drive=...)``
就是为此设计的：``drive`` 是比评估窗口更早开始的驱动序列，模型在它上面
完整模拟，只在最后 ``.loc[评估窗口]`` 取评估片段。本脚本沿用同一约定，
并把"不带自旋期"的结果一并打印出来作为对照——**两份都打，但只引用带自旋期的**。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.calib_cave_params import evaluate, harmonic  # noqa: E402
from src.physics.cave_model import CaveParams  # noqa: E402

EVAL_START, EVAL_END = "2010-01-01", "2019-12-31"

od_all = pd.read_csv(ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                     index_col=0, parse_dates=True).sort_index()
od = od_all.loc[EVAL_START:EVAL_END]

spinup_years = int(os.environ.get("CALIB_SPINUP_YEARS", "2"))
drive = od_all.loc[f"{int(EVAL_START[:4]) - spinup_years}-01-01":EVAL_END]

print(f"评估窗口 {od.index[0]:%Y-%m-%d} → {od.index[-1]:%Y-%m-%d}"
      f"（{len(od):,} h）；自旋期 {spinup_years} 年，"
      f"驱动 {drive.index[0]:%Y-%m-%d} → {drive.index[-1]:%Y-%m-%d}"
      f"（{len(drive):,} h）")

p = CaveParams()
r = evaluate(od, p, drive=drive)
print("\n默认参数标定核对（**带自旋期，引用此列**）")
print("-" * 60)
for k, v in r.items():
    print(f"  {k:24s} {v}")

r0 = evaluate(od, p)  # 不带自旋期，仅作对照
print("\n对照：不带自旋期（冷启动，**不要引用**）")
print("-" * 60)
for k in r:
    if k in r0:
        delta = ""
        try:
            delta = f"   （Δ {float(r0[k]) - float(r[k]):+.4f}）"
        except (TypeError, ValueError):
            delta = ""
        print(f"  {k:24s} {r0[k]}{delta}")

a_out, _ = harmonic(od["T2M"])
print(f"\n  窟外年均温 {od['T2M'].mean():.2f} degC -> 窟内 {r['T_in_mean']:.2f} degC "
      f"(差 {r['T_in_mean'] - od['T2M'].mean():+.2f} K)")
print(f"  窟外年振幅 {a_out:.2f} degC -> 窟内 {a_out * r['annual_amp_ratio_T']:.2f} degC")

print("\n  文献实测对照（Gong et al. 2025, npj HS 13:173，第 71 窟，2019-2021 逐时）：")
print("    窟内 RH  年均 30.8% / 最低 8.7% / 最高 80.0%")
print("    日较差比 开门 0.276 / 闭窟 0.043（2020 疫情闭窟，天然双状态对照）")
print("    年极差比 T 0.559 / RH 0.722")
print("  文献对照（Zhang & Wang 2023, Heritage Science 11:158，第 87 窟）：")
print("    窟内月均温 3.0-20.3 degC（年均约 11.7），窟外 -5.1-26.9（年均约 10.9）")
print("    -> 窟内仅比窟外高约 +0.75 K；年周期 T 滞后约 1 个月")
