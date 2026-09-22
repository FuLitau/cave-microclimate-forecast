"""ICCP 真实洞穴数据外部效度验证。

动机
----
此前所有结论都建立在「物理代理模型生成的窟内标签」上，最大的攻击面是
「用合成标签验证自己的算法」。ICCP（以色列洞穴气候计划）提供了 **真实观测**
的洞穴微气候：12 个岩溶洞、42 个记录仪、15 700 小时（2019-09 → 2021-07）
逐时气温与相对湿度，气候区（荒漠 / 山地 / 加利利）与岩性（石灰岩 / 白云岩）
与莫高窟（砾岩—砂岩、干旱区）完全不同。

设计
----
每个洞取一组 **Light 区（近洞口，最受外界影响）** 与 **Dark 区（洞内深处，
最受阻尼）** 记录仪对：

  * 驱动 = Light 区记录仪逐时 RH/T（相当于「洞口外场」的可观测替代）
  * 目标 = Dark 区记录仪逐时 RH

对比两条路线：
  A. FirstOrderTransfer（初稿方案）：RH_dark(t) = a · RH_light(t − Δ) + b
     a、Δ 在验证段网格搜索标定
  B. Operator-Full（本作品架构）：Light 区 T/RH 的延迟嵌入三族特征 + 岭回归直接读出

以及一个 oracle 上界（Persistence：直接用同一时刻的 Light 区 RH）。

若 B 在真实数据上同样优于 A，则「延迟嵌入输运算子优于一阶滞后传递函数」这一
架构结论不再依赖合成标签。

另外计算每个洞的 **谐波阻尼结构**（日周期与年周期的振幅比、相位滞后），
作为跨气候区传递结构的描述性证据。
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

warnings.filterwarnings("ignore")

NC = Path("code/data/raw/iccp/extracted/israel_caves-2025.nc")
OUT = Path("code/results")
OUT.mkdir(parents=True, exist_ok=True)

MIN_VALID = 5000          # 记录仪最少有效小时数
LAGS = np.arange(0, 25)   # 一阶传递函数的滞后搜索范围（小时）
BETA_GRID = (1e-3, 1e-2, 1e-1, 1, 10, 100)
N_FAST_LAGS = 24          # 算子特征的快变延迟阶数
SLOW_WINDOWS = (6, 24, 72)
HORIZON = 0               # 同刻读数（nowcast）——与 ICCP 无未来外场的事实一致


# ---------------------------------------------------------------- 工具
def harmonic(t_h: np.ndarray, y: np.ndarray, period_h: float):
    """最小二乘拟合单频正弦，返回 (振幅, 峰值相位/h)。"""
    w = 2.0 * np.pi / period_h
    m = np.isfinite(y)
    if m.sum() < max(50, period_h):
        return np.nan, np.nan
    A = np.column_stack([np.ones(m.sum()), np.cos(w * t_h[m]), np.sin(w * t_h[m])])
    coef, *_ = np.linalg.lstsq(A, y[m], rcond=None)
    amp = float(np.hypot(coef[1], coef[2]))
    phase = float((-np.arctan2(coef[2], coef[1]) / w) % period_h)
    return amp, phase


def build_features(drv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """对驱动序列（n×2：T, RH）构造因果延迟嵌入特征。

    三族：快变延迟（0..N_FAST_LAGS-1）、慢变滑动均值、Magnus 比值。
    返回 (特征矩阵, 有效起点的索引)。
    """
    n = drv.shape[0]
    T, RH = drv[:, 0], drv[:, 1]
    cols: list[np.ndarray] = []
    idx = np.arange(n)

    # 快变延迟（严格因果）
    for lag in range(N_FAST_LAGS):
        c = np.full(n, np.nan)
        c[lag:] = T[: n - lag]
        cols.append(c)
        c = np.full(n, np.nan)
        c[lag:] = RH[: n - lag]
        cols.append(c)

    # 慢变滑动均值（只用过去 + 当前）
    for w in SLOW_WINDOWS:
        s = pd.Series(T).rolling(w, min_periods=w).mean().to_numpy()
        cols.append(s)
        s = pd.Series(RH).rolling(w, min_periods=w).mean().to_numpy()
        cols.append(s)

    # Magnus 比值：RH/q_sat(T)
    es = 611.2 * np.exp(17.62 * T / (243.12 + T))
    cols.append(es)
    cols.append(RH * es)

    X = np.column_stack(cols)
    ok = np.isfinite(X).all(axis=1)
    return X[ok], idx[ok]


def ridge_fit_predict(Xtr, ytr, Xte, beta, clip=None):
    """带截距、只惩罚斜率的岭回归。

    用增广最小二乘求解（min ||Zw-y||²/n + beta||mask·w||²），而不是对
    G = Z'Z/n + beta·diag(mask) 直接求解——特征高度共线时后者会因条件数
    爆炸而给出 1e30 量级的解（实测洞 12 即如此）。
    """
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd = np.where(sd == 0, 1.0, sd)
    Ztr = np.column_stack([np.ones(len(Xtr)), (Xtr - mu) / sd])
    Zte = np.column_stack([np.ones(len(Xte)), (Xte - mu) / sd])
    mask = np.ones(Ztr.shape[1])
    mask[0] = 0.0                      # 不惩罚截距

    n = len(Ztr)
    A = np.vstack([Ztr / np.sqrt(n), np.diag(np.sqrt(beta) * mask)])
    b = np.concatenate([ytr / np.sqrt(n), np.zeros(Ztr.shape[1])])
    w, *_ = np.linalg.lstsq(A, b, rcond=None)   # 数值稳定
    p = Zte @ w
    if clip is not None:
        p = np.clip(p, *clip)
    return p


def r2(y, p):
    m = np.isfinite(y) & np.isfinite(p)
    if m.sum() < 10:
        return np.nan
    y, p = y[m], p[m]
    ss = ((y - y.mean()) ** 2).sum()
    return float(1.0 - ((y - p) ** 2).sum() / ss) if ss > 0 else np.nan


def rmse(y, p):
    m = np.isfinite(y) & np.isfinite(p)
    if m.sum() < 10:
        return np.nan
    return float(np.sqrt(np.mean((y[m] - p[m]) ** 2)))


# ---------------------------------------------------------------- 主流程
def main() -> None:
    ds = xr.open_dataset(NC, engine="h5netcdf")
    names = [str(x) for x in np.asarray(ds["Cave_Name"].values, dtype=object)]
    zones = [str(x) for x in np.asarray(ds["Lighting_Zone"].values, dtype=object)]
    mapping = np.asarray(ds["logger_cave_mapping"].values)
    T = np.asarray(ds["Temperature"].values) - 273.15      # K -> °C
    RH = np.asarray(ds["Relative_Humidity"].values)
    time = pd.to_datetime(np.asarray(ds["time"].values))
    t_h = (time - time[0]).total_seconds().to_numpy() / 3600.0

    # logger -> cave
    logger_cave = {}
    for li in range(mapping.shape[1]):
        col = mapping[:, li]
        logger_cave[li] = int(np.argmax(col)) if col.sum() > 0 else -1

    valid = [li for li in range(len(zones))
             if np.isfinite(RH[li]).sum() >= MIN_VALID
             and np.isfinite(T[li]).sum() >= MIN_VALID]

    rows, harm_rows = [], []
    for ci in range(len(names)):
        lg = [li for li in valid if logger_cave[li] == ci]
        light = [li for li in lg if zones[li] == "Light"]
        dark = [li for li in lg if zones[li] in ("Dark", "Twilight")]
        if not light or not dark:
            continue
        # 取覆盖最长的 Light / Dark 记录仪
        li_l = max(light, key=lambda i: np.isfinite(RH[i]).sum())
        li_d = max(dark, key=lambda i: np.isfinite(RH[i]).sum())

        # 谐波阻尼结构
        for tag, li in (("Light", li_l), ("Dark", li_d)):
            a_d, p_d = harmonic(t_h, RH[li], 24.0)
            a_y, p_y = harmonic(t_h, RH[li], 24.0 * 365.25)
            harm_rows.append({
                "cave": ci + 1, "name": names[ci], "zone": tag, "logger": li + 1,
                "amp_diurnal": round(a_d, 3), "peak_hour": round(p_d, 2),
                "amp_annual": round(a_y, 3), "peak_day": round(p_y / 24.0, 1),
                "RH_mean": round(float(np.nanmean(RH[li])), 1),
            })

        drv = np.column_stack([T[li_l], RH[li_l]])
        tgt = RH[li_d]

        X, ok_idx = build_features(drv)
        y = tgt[ok_idx]
        m = np.isfinite(y)
        X, y, t_ok = X[m], y[m], t_h[ok_idx][m]

        n = len(y)
        if n < 2000:
            continue
        ntr, nva = int(n * 0.6), int(n * 0.2)
        tr, va, te = slice(0, ntr), slice(ntr, ntr + nva), slice(ntr + nva, n)

        # --- A) FirstOrderTransfer：验证段网格搜索 a、Δ
        best = (-np.inf, None, None)
        for lag in LAGS:
            sh = np.full(n, np.nan)
            sh[lag:] = drv[ok_idx][: n - lag, 1]
            mtr = np.isfinite(sh[tr]); mva = np.isfinite(sh[va])
            if mtr.sum() < 100 or mva.sum() < 100:
                continue
            A = np.column_stack([sh[tr][mtr], np.ones(mtr.sum())])
            coef, *_ = np.linalg.lstsq(A, y[tr][mtr], rcond=None)
            pv = np.clip(coef[0] * sh[va][mva] + coef[1], 0, 100)
            sc = r2(y[va][mva], pv)
            if np.isfinite(sc) and sc > best[0]:
                best = (sc, lag, coef)
        _, lag_a, coef_a = best
        sh_all = np.full(n, np.nan)
        sh_all[lag_a:] = drv[ok_idx][: n - lag_a, 1]
        mte = np.isfinite(sh_all[te])
        pred_a = np.full(n, np.nan)
        pred_a[te] = np.clip(coef_a[0] * sh_all[te] + coef_a[1], 0, 100)

        # --- B) Operator-Full：验证段独立选 beta
        bestb = (-np.inf, None)
        for beta in BETA_GRID:
            pv = ridge_fit_predict(X[tr], y[tr], X[va], beta, clip=(0, 100))
            sc = r2(y[va], pv)
            if np.isfinite(sc) and sc > bestb[0]:
                bestb = (sc, beta)
        beta_b = bestb[1]
        pred_b = np.full(n, np.nan)
        pred_b[te] = ridge_fit_predict(X[tr], y[tr], X[te], beta_b, clip=(0, 100))

        # --- oracle 上界：同一时刻的 Light 区 RH
        pred_p = drv[ok_idx][:, 1].copy()

        # 目标方差守卫：深处洞窟 RH 近似常数时 R² 会爆炸式为负，没有意义
        y_te = y[te]
        sd_te = float(np.nanstd(y_te))

        rows.append({
            "cave": ci + 1, "name": names[ci],
            "logger_light": li_l + 1, "logger_dark": li_d + 1,
            "n_test": int(mte.sum()),
            "target_sd": round(sd_te, 3),
            "target_mean": round(float(np.nanmean(y_te)), 2),
            "R2_persistence_oracle": round(r2(y_te, pred_p[te]), 4),
            "R2_FirstOrderTransfer": round(r2(y_te, pred_a[te]), 4),
            "RMSE_FirstOrderTransfer": round(rmse(y_te, pred_a[te]), 3),
            "FOT_lag_h": int(lag_a), "FOT_a": round(float(coef_a[0]), 4),
            "R2_Operator_Full": round(r2(y_te, pred_b[te]), 4),
            "RMSE_Operator_Full": round(rmse(y_te, pred_b[te]), 3),
            "Operator_beta": beta_b,
        })
        print(f"  洞 {ci + 1:2d} {names[ci][:12]:12s} sd={sd_te:5.2f} "
              f"Persistence={rows[-1]['R2_persistence_oracle']:>7.4f}  "
              f"FOT={rows[-1]['R2_FirstOrderTransfer']:>7.4f}(Δ={lag_a}h)  "
              f"Operator={rows[-1]['R2_Operator_Full']:>7.4f}")

    df = pd.DataFrame(rows)
    hm = pd.DataFrame(harm_rows)
    df.to_csv(OUT / "iccp_transfer.csv", index=False, encoding="utf-8-sig")
    hm.to_csv(OUT / "iccp_harmonics.csv", index=False, encoding="utf-8-sig")

    print("\n" + "=" * 78)
    print("汇总（真实观测数据，测试段）")
    print("=" * 78)
    print(df.to_string(index=False))

    # ---- 有效性守卫：目标近似常数时 R² 的分母趋零，任何微小误差都会被放大成
    #      1e30 量级的负数。这种洞窟的 R² 无信息量，必须先从统计中剔除。
    SD_FLOOR = 0.5
    dfv = df[df["target_sd"] >= SD_FLOOR].copy()
    dropped = df[df["target_sd"] < SD_FLOOR]
    print(f"\n有效性守卫 target_sd >= {SD_FLOOR}：纳入 {len(dfv)} 洞，"
          f"剔除 {len(dropped)} 洞"
          + (f"（{', '.join(dropped['name'])}，目标近似常数）" if len(dropped) else ""))

    win = (dfv["R2_Operator_Full"] > dfv["R2_FirstOrderTransfer"]).sum()
    print(f"Operator 优于 FirstOrderTransfer：{win}/{len(dfv)} 洞")
    print("R² 中位数（剔除无效洞后）：")
    print(f"    Persistence(oracle 上界) = {dfv['R2_persistence_oracle'].median():+.4f}")
    print(f"    FirstOrderTransfer       = {dfv['R2_FirstOrderTransfer'].median():+.4f}")
    print(f"    Operator-Full（本作品）  = {dfv['R2_Operator_Full'].median():+.4f}")
    print(f"可用洞数（R² > 0）：FOT {int((dfv['R2_FirstOrderTransfer'] > 0).sum())}"
          f"/{len(dfv)}   Operator {int((dfv['R2_Operator_Full'] > 0).sum())}/{len(dfv)}")
    print("RMSE 中位数："
          f"FOT {dfv['RMSE_FirstOrderTransfer'].median():.3f}  "
          f"Operator {dfv['RMSE_Operator_Full'].median():.3f}  (RH 百分点)")
    bad = dfv[dfv["R2_Operator_Full"] < 0]
    if len(bad):
        print("⚠️ 失败案例（Operator R² < 0，须如实报告，不得隐去）："
              + ", ".join(f"{r['name']}(R²={r['R2_Operator_Full']:+.3f})"
                          for _, r in bad.iterrows()))

    # 阻尼结构：Dark / Light。
    # 相位只在两端振幅都显著时才报告 —— 深处洞窟的日周期几乎消失，
    # 此时谐波相位是纯噪声，报出「滞后 20 小时」是伪结论。
    AMP_FLOOR = 0.05          # RH 百分点的日周期振幅下限
    rows2 = []
    for (ci_, nm), g in hm.groupby(["cave", "name"]):
        gi = g.set_index("zone")
        if "Light" not in gi.index or "Dark" not in gi.index:
            continue
        ad_l = float(gi.loc["Light", "amp_diurnal"])
        ad_d = float(gi.loc["Dark", "amp_diurnal"])
        ay_l = float(gi.loc["Light", "amp_annual"])
        ay_d = float(gi.loc["Dark", "amp_annual"])
        ok_d = (ad_l > AMP_FLOOR) and (ad_d > AMP_FLOOR)
        lag = ((float(gi.loc["Dark", "peak_hour"])
                - float(gi.loc["Light", "peak_hour"])) % 24.0) * 60.0
        rows2.append({
            "cave": ci_, "name": nm,
            "amp_diurnal_light": round(ad_l, 3),
            "amp_diurnal_dark": round(ad_d, 3),
            "diurnal_amp_ratio": round(ad_d / ad_l, 3) if ad_l > 0 else np.nan,
            "annual_amp_ratio": round(ay_d / ay_l, 3) if ay_l > 0 else np.nan,
            "diurnal_lag_min": round(lag, 1) if ok_d else np.nan,
        })
    out = pd.DataFrame(rows2)
    if len(out):
        print("\n" + "=" * 78)
        print("真实洞穴的 Light -> Dark 传递结构")
        print("=" * 78)
        print(out.to_string(index=False))
        out.to_csv(OUT / "iccp_damping.csv", index=False, encoding="utf-8-sig")
        r_d = out["diurnal_amp_ratio"].dropna()
        r_y = out["annual_amp_ratio"].dropna()
        l_d = out["diurnal_lag_min"].dropna()
        print(f"\n日周期振幅比 中位数={r_d.median():.3f}  "
              f"范围=[{r_d.min():.3f}, {r_d.max():.3f}]")
        print(f"年周期振幅比 中位数={r_y.median():.3f}  "
              f"范围=[{r_y.min():.3f}, {r_y.max():.3f}]")
        if len(l_d):
            print(f"日周期滞后(min) 中位数={l_d.median():.1f}  "
                  f"范围=[{l_d.min():.1f}, {l_d.max():.1f}]  "
                  f"（仅 {len(l_d)}/{len(out)} 洞振幅显著）")
        else:
            print("日周期滞后：无洞窟两端振幅同时显著，故不报告")

    (OUT / "iccp_summary.json").write_text(json.dumps({
        "n_caves_total": int(len(df)),
        "n_caves_valid": int(len(dfv)),
        "target_sd_floor": SD_FLOOR,
        "dropped_for_near_constant_target": [str(x) for x in dropped["name"]],
        "operator_wins": int(win),
        "median_r2": {
            "persistence_oracle": round(float(dfv["R2_persistence_oracle"].median()), 4),
            "first_order_transfer": round(float(dfv["R2_FirstOrderTransfer"].median()), 4),
            "operator_full": round(float(dfv["R2_Operator_Full"].median()), 4),
        },
        "usable_caves_r2_positive": {
            "first_order_transfer": int((dfv["R2_FirstOrderTransfer"] > 0).sum()),
            "operator_full": int((dfv["R2_Operator_Full"] > 0).sum()),
        },
        "median_rmse_rh_percent": {
            "first_order_transfer": round(float(dfv["RMSE_FirstOrderTransfer"].median()), 3),
            "operator_full": round(float(dfv["RMSE_Operator_Full"].median()), 3),
        },
        "failure_cases_operator_negative": [str(x) for x in bad["name"]],
        "damping_diurnal_ratio_median": (
            round(float(r_d.median()), 3) if len(r_d) else None),
        "damping_annual_ratio_median": (
            round(float(r_y.median()), 3) if len(r_y) else None),
        "source": "ICCP Zenodo 10.5281/zenodo.17505739 (CC-BY-4.0)",
        "note": ("真实观测外部效度验证。目标近似常数的洞窟（RH 恒 100%）R² 无信息量，"
                 "已由 target_sd 守卫剔除。洞 4/11 为失败案例，如实保留。"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    ds.close()


if __name__ == "__main__":
    main()
