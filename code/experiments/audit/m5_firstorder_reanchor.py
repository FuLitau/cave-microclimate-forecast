# -*- coding: utf-8 -*-
"""只读审计诊断 M5：FirstOrderTransfer 的两种协议对比。

问题：`derisk_02_multihorizon.py` 把 `FirstOrderTransfer` 从**单一初值**
递归推演整个测试段（43 847 h）且**从不重置**；README 据此宣称"初稿方案失效 /
从不预警"。本脚本量化：
  P0  原样（单初值全程递归，不重置）
  P4  同模型的 1 步预报能力（逐小时用真实上一时刻值）
  P1  逐小时用真实观测重新锚定后 h 步递推（rolling-origin，滚动重锚）
  P2  每 24 h 重锚一次（相当于每日更新实测）
  P3  非递归直接传递 y(t+h) = b*x(t+h-3) + c（只用外场，可部署）

不修改仓库任何文件；输出仅打印 + 写入 _audit_tmp/。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CODE = Path(r"F:\Desktop\ai气象大赛\code")
sys.path.insert(0, str(CODE))

_spec = importlib.util.spec_from_file_location(
    "d02", CODE / "experiments" / "derisk_02_multihorizon.py")
d02 = importlib.util.module_from_spec(_spec)
sys.modules["d02"] = d02
_spec.loader.exec_module(d02)          # 模块级只定义常量/函数，main() 有 guard

outdoor = pd.read_csv(CODE / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                      index_col=0, parse_dates=True).sort_index()
outdoor = outdoor[~outdoor.index.duplicated(keep="first")]
cave = pd.read_csv(CODE / "data" / "interim" / "cave_synthetic_2001_2025.csv",
                   index_col=0, parse_dates=True).sort_index()
assert len(cave) == len(outdoor), (len(cave), len(outdoor))
y = cave["RH_in"].to_numpy(dtype=float)
print(f"[check] RH_in mean {np.nanmean(y):.2f}  std {np.nanstd(y):.2f}  "
      f"max {np.nanmax(y):.2f}  n={len(y):,}")

tr = outdoor.index <= pd.Timestamp(d02.TRAIN_END, tz="UTC")
va = (outdoor.index > pd.Timestamp(d02.TRAIN_END, tz="UTC")) & \
     (outdoor.index <= pd.Timestamp(d02.VAL_END, tz="UTC"))
te = outdoor.index > pd.Timestamp(d02.VAL_END, tz="UTC")
print(f"[check] 训练 {tr.sum():,} / 验证 {va.sum():,} / 测试 {te.sum():,}")

fot = d02.FirstOrderTransfer(lag_h=3).fit(outdoor.loc[tr, "RH2M"].to_numpy(), y[tr])
a, b, c = [float(v) for v in fot.coef_]
print(f"[check] FirstOrderTransfer(lag_h=3) 系数: a(y_{{t-1}})={a:.6f}  "
      f"b(x_{{t-3}})={b:.6f}  c={c:.6f}")
print(f"[check] 自回归极点 a={a:.6f} -> 特征时间常数 tau = "
      f"{-1.0 / np.log(a) / 24.0:.2f} 天（发散/饱和速度）")
yc = np.nanmean(y[tr])
print(f"[check] 递归不动点 y* = (b*xbar + c)/(1-a)，以 xbar=RH2M 训练均值 "
      f"{outdoor.loc[tr, 'RH2M'].mean():.2f}% 计 = "
      f"{(b * outdoor.loc[tr, 'RH2M'].mean() + c) / (1 - a):.4f}%")

od_te_rh = outdoor.loc[te, "RH2M"].to_numpy()
od_va_rh = outdoor.loc[va, "RH2M"].to_numpy()
y_te, y_va = y[te], y[va]
L_te, L_va = len(y_te), len(y_va)
LAG = 3


def rollout_from(anchor: float, xseq: np.ndarray, h: int) -> float:
    """完全复刻 FirstOrderTransfer.forecast 的前 h 步（含 <lag 的 x[0] 约定）。"""
    prev = anchor
    for j in range(h):
        src = xseq[j - LAG] if j >= LAG else xseq[0]
        prev = a * prev + b * src + c
    return prev


def p0(h):
    """原样：单初值、全程递归、不重置（测试段做 0..100 截断，同 derisk_02 L409）。"""
    raw = fot.forecast(od_te_rh, y_te[0])
    rawv = fot.forecast(od_va_rh, y_va[0])
    n_te = L_te - h
    return (np.clip(raw, 0.0, 100.0)[:n_te], y_te[h:],
            rawv[: L_va - h], y_va[h:], raw)


def p4():
    """1 步预报：逐小时用真实上一时刻窟内 RH 锚定（模型的真实一步能力）。"""
    def lag(xv):
        return xv[np.maximum(np.arange(len(xv)) - LAG, 0)]
    p = np.full(L_te, np.nan)
    p[1:] = a * y_te[:-1] + b * lag(od_te_rh)[1:] + c
    pv = np.full(L_va, np.nan)
    pv[1:] = a * y_va[:-1] + b * lag(od_va_rh)[1:] + c
    return p[1:], y_te[1:], pv[1:], y_va[1:], p


def p1(h):
    """逐小时重锚：每个起点 t 用真实 y_t，向前递推 h 步预测 y_{t+h}。"""
    w = np.array([a ** (h - j) for j in range(1, h + 1)])   # j=1..h
    def build(yv, xv):
        L = len(yv)
        out = np.zeros(L - h)          # 注意：不能用 nan 初始化（+= 会传播 NaN）
        for j in range(1, h + 1):
            sh = max(j - LAG, 0)
            xs = xv[sh: sh + (L - h)]
            out += w[j - 1] * (b * xs + c)
        out += (a ** h) * yv[: L - h]
        return out
    return (build(y_te, od_te_rh), y_te[h:],
            build(y_va, od_va_rh), y_va[h:], build(y_te, od_te_rh))


def p2(h, rebase=24):
    """每 rebase 小时用真实观测重锚一次。"""
    def build(yv, xv):
        L = len(yv)
        out = np.full(L - h, np.nan)
        for t0 in range(0, L - h, rebase):
            for t in range(t0, min(t0 + rebase, L - h)):
                extra = t - t0
                out[t] = rollout_from(yv[t - extra],
                                      xv[t - extra: t - extra + h + extra + LAG + 1],
                                      h + extra)
        return out
    return (build(y_te, od_te_rh), y_te[h:],
            build(y_va, od_va_rh), y_va[h:], build(y_te, od_te_rh))


def p3(h):
    """非递归直接传递（只用外场，可部署）：y = b'*x(t-3) + c'。"""
    x_tr = outdoor.loc[tr, "RH2M"].to_numpy()
    A = np.column_stack([x_tr[LAG:], np.ones(len(x_tr) - LAG)])
    coef, *_ = np.linalg.lstsq(A, y[tr][LAG:], rcond=None)
    b2, c2 = float(coef[0]), float(coef[1])

    def build(yv, xv, hh):
        n = len(yv) - hh
        xs = xv[hh - LAG: hh - LAG + n]
        return b2 * xs + c2

    return (build(y_te, od_te_rh, h), y_te[h:],
            build(y_va, od_va_rh, h), y_va[h:], build(y_te, od_te_rh, h))


def score(tag, yt, yp, yv, pv):
    m = d02.reg_metrics(yt, yp)
    row = {"protocol": tag, "n": len(yt), **m}
    for tname, thr in d02.THRESHOLDS.items():
        cut = d02.calibrate_cut(yv, pv, thr)
        e = d02.event_metrics(yt, yp, thr, cut=cut)
        l = d02.lead_time_metrics(yt, yp, thr, cut=cut)
        row[f"cut_{tname[:2]}"] = round(cut, 3)
        row[f"AUC_{tname[:2]}"] = e["AUC"]
        row[f"F1_{tname[:2]}"] = e["F1"]
        row[f"alarm_{tname[:2]}"] = e["alarm_rate"]
        row[f"detect_{tname[:2]}"] = l["detect_rate"]
        row[f"lead_{tname[:2]}"] = l["mean_lead_h"]
    return row


rows = []
for h in d02.HORIZONS:
    for tag, fn in (("P0 原样:单初值全程递归(不重置)", p0),
                    ("P1 逐小时重锚", p1),
                    ("P2 每24h重锚", p2),
                    ("P3 非递归直接传递(可部署)", p3)):
        yp, yt, pv, yv, _ = fn(h)
        r = score(tag, yt, yp, yv, pv)
        r["horizon_h"] = h
        rows.append(r)
    yp, yt, pv, yv, _ = p4()
    r = score("P4 一步预报(h=1)", yt, yp, yv, pv)
    r["horizon_h"] = 1
    rows.append(r)

df = pd.DataFrame(rows)[["horizon_h", "protocol", "n", "RMSE", "MAE", "R2", "bias",
                         "cut_62", "AUC_62", "F1_62", "alarm_62", "detect_62", "lead_62"]]
pd.set_option("display.width", 250)
for h in [1] + list(d02.HORIZONS):
    sub = df[df["horizon_h"] == h].drop(columns=["horizon_h", "n"])
    print(f"\n===== horizon h = {h} h =====")
    print(sub.to_string(index=False))

# 原样协议的预测分布（解释"从不预警"的机理）
raw = fot.forecast(od_te_rh, y_te[0])
rawc = np.clip(raw, 0, 100)
print(f"\n[P0 机理] 未截断递归输出: min {np.nanmin(raw):.3f}  max {np.nanmax(raw):.3f}  "
      f"mean {np.nanmean(raw):.3f}  std {np.nanstd(raw):.6f}")
print(f"[P0 机理] 截断后: min {rawc.min():.3f} max {rawc.max():.3f} "
      f"unique值个数 {len(np.unique(np.round(rawc, 6)))}")
print(f"[P0 机理] 前 5 个输出: {raw[:5]}   第 1000 个: {raw[1000]}")
print(f"[P0 机理] 截断后落在下界 0 的比例 {float((rawc <= 0).mean()):.4f}，"
      f"落在上界 100 的比例 {float((rawc >= 100).mean()):.4f}，"
      f"有效唯一值 {len(np.unique(np.round(rawc, 6)))} 个")
print(f"[P0 机理] 未截断输出单调性: raw[10]={raw[10]:.4f} raw[100]={raw[100]:.4f} "
      f"raw[5000]={raw[5000]:.4f} raw[20000]={raw[20000]:.4f} raw[40000]={raw[40000]:.4f}")
print(f"[P0 机理] a={a:.6f}>1 => 递归本身不稳定；不动点 "
      f"dbar/(a-1) 的符号决定它奔向 +inf 还是 -inf（测试段 RH2M 均值 "
      f"{od_te_rh.mean():.3f}%，训练段 {outdoor.loc[tr, 'RH2M'].mean():.3f}%）")

out = CODE / "experiments" / "_audit_tmp"
out.mkdir(parents=True, exist_ok=True)
df.to_csv(out / "m5_protocols.csv", index=False, encoding="utf-8-sig")
print(f"\n[saved] {out / 'm5_protocols.csv'}")
