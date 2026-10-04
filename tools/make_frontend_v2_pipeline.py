# -*- coding: utf-8 -*-
"""由 tools/build_frontend_data.py 派生 tools/build_frontend_data_v2.py。

原版管线**逐字节不动**；本脚本只做「读原文件 → 定点替换 → 写新文件」，
替换点全部用 assert 兜底，任何一处锚点失配都会立刻报错而不是静默产出错文件。

v2 相对 v1 的三处差异
--------------------
1. ``OUT`` 指向 ``frontend-v2/src/data``（原版仍写 ``frontend/src/data``）。
2. ``demo.ts`` 追加一个 **「预警触发窗口」（真阳性）** 场景并排在最前；原三个窗口
   顺序与数值一律不变。数据来自 ``code/results/demo_alarm.csv``（由
   ``code/experiments/build_demo_alarm_window.py`` 单独生成，不覆盖任何原产物）。
3. 对照类表（``models24`` / ``leadtime`` / ``baselines``）在数据层直接产出
   ``label``（已剥离括号后缀的显示名），视图不再靠正则清洗——正则散在六个渲染点，
   新增一张表忘套就会漏出内部话术，属于结构性隐患。

用法：python tools/make_frontend_v2_pipeline.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "build_frontend_data.py"
DST = ROOT / "tools" / "build_frontend_data_v2.py"

text = SRC.read_text(encoding="utf-8")


def sub(old: str, new: str, *, count: int = 1) -> None:
    global text
    assert text.count(old) == count, f"锚点失配（找到 {text.count(old)} 处，期望 {count}）：{old[:80]!r}"
    text = text.replace(old, new)


# ---- R0：文件头说明 ----
sub(
    '"""把 code/results/ 的实验结果转成前端 TypeScript 常量。\n\n'
    "用法：python tools/build_frontend_data.py\n"
    "输出：frontend/src/data/{meta,kpi,demo,history,stats,ablation,compare,validate,method}.ts\n",
    '"""把 code/results/ 的实验结果转成前端 TypeScript 常量（**v2 备用版前端**）。\n\n'
    "用法：python tools/build_frontend_data_v2.py\n"
    "输出：frontend-v2/src/data/{meta,kpi,demo,history,stats,ablation,compare,validate,method}.ts\n\n"
    "本文件由 tools/make_frontend_v2_pipeline.py 从 tools/build_frontend_data.py 派生。\n"
    "原版前端与 ``tools/build_frontend_data.py`` 均未被修改，两版可并行构建、互不干扰。\n\n"
    "v2 的三处差异：\n"
    "  * 输出目录指向 frontend-v2/；\n"
    "  * demo.ts 追加「预警触发窗口」（真阳性）场景并排在最前，原三窗不变；\n"
    "  * models24 / leadtime / baselines 增加 ``label`` 字段（数据层清洗显示名）。\n",
)

# ---- R1：输出目录 ----
sub('OUT = ROOT / "frontend" / "src" / "data"',
    'OUT = ROOT / "frontend-v2" / "src" / "data"')

# ---- R2：生成器署名 ----
sub("// 本文件由 tools/build_frontend_data.py 自动生成，请勿手改。",
    "// 本文件由 tools/build_frontend_data_v2.py 自动生成，请勿手改。")

# ---- R3：显示名清洗helper ----
sub(
    'def header(title: str, src: str, *extra: str) -> str:',
    'def model_label(name: str) -> str:\n'
    '    """CSV 里的模型名 → 界面显示名：剥离全部括号后缀。\n\n'
    '    数据层保留 CSV 原始名于 ``model`` 字段以便溯源；界面一律渲染 ``label``，\n'
    '    避免「初稿」一类内部话术散落在视图层的正则里。\n'
    '    """\n'
    '    import re\n'
    '    return re.sub(r"[（(][^（()）]*[)）]", "", str(name)).strip()\n\n\n'
    'def header(title: str, src: str, *extra: str) -> str:',
)

