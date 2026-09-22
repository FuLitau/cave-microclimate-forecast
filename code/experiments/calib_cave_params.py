"""窟内模型参数标定：把"衰减比"和"季节滞后"标到文献量级。

为什么需要标定
--------------
集总单区模型有一个已知的结构性偏差：它假定**整窟空气充分混合**，
而真实洞窟存在热力分层，窟门交换以置换流为主。若直接把文献实测的
换气次数（关门 1.6 /h、开门 9-13 /h）当作主体空气的换气量代入，
窟内气温会被外场"拉平"，季节衰减特征消失——这与实测的
"洞窟对外部气候存在显著衰减与滞后"相矛盾。

因此引入**有效混合系数** :math:`\\eta`：名义换气次数取文献实测值，
但只有 :math:`\\eta` 份额参与主体空气的热/湿交换。
:math:`\\eta` 由文献报导的窟内外响应规律标定，并做敏感性分析。

本脚本扫描 :math:`(\\eta, \\text{pillar\\_depth})`，报告：
  * 年周期振幅比 A_in/A_out 与相位滞后（天）
  * 日周期振幅比（应接近完全衰减）
  * 窟内平均 RH（文献约束：38-44%）
  * 超阈时长占比（必须 >0，否则盐害无法解释）
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.physics.cave_model import CaveModel, CaveParams  # noqa: E402


def harmonic(series: pd.Series, period_h: float = 24 * 365.25) -> tuple[float, float]:
    """对序列做单频最小二乘拟合，返回 (振幅, 相位弧度)。"""
    x = series.to_numpy(dtype=float)
    ok = np.isfinite(x)
    t = np.arange(len(x))[ok] / period_h
    x = x[ok]
    A = np.column_stack([np.sin(2 * np.pi * t), np.cos(2 * np.pi * t), np.ones_like(t)])
    coef, *_ = np.linalg.lstsq(A, x, rcond=None)
    amp = float(np.hypot(coef[0], coef[1]))
    phase = float(np.arctan2(coef[1], coef[0]))
    return amp, phase


def diurnal_std(series: pd.Series) -> float:
    """去掉月均值后的残差标准差，近似日循环强度。"""
    s = series.copy()
    monthly = s.groupby([s.index.year, s.index.month]).transform("mean")
    return float((s - monthly).std())


def daily_range_ratio(sim: pd.DataFrame, outdoor: pd.DataFrame,
                      is_open_hours: bool | None = None) -> float:
    """窟内/窟外**日较差比**（逐日 max-min 之比，取中位数）。

    Parameters
    ----------
    is_open_hours : bool or None
        若为 True/False，只统计"开放时段占优 / 不占优"的日期，
        以对应文献中"开放日 / 闭窟日"两种状态的实测比。
    """
    day = sim.index.tz_convert("Asia/Shanghai").date if sim.index.tz is not None \
        else sim.index.date
    tin = sim["T_in"].groupby(day).agg(lambda s: s.max() - s.min())
    tout = outdoor["T2M"].groupby(day).agg(lambda s: s.max() - s.min())
    if is_open_hours is not None:
        opn = sim["Q_m3h"].groupby(day).apply(
            lambda s: (s > 0.5 * (s.max() + s.min())).mean() > 0.5)
        keep = opn if is_open_hours else ~opn
        tin, tout = tin[keep], tout[keep]
    ok = (tout > 0.5) & np.isfinite(tin) & np.isfinite(tout)
    if ok.sum() < 10:
        return float("nan")
    return round(float(np.median((tin[ok] / tout[ok]).to_numpy())), 4)


def evaluate(outdoor: pd.DataFrame, params: CaveParams,
             drive: pd.DataFrame | None = None) -> dict:
    """在"正常开放"与"强制闭窟"两种门态下各跑一次，并量化游客效应。

    这样才能与 Gong et al. 2025 的第 71 窟对照实验（2019 开放 vs 2020 疫情闭窟）
    做同口径比较。

    Parameters
    ----------
    outdoor : DataFrame
        **统计窗口**（本文件用 2010–2019）。
    drive : DataFrame, optional
        比 ``outdoor`` 更长的驱动序列，其尾部覆盖 ``outdoor``。
        给出时，仿真的前段充当**自旋期**，只对 ``outdoor`` 覆盖的时段统计。

    为什么需要 ``drive``
    -------------------
    ``simulate()`` 只用外场**前 30 天**均值作初值，而 5 m 岩体导热链的
    时间常数是**月–年量级**，深部节点在短初值下并未平衡。实测对比
    （``code/experiments/check_spinup_sensitivity.py``）表明：
    6 个标定目标中 5 个几乎不变，但 **年极差比 T 由 0.529 降到 0.468**
    （文献 0.559）—— 即不加自旋期会**掩盖**模型年阻尼过强的真实偏差。
    """
    drive = outdoor if drive is None else drive
    lo, hi = outdoor.index[0], outdoor.index[-1]

    sim = CaveModel(params).simulate(drive).loc[lo:hi]
    sim_closed = CaveModel(replace(params, force_door_closed=True)).simulate(drive).loc[lo:hi]
    # 游客效应：同一天气下有人 vs 无人的窟内 RH 峰值差
    sim_novisit = CaveModel(replace(params, visitor_occupancy=0.0)).simulate(drive).loc[lo:hi]

    out = {"eta": params.ventilation_mixing_efficiency,
           "wall_pore_rh": params.wall_pore_rh,
           "depth_m": params.pillar_depth_m,
           "visitor_occ": params.visitor_occupancy}

    a_out, p_out = harmonic(outdoor["T2M"])
    a_in, p_in = harmonic(sim["T_in"])
    out["annual_amp_ratio_T"] = round(a_in / a_out, 4)

    lag_rad = (p_out - p_in) % (2 * np.pi)
    out["annual_lag_days"] = round(lag_rad / (2 * np.pi) * 365.25, 1)

    out["diurnal_ratio_open"] = daily_range_ratio(sim, outdoor)
    out["diurnal_ratio_closed"] = daily_range_ratio(sim_closed, outdoor)

    # 游客对窟内 RH 峰值的抬升（文献：常态日约 +11 个百分点）
    day = sim.index.tz_convert("Asia/Shanghai").date if sim.index.tz is not None \
        else sim.index.date
    pk_v = sim["RH_in"].groupby(day).max()
    pk_n = sim_novisit["RH_in"].groupby(day).max()
    out["visitor_RH_peak_gain"] = round(float((pk_v - pk_n).mean()), 3)

    tr = outdoor["T2M"].max() - outdoor["T2M"].min()
    hr = outdoor["RH2M"].max() - outdoor["RH2M"].min()
    out["annual_range_ratio_T"] = round(
        float((sim["T_in"].max() - sim["T_in"].min()) / tr), 4) if tr > 0 else np.nan
    out["annual_range_ratio_RH"] = round(
        float((sim["RH_in"].max() - sim["RH_in"].min()) / hr), 4) if hr > 0 else np.nan

    out["T_in_mean"] = round(float(sim["T_in"].mean()), 2)
    out["RH_in_mean"] = round(float(sim["RH_in"].mean()), 2)
    out["RH_in_min"] = round(float(sim["RH_in"].min()), 2)
    out["RH_in_max"] = round(float(sim["RH_in"].max()), 2)
    out["frac_gt62"] = round(float((sim["RH_in"] > 62).mean()), 5)
    out["frac_gt67"] = round(float((sim["RH_in"] > 67).mean()), 5)
    out["frac_gt75"] = round(float((sim["RH_in"] > 75).mean()), 5)
    return out


#: 标定目标 —— 全部来自 Gong et al. 2025, npj Heritage Science 13:173
#: （第 71 窟，2019-2021 逐时监测；2020 年因疫情闭窟，构成天然的"门开/门关"对照）
LIT_TARGETS = {
    "diurnal_ratio_open": (0.276, "开放日日较差比（2019-05-01）"),
    "diurnal_ratio_closed": (0.043, "闭窟日日较差比（2020-05-01 疫情闭窟）"),
    "annual_range_ratio_T": (0.559, "年极差比 T"),
    "annual_range_ratio_RH": (0.722, "年极差比 RH"),
    "RH_in_mean": (30.8, "窟内 RH 年均 %"),
    "visitor_RH_peak_gain": (11.0, "游客使窟内 RH 峰值抬升（百分点）"),
}


def _score(row) -> float:
    """加权归一化误差。日较差比（门态增益）是唯一直接实测的双状态约束，权重最高。"""
    s = 0.0
    w = {"diurnal_ratio_open": 2.0, "diurnal_ratio_closed": 1.5,
         "annual_range_ratio_T": 1.5, "annual_range_ratio_RH": 1.0,
         "RH_in_mean": 2.0, "visitor_RH_peak_gain": 1.0}
    for k, wt in w.items():
        tgt = LIT_TARGETS[k][0]
        v = row.get(k, np.nan)
        if not np.isfinite(v):
            return np.inf
        s += wt * abs(v - tgt) / abs(tgt)
    return s


def main() -> None:
    interim = ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv"
    outdoor_all = pd.read_csv(interim, index_col=0, parse_dates=True).sort_index()
    # 标定用 10 年即可，缩短耗时且足够分辨年周期
    EVAL_START, EVAL_END = "2010-01-01", "2019-12-31"
    outdoor = outdoor_all.loc[EVAL_START:EVAL_END]
    # 自旋期（理由见 evaluate() docstring）：simulate() 只用外场前 30 天均值作初值，
    # 而 5 m 岩体导热链的时间常数是月–年量级，深部节点短初值下并未平衡。
    spinup_years = int(os.environ.get("CALIB_SPINUP_YEARS", "2"))
    drive = (outdoor_all.loc[f"{2010 - spinup_years}-01-01":EVAL_END]
             if spinup_years > 0 else None)
    print(f"自旋期 = {spinup_years} 年"
          + (f"；驱动 {drive.index[0]:%Y-%m-%d} → {drive.index[-1]:%Y-%m-%d}"
             if drive is not None else "（关闭）")
          + f"，统计窗口 {outdoor.index[0]:%Y-%m-%d} → {outdoor.index[-1]:%Y-%m-%d}")

    a_out, _ = harmonic(outdoor["T2M"])
    print(f"窟外气温年振幅 = {a_out:.2f} degC   日循环 std = {diurnal_std(outdoor['T2M']):.3f} degC")
    print(f"窟外 RH 均值 = {outdoor['RH2M'].mean():.2f}%")
    print("\n标定目标（第 71 窟实测，Gong et al. 2025, npj HS 13:173）:")
    for k, (v, desc) in LIT_TARGETS.items():
        print(f"  {k:12s} = {v:6.1f}   {desc}")
    print("\nη 已由文献锚定（主室/入口风速比均值 0.17），不再作为自由参数。")
    print("剩余两个自由参数：wall_pore_rh（定 RH 水平）、pillar_depth_m（定衰减与滞后）。\n")

    rows = []
    # depth 已由**年极差比**独立锁定（0.552 vs 文献 0.559 @ 5.0 m），故固定为 5.0，
    # 不再参与联合搜索——避免用同一个约束同时定两个参数。
    for eta in (0.17, 0.30, 0.45):
        for ks in (2e-6, 2e-5, 8e-5):
            for pore in (25.0, 50.0, 75.0):
                p = CaveParams(ventilation_mixing_efficiency=eta,
                               k_sorption_m_s=ks,
                               wall_pore_rh=pore,
                               pillar_depth_m=5.0,
                               visitor_occupancy=1.0)
                r = evaluate(outdoor, p, drive=drive)
                r["k_sorption"] = ks
                r["score"] = _score(r)
                rows.append(r)
                print(f"  eta={eta:<5.2f} ks={ks:<7.0e} pore={pore:<4.0f} -> "
                      f"RH {r['RH_in_mean']:>5.1f}% "
                      f"日比 {r['diurnal_ratio_open']:.3f}/{r['diurnal_ratio_closed']:.3f}  "
                      f"年比T {r['annual_range_ratio_T']:.3f}  "
                      f"游客+{r['visitor_RH_peak_gain']:>4.1f}  "
                      f">62% {(r['frac_gt62'] or 0)*100:>5.2f}%  "
                      f"score {r['score']:.3f}")

    df = pd.DataFrame(rows)
    out = ROOT / "results" / "calib_cave_params.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\n已写入 {out}")

    df["score"] = df.apply(_score, axis=1)
    df = df.sort_values("score")
    best = df.iloc[0]
    print("\n最贴合文献实测传递比的配置（加权归一化误差最小）：")
    print(f"  eta={best.eta:.2f}, k_sorption={best.k_sorption:.0e}, "
          f"wall_pore_rh={best.wall_pore_rh:.0f}, pillar_depth={best.depth_m:.1f} m")
    print(f"  日较差比 开/关 = {best.diurnal_ratio_open:.3f} / {best.diurnal_ratio_closed:.3f}"
          f"   (文献 0.276 / 0.043)")
    print(f"  年极差比 T/RH  = {best.annual_range_ratio_T:.3f} / {best.annual_range_ratio_RH:.3f}"
          f"   (文献 0.559 / 0.722)")
    print(f"  窟内 RH 年均   = {best.RH_in_mean:.2f}%   (文献 30.8%)")
    print(f"  游客抬升峰值   = +{best.visitor_RH_peak_gain:.1f} pp   (文献约 +11)")
    df.to_csv(out, index=False)


if __name__ == "__main__":
    main()
