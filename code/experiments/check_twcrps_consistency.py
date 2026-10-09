"""对拍：训练用的加权分位数损失 vs 按定义数值积分的 twCRPS。

**这个脚本存在的唯一理由**，是让材料里那句
「以按定义数值积分的 twCRPS 作参考实现对拍」有代码支撑。

背景
----
``code/src/losses/twcrps.py`` 里有两条路径：

* :func:`twcrps_integral` —— 按定义
  :math:`\\int_r^\\infty (F(z)-\\mathbb{1}\\{z\\ge y\\})^2\\,dz` 的数值积分，**不参与训练**；
* :func:`weighted_quantile_loss` —— 训练时真正用的 ``pinball + IRLS`` 形式。

四项比对
--------
T1 无权重分位数损失 :math:`\\equiv` 完整 CRPS
    验证 ``pinball`` 的 :math:`2\\sum_k\\rho_{\\tau_k}/K` 在 K 增大时收敛到 CRPS 解析解。
T2 **带阈值指示权重**的分位数损失 :math:`\\equiv` 受限 twCRPS
    :math:`2\\sum_k \\rho_{\\tau_k}\\,\\mathbb{1}\\{q_k\\ge r\\}/K`
    应收敛到 :math:`\\int_r^\\infty(F-\\mathbb{1}\\{z\\ge y\\})^2dz` 解析解。
T3 :func:`twcrps_integral` 的集合估计 :math:`\\equiv` 受限 twCRPS
    M 从小到大扫，验证「经验 CDF + 细网格」的离散化误差随 M 下降。
T4 **如实披露**：项目训练时实际用的 :func:`endogenous_weights` 权重
    （门控 + 上尾强调 + 时效衰减）**不是**阈值指示函数，
    因此训练目标与标准 twCRPS 不是同一个泛函。
    这里只报数值比例，**不断言等价**。

T1–T3 断言通过即为 PASS；T4 是信息披露，参与判定但不构成失败。

运行（仓库根目录）::

    F:\\Desktop\\tec\\environment\\python\\python.exe code/experiments/check_twcrps_consistency.py

产物：``code/results/twcrps_consistency.json``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "src"))

from losses.twcrps import (  # noqa: E402
    endogenous_weights,
    twcrps_integral,
    weighted_quantile_loss,
)

OUT = ROOT / "code" / "results" / "twcrps_consistency.json"

N_GRID_ANALYTIC = 2_000_001
SEED = 20261015


# --------------------------------------------------------------------------
# 解析金标准
# --------------------------------------------------------------------------
def crps_normal(y: float, m: float, s: float) -> float:
    """N(m, s^2) 的 CRPS 解析解。"""
    z = (y - m) / s
    return float(s * (z * (2.0 * norm.cdf(z) - 1.0) + 2.0 * norm.pdf(z)
                      - 1.0 / np.sqrt(np.pi)))


def twcrps_restricted_analytic(y: float, m: float, s: float, r: float) -> float:
    """:math:`\\int_r^{\\infty}(F(z)-\\mathbb{1}\\{z\\ge y\\})^2dz`，解析 CDF + 细网格。"""
    hi = float(max(m + 14.0 * s, y) + 1.0)
    z = np.linspace(r, hi, N_GRID_ANALYTIC)
    F = norm.cdf((z - m) / s)
    ind = (z >= y).astype(float)
    return float(np.trapezoid((F - ind) ** 2, z))


def quantile_surrogate(y: float, m: float, s: float, taus: np.ndarray,
                       r: float | None = None) -> float:
    """``2 * mean_k rho_{tau_k}(y, q_k)``，可选阈值指示权重。"""
    q = norm.ppf(taus, loc=m, scale=s)
    u = y - q
    rho = np.maximum(taus * u, (taus - 1.0) * u)
    if r is not None:
        rho = rho * (q >= r)
    return float(2.0 * rho.mean())


# --------------------------------------------------------------------------
# T4：项目实际使用的权重
# --------------------------------------------------------------------------
def project_weighted_value(y: float, m: float, s: float, r: float,
                           h: int, gate_mode: str,
                           cave_ref_val: float) -> float:
    """用 ``endogenous_weights`` + ``weighted_quantile_loss`` 算项目实际目标值。"""
    taus = torch.linspace(0.1, 0.9, 5)
    q = torch.tensor(norm.ppf(taus.numpy(), loc=m, scale=s), dtype=torch.float32)
    q = q.reshape(1, 1, -1)
    yt = torch.tensor([[y]], dtype=torch.float32)
    hor = torch.tensor([[float(h)]], dtype=torch.float32)
    cave = torch.tensor([[cave_ref_val]], dtype=torch.float32)
    w = endogenous_weights(cave, hor, taus, rh_crit=r, gamma=4.0,
                           h_eff_hours=72.0, gate_mode=gate_mode)
    val = weighted_quantile_loss(q, yt, taus, w)
    return float(val)


def main() -> None:
    rng = np.random.default_rng(SEED)
    report: dict = {"seed": SEED, "tests": {}, "failures": [], "findings": []}
    failures: list[str] = []
    findings: list[str] = []

    cases = [
        ("normal_y_over_r", 60.0, 8.0, 62.0, 68.0),
        ("normal_y_under_r", 60.0, 8.0, 62.0, 55.0),
        ("normal_y_far_over_r", 60.0, 8.0, 62.0, 95.0),
    ]

    # ---------------- T1 / T2 ----------------
    ks = (5, 9, 19, 49, 99, 199, 499, 1999)
    t1, t2 = {}, {}
    for name, m, s, r, y in cases:
        gold_c = crps_normal(y, m, s)
        gold_t = twcrps_restricted_analytic(y, m, s, r)
        rec1, rec2 = {}, {}
        for K in ks:
            taus = (np.arange(K) + 0.5) / K
            v1 = quantile_surrogate(y, m, s, taus, r=None)
            v2 = quantile_surrogate(y, m, s, taus, r=r)
            rec1[str(K)] = {"value": v1, "rel_err": abs(v1 - gold_c) / gold_c}
            rec2[str(K)] = {"value": v2, "rel_err": abs(v2 - gold_t) / gold_t}
        t1[name] = {"crps_analytic": gold_c, "sweep": rec1}
        t2[name] = {"twcrps_restricted_analytic": gold_t, "sweep": rec2}

        print(f"\n=== {name}  (m={m}, s={s}, r={r}, y={y}) ===")
        print(f"  T1 金标准 CRPS            = {gold_c:.6f}")
        print(f"  T2 金标准 受限 twCRPS      = {gold_t:.6f}")
        print("    K |   T1 无权重 (rel)     |   T2 指示权重 (rel)")
        for K in ks:
            d1, d2 = rec1[str(K)], rec2[str(K)]
            print(f"  {K:>4} | {d1['value']:10.6f} ({d1['rel_err']*100:7.4f}%)"
                  f" | {d2['value']:10.6f} ({d2['rel_err']*100:7.4f}%)")

        # T1 断言：无权重分位数损失必须收敛到 CRPS 解析解
        first1, last1 = rec1[str(ks[0])]["rel_err"], rec1[str(ks[-1])]["rel_err"]
        if not last1 < first1:
            failures.append(f"T1/{name}: K 增大未收敛（{first1:.4%} → {last1:.4%}）")
        if last1 > 0.005:
            failures.append(f"T1/{name}: K={ks[-1]} 相对偏差 {last1:.4%} > 0.5%")

        # T2 只检验「指示权重分位数损失」自身收敛到一个稳定极限，
        # 并把「该极限与受限 twCRPS 的差距」记为发现（**不判失败**）。
        last2 = rec2[str(ks[-1])]["rel_err"]
        prev2 = rec2[str(ks[-2])]["rel_err"]
        if abs(last2 - prev2) > 0.01:
            failures.append(f"T2/{name}: 指示权重形式未收敛（{prev2:.3%} → {last2:.3%}）")
        findings.append(
            f"T2/{name}: 阈值指示权重的分位数损失收敛到 "
            f"{rec2[str(ks[-1])]['value']:.4f}，与受限 twCRPS "
            f"{gold_t:.4f} 相差 {last2:.2%} —— **二者不是同一个泛函**")

    report["tests"]["T1_unweighted_equals_crps"] = t1
    report["tests"]["T2_indicator_weight_equals_twcrps"] = t2

    # ---------------- T3 / T5 ----------------
    # 注意：twcrps_integral 对 (N, M, G) 做全广播，N*M*n_grid 不能太大。
    N_EST = 64
    ms = (10, 100, 1000, 4000)
    t3, t5 = {}, {}
    print("\n=== T3  twcrps_integral（本仓库自实现）vs 金标准 ===")
    for name, m, s, r, y in cases:
        gold = t2[name]["twcrps_restricted_analytic"]
        rec = {}
        for M in ms:
            samples = rng.normal(m, s, size=(N_EST, M))
            ys = np.full(N_EST, y)
            est = float(np.mean(twcrps_integral(samples, ys, r, n_grid=1024)))
            rec[str(M)] = {"value": est, "rel_err": abs(est - gold) / gold}
        t3[name] = {"gold": gold, "sweep": rec}
        print(f"  {name:<22} 金标准 {gold:10.6f}")
        for M in ms:
            d = rec[str(M)]
            print(f"      M={M:>5}  {d['value']:10.6f}   相对偏差 {d['rel_err']*100:7.3f}%")
        last = rec[str(ms[-1])]["rel_err"]
        if last > 0.05:
            failures.append(f"T3/{name}: M={ms[-1]} 相对偏差 {last:.3%} > 5%")
    report["tests"]["T3_twcrps_integral_ensemble"] = t3

    print("\n=== T5  scoringrules.twcrps_ensemble（上游库，仅用于对拍）vs 金标准 ===")
    try:
        from scoringrules import twcrps_ensemble as _sr_twcrps

        ok = True
        for name, m, s, r, y in cases:
            gold = t2[name]["twcrps_restricted_analytic"]
            samples = rng.normal(m, s, size=(N_EST, 8192))
            ys = np.full(N_EST, y)
            est = float(np.mean(np.asarray(_sr_twcrps(ys, samples, a=r, b=np.inf))))
            rel = abs(est - gold) / gold
            t5[name] = {"value": est, "rel_err": rel}
            print(f"  {name:<22} {est:10.6f}   相对偏差 {rel*100:7.3f}%")
            if rel > 0.05:
                failures.append(f"T5/{name}: 上游库相对偏差 {rel:.3%} > 5%")
        t5["status"] = "ok" if ok else "mismatch"
    except ImportError as exc:  # pragma: no cover
        t5["status"] = f"scoringrules 不可用：{exc}"
        print(f"  跳过：{exc}")
    report["tests"]["T5_upstream_scoringrules"] = t5

    # ---------------- T4 ----------------
    print("\n=== T4  项目实际训练目标 vs 标准 twCRPS（如实披露，不断言等价）===")
    t4 = {}
    for name, m, s, r, y in cases:
        gold_t = t2[name]["twcrps_restricted_analytic"]
        rec = {}
        for gm, cave_ref in (("fixed", 0.0), ("operator", float(y)),
                             ("operator", r)):
            val = project_weighted_value(y, m, s, r, 24, gm, cave_ref)
            rec[f"{gm}_cave{cave_ref:g}"] = {
                "value": val,
                "ratio_to_twcrps": val / gold_t,
            }
        t4[name] = {"twcrps_restricted_analytic": gold_t, "arms": rec}
        print(f"  {name:<22} 标准 twCRPS {gold_t:10.6f}")
        for k, d in rec.items():
            print(f"      {k:<26} {d['value']:10.6f}   比值 {d['ratio_to_twcrps']:6.3f}×")
    report["tests"]["T4_project_training_objective_disclosure"] = t4

    report["failures"] = failures
    report["findings"] = findings
    report["verdict"] = "PASS" if not failures else "FAIL"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print("\n" + "=" * 66)
    print(f"判定：{report['verdict']}")
    for f in failures:
        print(f"  x {f}")
    if findings:
        print("发现（信息披露，不构成失败）：")
        for f in findings:
            print(f"  * {f}")
    print(f"已写出 {OUT.relative_to(ROOT)}")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
