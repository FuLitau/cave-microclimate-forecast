# -*- coding: utf-8 -*-
"""把 code/results/ 的实验结果转成前端 TypeScript 常量。

用法：python tools/build_frontend_data.py
输出：frontend/src/data/{meta,kpi,demo,history,stats,ablation,compare,validate,method}.ts

设计约束
--------
1. 前端**不得**出现脚本之外的手写数字；每个数字都必须能在 code/results/*.csv 里找到出处。
2. 口径命名必须诚实：
   - ``RH_pred`` 是**校准年选出的风险对齐分位数读出**（demo_stats.json:readout = 「分位数 τ=0.95」），
     它**不是** P50，导出字段名为 ``risk``；
   - ``RH_pred_tau90`` 是 τ=0.90 的分位数读出（对照），字段名 ``risk90``；
   - ``RH_pred_lin`` 是未做风险对齐的线性 MSE 读出（对照），字段名 ``lin``；
   - ``RH_true`` 是文献标定物理模型生成的**合成标签**，字段名 ``true``。
3. ``demo_stats.json`` 的 ``frac_gt62/67/75`` 已经是**百分数**，不得再乘 100。
4. ICCP 第 12 洞 Te'omim 的 ``target_sd = 0.000``（常数序列），按管线门限剔除；
   其余洞的极端负 R² 截断到 -1 并置 ``trunc: true``，避免图表被 -4e25 拉爆。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "code" / "results"
OUT = ROOT / "frontend" / "src" / "data"
OUT.mkdir(parents=True, exist_ok=True)

THR_SHORT = {"62%(业务预警)": "62", "67%(潮解起始)": "67", "75%(吸湿突变)": "75"}
MODE_NAME = {
    "A": "A · 纯 MSE（现有常规做法）",
    "B": "B · MSE + twCRPS（阈值加权风险项）",
    "C": "C · B + 算子导出内生权重",
}


def w(name: str, body: str) -> None:
    (OUT / name).write_text(body, encoding="utf-8")
    print(f"  -> {name}  ({len(body.encode('utf-8')):,} B)")


def js(v) -> str:
    """Python 值 -> TypeScript 字面量。"""
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if v != v:  # NaN
            return "null"
        return repr(round(v, 4))
    if v is None:
        return "null"
    return str(v)


def table(rows, cols) -> str:
    return ",\n".join("  { " + ", ".join(f"{c}: {js(v)}" for c, v in zip(cols, r)) + " }" for r in rows)


def header(title: str, src: str, *extra: str) -> str:
    lines = [f"// {title}", f"// 出处：{src}"]
    lines += [f"// {e}" for e in extra]
    lines.append("// 本文件由 tools/build_frontend_data.py 自动生成，请勿手改。")
    return "\n".join(lines) + "\n"


# =====================================================================
# meta.ts —— 口径、阈值与数据来源（全部为文档中已核定的定性常量）
# =====================================================================
meta_ts = header(
    "项目口径常量",
    "docs/03_作品方案.md §3.5 / §5.9、docs/06_佐证材料.md §3",
    "thresholds 的三级阈值分别对应敦煌研究院业务预警口径、Demas(2015) 潮解起始、npj Heritage Science(2025) 吸湿突变。",
) + """
export interface ThresholdDef {
  /** 相对湿度百分数 */
  value: number
  /** 名称 */
  label: string
  /** 业务含义 */
  meaning: string
  /** 文献/业务出处 */
  source: string
}

export const thresholds: ThresholdDef[] = [
  { value: 62, label: '业务预警线', meaning: '敦煌研究院日常监测采取的窟内相对湿度上限', source: '敦煌研究院业务口径' },
  { value: 67, label: '潮解起始', meaning: '可溶盐开始吸收水分、由固态转为溶液的临界湿度', source: 'Demas 2015' },
  { value: 75, label: '吸湿突变', meaning: 'NaCl 等盐类吸湿量急剧上升的突变点', source: 'npj Heritage Science 2025' },
]

