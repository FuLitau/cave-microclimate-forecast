# -*- coding: utf-8 -*-
"""只读审计诊断 M2：PS（格点气压，1639 m）vs PSC（site-elevation 订正）的数值差，
以及把输运算子的驱动 PS -> PSC 替换后模型指标的变化。不修改仓库文件。"""
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
_spec.loader.exec_module(d02)
from src.operator.transport import KoopmanTransport, TransportConfig, build_features  # noqa: E402

outdoor = pd.read_csv(CODE / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                      index_col=0, parse_dates=True).sort_index()
outdoor = outdoor[~outdoor.index.duplicated(keep="first")]
cave = pd.read_csv(CODE / "data" / "interim" / "cave_synthetic_2001_2025.csv",
                   index_col=0, parse_dates=True).sort_index()
y = cave["RH_in"].to_numpy(dtype=float)

ps = outdoor["PS"].to_numpy(dtype=float)
psc = outdoor["PSC"].to_numpy(dtype=float)
d = psc - ps
k, b0 = np.polyfit(ps[np.isfinite(ps) & np.isfinite(psc)],
                   psc[np.isfinite(ps) & np.isfinite(psc)], 1)
r = np.corrcoef(ps[np.isfinite(ps) & np.isfinite(psc)],
                psc[np.isfinite(ps) & np.isfinite(psc)])[0, 1]
print("=" * 78)
print("[1] PS / PSC 数值统计（全期逐小时，n = %s）" % f"{len(ps):,}")
print("=" * 78)
print(f"  PS   mean {np.nanmean(ps):7.3f}  std {np.nanstd(ps):6.3f}  "
      f"min {np.nanmin(ps):7.3f}  max {np.nanmax(ps):7.3f}  kPa")
print(f"  PSC  mean {np.nanmean(psc):7.3f}  std {np.nanstd(psc):6.3f}  "
      f"min {np.nanmin(psc):7.3f}  max {np.nanmax(psc):7.3f}  kPa")
print(f"  差值 PSC-PS: mean {np.nanmean(d):+.3f}  std {np.nanstd(d):.3f}  "
      f"min {np.nanmin(d):+.3f}  max {np.nanmax(d):+.3f}  kPa  "
      f"（相对 {np.nanmean(d) / np.nanmean(ps) * 100:.2f}%）")
print(f"  PSC ≈ {k:.6f} * PS {b0:+.4f}   corr = {r:.6f}   "
      f"R2 = {r ** 2:.8f}")
print(f"  CaveModel 内部常数 P_ATM = 88000 Pa = 88.000 kPa "
      f"（更接近 PSC 均值 {np.nanmean(psc):.3f} 而非 PS 均值 {np.nanmean(ps):.3f}）")
print(f"  训练段 PS 均值 {outdoor.loc[outdoor.index <= pd.Timestamp('2019-12-31', tz='UTC'), 'PS'].mean():.3f}"
      f"  PSC 均值 {outdoor.loc[outdoor.index <= pd.Timestamp('2019-12-31', tz='UTC'), 'PSC'].mean():.3f}")

tr = outdoor.index <= pd.Timestamp(d02.TRAIN_END, tz="UTC")
va = (outdoor.index > pd.Timestamp(d02.TRAIN_END, tz="UTC")) & \
     (outdoor.index <= pd.Timestamp(d02.VAL_END, tz="UTC"))
te = outdoor.index > pd.Timestamp(d02.VAL_END, tz="UTC")
y_te = y[te]

BASE = ["T2M", "RH2M", "WS10M", "PS", "ALLSKY_SFC_SW_DWN"]
ALT = ["T2M", "RH2M", "WS10M", "PSC", "ALLSKY_SFC_SW_DWN"]

print()
print("=" * 78)
print("[2] 输运算子 Full 配置（beta*=1，同 derisk_02 日志 [3]）驱动 PS vs PSC")
print("=" * 78)
rows = []
for tag, drv in (("drivers 含 PS（现状）", BASE), ("drivers 含 PSC（替换）", ALT)):
    cfg = TransportConfig(ridge_beta=1.0, drivers=drv)
    kt = KoopmanTransport(cfg).fit(outdoor[tr], y[tr], fit_koopman=False)
    for h in d02.HORIZONS:
        w = kt.fit_direct(outdoor[tr], y[tr], h)
        pred = kt.predict_direct(outdoor[te], w)[: len(y_te) - h]
        m = d02.reg_metrics(y_te[h:], pred)
        row = {"drivers": tag, "h": h, **m}
        for tname, thr in d02.THRESHOLDS.items():
            cut = d02.calibrate_cut(
                y[va][h:],
                kt.predict_direct(outdoor[va], w)[: int(va.sum()) - h], thr)
            e = d02.event_metrics(y_te[h:], pred, thr, cut=cut)
            row[f"AUC_{tname[:2]}"] = e["AUC"]
            row[f"F1_{tname[:2]}"] = e["F1"]
        rows.append(row)
        if h == 24:
            names = kt.feature_names_
            pidx = [i for i, nm in enumerate(names)
                    if nm.startswith("PS_lag") or nm.startswith("PSC_lag")]
            tot = float(np.abs(w[:-1]).sum())
            pw = float(np.abs(w[pidx]).sum())
            print(f"  [{tag}] h=24 气压族特征 {len(pidx)} 个 "
                  f"|w|合计 {pw:.4f} / 全部 |w|合计 {tot:.4f} = {pw / tot * 100:.2f}%")

df = pd.DataFrame(rows)
print()
print(df.round(5).to_string(index=False))
out = CODE / "experiments" / "_audit_tmp"
out.mkdir(parents=True, exist_ok=True)
df.to_csv(out / "m2_ps_psc_impact.csv", index=False, encoding="utf-8-sig")
print(f"\n[saved] {out / 'm2_ps_psc_impact.csv'}")
