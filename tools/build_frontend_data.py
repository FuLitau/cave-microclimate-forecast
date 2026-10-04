# -*- coding: utf-8 -*-
"""把 code/results/ 的实验结果转成前端 TypeScript 常量。

用法：python tools/build_frontend_data.py
输出：frontend/src/data/{kpi,demo,history,ablation,compare,validate}.ts
每个数字都能在 docs/ 的对应 CSV 里找到出处；改动实验后重跑本脚本即可同步前端。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "code" / "results"
OUT = ROOT / "frontend" / "src" / "data"
OUT.mkdir(parents=True, exist_ok=True)


def w(name: str, body: str) -> None:
    (OUT / name).write_text(body, encoding="utf-8")
    print(f"  -> {name}")


def ts_array(rows, cols, wrap=str) -> str:
    """rows: list of tuples; cols: list of names."""
    lines = []
    for r in rows:
        vals = ", ".join(json.dumps(v) if isinstance(wrap, str) and wrap == "json" else v for v in r)
        lines.append("  { " + ", ".join(f"{c}: {vals_i}" for c, vals_i in zip(cols, _vals(r))) + " },")
    return "\n".join(lines)


def _vals(r):
    out = []
    for v in r:
        if isinstance(v, float):
            out.append(repr(round(v, 4)))
        elif isinstance(v, (int,)) or isinstance(v, str):
            out.append(json.dumps(v, ensure_ascii=False) if isinstance(v, str) else str(v))
        else:
            out.append(json.dumps(v, ensure_ascii=False))
    return out


def ts_table(rows, cols) -> str:
    lines = []
    for r in rows:
        pairs = ", ".join(f"{c}: {v}" for c, v in zip(cols, _vals(r)))
        lines.append("  { " + pairs + " },")
    return "\n".join(lines)


# ---------------- KPI ----------------
lead = pd.read_csv(RES / "derisk02_leadtime.csv")
l24 = lead[(lead.horizon_h == 24) & (lead.threshold == "62%(业务预警)") & (lead.model == "Operator-direct(本作品)")].iloc[0]
abc = pd.read_csv(RES / "exp03_abc_ablation.csv")
a62 = abc[(abc.segment == "test") & (abc.horizon_h == 24) & (abc.threshold == "62%(业务预警)")]
aA = a62[a62["mode"] == "A"].iloc[0]
aB = a62[a62["mode"] == "B"].iloc[0]

kpi = f"""// 关键指标（口径见 docs/03 §5.9；端到端 = 含 L1 预报误差；检出率/提前量为滚动预报口径）
export interface Kpi {{ label: string; value: string; sub: string; hint: string }}
export const kpis: Kpi[] = [
  {{ label: '超阈 F1（端到端）', value: '0.072 → 0.164', sub: '风险对齐训练后 · 测试段 2021–2025', hint: '24 h 时效 / 62% 阈值；MSE 基线 → MSE+twCRPS' }},
  {{ label: 'AUC（端到端）', value: '0.862 → 0.903', sub: '同口径六格全胜', hint: '验证/测试 × 24/48/72 h，62% 口径全部为正增益' }},
  {{ label: '预警检出率（上界）', value: '{l24.detect_rate * 100:.1f}%', sub: '{l24.n_onset} 次真实超阈起报事件命中 {l24.n_warned} 次', hint: '理想外场驱动：以真实未来再分析替代预报，属可部署性上界' }},
  {{ label: '平均首次预警提前', value: '{l24.mean_lead_h:.1f} h', sub: '事件前 72 h 窗口内滚动预报口径', hint: '连续滚动预报信号的累计提前量，非单次预报直接预见' }},
]
export const aucB = {aB.AUC:.4f}
export const aucA = {aA.AUC:.4f}
"""
w("kpi.ts", kpi)

# ---------------- demo 场景 ----------------
demo = pd.read_csv(RES / "demo_forecast.csv")
parts = []
for scen, g in demo.groupby("scenario", sort=False):
    g = g.sort_values("step_h")
    pts = ",\n".join(
        "    {{ t: {t!r}, rhOut: {o:.2f}, true: {tr:.2f}, p50: {p:.2f}, p90: {p9:.2f}, lin: {l:.2f}, advice: {adv}, cut62: {c62:.2f}, cut67: {c67:.2f}, cut75: {c75:.2f} }}".format(
            t=r.time, o=r.RH_out, tr=r.RH_true, p=r.RH_pred, p9=r.RH_pred_tau90, l=r.RH_pred_lin,
            adv=json.dumps(r.advice_raw, ensure_ascii=False), c62=r.cut_62, c67=r.cut_67, c75=r.cut_75,
        )
        for r in g.itertuples()
    )
    parts.append(f"  {{\n    name: {json.dumps(scen, ensure_ascii=False)},\n    points: [\n{pts}\n    ]\n  }}")
demo_ts = (
    "// 演示场景：文献标定物理模型生成的窟内序列 + 算子预报（τ=0.95 分位数读出）\n"
    "// lin = 未做风险对齐的 MSE 线性读出（同驱动对照），出处 code/results/demo_forecast.csv\n"
    "export interface DemoPoint { t: string; rhOut: number; true: number; p50: number; p90: number; lin: number; advice: string; cut62: number; cut67: number; cut75: number }\n"
    "export interface DemoScenario { name: string; points: DemoPoint[] }\n"
    "export const scenarios: DemoScenario[] = [\n" + ",\n".join(parts) + "\n]\n"
)
w("demo.ts", demo_ts)

# ---------------- 4 年历史（按日重采样） ----------------
h = pd.read_csv(RES / "demo_history.csv", parse_dates=["time"])
g = h.set_index("time").resample("D").agg(rh_in_mean=("RH_in", "mean"), rh_in_max=("RH_in", "max"), rh_out_mean=("RH_out", "mean")).reset_index()
g = g[g.rh_in_mean.notna()]
rows = ",\n".join(
    "  {{ t: '{d}', mean: {m:.2f}, max: {x:.2f}, out: {o:.2f} }}".format(
        d=r.time.strftime("%Y-%m-%d"), m=r.rh_in_mean, x=r.rh_in_max, o=r.rh_out_mean)
    for r in g.itertuples()
)
hist_ts = (
    "// 演示窟 4 年逐日窟内 RH（均值/日最大）与窟外均值，出处 code/results/demo_history.csv\n"
    "export interface HistPoint { t: string; mean: number; max: number; out: number }\n"
    "export const history: HistPoint[] = [\n" + rows + "\n]\n"
)
w("history.ts", hist_ts)

stats = json.loads((RES / "demo_stats.json").read_text(encoding="utf-8"))
stats_ts = (
    "// 出处 code/results/demo_stats.json\n"
    "export const demoStats = " + json.dumps(
        {k: stats[k] for k in ("RH_in_mean", "RH_in_min", "RH_in_max", "frac_gt62", "frac_gt67", "frac_gt75", "n_hours", "period")},
        ensure_ascii=False, indent=2) + "\n"
)
w("stats.ts", stats_ts)

# ---------------- 消融 A/B/C ----------------
rows = []
for (mode, thr), gg in abc[(abc.segment == "test")].groupby(["mode", "threshold"]):
    g24 = gg[gg.horizon_h == 24]
    if g24.empty:
        continue
    r = g24.iloc[0]
    rows.append((mode, thr.split("%")[0], float(r.F1), float(r.AUC), float(r.pt_R2), float(r.pred_max)))
mode_name = {"A": "A · MSE（现有做法）", "B": "B · MSE + twCRPS（固定阈值）", "C": "C · + 算子导出内生权重"}
ablation_rows = ",\n".join(
    "  {{ mode: '{}', modeName: {}, thr: '{}', F1: {:.4f}, AUC: {:.4f}, ptR2: {:.4f}, predMax: {:.2f} }}".format(
        m, json.dumps(mode_name[m], ensure_ascii=False), t, f1, auc, pt, pmax)
    for m, t, f1, auc, pt, pmax in rows
)
ablation_ts = (
    "// 消融实验（测试段 24h，出处 code/results/exp03_abc_ablation.csv）\n"
    "export interface AblRow { mode: string; modeName: string; thr: string; F1: number; AUC: number; ptR2: number; predMax: number }\n"
    "export const ablation: AblRow[] = [\n" + ablation_rows + "\n]\n"
)
w("ablation.ts", ablation_ts)

# ---------------- 多模型对比 ----------------
ev = pd.read_csv(RES / "derisk02_events.csv")
e24 = ev[(ev.horizon_h == 24) & (ev.threshold == "62%(业务预警)")]
cmp_rows = ",\n".join(
    "  {{ model: {}, AUC: {:.4f}, F1: {:.4f}, recall: {:.4f}, precision: {:.4f} }}".format(
        json.dumps(r.model, ensure_ascii=False), r.AUC, r.F1, r.recall, r.precision)
    for r in e24.itertuples()
)
lt_rows = ",\n".join(
    "  {{ model: {}, detect: {:.4f}, lead: {:.2f} }}".format(
        json.dumps(r.model, ensure_ascii=False), r.detect_rate, r.mean_lead_h)
    for r in lead[(lead.horizon_h == 24) & (lead.threshold == "62%(业务预警)")].itertuples()
)
b1 = pd.read_csv(RES / "derisk01_model_comparison.csv")
base_rows = ",\n".join(
    "  {{ model: {}, RMSE: {:.3f}, R2: {:.4f} }}".format(
        json.dumps(r.model, ensure_ascii=False), r.RMSE, r.R2)
    for r in b1.itertuples()
)

# 94 次超阈事件命中点阵（24h / 62% 档；递归形式从不在 derisk02 表中产生报警行，检出率 0.0% 见 docs/03 §5.9）
l62 = lead[(lead.horizon_h == 24) & (lead.threshold == "62%(业务预警)")]
on62 = int(l62[l62.model.str.contains("本作品")].iloc[0].n_onset)
hit_op = int(l62[l62.model.str.contains("本作品")].iloc[0].n_warned)
hit_fot = int(l62[l62.model.str.contains("初稿形式")].iloc[0].n_warned)
events62_ts = (
    "\n// 94 次真实超阈起报事件的命中数（24h / 62% 档，出处 code/results/derisk02_leadtime.csv）\n"
    "export interface EventRow { name: string; hit: number; onset: number; note: string }\n"
    "export const events62: EventRow[] = [\n"
    f"  {{ name: '本作品 · 风险对齐预警', hit: {hit_op}, onset: {on62}, note: '风险分数滚动预警' }},\n"
    f"  {{ name: '初稿 · 直接传递形式', hit: {hit_fot}, onset: {on62}, note: '未做风险对齐的可部署化形式' }},\n"
    f"  {{ name: '初稿 · 递归推演', hit: 0, onset: {on62}, note: '极点 > 1 必然饱和，从不能发出预警' }},\n"
    "]\n"
)
cmp_ts = (
    "// 多模型对比（24h / 62% 档，出处 code/results/derisk02_events.csv、derisk02_leadtime.csv、derisk01_model_comparison.csv）\n"
    "export interface CmpRow { model: string; AUC: number; F1: number; recall: number; precision: number }\n"
    "export const models24: CmpRow[] = [\n" + cmp_rows + "\n]\n"
    "export interface LeadRow { model: string; detect: number; lead: number }\n"
    "export const leadtime: LeadRow[] = [\n" + lt_rows + "\n]\n"
    "export interface BaseRow { model: string; RMSE: number; R2: number }\n"
    "export const baselines: BaseRow[] = [\n" + base_rows + "\n]\n"
    + events62_ts
)
w("compare.ts", cmp_ts)

# ---------------- 外部验证 ----------------
ic = pd.read_csv(RES / "iccp_transfer.csv", encoding="utf-8-sig")
iccp_rows = ",\n".join(
    "  {{ cave: {}, name: {}, r2Fot: {:.4f}, r2Op: {:.4f} }}".format(
        int(r.cave), json.dumps(r.name, ensure_ascii=False), r.R2_FirstOrderTransfer, r.R2_Operator_Full)
    for r in ic.itertuples()
)
cc = pd.read_csv(RES / "validate_crosscave.csv")
cc_rows = ",\n".join(
    "  {{ metric: {}, lo: {:.2f}, hi: {:.2f}, litLo: {:.2f}, litHi: {:.2f}, pass: {} }}".format(
        json.dumps(r["metric"], ensure_ascii=False), r["model_lo"], r["model_hi"], r["lit_lo"], r["lit_hi"],
        "true" if r["pass"] else "false")
    for _, r in cc.iterrows()
)
isd = pd.read_csv(RES / "isd_vs_power.csv")
isd_rows = ",\n".join(
    "  {{ variable: {}, r: {:.4f} }}".format(json.dumps(r.variable, ensure_ascii=False), r.r)
    for r in isd.itertuples()
)
val_ts = (
    "// 外部验证（出处 code/results/iccp_transfer.csv、validate_crosscave.csv、isd_vs_power.csv）\n"
    "export interface IccpRow { cave: number; name: string; r2Fot: number; r2Op: number }\n"
    "export const iccp: IccpRow[] = [\n" + iccp_rows + "\n]\n"
    "export interface CrossRow { metric: string; lo: number; hi: number; litLo: number; litHi: number; pass: boolean }\n"
    "export const crosscave: CrossRow[] = [\n" + cc_rows + "\n]\n"
    "export interface IsdRow { variable: string; r: number }\n"
    "export const isd: IsdRow[] = [\n" + isd_rows + "\n]\n"
)
w("validate.ts", val_ts)

print("前端数据生成完毕")