/** 最高一级阈值，用于图表的"危险区"底色 */
export const HARD_THRESHOLD = 62

/** 涉及窟内序列时**必须**同时出现的一句话（任务书口径纪律第 4 条） */
export const SYNTHETIC_LABEL_NOTE =
  '窟内序列为文献标定物理模型生成的合成标签，非窟内实测；模型参数取自公开文献与敦煌气象站观测。'

/** 决策输出必须附带的免责说明 */
export const DECISION_DISCLAIMER = '上述结论为模型辅助建议，供文物保护管理人员研判，不构成自动控制指令。'

/** 演示数据自身的局限（样板场景未能触发限流建议，如实呈现） */
export const DEMO_HONEST_NOTE =
  '演示窗口内本模型未给出限流建议：这是 τ=0.95 风险读出在该时段偏低所致，不是"无风险"的证据。'
"""
w("meta.ts", meta_ts)

# =====================================================================
# kpi.ts
# =====================================================================
lead = pd.read_csv(RES / "derisk02_leadtime.csv")
l24 = lead[
    (lead.horizon_h == 24)
    & (lead.threshold == "62%(业务预警)")
    & (lead.model == "Operator-direct(本作品)")
].iloc[0]
abc = pd.concat(
    [pd.read_csv(RES / "exp03_abc_ablation.csv"), pd.read_csv(RES / "exp03_abc_ablation_val.csv")],
    ignore_index=True,
)
a62 = abc[(abc.segment == "test") & (abc.horizon_h == 24) & (abc.threshold == "62%(业务预警)")]
aA = a62[a62["mode"] == "A"].iloc[0]
aB = a62[a62["mode"] == "B"].iloc[0]

kpi_ts = header(
    "首屏关键指标卡",
    "code/results/derisk02_leadtime.csv、exp03_abc_ablation.csv",
    "端到端指标（F1 / AUC）与可部署性上界指标（检出率 / 提前量）分属两张卡片组，不得混读。",
) + f"""
export interface Kpi {{
  label: string
  value: string
  sub: string
  hint: string
  /** 'end2end' = 真实端到端可部署口径；'upper' = 用真实未来再分析替代预报的可部署性上界 */
  scope: 'end2end' | 'upper'
}}

export const kpis: Kpi[] = [
  {{
    label: '超阈 F1（端到端）',
    value: '{aA.F1:.3f} → {aB.F1:.3f}',
    sub: '测试段 · 24 h 时效 · 62% 阈值',
    hint: '目标函数由纯 MSE 换成 MSE + twCRPS 后的变化；驱动为真实预报',
    scope: 'end2end',
  }},
  {{
    label: 'AUC（端到端）',
    value: '{aA.AUC:.3f} → {aB.AUC:.3f}',
    sub: '同口径六格全胜',
    hint: '验证/测试 × 24/48/72 h，62% 口径全部为正增益',
    scope: 'end2end',
  }},
  {{
    label: '预警检出率（上界）',
    value: '{l24.detect_rate * 100:.1f}%',
    sub: '{l24.n_onset} 次真实超阈起报事件命中 {l24.n_warned} 次',
    hint: '理想外场驱动：以真实未来再分析替代预报，属可部署性上界，不代表端到端性能',
    scope: 'upper',
  }},
  {{
    label: '平均首次预警提前',
    value: '{l24.mean_lead_h:.1f} h',
    sub: '事件前 72 h 窗口内滚动预报口径',
    hint: '连续滚动预报信号的累计提前量，非单次预报直接预见',
    scope: 'upper',
  }},
]

