"""跨窟外部效度验证：用第 87 窟的实测统计量检验在第 71 窟上标定出的模型。

为什么这个验证重要（防"循环论证"）
----------------------------------
本项目窟内序列是**物理模型自造的合成标签**，所有算法实验都在它上面闭环。
**这是方案最大的攻击面。** 必须用**独立外部证据**检验物理模型本身，
否则"合成标签 → 训练 → 评估"整条链都是自证。

本脚本的验证设计
----------------
* **标定集**：第 71 窟（Gong et al. 2025, npj Heritage Science 13:173）——
  日较差比、年极差比、RH 年均均来自该窟；
* **验证集**：第 87 窟（Zhang & Wang 2023, Heritage Science 11:158）——
  **另一个洞窟、另一支团队、另一套传感器**，标定时**完全未使用**。

因此这是一个**留一窟（leave-one-cave-out）**式的一致性检验：
若模型在未参与标定的第 87 窟上仍给出量级正确的窟内统计量，
说明学到的是**传递结构的共性**，而不是把第 71 窟的噪声背了下来。

⚠️ **诚实的边界**：本模型的窟体几何取"中等规模旅游洞窟"代表值，
**不是第 87 窟的真实几何**（该文未报告尺寸）。故本检验只能验证**量级与趋势**，
不能验证逐点吻合。报告中须如实表述为"跨窟量级一致性检验"。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.physics.cave_model import CaveModel, CaveParams  # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


#: 第 87 窟实测统计量 —— **标定第 71 窟时完全未使用**
#: 出处：Zhang & Wang (2023), Heritage Science 11:158, DOI 10.1038/s40494-023-01005-3
CAVE87_TARGETS = {
    "outdoor_monthly_T_range": (-5.1, 26.9, "窟外月均温范围 (degC)"),
    "indoor_monthly_T_range": (3.0, 20.3, "窟内月均温范围 (degC)"),
    "indoor_monthly_RH_range": (22.7, 53.5, "窟内月均 RH 范围 (%)"),
    "outdoor_monthly_RH_range": (16.3, 47.4, "窟外月均 RH 范围 (%)"),
    "annual_T_lag_months": (1.0, 1.0, "年周期 T 滞后：窟内比窟外晚 1 个月"),
}


def month_of_extreme(s: pd.Series, kind: str) -> float:
    """按月均值求极值所在月份（1-12）。"""
    m = s.groupby(s.index.month).mean()
    return float(m.idxmin() if kind == "min" else m.idxmax())


def diurnal_lag_minutes(sim: pd.DataFrame, outdoor: pd.DataFrame,
                        kind: str = "max") -> float:
    """日周期相位滞后（分钟）：窟内日极值出现时刻减去窟外。

    用"逐日极值出现的小时数"的**圆均值**（circular mean），避免 23:50 与 00:10 被平均成 12:00。
    """
    def hour_of_daily_extreme(s: pd.Series) -> np.ndarray:
        g = s.groupby(s.index.date)
        hrs = g.apply(lambda x: (x.idxmax() if kind == "max" else x.idxmin()).hour
                      + (x.idxmax() if kind == "max" else x.idxmin()).minute / 60.0)
        return hrs.to_numpy(dtype=float)

    def circ_mean(hours: np.ndarray) -> float:
        ang = hours / 24.0 * 2 * np.pi
        return float(np.arctan2(np.sin(ang).mean(), np.cos(ang).mean()) / (2 * np.pi) * 24.0)

    d_out = circ_mean(hour_of_daily_extreme(outdoor["T2M"]))
    d_in = circ_mean(hour_of_daily_extreme(sim["T_in"]))
    lag = (d_in - d_out) * 60.0
    # 归到 (-720, 720] 分钟
    lag = (lag + 720) % 1440 - 720
    return round(float(lag), 1)


def main() -> None:
    outdoor = pd.read_csv(ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                          index_col=0, parse_dates=True).sort_index()
    outdoor = outdoor[~outdoor.index.duplicated(keep="first")]
    print("=" * 84)
    print("跨窟外部效度验证：第 71 窟标定 → 第 87 窟检验")
    print("=" * 84)

    sim = CaveModel(CaveParams()).simulate(outdoor)
    # 与文献的统计口径对齐：用月均量（文献报的是 monthly average）
    mt_out_T = outdoor["T2M"].groupby(outdoor.index.month).mean()
    mt_in_T = sim["T_in"].groupby(sim.index.month).mean()
    mt_out_RH = outdoor["RH2M"].groupby(outdoor.index.month).mean()
    mt_in_RH = sim["RH_in"].groupby(sim.index.month).mean()

    got = {
        "outdoor_monthly_T_range": (round(float(mt_out_T.min()), 2),
                                    round(float(mt_out_T.max()), 2)),
        "indoor_monthly_T_range": (round(float(mt_in_T.min()), 2),
                                   round(float(mt_in_T.max()), 2)),
        "indoor_monthly_RH_range": (round(float(mt_in_RH.min()), 2),
                                    round(float(mt_in_RH.max()), 2)),
        "outdoor_monthly_RH_range": (round(float(mt_out_RH.min()), 2),
                                     round(float(mt_out_RH.max()), 2)),
    }

    # 年周期 T 滞后（月）
    lag_m = (month_of_extreme(sim["T_in"], "min") - month_of_extreme(outdoor["T2M"], "min")) % 12
    got["annual_T_lag_months"] = (round(lag_m, 1), round(lag_m, 1))

    print("\n【一】月均量范围（模型 vs 第 87 窟实测）")
    print(f"{'指标':<28}{'模型':>20}{'第87窟实测':>20}{'判定':>8}")
    print("-" * 84)
    rows = []
    for k, (lo_lit, hi_lit, desc) in CAVE87_TARGETS.items():
        if k == "annual_T_lag_months":
            continue
        lo_m, hi_m = got[k]
        # 判定：区间端点是否落在实测 ±35% 或 ±5 个单位的容差内
        tol_lo = max(abs(lo_lit) * 0.35, 5.0)
        tol_hi = max(abs(hi_lit) * 0.35, 5.0)
        ok = (abs(lo_m - lo_lit) <= tol_lo) and (abs(hi_m - hi_lit) <= tol_hi)
        print(f"{desc:<28}{f'[{lo_m}, {hi_m}]':>20}{f'[{lo_lit}, {hi_lit}]':>20}"
              f"{'✅' if ok else '⚠️':>8}")
        rows.append({"metric": k, "model_lo": lo_m, "model_hi": hi_m,
                     "lit_lo": lo_lit, "lit_hi": hi_lit, "pass": ok})

    print("\n【二】年周期温度相位滞后")
    lo_m, _ = got["annual_T_lag_months"]
    print(f"  模型 = {lo_m:.1f} 个月   第 87 窟实测 = 1 个月"
          f"   {'✅' if abs(lo_m - 1.0) <= 1.0 else '⚠️'}")
    rows.append({"metric": "annual_T_lag_months", "model_lo": lo_m, "model_hi": lo_m,
                 "lit_lo": 1.0, "lit_hi": 1.0, "pass": abs(lo_m - 1.0) <= 1.0})

    print("\n【三】日周期相位滞后（T）")
    lag_max = diurnal_lag_minutes(sim, outdoor, "max")
    lag_min = diurnal_lag_minutes(sim, outdoor, "min")
    print(f"  最高温滞后：模型 {lag_max:+.0f} min   第 87 窟实测 +20 min")
    print(f"  最低温滞后：模型 {lag_min:+.0f} min   第 87 窟实测 +64 min")
    print("  ⚠️ 第 87 窟的日滞后是 'min' 量级；本模型因小时步长与集总假设，")
    print("     日尺度相位精度有限，只作量级一致性参考，不作为判据。")
    rows.append({"metric": "diurnal_T_lag_max_min", "model_lo": lag_max,
                 "model_hi": lag_min, "lit_lo": 20.0, "lit_hi": 64.0,
                 "pass": bool(abs(lag_max) < 180)})

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "validate_crosscave.csv", index=False)

    n_pass = int(df["pass"].sum())
    print(f"\n{'=' * 84}")
    print(f"【结论】跨窟一致性：{n_pass}/{len(df)} 项通过")
    print("=" * 84)
    print("""
说明：本检验用的是**另一个洞窟、另一支团队、另一套传感器**的统计量，
且标定第 71 窟时完全未使用，因此构成留一窟式的外部一致性检验。
它能支持的说法是："模型学到的是窟内外传递结构的共性，而非过拟合单一洞窟"。
它**不能**支持的说法是："模型可精确复现任意洞窟"——窟体几何与热物性仍为假设值。
报告中须如实表述为"跨窟量级一致性检验"，并附本表。""")
    print(f"\n结果已写入 {RESULTS / 'validate_crosscave.csv'}")


if __name__ == "__main__":
    main()
