"""实验六：L1 多时效外场气象预测的域泛化（域 = 年份，Koodos CTDG 原生设定）。

导师意见是把无监督域泛化（实际是多源域泛化，源域有标签、目标域零标签）
缝合进 L1 多时效外场气象预测。本脚本给 L1 补上两条域轴上的泛化证据：

``power``  域 = 年份（2001–2025，25 个域）。在 NASA POWER 再分析上做自预测：
           用 ``u_{t-23:t}`` 预测 ``u_{t+h}``，留一年 / 前向外推。目标年零标签。
           这是 Koodos 的 CTDG 设定原样搬过来——域坐标就是采集时刻本身。
``isd``    域 = 年份（2015–2022，8 个域）。同样的多时效预测，但目标是**敦煌
           现场站**的实测 RH。源年是「再分析 → 站点」的配对标签，目标年零标签。
           这一条才是真正的跨源域偏移（``code/results/isd_vs_power.csv``：
           RH 偏差 +9.16%、RMSE 19.56），也是域泛化该起作用的地方。

协议
----
* 段内 6:2:2 时间切分（标定 / 验证 / 测试），跨域只用源域的验证段选参。
* 域坐标 :math:`s` = 年份。年份是**元数据**，不是标签，零标签口径不受影响。
* ``interp``：留一年（目标年在源年份区间内部）。
* ``forward``：只用**更早**的年份当源域，预测更晚的年份（真正的部署设定）。

输出
----
``code/results/l1_dg_horizon.csv``
``code/results/l1_dg_summary.json``

运行::

    python code/experiments/exp06_l1_domain_generalization.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]          # code/
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.operator.domain_generalization import (    # noqa: E402
    Domain,
    DomainGeneralizer,
)

from check_isd_outdoor import load_isd, load_power     # noqa: E402

POWER_CSV = ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv"
OUT = ROOT / "results"

#: NASA POWER 五要素；与 ``code/src/operator/transport.py`` 的 DEFAULT_DRIVERS 一致
DRIVERS = ("T2M", "RH2M", "WS10M", "PSC", "ALLSKY_SFC_SW_DWN")
#: L1 要预报的要素——只有这两个进得了窟内物理模型
TARGETS_POWER = ("T2M", "RH2M")
TARGETS_ISD = ("RH_isd",)
#: 多时效：1 h（临近）/ 6 h / 24 h（日尺度）/ 72 h（业务预警提前量上限）
HORIZONS = (1, 6, 24, 72)
N_LAGS = 24
WINDOWS = (24, 72, 168)
ARMS = ("pooled", "nearest", "koopman", "subspace", "oracle")
MIN_DOMAIN_N = 1500
#: 岭强度固定 1.0（与 ``subspace`` 臂的 ``theta_beta`` 一致）。L1 是 n≫p 的
#: 大样本设定，特征已标准化，1.0 的岭惩罚近乎不影响解；固定它是为了让
#: 8 个 (要素, 时效) × 2 协议 × ~46 折 的组合不至于再乘上 6 点扫描。
BETA_FIXED = 1.0


# --------------------------------------------------------------------- 特征
def base_features(df: pd.DataFrame, drivers: tuple[str, ...]) -> np.ndarray:
    """驱动变量的**严格因果**延迟嵌入：24 个逐时滞后 + 3 个滑动均值。"""
    cols: list[np.ndarray] = []
    for v in drivers:
        a = df[v].to_numpy(dtype=float)
        for lag in range(N_LAGS):
            c = np.full(len(a), np.nan)
            if lag == 0:
                c[:] = a
            else:
                c[lag:] = a[: len(a) - lag]
            cols.append(c)
        s = pd.Series(a)
        for w in WINDOWS:
            cols.append(s.rolling(w, min_periods=w).mean().to_numpy())
    return np.column_stack(cols)


def calendar_features(time: pd.Series) -> np.ndarray:
    """目标时刻的日历编码。

    预报时刻 :math:`t+h` 是**已知**的（不是预报出来的量），所以它不构成泄漏；
    而且它必须取自 :math:`t+h` 而不是 :math:`t`，否则模型无从知道未来是白天
    还是夜里——这正是多时效外场预报里最不能省的一组特征。
    """
    t = pd.to_datetime(time)
    hour = t.dt.hour.to_numpy(dtype=float)
    doy = t.dt.dayofyear.to_numpy(dtype=float)
    return np.column_stack([
        np.sin(2 * np.pi * hour / 24.0), np.cos(2 * np.pi * hour / 24.0),
        np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25),
    ])


# --------------------------------------------------------------------- 数据
def load_power_frame() -> pd.DataFrame:
    """POWER 再分析：``time_utc`` + 五要素。"""
    df = pd.read_csv(POWER_CSV)
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True).dt.tz_localize(None)
    return df[["time_utc", *DRIVERS]].sort_values("time_utc").reset_index(drop=True)


def load_isd_frame() -> pd.DataFrame:
    """POWER 再分析驱动 + 敦煌现场站实测目标（``merge_asof`` 30 min 容差）。"""
    isd = load_isd().sort_values("time_utc")
    pw = load_power_frame()
    m = pd.merge_asof(isd, pw, on="time_utc", direction="nearest",
                      tolerance=pd.Timedelta("30min"))
    return (m.dropna(subset=["RH_isd", "T2M", "RH2M"])
             .sort_values("time_utc").reset_index(drop=True))


# ------------------------------------------------------------------- 单折
def make_domains(df: pd.DataFrame, target: str, horizon: int, years: list[int],
                 stride: int) -> list[Domain]:
    """构造若干年的 :class:`Domain`。

    样本必须同时满足三条：**特征全有限**、**标签有限**、**目标时刻与 t 同年**。
    第一条不能省——延迟嵌入与 168 h 滑动窗会给序列开头留下一段 NaN，而域内
    :math:`\\mu/\\sigma` 一旦被 NaN 污染，整个域空间外推就全线崩掉（实测会报
    ``LinAlgError: SVD did not converge in Linear Least Squares``）。
    第三条不能省，否则标签会跨域泄露到下一年。
    """
    t = pd.to_datetime(df["time_utc"])
    year = t.dt.year.to_numpy()
    tgt_time = t.shift(-horizon)
    y_all = df[target].shift(-horizon).to_numpy(dtype=float)
    cal_all = calendar_features(tgt_time)
    base = _base(df)

    ok = (np.isfinite(base).all(axis=1)
          & np.isfinite(cal_all).all(axis=1)
          & np.isfinite(y_all)
          & (tgt_time.dt.year.to_numpy() == year))

    doms: list[Domain] = []
    for yr in years:
        idx = np.flatnonzero((year == yr) & ok)[::stride]
        n = len(idx)
        if n < MIN_DOMAIN_N:
            continue
        ntr, nva = int(n * 0.6), int(n * 0.2)
        doms.append(Domain(
            name=str(yr), s=float(yr),
            Xtr=_rows(base, cal_all, idx[:ntr]),
            ytr=y_all[idx[:ntr]],
            Xva=_rows(base, cal_all, idx[ntr:ntr + nva]),
            yva=y_all[idx[ntr:ntr + nva]],
            Xte=_rows(base, cal_all, idx[ntr + nva:]),
            yte=y_all[idx[ntr + nva:]],
        ))
    return doms


_BASE_CACHE: dict[int, tuple[pd.DataFrame, np.ndarray]] = {}


def _base(df: pd.DataFrame) -> np.ndarray:
    """基座特征（与时效无关）按 ``id(df)`` 缓存；缓存里存 ``df`` 引用防止 id 重用。"""
    key = id(df)
    hit = _BASE_CACHE.get(key)
    if hit is None or hit[0] is not df:
        hit = (df, base_features(df, DRIVERS))
        _BASE_CACHE[key] = hit
    return hit[1]


def _rows(base: np.ndarray, cal_all: np.ndarray, idx: np.ndarray) -> np.ndarray:
    return np.column_stack([base[idx], cal_all[idx]])


def run_fold(domains: list[Domain], hold: int, target: str = "") -> dict[str, dict]:
    """留出 ``domains[hold]``（或前向外推时它就是最后一个），逐臂预测。"""
    tgt = domains[hold]
    srcs = [d for k, d in enumerate(domains) if k != hold]
    if len(srcs) < 3:
        return {}
    # 只有湿度类目标才截断到 [0,100]；温度截断会把负温抹成 0，R² 直接崩
    clip = (0.0, 100.0) if "RH" in target else None
    # 逐域标准化：theta_k 只依赖域 k，于是内层留一可以缓存、不 O(K^2)
    mu, sd = _per_domain_scale(srcs)
    src_scaled = [_rescale(d, mu, sd) for d in srcs]
    tgt_scaled = _rescale(tgt, mu, sd)
    s_star = float(tgt.s)

    res: dict[str, dict] = {}
    for arm in ARMS:
        oracle = (Domain(name=tgt.name, s=s_star, Xtr=tgt_scaled.Xtr,
                         ytr=tgt_scaled.ytr, Xva=tgt_scaled.Xva,
                         yva=tgt_scaled.yva)
                  if arm == "oracle" else None)
        g = DomainGeneralizer(method=arm, standardize=False, beta=BETA_FIXED,
                              clip=clip)
        try:
            g.fit(src_scaled, s_star=s_star, oracle=oracle)
            pred = g.predict(tgt_scaled.Xte, s_star)
        except (ValueError, np.linalg.LinAlgError) as exc:
            # 失败要留下痕迹，不能静默丢臂——静默丢臂在图表里就是一个空洞
            res[arm] = {"n": 0, "r2": float("nan"), "rmse": float("nan"),
                        "nrmse": float("nan"),
                        "error": f"{type(exc).__name__}: {exc}"}
            continue
        res[arm] = _score(tgt_scaled.yte, pred)
        if arm == "subspace":
            info = g.koopman_info(s_star)
            res[arm]["dims"] = int(info["dims"])
            res[arm]["shrink"] = float(info["shrink"])
        if arm == "koopman":
            ev = np.asarray(g.koopman_info(s_star)["eigenvalues"])
            res[arm]["eig_absmax"] = float(np.max(np.abs(ev)))
    return res


def _per_domain_scale(srcs: list[Domain]) -> tuple[np.ndarray, np.ndarray]:
    """逐域标准化的共享尺度：各源域**内部**标准差的平均。

    不用全体拼接后的统计量，是为了让特征尺度不随「留出哪个域」而变——这样
    :math:`\\theta_k` 才只由域 :math:`k` 决定（内层留一可缓存的前提）。
    """
    mus, sds = [], []
    for d in srcs:
        X = np.asarray(d.Xtr, dtype=float)
        mus.append(X.mean(axis=0))
        sds.append(X.std(axis=0))
    mu = np.mean(mus, axis=0)
    sd = np.mean(sds, axis=0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    return mu, sd


def _rescale(d: Domain, mu: np.ndarray, sd: np.ndarray) -> Domain:
    f = lambda A: None if A is None else (np.asarray(A, dtype=float) - mu) / sd
    return Domain(name=d.name, s=d.s, Xtr=f(d.Xtr), ytr=d.ytr,
                  Xva=f(d.Xva), yva=d.yva, Xte=f(d.Xte), yte=d.yte)


def _score(y: np.ndarray, p: np.ndarray) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    m = np.isfinite(y) & np.isfinite(p)
    y, p = y[m], p[m]
    if len(y) < 10:
        return {"n": int(len(y)), "r2": float("nan"), "rmse": float("nan"),
                "nrmse": float("nan")}
    rmse = float(np.sqrt(np.mean((y - p) ** 2)))
    sd = float(np.std(y))
    ss = float(np.sum((y - y.mean()) ** 2))
    return {
        "n": int(len(y)),
        "r2": float(1.0 - np.sum((y - p) ** 2) / ss) if ss > 0 else float("nan"),
        "rmse": rmse,
        "nrmse": rmse / sd if sd > 0 else float("nan"),
    }


# ------------------------------------------------------------------- 主流程
def run_task(task: str, df: pd.DataFrame, targets: tuple[str, ...],
             stride: int) -> list[dict]:
    years = sorted({int(y) for y in pd.to_datetime(df["time_utc"]).dt.year})
    rows: list[dict] = []
    for target in targets:
        for h in HORIZONS:
            doms = make_domains(df, target, h, years, stride)
            if len(doms) < 5:
                print(f"[{task}/{target}/h={h}] 可用域不足（{len(doms)}），跳过")
                continue
            protocols = {"interp": [(i, doms) for i in range(len(doms))]}
            # 前向外推：至少 4 个源域打底，逐年后推
            fwd = [(i, doms[: i + 1]) for i in range(4, len(doms))]
            if fwd:
                protocols["forward"] = fwd
            for proto, folds in protocols.items():
                for hold, sub in folds:
                    res = run_fold(sub, hold, target)
                    for arm, m in res.items():
                        rows.append({
                            "task": task, "variable": target, "horizon": h,
                            "protocol": proto, "fold": sub[hold].name, "arm": arm,
                            "n_source_domains": len(sub) - 1,
                            **{k: (None if not np.isfinite(v) else round(v, 4))
                               for k, v in m.items() if k != "n"},
                            "n_test": m.get("n"),
                        })
                if proto == "interp":
                    agg = _agg(rows, task, target, h, proto)
                    print(f"[{task}/{target}/h={h:>2d}] "
                          + " ".join(f"{a}={_f(agg.get(a))}" for a in ARMS)
                          + f"   (成功折 {agg['n_ok__subspace'][0]}"
                            f"/{agg['n_ok__subspace'][1]})")
    return rows


def _agg(rows: list[dict], task: str, var: str, h: int, proto: str) -> dict:
    """各臂 R² 的中位数（只统计成功折），并把「成功折 / 总折」一并返回。

    成功折数必须一起报——否则一个只在少数折上跑通的臂，看起来会比全折跑通的
    臂还漂亮（这正是本轮 ``oracle`` 全折失败却被静默吞掉的教训）。
    """
    sub = [r for r in rows if r["task"] == task and r["variable"] == var
           and r["horizon"] == h and r["protocol"] == proto]
    out: dict = {}
    for a in ARMS:
        vals = [r["r2"] for r in sub if r["arm"] == a]
        good = [v for v in vals if v is not None]
        out[a] = float(np.median(good)) if good else float("nan")
        out[f"n_ok__{a}"] = (len(good), len(vals))
    return out


def _f(x) -> str:
    return "  n/a " if x is None or not np.isfinite(x) else f"{x:+.3f}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []

    print("=== 任务一：POWER 再分析自预测（域 = 年份，25 个域）===")
    all_rows += run_task("power", load_power_frame(), TARGETS_POWER, stride=3)

    print("\n=== 任务二：再分析 → 敦煌现场站（域 = 年份，8 个域）===")
    all_rows += run_task("isd", load_isd_frame(), TARGETS_ISD, stride=1)

    df = pd.DataFrame(all_rows)
    csv_path = OUT / "l1_dg_horizon.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    summary: dict = {
        "protocol": "域 = 年份；源域有标签、目标域零标签（Koodos CTDG 设定）",
        "anchor": "Koodos, NeurIPS 2024, Continuous Temporal Domain Generalization "
                  "(arXiv:2405.16075); 代码 github.com/Zekun-Cai/Koodos",
        "drivers": list(DRIVERS), "horizons": list(HORIZONS),
        "arms": list(ARMS), "n_lags": N_LAGS, "windows": list(WINDOWS),
        "per_task": {},
    }
    for task in df["task"].unique():
        entry: dict = {}
        for var in df[df["task"] == task]["variable"].unique():
            for proto in df["protocol"].unique():
                for h in HORIZONS:
                    med = _agg(all_rows, task, var, h, proto)
                    n_folds = len({r["fold"] for r in all_rows
                                   if r["task"] == task and r["variable"] == var
                                   and r["horizon"] == h and r["protocol"] == proto})
                    if not n_folds or not np.isfinite(med.get("subspace", np.nan)):
                        continue
                    entry[f"{var}|h{h}|{proto}"] = {
                        "n_folds": n_folds,
                        "n_ok": {a: list(med[f"n_ok__{a}"]) for a in ARMS},
                        "median_r2": {a: (None if not np.isfinite(v) else round(v, 4))
                                      for a, v in ((a, med[a]) for a in ARMS)},
                    }
        summary["per_task"][task] = entry

    # ---- 头版结论：主推臂 vs 池化基线，只看 interp 协议
    head = {}
    for task in df["task"].unique():
        for key, val in summary["per_task"][task].items():
            if not key.endswith("|interp"):
                continue
            m = val["median_r2"]
            if m.get("subspace") is None or m.get("pooled") is None:
                continue
            head[key] = {
                "n_folds": val["n_folds"],
                "n_ok": val["n_ok"],
                **{a: m[a] for a in ARMS},
                "gain_vs_pooled": round(m["subspace"] - m["pooled"], 4),
            }
    summary["headline_interp"] = head

    json_path = OUT / "l1_dg_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                         encoding="utf-8")

    print("\n=== 头版对照（interp 协议，各折 R² 中位数）===")
    for k, v in head.items():
        print(f"  {k:<26s} pooled={_f(v['pooled'])} nearest={_f(v['nearest'])} "
              f"koopman={_f(v['koopman'])} subspace={_f(v['subspace'])} "
              f"oracle={_f(v['oracle'])}  Δ={v['gain_vs_pooled']:+.3f}  "
              f"(n_ok={v['n_ok']['subspace'][0]}/{v['n_ok']['subspace'][1]})")
    print(f"\n写出 {csv_path}\n写出 {json_path}")


if __name__ == "__main__":
    main()