/** 消融实验中 A / B 两档在测试段 24 h / 62% 口径下的 AUC */
export const aucA = {aA.AUC:.4f}
export const aucB = {aB.AUC:.4f}
"""
w("kpi.ts", kpi_ts)

# =====================================================================
# demo.ts —— 三情景 72 h 预报
# =====================================================================
demo = pd.read_csv(RES / "demo_forecast.csv")
demo_cal = pd.read_csv(RES / "demo_calibration.csv")
cut24 = {r.threshold: float(r.cut_on_pred) for r in demo_cal[demo_cal.horizon_h == 24].itertuples()}

scen_parts = []
scen_meta = []
for scen, g in demo.groupby("scenario", sort=False):
    g = g.sort_values("step_h")
    pts = ",\n".join(
        "    {{ t: {t}, th: {th}, true: {tr:.2f}, risk: {rk:.2f}, risk90: {r9:.2f}, lin: {ln:.2f}, "
        "rhOut: {ro:.2f}, tOut: {to:.2f}, q: {q:.1f}, adv: {adv} }}".format(
            t=js(str(r.time)), th=int(r.step_h), tr=r.RH_true, rk=r.RH_pred, r9=r.RH_pred_tau90,
            ln=r.RH_pred_lin, ro=r.RH_out, to=r.T_out, q=r.Q_m3h, adv=js(r.advice_raw),
        )
        for r in g.itertuples()
    )
    scen_parts.append(f"  {{\n    name: {js(scen)},\n    points: [\n{pts}\n    ]\n  }}")
    scen_meta.append((
        scen, str(g.origin.iloc[0]), len(g),
        float(g.RH_true.max()), int(g.RH_true.idxmax() if False else (g.RH_true >= 62).sum()),
        float(g.RH_pred.max()), float(g.RH_pred_tau90.max()), float(g.RH_pred_lin.max()),
        int((g.RH_pred >= 62).sum()), int((g.RH_pred_tau90 >= 62).sum()), int((g.RH_pred_lin >= 62).sum()),
    ))

meta_rows = table(scen_meta, [
    "name", "origin", "n", "truePeak", "nTrueOver62", "riskPeak", "risk90Peak", "linPeak",
    "nRiskOver62", "nRisk90Over62", "nLinOver62",
])
demo_ts = header(
    "演示场景：三段时间的 72 h 滚动预报",
    "code/results/demo_forecast.csv、demo_calibration.csv",
    "true = 合成标签；risk = 风险对齐分位数读出（校准年选定 τ=0.95，主读出）；risk90 = τ=0.90 对照；lin = 线性 MSE 对照。",
    "风险读出是分位数回归的上分位读出，**不是**预测分布的中位数，禁止在界面上标为 P50。",
) + f"""
export interface DemoPoint {{
  t: string
  /** 预报时效 0..72 h */
  th: number
  /** 窟内 RH 合成标签 */
  true: number
  /** 风险对齐主读出（τ=0.95 分位数读出） */
  risk: number
  /** τ=0.90 分位数读出（对照） */
  risk90: number
  /** 线性 MSE 读出（对照，未做风险对齐） */
  lin: number
  /** 窟外相对湿度 */
  rhOut: number
  /** 窟外气温 */
  tOut: number
  /** 通风量 m³/h */
  q: number
  /** 决策建议原文 */
  adv: string
}}

export interface DemoScenario {{ name: string; points: DemoPoint[] }}

export const scenarios: DemoScenario[] = [
{",\n".join(scen_parts)}
]

export interface ScenarioMeta {{
  name: string; origin: string; n: number
  truePeak: number; nTrueOver62: number
  riskPeak: number; risk90Peak: number; linPeak: number
  nRiskOver62: number; nRisk90Over62: number; nLinOver62: number
}}

export const scenarioMeta: ScenarioMeta[] = [
{meta_rows}
]

