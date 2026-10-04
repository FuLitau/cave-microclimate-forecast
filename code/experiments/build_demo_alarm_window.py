"""为前端看板**追加**一个「预警触发窗口」演示场景（真阳性 / 带提前量）。

背景与定位
----------
``code/experiments/build_demo_forecast.py`` 现有的三个演示场景（高湿事件 / 偏高湿 /
平稳期）是**按未来 72 h 内真实窟内 RH 峰值的分位数**挑的（0.9999 / 0.98 / 0.50）。
结果是三个窗口的标定判定**全为 0 级**：真实峰值 89.0% 的那一窗，风险读出只到 49.1%，
够不到标定门限。演示看板因此从来没有演示过一次「预报 → 过线 → 预警」的完整闭环。

但模型是报得出来的：测试段 24 h / 62% 档召回 14.8%，94 次起报事件命中 33 次。命中的
窗口就在数据里，只是原来的挑选规则（按真实峰值分位）选不中它们。

本脚本**只做一件事**：在测试段上逐起点计算主读出（标定段选出的分位数读出）的
逐时效判定，挑出一个**真阳性且提前量最大**的窗口，单独写出 ``demo_alarm.csv``。

严格不改动原版
--------------
本脚本 **不覆盖** 现有任何产物：只新增 ``code/results/demo_alarm.csv`` 与
``code/results/demo_alarm_summary.json``。``demo_forecast.csv`` / ``demo_calibration.csv``
/ ``demo_history.csv`` / ``demo_stats.json`` 一律不写。拟合口径、标定段、读出选择规则
与原脚本逐行一致，保证新场景与既有三个场景可直接横向比较。

挑选规则（真阳性优先，再看提前量）
----------------------------------
对每个候选起点 p（测试段，排除标定年 2021 与训练段，且前后留出安全边界）：
  * 用标定段选出的主读出取逐时效预报值 ``pred[h]``（h = 0..72）
  * 用**同一套**按基准率标定的门限 ``cut_62/67/75[h]`` 得到逐小时 ``level``
  * 要求 ``level`` 至少有一小时 ≥ 1（模型确实报了警）
  * 要求窗口内真实值也至少有一小时 ≥ 62%（确实是真阳性，不是误报）
  * 打分 = 首次报警时刻到首次真实超阈时刻的**提前量**（真值先超阈则为负，直接淘汰）
  * 并列时取报警小时数更多者
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operator.transport import (                        # noqa: E402
    KoopmanTransport, TransportConfig, build_features,
)
from src.physics.cave_model import CaveModel, CaveParams    # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

TRAIN_END = "2020-12-31"
CALIB_YEAR = 2021
N_HORIZON = 73
HORIZONS = (24, 48, 72)

RH_WARN, RH_CRIT, RH_CLOSE = 62.0, 67.0, 75.0
THRESHOLDS = (("62%(业务预警)", RH_WARN), ("67%(潮解起始)", RH_CRIT),
              ("75%(吸湿突变)", RH_CLOSE))

TAU_GRID = (0.90, 0.95)

LABEL = "预警触发窗口"


def cal_level(v: float, cut62: float, cut67: float, cut75: float) -> int:
    if v >= cut75:
        return 2
    if v >= cut67:
        return 1
    if v >= cut62:
        return 1
    return 0


def main() -> None:
    t0 = time.time()
    outdoor = pd.read_csv(ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                          index_col=0, parse_dates=True).sort_index()
    outdoor = outdoor[~outdoor.index.duplicated(keep="first")]
    idx = outdoor.index

    print("[1] 生成窟内物理合成标签 ...")
    cave = CaveModel(CaveParams()).simulate(outdoor)
    rh_true = cave["RH_in"].to_numpy(dtype=float)

    ts = lambda s: pd.Timestamp(s, tz="UTC")                      # noqa: E731
    tr = np.asarray(outdoor.index <= ts(TRAIN_END))
    ca = np.asarray((outdoor.index > ts(TRAIN_END)) &
                    (outdoor.index <= ts(f"{CALIB_YEAR}-12-31")))

    print(f"[2] 拟合输运算子（训练段 {tr.sum():,} h, ≤{TRAIN_END}）...")
    kt = KoopmanTransport(TransportConfig(ridge_beta=1.0)).fit(
        outdoor[tr], rh_true[tr], fit_koopman=False)

    print("[3] 全序列构造特征（严格因果，供切片使用）...")
    Psi = build_features(outdoor, kt.cfg)
    print(f"    特征维度 p = {Psi.shape[1]}")

    # 权重缓存：73×3 次岭回归/pinball 拟合约 12 分钟，是整条链最贵的一步，必须可复用。
    CACHE = RESULTS / "demo_alarm_weights.npz"
    fp = f"{len(Psi)}x{Psi.shape[1]}|train<={TRAIN_END}|beta=1.0|tau={TAU_GRID}"
    w_mse: dict[int, np.ndarray] = {}
    w_q: dict[float, dict[int, np.ndarray]] = {}
    if CACHE.exists():
        _z = np.load(CACHE, allow_pickle=False)
        if "fingerprint" in _z and str(_z["fingerprint"]) == fp:
            w_mse = {h: _z[f"mse_{h}"] for h in range(N_HORIZON)}
            w_q = {tau: {h: _z[f"q{tau}_{h}"] for h in range(N_HORIZON)} for tau in TAU_GRID}
            print(f"[4] 命中权重缓存 {CACHE.name}，跳过 {N_HORIZON}×{1 + len(TAU_GRID)} 次拟合")
        else:
            print(f"[4] 权重缓存指纹不符，重新拟合（{_z.get('fingerprint', '无')} ≠ {fp}）")

    if not w_mse:
        print(f"[4] 逐时效拟合 {N_HORIZON} 个读出权重 ...")
        t1 = time.time()
        w_mse = {h: kt.fit_direct(outdoor[tr], rh_true[tr], h, Psi=Psi[tr])
                 for h in range(N_HORIZON)}
        print(f"    线性 MSE       {time.time() - t1:6.1f}s")
        for tau in TAU_GRID:
            t1 = time.time()
            w_q[tau] = {h: kt.fit_direct_quantile(outdoor[tr], rh_true[tr], h, tau=tau,
                                                  Psi=Psi[tr])
                        for h in range(N_HORIZON)}
            print(f"    分位数 τ={tau}   {time.time() - t1:6.1f}s")
        np.savez_compressed(
            CACHE, fingerprint=np.array(fp),
            **{f"mse_{h}": v for h, v in w_mse.items()},
            **{f"q{tau}_{h}": v for tau, d in w_q.items() for h, v in d.items()},
        )
        print(f"    权重已缓存 → {CACHE.name}（下次重跑可省约 12 分钟）")

    def pred_series(weights: dict[int, np.ndarray], mask: np.ndarray) -> dict[int, np.ndarray]:
        Z = kt._add_intercept(kt.transform(Psi[mask]))
        return {h: (Z @ weights[h]).reshape(-1) for h in range(N_HORIZON)}

    pm_ca = pred_series(w_mse, ca)
    pq_ca = {tau: pred_series(w_q[tau], ca) for tau in TAU_GRID}

    def f1_at(pred: dict[int, np.ndarray], cuts: dict[int, float]) -> float:
        tp = fp = fn = 0
        for h in HORIZONS:
            true_h = rh_true[ca][h:]
            n = len(true_h)
            a = true_h >= RH_WARN
            b = pred[h][:n] >= cuts[h]
            tp += int((a & b).sum()); fp += int((~a & b).sum()); fn += int((a & ~b).sum())
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        return 2 * pr * rc / (pr + rc) if pr + rc else 0.0

    print(f"[5] 在标定段 {CALIB_YEAR} 上选分位数 τ（判据 = 62% 档 F1，各时效合并）...")
    cands = {"线性 MSE（对照）": pm_ca, **{f"分位数 τ={t}": pq_ca[t] for t in TAU_GRID}}
    cuts_by_cand: dict[str, dict[int, float]] = {}
    for name, pred in cands.items():
        cuts_by_cand[name] = {}
        for h in HORIZONS:
            true_h = rh_true[ca][h:]
            base = float((true_h >= RH_WARN).mean())
            cuts_by_cand[name][h] = (float(np.quantile(pred[h][:len(true_h)], 1 - base))
                                     if base > 0 else RH_WARN)
    f1s = {name: f1_at(pred, cuts_by_cand[name]) for name, pred in cands.items()}
    for name, v in sorted(f1s.items(), key=lambda kv: -kv[1]):
        print(f"      {name:<18} 标定段 F1@62% = {v:.4f}")
    best = max(f1s, key=lambda k: f1s[k])
    print(f"    → 选用 **{best}**")

    final_pred_ca = cands[best]
    cuts: dict[str, dict[int, float]] = {}
    for tname, thr in THRESHOLDS:
        cuts[tname] = {}
        for h in range(N_HORIZON):
            true_h = rh_true[ca][h:]
            base = float((true_h >= thr).mean())
            v = final_pred_ca[h][:len(true_h)]
            cuts[tname][h] = float(np.quantile(v, 1 - base)) if base > 0 else thr
    cut62 = cuts["62%(业务预警)"]; cut67 = cuts["67%(潮解起始)"]; cut75 = cuts["75%(吸湿突变)"]
    print(f"      门限 62%: h=24 → {cut62[24]:.2f}, h=48 → {cut62[48]:.2f}, h=72 → {cut62[72]:.2f}")

    tau_sel = float(best.split("=")[1]) if "分位数" in best else None
    w_best = w_q[tau_sel] if tau_sel is not None else w_mse

    # ---------- 在测试段上逐起点扫描，找真阳性且提前量最大的窗口 ----------
    print("\n[6] 扫描测试段全部起点，寻找「模型提前报警 ∧ 真值确有超阈事件」的窗口 ...")
    te_pos = np.where(~tr & ~ca)[0]
    te_pos = te_pos[(te_pos > 168) & (te_pos < len(idx) - 200)]
    Z_te = kt._add_intercept(kt.transform(Psi[te_pos]))
    preds = {h: (Z_te @ w_best[h]).reshape(-1) for h in range(N_HORIZON)}
    n_te = len(te_pos)
    print(f"    候选起点 {n_te:,} 个；逐时效预报矩阵已算完（{time.time() - t0:.0f}s）")

    lvl = np.zeros((n_te, N_HORIZON), dtype=np.int8)
    for h in range(N_HORIZON):
        p = preds[h]
        lvl[:, h] = ((p >= cut62[h]).astype(np.int8)
                     + (p >= cut67[h]).astype(np.int8)
                     + (p >= cut75[h]).astype(np.int8)).clip(0, 2)

    truth_win = np.stack([rh_true[p:p + N_HORIZON] for p in te_pos])       # (n_te, 73)
    over_true = truth_win >= RH_WARN
    over_pred = lvl >= 1

    has_true = over_true.any(axis=1)
    has_alarm = over_pred.any(axis=1)
    ok = has_true & has_alarm
    print(f"    模型报过警的起点 {has_alarm.sum():,}；真值超阈的起点 {has_true.sum():,}；"
          f"两者同时成立 {ok.sum():,}")

    first_true = np.where(has_true, over_true.argmax(axis=1), N_HORIZON)
    first_alarm = np.where(has_alarm, over_pred.argmax(axis=1), N_HORIZON)
    lead = first_true - first_alarm                     # >0 表示预警早于真值超阈
    n_alarm = over_pred.sum(axis=1)
    n_true_over = over_true.sum(axis=1)                 # 窗口内真值超阈的小时数
    true_peak = truth_win.max(axis=1)
    pred_peak_arr = np.stack([preds[h] for h in range(N_HORIZON)], axis=1).max(axis=1)

    # 演示窗口的挑选判据（可辩护，且只用到模型自己的输出与合成标签，无人工挑选）：
    #   ① 模型报警 ≥ 6 h —— 保证时间轴上确实看得到预警态
    #   ② 提前量 ≥ 12 h —— 保证「提前预警」这件事成立
    #   ③ 真值在窗口内超阈 ≥ 6 h —— 保证它不是「擦线 1 小时」凑出来的真阳性
    # 在此前提下按 (读出自己是否越过 62% 线, 真值超阈小时数, 提前量, 真值峰值) 词典序取最大。
    # 只按「提前量最大」挑会选中真值峰值恰好 62.04%、只超阈 1 小时的擦线窗口——数字上
    # 成立、演示上毫无说服力，故加 ③；再优先挑「风险读出曲线自己也穿过 62% 线」的窗口，
    # 这样图上三条线（真值 / 风险读出 / 线性 MSE 对照）的高低关系一眼可读。
    MIN_ALARM_H, MIN_LEAD_H, MIN_TRUE_H = 6, 12, 6
    cross = (pred_peak_arr >= RH_WARN).astype(np.int8)
    cand = np.where(ok & (first_alarm < first_true)
                    & (n_alarm >= MIN_ALARM_H) & (lead >= MIN_LEAD_H)
                    & (n_true_over >= MIN_TRUE_H))[0]
    if len(cand) == 0:
        print(f"    没有同时满足「报警≥{MIN_ALARM_H}h ∧ 提前≥{MIN_LEAD_H}h ∧ 真值超阈≥{MIN_TRUE_H}h」"
              "的窗口，退化为「报警 ∧ 真值超阈」")
        cand = np.where(ok)[0]
        cross = np.zeros(n_te, dtype=np.int8)
    order = cand[np.lexsort((-true_peak[cand], -lead[cand], -n_true_over[cand], -cross[cand]))]
    print(f"    真阳性且有提前量的窗口 {len(np.where(ok & (first_alarm < first_true))[0]):,} 个，"
          f"其中满足三条件的 {len(cand):,} 个，前 10 名：")
    rank_rows = []
    for j in order[:10]:
        p = int(te_pos[j])
        rank_rows.append({
            "origin": str(idx[p]), "lead_h": int(lead[j]),
            "n_alarm_h": int(n_alarm[j]), "n_true_over_h": int(n_true_over[j]),
            "pred_peak": round(float(preds_h_max := max(preds[h][j] for h in range(N_HORIZON))), 2),
            "true_peak": round(float(true_peak[j]), 2),
            "first_alarm_h": int(first_alarm[j]), "first_true_h": int(first_true[j]),
        })
        print(f"      起点 {idx[p]}  提前 {lead[j]:>2}h  报警 {n_alarm[j]:>2}h  "
              f"真值超阈 {n_true_over[j]:>2}h  读出峰值 {preds_h_max:6.2f}  真值峰值 {true_peak[j]:6.2f}  "
              f"(首次报警 h={first_alarm[j]}, 首次超阈 h={first_true[j]})")
    pd.DataFrame(rank_rows).to_csv(RESULTS / "demo_alarm_candidates.csv", index=False)

    j = int(order[0])
    pos = int(te_pos[j])
    print(f"\n    → 选中起点 {idx[pos]}")

    # ---------- 生成该窗口的 72 h 预报（与原脚本逐字段一致） ----------
    rows = []
    z1 = kt._add_intercept(kt.transform(Psi[pos:pos + 1]))
    for h in range(N_HORIZON):
        tgt = pos + h
        if tgt >= len(idx):
            break
        pred = float(np.asarray(z1 @ w_q[TAU_GRID[0]][h]).reshape(-1)[0])
        pred_best = float(np.asarray(z1 @ w_best[h]).reshape(-1)[0])
        pred_mse = float(np.asarray(z1 @ w_mse[h]).reshape(-1)[0])
        truth = float(rh_true[tgt])
        lvl_v = cal_level(pred_best, cut62[h], cut67[h], cut75[h])
        adv = ("关闭高危洞窟" if lvl_v >= 2 else
               "限流（控制人数与停留时长）" if lvl_v >= 1 else "正常开放")
        lvl_raw = cal_level(pred_best, RH_WARN, RH_CRIT, RH_CLOSE)
        adv_raw = ("关闭高危洞窟" if lvl_raw >= 2 else
                   "限流（控制人数与停留时长）" if lvl_raw >= 1 else "正常开放")
        rows.append({
            "origin": str(idx[pos]),
            "scenario": LABEL,
            "step_h": h,
            "time": str(idx[tgt]),
            "RH_pred": round(pred_best, 3),
            "RH_pred_lin": round(pred_mse, 3),
            "RH_pred_tau90": round(pred, 3),
            "RH_true": round(truth, 3),
            "level": lvl_v,
            "advice": adv,
            "level_raw": lvl_raw,
            "advice_raw": adv_raw,
            "cut_62": round(cut62[h], 3),
            "cut_67": round(cut67[h], 3),
            "cut_75": round(cut75[h], 3),
            "T_out": round(float(outdoor["T2M"].iloc[tgt]), 2),
            "RH_out": round(float(outdoor["RH2M"].iloc[tgt]), 2),
            "Q_m3h": round(float(cave["Q_m3h"].iloc[tgt]), 1),
        })

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "demo_alarm.csv", index=False)
    print(f"[7] 写出 demo_alarm.csv  {df.shape}（原版 demo_forecast.csv 未被改动）")

    nz = df[df.level > 0]
    summary = {
        "scenario": LABEL,
        "origin": str(idx[pos]),
        "readout": best,
        "pred_peak": round(float(df.RH_pred.max()), 3),
        "pred_peak_lin": round(float(df.RH_pred_lin.max()), 3),
        "pred_peak_tau90": round(float(df.RH_pred_tau90.max()), 3),
        "true_peak": round(float(df.RH_true.max()), 3),
        "level_max": int(df.level.max()),
        "level_raw_max": int(df.level_raw.max()),
        "n_warn_h": int(len(nz)),
        "first_warn_h": int(nz.step_h.min()) if len(nz) else -1,
        "first_true_over_h": int(np.argmax((df.RH_true >= RH_WARN).to_numpy()))
                             if (df.RH_true >= RH_WARN).any() else -1,
        "advice_set": sorted(set(df.advice.tolist())),
        "n_true_over_h": int((df.RH_true >= RH_WARN).sum()),
    }
    (RESULTS / "demo_alarm_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n总用时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