# ---- R4：demo 段并入预警触发窗口 ----
sub(
    'scen_parts = []\nscen_meta = []\nfor scen, g in demo.groupby("scenario", sort=False):',
    '# ---- v2 增补：预警触发窗口（真阳性）排在最前，原三个窗口顺序不动 ----\n'
    'ALARM_CSV = RES / "demo_alarm.csv"\n'
    'alarm_summary: dict = {}\n'
    'if ALARM_CSV.exists():\n'
    '    _alarm = pd.read_csv(ALARM_CSV)\n'
    '    alarm_summary = json.loads((RES / "demo_alarm_summary.json").read_text(encoding="utf-8"))\n'
    '    demo = pd.concat([_alarm, demo], ignore_index=True)\n'
    '    _lead = alarm_summary["first_true_over_h"] - alarm_summary["first_warn_h"]\n'
    '    print(f"  [v2] 已并入「{alarm_summary[\'scenario\']}」 起点 {alarm_summary[\'origin\']}，"\n'
    '          f"首次报警 h={alarm_summary[\'first_warn_h\']}，首次真值超阈 h={alarm_summary[\'first_true_over_h\']}，提前 {_lead} h")\n'
    'else:\n'
    '    print("  [v2] 警告：code/results/demo_alarm.csv 不存在，本次仅导出原有三个演示窗口")\n\n'
    'SCEN_KIND = {alarm_summary.get("scenario", "\u9884\u8b66\u89e6\u53d1\u7a97\u53e3"): "alarm"}\n\n'
    'scen_parts = []\nscen_meta = []\nfor scen, g in demo.groupby("scenario", sort=False):',
)

sub(
    '        int((g.RH_pred >= 62).sum()), int((g.RH_pred_tau90 >= 62).sum()), int((g.RH_pred_lin >= 62).sum()),\n'
    '    ))',
    '        int((g.RH_pred >= 62).sum()), int((g.RH_pred_tau90 >= 62).sum()), int((g.RH_pred_lin >= 62).sum()),\n'
    '        int((g.level >= 1).sum()),\n'
    '        SCEN_KIND.get(scen, "sample"),\n'
    '    ))',
)

sub(
    '    "nRiskOver62", "nRisk90Over62", "nLinOver62",\n])',
    '    "nRiskOver62", "nRisk90Over62", "nLinOver62", "nAlarm", "kind",\n])',
)

sub(
    '  nRiskOver62: number; nRisk90Over62: number; nLinOver62: number\n}}',
    '  nRiskOver62: number; nRisk90Over62: number; nLinOver62: number\n'
    '  /** 处于预警态的小时数：按校准年标定的判定切点（level >= 1）逐小时统计，与时间轴、风险态势同源。\n'
    '   *  它**不等于** nRiskOver62（读出直接与 62% 比）：62% 档 h=24 的切点只有 58.26%RH，\n'
    '   *  所以 nAlarm >= nRiskOver62。表格里「预警小时」一列必须用本字段，否则会与时间轴自相矛盾。 */\n'
    '  nAlarm: number\n'
    "  /** 'alarm' = 在测试段按「模型报警 ∧ 真值超阈」扫描选出的真阳性窗口；'sample' = 按真实峰值分位挑选的教学样例 */\n"
    '  kind: string\n}}',
)

# ---- R4b：页脚口径说明改为「四窗规则不同」的中性表述 ----
sub(
    "/** 演示窗口说明 */\n"
    "export const DEMO_HONEST_NOTE =\n"
    "  '演示窗口为教学样例：本窗口读出峰值未触及判定线，系统维持正常开放建议；完整测试段的滚动预警能力见「效果对照」页。'",
    "/** 演示窗口说明（v2：四个窗口的挑规则不同，逐窗口口径在「风险指挥台」卡片内标注） */\n"
    "export const DEMO_HONEST_NOTE =\n"
    "  '四个演示窗口的挑选规则不同：一个按「模型确实报警 ∧ 真实值确实超阈」扫描测试段选出（真阳性），三个按真实峰值分位挑选（教学样例）。逐窗口口径与结果见「风险指挥台」；完整测试段的滚动预警能力见「效果对照」页。'",
)