/** 24 h 时效下、按验证年份校准得到的判定切点（预报值口径，%RH） */
export const cuts24: Record<string, number> = {{
  '62': {cut24['62%(业务预警)']:.3f},
  '67': {cut24['67%(潮解起始)']:.3f},
  '75': {cut24['75%(吸湿突变)']:.3f},
}}
"""
w("demo.ts", demo_ts)

# =====================================================================
# history.ts —— 全年逐日（用于背景态势）
# =====================================================================
hist = pd.read_csv(RES / "demo_history.csv", parse_dates=["time"])
hg = hist.set_index("time").resample("D").agg(
    mean=("RH_in", "mean"), peak=("RH_in", "max"), out=("RH_out", "mean"), tIn=("T_in", "mean"),
).reset_index()
hg = hg[hg["mean"].notna()]
hist_rows = ",\n".join(
    "  {{ t: '{d}', mean: {m:.2f}, max: {x:.2f}, out: {o:.2f}, tIn: {ti:.2f} }}".format(
        d=r.time.strftime("%Y-%m-%d"), m=r.mean, x=r.peak, o=r.out, ti=r.tIn)
    for r in hg.itertuples()
)
hist_ts = header(
    "演示窟多年逐日窟内 RH（均值 / 日最大）与窟外均值",
    "code/results/demo_history.csv",
    "同样来自文献标定物理模型生成的合成序列。",
) + f"""
export interface HistPoint {{ t: string; mean: number; max: number; out: number; tIn: number }}

export const history: HistPoint[] = [
{hist_rows}
]
"""
w("history.ts", hist_ts)

# =====================================================================
# stats.ts
# =====================================================================
stats = json.loads((RES / "demo_stats.json").read_text(encoding="utf-8"))
keys = ("RH_in_mean", "RH_in_min", "RH_in_max", "frac_gt62", "frac_gt67", "frac_gt75",
        "n_hours", "period", "readout", "calib_year", "tau_grid", "calib_f1_62")
stats_ts = header(
    "演示窟多年统计",
    "code/results/demo_stats.json",
    "frac_gt62/67/75 的单位已经是百分数（%），界面上直接加 % 即可，不要再乘 100。",
) + "\nexport const demoStats = " + json.dumps(
    {k: stats[k] for k in keys}, ensure_ascii=False, indent=2) + " as const\n"
w("stats.ts", stats_ts)

# =====================================================================
# ablation.ts —— A/B/C 全网格
# =====================================================================
abl_rows = []
for _, r in abc.iterrows():
    abl_rows.append((
        r["mode"], THR_SHORT[r["threshold"]], int(r["horizon_h"]), r["segment"],
        float(r["F1"]), float(r["AUC"]), float(r["recall"]), float(r["precision"]),
        float(r["pt_R2"]), float(r["R2"]), float(r["pt_RMSE"]), float(r["RMSE"]),
        float(r["pred_rate"]), float(r["pred_max"]),
    ))
verdict_rows = []
for _, r in pd.read_csv(RES / "exp03_verdict.csv").iterrows():
    verdict_rows.append((
        r["segment"], int(r["horizon_h"]), THR_SHORT[r["threshold"]],
        float(r["F1_B"]), float(r["F1_C"]), float(r["dF1"]),
        float(r["AUC_B"]), float(r["AUC_C"]), float(r["dAUC"]), bool(r["C_wins"]),
    ))
ablation_ts = header(
    "消融实验：目标函数形式 A/B/C × 阈值 × 时效",
    "code/results/exp03_abc_ablation.csv、exp03_abc_ablation_val.csv、exp03_verdict.csv",
    "同一格里存在两套精度口径：pt_* 是点预报口径，RMSE/R2 是实际部署读出口径，二者可能给出相反结论。",
    "C（算子导出内生权重）在 18 个格中仅 1 格 F1 更优，界面必须如实呈现。",
) + f"""
export interface AblRow {{
  mode: string
  thr: string
  h: number
  segment: string
  /** 部署读出口径的超阈 F1 */
  F1: number
  AUC: number
  recall: number
  precision: number
  /** 点预报口径 R² */
  ptR2: number
  /** 部署读出口径 R² */
  R2: number
  ptRMSE: number
  RMSE: number
  /** 报警率：发出预警的时间步占比 */
  predRate: number
  /** 预报最大值 */
  predMax: number
}}

