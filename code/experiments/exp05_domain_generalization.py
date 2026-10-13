"""实验五：留一洞多源域泛化（域 = 洞窟，Koodos 式域空间 Koopman 外推）。

协议
----
* **域 = 洞窟**。取 ICCP 真实洞窟中通过有效性筛选的那 8 个洞，做留一洞
  （leave-one-cave-out）：其余 7 洞为源域（有标签），被留出洞为目标域。
* **目标域零标签**。域坐标 :math:`s` 只由目标域的**无标签驱动输入**（洞外
  Light 区逐时 T/RH）算出，全程不触碰目标域 Dark 区的 RH 标签。
* 每个源域内部按 6:2:2 切分（标定/验证/测试），超参与标准化只由源域决定；
  目标域只用最后 20% 的时间段作为测试段。

对照臂
------
``pooled``     所有源域直接混合 ERM（最朴素基线）
``group_dro``  Sagawa et al., ICLR 2020：组 DRO，最差域风险
``vrex``       Krueger et al., ICML 2021：风险外推（方差惩罚）
``nearest``    最近域迁移：按 :math:`s` 距离只取单一源域
``koopman``    Koodos, NeurIPS 2024 的域空间版本：逐域解读出 :math:`\\theta(s_k)`
               （其 Eq.6），在连续域坐标上拟合 Koopman 生成元
               :math:`\\exp(A\\Delta s)` 外推到 :math:`s^*`，再重建读出
``subspace``   **本实验主推臂**：只在「域敏感子空间」（逐坐标域间标准差最大的
               ``dims`` 个坐标）做核 + 线性外推，并用 ``shrink`` 向池化解收缩；
               其余坐标保持池化值。完整 :math:`\\theta` 外推会把洞级水平一起外推，
               实测在水平差异大的洞上崩溃（见 ``docs`` 中的诊断）
``oracle``     目标域自身标定段直接拟合（上界参考，不是泛化方法）

输出
----
``code/results/dg_leave_one_cave_out.csv``
``code/results/dg_deployable_protocol.csv``
``code/results/dg_summary.json``

运行::

    python code/experiments/exp05_domain_generalization.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]          # code/
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.operator.domain_generalization import (    # noqa: E402
    Domain,
    DomainGeneralizer,
)

from validate_iccp import (                         # noqa: E402
    MIN_VALID,
    build_features,
    harmonic,
    r2,
    rmse,
)

NC = ROOT / "data" / "raw" / "iccp" / "extracted" / "israel_caves-2025.nc"
OUT = ROOT / "results"

ARMS = ("pooled", "group_dro", "vrex", "nearest", "koopman", "subspace", "oracle")
#: 主协议用第一项；其余为敏感性分析（域坐标是设计选择，必须交代它有多敏感）
COORDS = ("amp_diurnal_light", "rh_mean_light", "amp_annual_light")
#: 域坐标是设计选择，主协议不预先钉死任何一个：由源域侧内层留一风险选出
#: （见 ``main`` 的「部署协议」段），此处仅作为全部风险都非有限时的兜底。
FALLBACK_COORD = "rh_mean_light"
COORD_LABEL = {
    "amp_diurnal_light": "洞外 Light 区 RH 日周期振幅 (%)",
    "rh_mean_light": "洞外 Light 区 RH 均值 (%)",
    "amp_annual_light": "洞外 Light 区 RH 年周期振幅 (%)",
}


# --------------------------------------------------------------------- 数据
def load_caves() -> list[dict]:
    """按 ``validate_iccp`` 的同一套配对逻辑取出各洞的 (特征, 目标) 序列。

    与 ``validate_iccp.main`` 的唯一区别：这里保留完整的时间索引切片信息，
    并把域坐标一并算出（只用 Light 区驱动，不含 Dark 区标签）。
    """
    ds = xr.open_dataset(NC, engine="h5netcdf")
    names = [str(x) for x in np.asarray(ds["Cave_Name"].values, dtype=object)]
    zones = [str(x) for x in np.asarray(ds["Lighting_Zone"].values, dtype=object)]
    mapping = np.asarray(ds["logger_cave_mapping"].values)
    T = np.asarray(ds["Temperature"].values) - 273.15      # K -> °C
    RH = np.asarray(ds["Relative_Humidity"].values)
    time = pd.to_datetime(np.asarray(ds["time"].values))
    t_h = (time - time[0]).total_seconds().to_numpy() / 3600.0

    logger_cave = {}
    for li in range(mapping.shape[1]):
        col = mapping[:, li]
        logger_cave[li] = int(np.argmax(col)) if col.sum() > 0 else -1

    valid = [li for li in range(len(zones))
             if np.isfinite(RH[li]).sum() >= MIN_VALID
             and np.isfinite(T[li]).sum() >= MIN_VALID]

    caves: list[dict] = []
    for ci in range(len(names)):
        lg = [li for li in valid if logger_cave[li] == ci]
        light = [li for li in lg if zones[li] == "Light"]
        dark = [li for li in lg if zones[li] in ("Dark", "Twilight")]
        if not light or not dark:
            continue
        li_l = max(light, key=lambda i: np.isfinite(RH[i]).sum())
        li_d = max(dark, key=lambda i: np.isfinite(RH[i]).sum())

        drv = np.column_stack([T[li_l], RH[li_l]])
        X, ok_idx = build_features(drv)
        y = RH[li_d][ok_idx]
        m = np.isfinite(y)
        X, y = X[m], y[m]

        n = len(y)
        if n < 2000:
            continue
        if float(np.nanstd(y)) < 0.5:          # 与 validate_iccp 的 SD_FLOOR 一致
            continue
        ntr, nva = int(n * 0.6), int(n * 0.2)

        amp_d, _ = harmonic(t_h, RH[li_l], 24.0)
        amp_y, _ = harmonic(t_h, RH[li_l], 24.0 * 365.25)
        caves.append({
            "index": ci + 1,
            "name": names[ci],
            "n": n,
            "X": X,
            "y": y,
            "tr": slice(0, ntr),
            "va": slice(ntr, ntr + nva),
            "te": slice(ntr + nva, n),
            "coords": {
                "amp_diurnal_light": float(amp_d),
                "rh_mean_light": float(np.nanmean(RH[li_l])),
                "amp_annual_light": float(amp_y),
            },
            "n_test": int(n - (ntr + nva)),
        })
    return caves


# ------------------------------------------------------------------- 单折
def run_fold(caves: list[dict], hold: int, coord: str) -> dict[str, dict]:
    """留出 ``caves[hold]``，返回 {arm: {r2, rmse, beta}}。"""
    tgt = caves[hold]
    srcs = [c for k, c in enumerate(caves) if k != hold]
    s_star = float(tgt["coords"][coord])

    domains = [
        Domain(
            name=c["name"],
            s=float(c["coords"][coord]),
            Xtr=c["X"][c["tr"]], ytr=c["y"][c["tr"]],
            Xva=c["X"][c["va"]], yva=c["y"][c["va"]],
        )
        for c in srcs
    ]
    Xte, yte = tgt["X"][tgt["te"]], tgt["y"][tgt["te"]]

    res: dict[str, dict] = {}
    for arm in ARMS:
        oracle = None
        if arm == "oracle":
            oracle = Domain(
                name=tgt["name"], s=s_star,
                Xtr=tgt["X"][tgt["tr"]], ytr=tgt["y"][tgt["tr"]],
                Xva=tgt["X"][tgt["va"]], yva=tgt["y"][tgt["va"]],
            )
        g = DomainGeneralizer(method=arm)
        g.fit(domains, s_star=s_star, oracle=oracle)
        pred = g.predict(Xte, s_star)
        res[arm] = {
            "r2": float(r2(yte, pred)),
            "nrmse": float(rmse(yte, pred) / np.std(yte)),
            "rmse": float(rmse(yte, pred)),
            "beta": float(g.beta_),
        }
        if arm == "subspace":
            info = g.koopman_info(s_star)
            res[arm]["dims"] = int(info["dims"])
            res[arm]["shrink"] = float(info["shrink"])
        if arm == "koopman":
            info = g.koopman_info(s_star)
            ev = np.asarray(info["eigenvalues"])
            res[arm]["eig_absmax"] = float(np.max(np.abs(ev)))
            res[arm]["eig_re_max"] = float(np.max(ev.real))
            res[arm]["n_latent"] = int(info["n_latent"])
            res[arm]["sv_ratio"] = float(
                info["singular_values"][-1] / max(info["singular_values"][0], 1e-12)
            )
    return res


# ------------------------------------------------------------------- 主流程
def main() -> None:
    caves = load_caves()
    names = [c["name"] for c in caves]
    print(f"[ICCP] 有效洞 {len(caves)} 个：" + ", ".join(names))
    for c in caves:
        print(f"  - {c['name']:<18s} n={c['n']:>6d} n_test={c['n_test']:>5d} "
              f"amp_d={c['coords']['amp_diurnal_light']:6.2f} "
              f"rh_mean={c['coords']['rh_mean_light']:6.2f}")

    rows: list[dict] = []
    for coord in COORDS:
        for i, c in enumerate(caves):
            res = run_fold(caves, i, coord)
            for arm, m in res.items():
                rows.append({
                    "coord": coord, "fold": c["name"], "arm": arm,
                    "r2": round(m["r2"], 4), "rmse": round(m["rmse"], 4),
                    "nrmse": round(m["nrmse"], 4), "beta": m["beta"],
                    **({k: v for k, v in m.items()
                        if k.startswith("eig") or k in ("n_latent", "sv_ratio",
                                                        "dims", "shrink")}),
                })
            print(f"[{coord}] 留出 {c['name']:<18s} " +
                  " ".join(f"{a}={res[a]['r2']:+.3f}" for a in ARMS))

    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "dg_leave_one_cave_out.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # ---- 部署协议：域坐标也由源域内层留一选出（目标域零参与）
    print("\n=== 部署协议：域坐标由源域侧内层留一选出 ===")
    dep_rows: list[dict] = []
    for i, tgt in enumerate(caves):
        srcs = [c for k, c in enumerate(caves) if k != i]
        risks: dict[str, float] = {}
        for coord in COORDS:
            doms = [
                Domain(name=c["name"], s=float(c["coords"][coord]),
                       Xtr=c["X"][c["tr"]], ytr=c["y"][c["tr"]],
                       Xva=c["X"][c["va"]], yva=c["y"][c["va"]])
                for c in srcs
            ]
            probe = DomainGeneralizer(method="subspace")
            probe.fit(doms, s_star=float(tgt["coords"][coord]))
            risks[coord] = float(probe.info_["subspace"].get("best_risk", np.nan))
        chosen = min((c for c in COORDS if np.isfinite(risks[c])),
                     key=lambda c: risks[c], default=FALLBACK_COORD)
        sub = df[(df["coord"] == chosen) & (df["fold"] == tgt["name"])
                 & (df["arm"] == "subspace")].iloc[0]
        dep_rows.append({
            "fold": tgt["name"], "chosen_coord": chosen,
            "source_risk": {c: (None if not np.isfinite(v) else round(v, 4))
                            for c, v in risks.items()},
            "r2": float(sub["r2"]), "nrmse": float(sub["nrmse"]),
            "dims": int(sub["dims"]), "shrink": float(sub["shrink"]),
        })
        print(f"  留出 {tgt['name']:<18s} 选中坐标={chosen:<18s} "
              f"R²={sub['r2']:+.3f} nRMSE={sub['nrmse']:.3f} "
              f"(dims={int(sub['dims'])}, shrink={sub['shrink']:.1f})")

    dep = pd.DataFrame(dep_rows)
    dep_path = OUT / "dg_deployable_protocol.csv"
    dep.to_csv(dep_path, index=False, encoding="utf-8-sig")
    print(f"  部署协议中位数：R²={dep['r2'].median():+.4f} "
          f"nRMSE={dep['nrmse'].median():.4f} R²>0 的洞数={int((dep['r2'] > 0).sum())}/{len(dep)}")

    # ---- 汇总：主协议逐臂中位数 + 逐洞胜负
    summary: dict = {
        "protocol": "leave-one-cave-out (域 = 洞窟)，目标域零标签",
        "n_caves": len(caves),
        "caves": names,
        "arms": list(ARMS),
        "fallback_coord": FALLBACK_COORD,
        "coord_labels": COORD_LABEL,
        "source": "ICCP Zenodo 10.5281/zenodo.17505739 (CC-BY-4.0)",
        "per_coord": {},
    }
    for coord in COORDS:
        sub = df[df["coord"] == coord]
        piv_r2 = sub.pivot(index="fold", columns="arm", values="r2")
        piv_rmse = sub.pivot(index="fold", columns="arm", values="rmse")
        piv_n = sub.pivot(index="fold", columns="arm", values="nrmse")
        entry = {
            "median_r2": {a: round(float(piv_r2[a].median()), 4) for a in ARMS},
            "median_rmse": {a: round(float(piv_rmse[a].median()), 4) for a in ARMS},
            "median_nrmse": {a: round(float(piv_n[a].median()), 4) for a in ARMS},
            "mean_r2": {a: round(float(piv_r2[a].mean()), 4) for a in ARMS},
            "positive_r2_count": {a: int((piv_r2[a] > 0).sum()) for a in ARMS},
            "nrmse_below_1_count": {a: int((piv_n[a] < 1).sum()) for a in ARMS},
            "wins_vs_pooled": {
                a: int((piv_r2[a] > piv_r2["pooled"]).sum())
                for a in ARMS if a != "pooled"
            },
            "wins_vs_nearest": {
                a: int((piv_r2[a] > piv_r2["nearest"]).sum())
                for a in ARMS if a != "nearest"
            },
            "per_fold_r2": {
                f: {a: round(float(piv_r2.loc[f, a]), 4) for a in ARMS}
                for f in piv_r2.index
            },
            "per_fold_nrmse": {
                f: {a: round(float(piv_n.loc[f, a]), 4) for a in ARMS}
                for f in piv_n.index
            },
        }
        summary["per_coord"][coord] = entry
        best = max(ARMS, key=lambda a: entry["median_r2"][a])
        print(f"\n[{coord}] 各臂 R² 中位数（最优 = {best}）")
        for a in ARMS:
            print(f"   {a:<10s} median_r2={entry['median_r2'][a]:+9.4f} "
                  f"median_nRMSE={entry['median_nrmse'][a]:7.3f} "
                  f"R²>0 的洞数={entry['positive_r2_count'][a]}/{len(caves)} "
                  f"nRMSE<1 的洞数={entry['nrmse_below_1_count'][a]}/{len(caves)}")

    summary["deployable_protocol"] = {
        "note": "域坐标由源域侧内层留一风险选出（目标域零参与），逐洞记录",
        "per_fold": dep_rows,
        "median_r2": round(float(dep["r2"].median()), 4),
        "median_nrmse": round(float(dep["nrmse"].median()), 4),
        "positive_r2_count": int((dep["r2"] > 0).sum()),
        "nrmse_below_1_count": int((dep["nrmse"] < 1).sum()),
    }

    # ---- 与既有的洞内标定基线对照（validate_iccp 的产出）
    tr_path = OUT / "iccp_transfer.csv"
    if tr_path.exists():
        base = pd.read_csv(tr_path, encoding="utf-8-sig")
        summary["in_cave_baseline"] = {
            "note": "validate_iccp.py 的洞内标定结果，仅作上界对照；非迁移方法",
            "median_r2_operator_full": round(float(base["R2_Operator_Full"].median()), 4),
            "median_r2_first_order_transfer": round(
                float(base["R2_FirstOrderTransfer"].median()), 4),
            "median_rmse_operator_full": round(float(base["RMSE_Operator_Full"].median()), 4),
        }

    json_path = OUT / "dg_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"\n写出 {csv_path}\n写出 {json_path}")


if __name__ == "__main__":
    main()