# ---- R4c：逐点导出「系统判定级」，并让 adv 改用**标定口径**的建议 ----
# 原版导出的是 advice_raw（拿预报值直接比 62/67/75 的天真口径），而 62% 档的标定切点
# 只有 58.26（h=24），两者会打架：表格显示「已预警」而建议栏显示「正常开放」。
# 对原有三个窗口无影响（它们的 level 与 level_raw 同为 0）。
sub('"rhOut: {ro:.2f}, tOut: {to:.2f}, q: {q:.1f}, adv: {adv} }}".format(',
    '"rhOut: {ro:.2f}, tOut: {to:.2f}, q: {q:.1f}, lvl: {lv}, adv: {adv} }}".format(')
sub('q=r.Q_m3h, adv=js(r.advice_raw),',
    'q=r.Q_m3h, lv=int(r.level), adv=js(r.advice),')
sub("  /** 决策建议原文 */\n  adv: string",
    "  /** 系统判定级（0 / 1 / 2）：按校准年标定的判定切点得出，界面显示的处置建议即由此产生 */\n"
    "  lvl: number\n"
    "  /** 决策建议原文（与判定级同源；不是「拿预报值直接比 62%」的天真口径） */\n"
    "  adv: string")

# ---- R5：对照表增加 label ----
sub(
    'cmp_rows = [(r.model, float(r.AUC), float(r.F1), float(r.recall), float(r.precision), float(r.base_rate))\n'
    '            for _, r in e24.iterrows()]',
    'cmp_rows = [(r.model, model_label(r.model), float(r.AUC), float(r.F1), float(r.recall),\n'
    '             float(r.precision), float(r.base_rate))\n'
    '            for _, r in e24.iterrows()]',
)
sub("export interface CmpRow {{ model: string; AUC: number; F1: number; recall: number; precision: number; baseRate: number }}",
    "export interface CmpRow {{ model: string; label: string; AUC: number; F1: number; recall: number; precision: number; baseRate: number }}")
sub("{table(cmp_rows, ['model', 'AUC', 'F1', 'recall', 'precision', 'baseRate'])}",
    "{table(cmp_rows, ['model', 'label', 'AUC', 'F1', 'recall', 'precision', 'baseRate'])}")

sub(
    'lt_rows = [(r.model, int(r.n_onset), int(r.n_warned), float(r.detect_rate), float(r.mean_lead_h))\n'
    '           for _, r in lt24.iterrows()]',
    'lt_rows = [(r.model, model_label(r.model), int(r.n_onset), int(r.n_warned),\n'
    '            float(r.detect_rate), float(r.mean_lead_h))\n'
    '           for _, r in lt24.iterrows()]',
)
sub("export interface LeadRow {{ model: string; onset: number; warned: number; detect: number; lead: number }}",
    "export interface LeadRow {{ model: string; label: string; onset: number; warned: number; detect: number; lead: number }}")
sub("{table(lt_rows, ['model', 'onset', 'warned', 'detect', 'lead'])}",
    "{table(lt_rows, ['model', 'label', 'onset', 'warned', 'detect', 'lead'])}")

sub(
    '    base_rows.append((r.model, float(r.RMSE), float(r.R2), float(r.MAE) if r.MAE == r.MAE else None,',
    '    base_rows.append((r.model, model_label(r.model), float(r.RMSE), float(r.R2),\n'
    '                      float(r.MAE) if r.MAE == r.MAE else None,',
)
sub('                      int(r.n_features) if r.n_features == r.n_features else None,',
    '                      int(r.n_features) if r.n_features == r.n_features else None,')
sub(
    'export interface BaseRow {{\n  model: string; RMSE: number; R2: number; MAE: number | null',
    'export interface BaseRow {{\n  model: string; label: string; RMSE: number; R2: number; MAE: number | null',
)
sub("{table(base_rows, ['model', 'RMSE', 'R2', 'MAE', 'nFeatures', 'fitSeconds', 'group', 'note'])}",
    "{table(base_rows, ['model', 'label', 'RMSE', 'R2', 'MAE', 'nFeatures', 'fitSeconds', 'group', 'note'])}")

DST.write_text(text, encoding="utf-8")
print(f"已写出 {DST.relative_to(ROOT)}  ({len(text.encode('utf-8')):,} B)")