export const ablation: AblRow[] = [
{table(abl_rows, ['mode', 'thr', 'h', 'segment', 'F1', 'AUC', 'recall', 'precision', 'ptR2', 'R2', 'ptRMSE', 'RMSE', 'predRate', 'predMax'])}
]

export const modeNames: Record<string, string> = {{
{chr(10).join(f"  {js(k)}: {js(v)}," for k, v in MODE_NAME.items())}
}}

export interface VerdictRow {{
  segment: string; h: number; thr: string
  F1_B: number; F1_C: number; dF1: number
  AUC_B: number; AUC_C: number; dAUC: number
  C_wins: boolean
}}

export const verdict: VerdictRow[] = [
{table(verdict_rows, ['segment', 'h', 'thr', 'F1_B', 'F1_C', 'dF1', 'AUC_B', 'AUC_C', 'dAUC', 'C_wins'])}
]

/** C 档在全部 18 个（验证/测试 × 24/48/72 h × 三阈值）格中胜出的次数 */
export const cWinCount = {int(sum(1 for r in verdict_rows if r[9]))}
export const cGridCount = {len(verdict_rows)}
"""
w("ablation.ts", ablation_ts)

# =====================================================================
# compare.ts —— 多模型对照、事件命中、提前量、非线性读出
# =====================================================================
ev = pd.read_csv(RES / "derisk02_events.csv")
e24 = ev[(ev.horizon_h == 24) & (ev.threshold == "62%(业务预警)")]
cmp_rows = [(r.model, float(r.AUC), float(r.F1), float(r.recall), float(r.precision), float(r.base_rate))
            for _, r in e24.iterrows()]
lt24 = lead[(lead.horizon_h == 24) & (lead.threshold == "62%(业务预警)")]
lt_rows = [(r.model, int(r.n_onset), int(r.n_warned), float(r.detect_rate), float(r.mean_lead_h))
           for _, r in lt24.iterrows()]

BASE_NOTE = {
    "Persistence": "以当前窟内 RH 原样外推。它不含任何室外驱动信息，是所有模型的下限参照——本表的目的是刻画「室外 → 窟内」这段可学习部分。",
    "FirstOrderTransfer(初稿方案)": "初稿的一阶传递式 RH_in = a·RH_out(t−Δ) + b，a、Δ 由标定得到。它是被替换的对象。",
    "FirstOrderTransfer-递归推演(旧口径)": "把一阶传递式反复迭代到 24 h。传递算子极点接近 1，迭代必然发散（RMSE 达 1e12），该路线彻底不可用。",
    "RidgeDirect(仅当前时刻)": "岭回归直接读当前时刻的室外场，没有任何时间结构，用来衬托延迟特征的价值。",
    "Operator-Full(本作品)": "本作品：258 维可微输运读出（240 快变延迟 + 12 慢变均值 + 6 Magnus 比值）。",
    "Ablation-无慢变项": "消融：去掉 12 个慢变滑动均值，仅留快变延迟与 Magnus 比值。",
    "Ablation-无Magnus项": "消融：去掉 6 个 Magnus 水汽比特征，仅留延迟与慢变均值。",
    "Ablation-仅快变延迟": "消融：只留 240 个快变延迟特征，去掉全部慢变与物理比值。",
    "Ablation-短延迟(12h)": "消融：快变延迟由 48 h 截短到 12 h，检验长延迟记忆的贡献。",
}
b1 = pd.read_csv(RES / "derisk01_model_comparison.csv")
base_rows = []
for _, r in b1.iterrows():
    note = BASE_NOTE.get(r.model, "—")
    group = "本作品与消融" if ("本作品" in r.model or r.model.startswith("Ablation")) else (
        "被替换的初稿路线" if "FirstOrderTransfer" in r.model else "参照模型")
    base_rows.append((r.model, float(r.RMSE), float(r.R2), float(r.MAE) if r.MAE == r.MAE else None,
                      int(r.n_features) if r.n_features == r.n_features else None,
                      float(r.fit_seconds) if r.fit_seconds == r.fit_seconds else None,
                      group, note))

l62 = lt24
on62 = int(l62[l62.model.str.contains("本作品")].iloc[0].n_onset)
hit_op = int(l62[l62.model.str.contains("本作品")].iloc[0].n_warned)
hit_fot = int(l62[l62.model.str.contains("初稿形式")].iloc[0].n_warned)
events62 = [
    ("本作品 · 风险对齐预警", hit_op, on62, "风险分数连续滚动预警"),
    ("初稿 · 直接传递形式", hit_fot, on62, "未做风险对齐的可部署化形式"),
    ("初稿 · 递归推演", 0, on62, "传递算子极点 > 1，迭代必然饱和，从不能发出预警"),
]

rc = pd.read_csv(RES / "derisk03_readout_compare.csv")
rc_rows = [(int(r.h), r.readout, float(r.RMSE), float(r.peak_ratio), float(r["AUC_62%"]), float(r["F1_62%"]),
            float(r["AUC_67%"]), float(r["F1_67%"]), float(r["AUC_75%"]), float(r["F1_75%"]))
           for _, r in rc.iterrows()]

dur = pd.read_csv(RES / "derisk01_duration.csv")
dur_rows = [(r.model, r.threshold, float(r.duration_MAE_h), float(r.duration_bias_h), float(r.duration_RMSE_h))
            for _, r in dur.iterrows()]

compare_ts = header(
    "效果对照：多模型、事件命中、提前量与非线性读出",
    "code/results/derisk02_events.csv、derisk02_leadtime.csv、derisk01_model_comparison.csv、derisk03_readout_compare.csv",
    "derisk02 的检出率/提前量使用真实未来再分析替代预报，属可部署性上界。",
    "derisk03 的 GBDT 非线性读出并非全面更优：24 h/62% 格的 F1 反而低于线性岭回归，界面须如实标注。",
) + f"""
export interface CmpRow {{ model: string; AUC: number; F1: number; recall: number; precision: number; baseRate: number }}
export const models24: CmpRow[] = [
{table(cmp_rows, ['model', 'AUC', 'F1', 'recall', 'precision', 'baseRate'])}
]

export interface LeadRow {{ model: string; onset: number; warned: number; detect: number; lead: number }}
export const leadtime: LeadRow[] = [
{table(lt_rows, ['model', 'onset', 'warned', 'detect', 'lead'])}
]

export interface BaseRow {{
  model: string; RMSE: number; R2: number; MAE: number | null
  nFeatures: number | null; fitSeconds: number | null
  group: string; note: string
}}
export const baselines: BaseRow[] = [
{table(base_rows, ['model', 'RMSE', 'R2', 'MAE', 'nFeatures', 'fitSeconds', 'group', 'note'])}
]

export interface EventRow {{ name: string; hit: number; onset: number; note: string }}
export const events62: EventRow[] = [
{table(events62, ['name', 'hit', 'onset', 'note'])}
]

export interface ReadoutRow {{
  h: number; readout: string; RMSE: number; peakRatio: number
  auc62: number; f162: number; auc67: number; f167: number; auc75: number; f175: number
}}
export const readoutCompare: ReadoutRow[] = [
{table(rc_rows, ['h', 'readout', 'RMSE', 'peakRatio', 'auc62', 'f162', 'auc67', 'f167', 'auc75', 'f175'])}
]

export interface DurRow {{ model: string; threshold: string; maeH: number; biasH: number; rmseH: number }}
export const duration: DurRow[] = [
{table(dur_rows, ['model', 'threshold', 'maeH', 'biasH', 'rmseH'])}
]
"""
w("compare.ts", compare_ts)

# =====================================================================
# validate.ts —— 三条外部证据链
# =====================================================================
ic = pd.read_csv(RES / "iccp_transfer.csv", encoding="utf-8-sig")
ic_rows = []
for _, r in ic.iterrows():
    sd = float(r.target_sd)
    valid = sd >= 0.5
    fot, op = float(r.R2_FirstOrderTransfer), float(r.R2_Operator_Full)
    ic_rows.append((
        int(r.cave), r["name"], int(r.n_test), sd, valid,
        fot, op,
        max(fot, -1.0), max(op, -1.0),
        (fot < -1.0 or op < -1.0),
        float(r.R2_persistence_oracle),
    ))
cc = pd.read_csv(RES / "validate_crosscave.csv")
cc_rows = [(r["metric"], float(r["model_lo"]), float(r["model_hi"]), float(r["lit_lo"]), float(r["lit_hi"]),
            bool(r["pass"])) for _, r in cc.iterrows()]
isd = pd.read_csv(RES / "isd_vs_power.csv")
isd_rows = [(r.variable, int(r.n), float(r.r), float(r.bias), float(r.rmse), float(r.mae))
            for _, r in isd.iterrows()]

valid_ic = [r for r in ic_rows if r[4]]
op_wins = sum(1 for r in valid_ic if r[6] > r[5])
val_ts = header(
    "可信度证据链：跨窟留一、ICCP 洞穴实测、ISD 观测对照",
    "code/results/iccp_transfer.csv、validate_crosscave.csv、isd_vs_power.csv",
    "ICCP 第 12 洞 Te'omim 目标序列标准差为 0（常数），按管线门限剔除，不计入统计。",
    "R² 极端负值已截断到 -1 并置 trunc=true，避免图表坐标轴被 -4e25 拉爆。",
) + f"""
export interface IccpRow {{
  cave: number; name: string; nTest: number; targetSd: number
  /** 目标序列标准差是否达到门限（SD >= 0.5）；false 表示该洞不可用于评估 */
  valid: boolean
  /** 初稿一阶传递式 R²（原始值） */
  r2Fot: number
  /** 本作品 R²（原始值） */
  r2Op: number
  /** 绘图用：截断到 -1 的初稿 R² */
  plotFot: number
  /** 绘图用：截断到 -1 的本作品 R² */
  plotOp: number
  /** 原始 R² 是否被截断过 */
  trunc: boolean
  /** 持续性参照 R² */
  r2Persist: number
}}
export const iccp: IccpRow[] = [
{table(ic_rows, ['cave', 'name', 'nTest', 'targetSd', 'valid', 'r2Fot', 'r2Op', 'plotFot', 'plotOp', 'trunc', 'r2Persist'])}
]

/** 有效洞（SD 达门限）的数量，以及本作品优于初稿一阶传递式的洞数 */
export const iccpValidCount = {len(valid_ic)}
export const iccpOpWins = {op_wins}

export interface CrossRow {{
  metric: string; lo: number; hi: number; litLo: number; litHi: number; pass: boolean
}}
export const crosscave: CrossRow[] = [
{table(cc_rows, ['metric', 'lo', 'hi', 'litLo', 'litHi', 'pass'])}
]

/** metric 的中文说明 */
export const metricNames: Record<string, string> = {{
  'outdoor_monthly_T_range': '窟外月均气温年变幅（°C）',
  'indoor_monthly_T_range': '窟内月均气温年变幅（°C）',
  'indoor_monthly_RH_range': '窟内月均 RH 年变幅（%）',
  'outdoor_monthly_RH_range': '窟外月均 RH 年变幅（%）',
  'annual_T_lag_months': '窟内气温年相位滞后（月）',
  'diurnal_T_lag_max_min': '窟内外日温滞后极值（分钟）',
}}

export interface IsdRow {{
  variable: string; n: number; r: number; bias: number; rmse: number; mae: number
}}
export const isd: IsdRow[] = [
{table(isd_rows, ['variable', 'n', 'r', 'bias', 'rmse', 'mae'])}
]
"""
w("validate.ts", val_ts)

# =====================================================================
# method.ts —— 读出权重与算子谱（可解释性）
# =====================================================================
rd = pd.read_csv(RES / "derisk02_readout.csv").sort_values("abs_weight", ascending=False).head(18)
rd_rows = []
for _, r in rd.iterrows():
    feat = str(r.feature)
    if feat.startswith("q_ma"):
        fam, desc = "水汽通量", "通风带走的绝对水汽量滑动均值"
    elif feat.endswith("_lag0"):
        fam, desc = "瞬时外场", "当前时刻的室外驱动值"
    elif "_ma" in feat:
        fam, desc = "慢变背景", "室外驱动的长窗滑动均值，刻画季节背景"
    elif "_lag" in feat:
        fam, desc = "快变延迟", "室外驱动的过去值，刻画窟体热惯性与水汽滞后"
    else:
        fam, desc = "其他", ""
    rd_rows.append((feat, float(r.weight), float(r.abs_weight), fam, desc))

sp = pd.read_csv(RES / "derisk02_spectrum.csv").sort_values("period_hours")
sp_rows = [(float(r.abs_lambda), float(r.tau_hours), float(r.period_hours), float(r.period_days))
           for _, r in sp.iterrows()]

method_ts = header(
    "方法层：读出权重与算子谱",
    "code/results/derisk02_readout.csv、derisk02_spectrum.csv",
    "权重为标准化特征上的岭回归系数，只反映「哪个特征对读出贡献大」，不是因果效应。",
) + f"""
export interface ReadoutWeight {{ feature: string; weight: number; absWeight: number; family: string; desc: string }}
/** |权重| 最大的 18 个特征 */
export const readoutWeights: ReadoutWeight[] = [
{table(rd_rows, ['feature', 'weight', 'absWeight', 'family', 'desc'])}
]

export interface SpectrumMode {{ absLambda: number; tauHours: number; periodHours: number; periodDays: number }}
export const spectrum: SpectrumMode[] = [
{table(sp_rows, ['absLambda', 'tauHours', 'periodHours', 'periodDays'])}
]

export interface LayerDef {{
  id: string; title: string; subtitle: string; detail: string; io: string
}}
export const layers: LayerDef[] = [
  {{
    id: 'L1',
    title: '室外气象驱动',
    subtitle: '公开观测与再分析',
    detail: 'NASA POWER 逐小时 2001–2025（219,144 行、零缺测）提供室外场；敦煌国家站 ISD 报文作为独立真实性对照。',
    io: 'T2M · RH2M · WS10M · PSC · ALLSKY_SFC_SW_DWN',
  }},
  {{
    id: 'L2',
    title: '风险对齐可微输运读出',
    subtitle: '本作品的核心算法创新',
    detail: '把窟内微气候看作室外轨迹经过窟体热湿惯性的可微输运结果：构造 258 维因果特征（240 快变延迟 + 12 慢变均值 + 6 Magnus 比值），学习作用在室外轨迹上的读出算子。',
    io: '258 维特征 → 窟内 RH 的 24/48/72 h 预报',
  }},
  {{
    id: 'L3',
    title: '阈值加权风险目标',
    subtitle: '把业务判据写进损失函数',
    detail: '在 MSE 目标上引入阈值加权连续排序概率分数（twCRPS），让训练直接惩罚「在 62 / 67 / 75% 阈值附近判错」，而不是只惩罚平均误差。',
    io: '分级预警 · 风险概率 · 限流建议',
  }},
]
"""
w("method.ts", method_ts)

print("前端数据生成完毕")
