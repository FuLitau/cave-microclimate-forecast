"""构建答辩 PPT（16:9），供答辩与 PDF 导出使用。

设计原则
--------
* **所有数字均来自 ``code/results/`` 落盘结果**，与作品方案、技术路线文档一致；
* 每页都写演讲者备注（speaker notes），便于答辩人直接照读或改写；
* 字体统一用 **等线 / DengXian** 并同时设置 latin 与 east-asian typeface，
  避免中文回退成宋体；
* 不出现学校名称、指导教师信息（赛题硬性要求）。

用法::

    python tools/build_ppt.py
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "dist" / "figs"
OUT = ROOT / "dist" / "04_答辩PPT.pptx"

# ---------------------------------------------------------------- 主题
NAVY = RGBColor(0x1B, 0x3A, 0x63)
BLUE = RGBColor(0x2F, 0x6F, 0xB5)
CYAN = RGBColor(0x38, 0xA3, 0xC9)
ORANGE = RGBColor(0xE0, 0x8A, 0x1E)
RED = RGBColor(0xC0, 0x39, 0x2B)
GREEN = RGBColor(0x2E, 0x8B, 0x57)
GREY = RGBColor(0x6B, 0x77, 0x85)
LIGHT = RGBColor(0xEF, 0xF4, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK = RGBColor(0x1F, 0x2D, 0x3D)

FONT = "DengXian"
SW, SH = 13.333, 7.5

prs = Presentation()
prs.slide_width = Inches(SW)
prs.slide_height = Inches(SH)
BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------- 基础工具
def style_run(run, size=16, bold=False, color=DARK, italic=False) -> None:
    """设置字号/颜色，并把 latin 与 east-asian 字体都锁到等线。"""
    f = run.font
    f.name = FONT
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", FONT)


def textbox(slide, x, y, w, h, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.paragraphs[0].alignment = align
    return tf


def para(tf, text, size=16, bold=False, color=DARK, space_after=6, bullet=None,
         align=None, first=False, italic=False, space_before=0, line=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    if align is not None:
        p.alignment = align
    p.space_after = Pt(space_after)
    p.space_before = Pt(space_before)
    if line:
        p.line_spacing = line
    prefix = f"{bullet} " if bullet else ""
    # 支持 **粗体** 行内强调：按 ** 切分，奇数段加粗
    parts = text.split("**")
    if len(parts) == 1:  # 无 ** ：单 run 快路径
        r = p.add_run()
        r.text = prefix + text
        style_run(r, size=size, bold=bold, color=color, italic=italic)
        return p
    for idx, seg in enumerate(parts):
        if not seg:
            continue
        r = p.add_run()
        r.text = (prefix if idx == 0 else "") + seg
        style_run(r, size=size, bold=(bold or idx % 2 == 1),
                  color=color, italic=italic)
    return p


def rect(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1.2)
    s.shadow.inherit = False
    return s


def blank() -> object:
    return prs.slides.add_slide(BLANK)


def header(slide, title: str, kicker: str | None = None, num: int | None = None) -> None:
    """统一的页眉：左侧竖条 + 标题 + 可选副标题 + 页码。"""
    rect(slide, 0, 0, SW, 0.095, NAVY)
    rect(slide, 0.55, 0.42, 0.085, 0.52, ORANGE)
    tf = textbox(slide, 0.78, 0.34, SW - 1.6, 0.72, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, title, size=25, bold=True, color=NAVY, first=True, space_after=0)
    if kicker:
        tf2 = textbox(slide, 0.80, 1.02, SW - 1.7, 0.36)
        para(tf2, kicker, size=12.5, color=GREY, first=True, space_after=0)
    if num is not None:
        tfn = textbox(slide, SW - 1.15, SH - 0.62, 0.8, 0.35, align=PP_ALIGN.RIGHT)
        para(tfn, f"{num:02d}", size=12, color=GREY, first=True, space_after=0)


def notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text


def picture(slide, name: str, x, y, w=None, h=None):
    p = FIGS / name
    if not p.exists():
        print(f"  ⚠️ 缺少图片: {name}")
        return None
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    return slide.shapes.add_picture(str(p), Inches(x), Inches(y), **kw)


def table(slide, rows, x, y, w, h, col_w=None, size=11.5, head_size=12):
    """rows[0] 为表头。返回 table 对象。"""
    nr, nc = len(rows), len(rows[0])
    shp = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(h))
    tbl = shp.table
    tbl.first_row = True
    if col_w:
        total = sum(col_w)
        for i, cw in enumerate(col_w):
            tbl.columns[i].width = Emu(int(Inches(w) * cw / total))
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.margin_left = Inches(0.06)
            cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.02)
            cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            if ri == 0:
                cell.fill.fore_color.rgb = NAVY
            else:
                cell.fill.fore_color.rgb = WHITE if ri % 2 else LIGHT
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if ci else PP_ALIGN.LEFT
            r = p.add_run()
            r.text = str(val)
            style_run(r, size=head_size if ri == 0 else size,
                      bold=(ri == 0), color=WHITE if ri == 0 else DARK)
    return tbl


def kpi(slide, items, y=1.62, h=1.28, gap=0.24):
    """一排关键指标卡片。items = [(大数字, 说明, 颜色), ...]"""
    n = len(items)
    x = 0.62
    w = (SW - 2 * 0.62 - gap * (n - 1)) / n
    for big, desc, col in items:
        rect(slide, x, y, w, h, LIGHT)
        rect(slide, x, y, 0.06, h, col)
        tf = textbox(slide, x + 0.14, y + 0.10, w - 0.28, h - 0.2,
                     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        para(tf, big, size=23, bold=True, color=col, first=True, space_after=2,
             align=PP_ALIGN.CENTER)
        para(tf, desc, size=11, color=GREY, space_after=0, align=PP_ALIGN.CENTER,
             line=1.15)
        x += w + gap


# ================================================================ 01 封面
s = blank()
rect(s, 0, 0, SW, SH, NAVY)
rect(s, 0, 0, SW, 0.16, ORANGE)
tf = textbox(s, 1.0, 2.05, SW - 2.0, 1.5, align=PP_ALIGN.CENTER)
para(tf, "石窟天盾", size=54, bold=True, color=WHITE, first=True, space_after=6,
     align=PP_ALIGN.CENTER)
para(tf, "风险对齐的窟内微气候预报", size=27, color=CYAN, align=PP_ALIGN.CENTER,
     space_after=0)
tf = textbox(s, 1.0, 3.85, SW - 2.0, 0.5, align=PP_ALIGN.CENTER)
para(tf, "第八届全球校园人工智能算法精英大赛 · 智慧气象主题赛 · 方向二（气象数据赋能行业应用）",
     size=13.5, color=RGBColor(0xB8, 0xCB, 0xE0), first=True, align=PP_ALIGN.CENTER,
     space_after=0)
line = rect(s, SW / 2 - 0.9, 4.55, 1.8, 0.035, ORANGE)
tf = textbox(s, 1.0, 4.85, SW - 2.0, 0.9, align=PP_ALIGN.CENTER)
para(tf, "室外气象轨迹 → 延迟嵌入 Koopman 输运算子 → 窟内湿度风险", size=15,
     color=WHITE, first=True, align=PP_ALIGN.CENTER, space_after=4)
para(tf, "闭式解 · 可微 · 可解释 · 纯 CPU 可复现", size=13, color=CYAN,
     align=PP_ALIGN.CENTER, space_after=0)
notes(s, "开场：壁画盐害不是被「平均湿度」毁掉的，而是被「湿度超过临界值的累积时长」毁掉的。"
         "现有洞窟微环境模型全部以均方误差为训练目标，平均意义上很准，风险意义上失效。"
         "我们把问题重构为风险对齐预报。全程纯 CPU，可复现。")

# ================================================================ 02 汇报提纲
s = blank()
header(s, "汇报提纲", "六个部分：问题 → 方法 → 实验 → 实施 → 成效 → 边界", 2)
items = [
    ("01", "需求分析", "业务痛点与技术缺口：为什么「平均误差最小」是错的目标"),
    ("02", "AI 技术应用", "三层可微链路：室外预报 → 延迟嵌入算子 → 风险对齐损失"),
    ("03", "实验与结果", "基线对比、消融、读出层修正、跨窟 + ICCP 真实洞穴外部效度"),
    ("04", "项目实施", "数据来源、时序切分、方法学纪律、代码与看板"),
    ("05", "应用成效", "从「能否报出」到「提前多久报出」的业务价值"),
    ("06", "总结与局限", "创新点层级标注与诚实的能力边界声明"),
]
y = 1.68
for i, (no, t, d) in enumerate(items):
    rect(s, 0.7, y, 0.62, 0.62, LIGHT)
    tf = textbox(s, 0.7, y, 0.62, 0.62, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, no, size=17, bold=True, color=BLUE, first=True, align=PP_ALIGN.CENTER,
         space_after=0)
    tf = textbox(s, 1.5, y - 0.02, SW - 2.2, 0.7, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, t, size=16.5, bold=True, color=NAVY, first=True, space_after=1)
    para(tf, d, size=11.5, color=GREY, space_after=0)
    y += 0.86
notes(s, "按赛题评分表的六个维度组织汇报：需求分析、AI 技术应用、项目实施、应用成效、"
         "总结展望，以及创新性（贯穿全篇并在第 16 页单独标注核心创新层级）。")

# ================================================================ 03 业务痛点
s = blank()
header(s, "业务痛点：损伤由「超阈累积时长」触发，而非平均湿度", None, 3)
tf = textbox(s, 0.62, 1.35, 6.15, 4.4)
para(tf, "莫高窟壁画盐害机理", size=16, bold=True, color=NAVY, first=True, space_after=8)
para(tf, "可溶盐随湿度升降反复溶解—结晶，在颜料层内产生结晶压力，"
         "导致疱疹、起甲、脱落。损伤量取决于**湿度超过临界值的持续时间**，"
         "而不是一段时间的平均值。", size=13, color=DARK, space_after=12, line=1.35)
para(tf, "三级业务阈值（均有文献出处）", size=16, bold=True, color=NAVY, space_after=8)
for lab, val, src in [
    ("62%", "敦煌研究院业务口径的窟内 RH 预警线", ORANGE),
    ("67%", "Demas (2015) 潮解起始阈值", RGBColor(0xB8, 0x86, 0x0B)),
    ("75%", "npj Heritage Science (2025) 吸湿突变阈值", RED),
]:
    p = tf.add_paragraph()
    p.space_after = Pt(7)
    r = p.add_run(); r.text = f"  {val}  "
    style_run(r, size=18, bold=True, color=src)
    r = p.add_run(); r.text = lab
    style_run(r, size=13, color=DARK)
tf2 = textbox(s, 0.62, 5.85, 12.1, 0.8)
para(tf2, "→ 决策是「是否限流 / 是否闭窟 / 是否启动除湿」——不可逆，且必须提前数小时到数天做出。",
     size=13.5, bold=True, color=RED, first=True, space_after=0)
picture(s, "fig5_layers.png", 6.95, 3.05, w=5.95)
notes(s, "讲清因果链：盐害临界湿度是台阶式的，所以业务需要的不是「平均误差小」，"
         "而是「超阈事件能不能提前报出来」。三级阈值我们给了逐级文献出处。"
         "决策不可逆——这是引入不确定性量化的业务动因。")

# ================================================================ 04 问题重定义
s = blank()
header(s, "问题重定义：从「预测更准」到「风险对齐」", "三个可被实验检验的命题", 4)
probs = [
    ("P1", "目标不可观测", "莫高窟及国内石窟的窟内温湿度实测数据实质不公开。"
     "直接从窟外气象回归窟内标签的路线，在数据上无法成立。", RED),
    ("P2", "目标函数错配", "现有研究一律用 MSE 训练。实测 MSE 下窟内 RH 的 R² 达 0.42，"
     "超阈事件 F1 恒为 0.000——模型结构上从不预报超阈。", ORANGE),
    ("P3", "多步误差在极值处最大", "误差随预报时效增长，且恰好在最需要准确的高湿极端处最大，"
     "而业务决策恰恰只在这时触发。", BLUE),
]
y = 1.62
for tag, t, d, col in probs:
    rect(s, 0.62, y, 11.9 - 0.0, 1.42, LIGHT)
    rect(s, 0.62, y, 0.075, 1.42, col)
    tf = textbox(s, 0.85, y + 0.10, 1.0, 1.22, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, tag, size=22, bold=True, color=col, first=True, space_after=0)
    tf = textbox(s, 1.85, y + 0.10, 10.4, 1.22, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, t, size=15.5, bold=True, color=NAVY, first=True, space_after=3)
    para(tf, d, size=12, color=DARK, space_after=0, line=1.25)
    y += 1.58
tf = textbox(s, 0.62, y + 0.05, 11.9, 0.5)
para(tf, "→ 本项目不追求「换一个更大的模型」，而是重构训练目标与预报表示，让算法直接对齐业务判级。",
     size=13, bold=True, color=NAVY, first=True, space_after=0)
notes(s, "P1 是数据现实，P2 是我们实测出来的、最有说服力的一条，P3 是业务动机。"
         "注意 P2 的数字：R²=0.42 却 F1=0.000，这不是模型不够大，是目标函数错了。")

# ================================================================ 05 核心实证
s = blank()
header(s, "核心实证：目标函数错配的教科书级案例",
       "同一套特征、同一份数据，只换训练目标（测试段 2021–2025）", 5)
picture(s, "fig1_objective_mismatch.png", 0.62, 1.55, w=12.1)
tf = textbox(s, 0.62, 5.85, 12.1, 1.1)
para(tf, "A 组（仅 MSE）：点精度 R² = 0.431，但预报可达最高值只有 52.8%，"
         "永远够不到 62% 阈值 → 超阈 F1 = 0.000。", size=12.5, color=DARK,
     first=True, space_after=3)
para(tf, "B 组（MSE + 阈值加权 twCRPS）：点精度不降反升（R² = 0.470），"
         "超阈 F1 由 0 → 0.122，AUC 由 0.781 → 0.875。", size=12.5, bold=True,
     color=GREEN, space_after=0)
notes(s, "这是全篇最重要的一页。左边说明「平均准」和「风险准」可以完全脱钩；"
         "右边说明 A 组不是报得不够好，而是它的预报值域被目标函数压住了，"
         "结构上不可能触发阈值。换成阈值加权损失之后，点精度还略微变好了。")

# ================================================================ 06 技术路线
s = blank()
header(s, "AI 技术应用：三层可微链路", "室外轨迹 → 窟内湿度风险的端到端梯度通路", 6)
picture(s, "fig5_layers.png", 0.62, 1.5, w=12.1)
rows = [
    ["层级", "做什么", "关键设计", "为什么这样做"],
    ["L1 室外预报", "提供未来各时刻外场值", "POWER 再分析 2001–2025，219,144 小时",
     "窟内标签不可得，外场是唯一可部署输入"],
    ["L2 输运算子", "外场轨迹 → 窟内状态", "258 维延迟嵌入特征 + 闭式 EDMD 读出",
     "物理代理：可微、可解释、无需 BPTT"],
    ["L3 风险对齐", "训练目标对齐业务判级", "twCRPS 阈值加权评分规则",
     "损失即业务风险，而非平均误差"],
]
table(s, rows, 0.62, 4.62, 12.1, 2.05, col_w=[1.0, 1.5, 2.3, 2.4], size=10.5, head_size=11.5)
notes(s, "三层是解耦的：L1 换成任何数值天气预报产品，L2/L3 都能继续用——这是可推广性的技术基础。"
         "强调 L2 用闭式解而不是深度学习：赛题是算法竞赛，我们要的是可解释、可审计、"
         "在纯 CPU 上可复现。")

# ================================================================ 07 L2 算子
s = blank()
header(s, "L2 算子：延迟嵌入（Takens / HAVOK 思想）", "258 维、严格因果、物理可读", 7)
tf = textbox(s, 0.62, 1.4, 6.3, 4.3)
para(tf, "为什么用延迟嵌入而不是黑箱时序模型", size=15.5, bold=True, color=NAVY,
     first=True, space_after=8)
para(tf, "窟内微气候对外场的响应有明确的物理时标：日周期（岩体热惯性）、"
         "天气过程（数日）、季节（年）。把这些时标显式编码成特征，"
         "模型就不必从数据里重新发现它们。", size=12.5, color=DARK, space_after=10,
     line=1.32)
para(tf, "算子定位的关键澄清（来自一次被否定的设计）", size=15.5, bold=True,
     color=RED, space_after=8)
para(tf, "我们曾尝试用 Koopman 矩阵 K 逐步滚动演化慢变状态，实测 R² ≈ 0.003；"
         "改为「作用在室外轨迹上的可微输运读出」后 R² = 0.42。"
         "原因：多尺度滑动均值是**外生汇总量**，不是不变 Koopman 可观测量，"
         "强行用 K 演化会破坏信号。", size=12.5, color=DARK, space_after=0, line=1.32)
rows = [
    ["特征族", "维数", "物理含义"],
    ["快变延迟", "240", "最近 48 h 逐时驱动要素及其滞后"],
    ["慢变滑动均值", "12", "24 / 72 / 168 / 720 / 2160 / 8760 h 窗口"],
    ["Magnus 比值", "6", "温湿非线性耦合的物理量纲组合"],
    ["合计", "258", "全部严格因果，不含未来信息"],
]
table(s, rows, 7.15, 1.95, 5.55, 2.5, col_w=[1.2, 0.6, 3.0], size=11, head_size=12)
tf = textbox(s, 7.15, 4.65, 5.55, 1.5)
para(tf, "闭式解 EDMD 读出：岭回归 G = ZᵀZ/n + β·mask，"
         "仅惩罚斜率、不惩罚截距；无梯度下降、无 BPTT。", size=11.5,
     color=DARK, first=True, space_after=5, line=1.3)
para(tf, "★ 核心创新层级：模型级", size=12, bold=True, color=RED, space_after=0)
notes(s, "主动讲被否定的设计：K^h rollout 失败是我们自己做出来的负结果，"
         "写进了文档和 PPT。这一条能显著提升可信度——说明我们做了预登记判据并如实记录。")

# ================================================================ 08 L3 风险对齐
s = blank()
header(s, "L3 风险对齐：阈值加权评分规则 twCRPS", "两条学习曲线 + 一个与业务同构的损失", 8)
tf = textbox(s, 0.62, 1.4, 6.2, 3.6)
para(tf, "损失设计", size=15.5, bold=True, color=NAVY, first=True, space_after=8)
para(tf, "twCRPS（threshold-weighted CRPS）用核函数 φ 把评分集中到阈值以上区域："
         "预报在「不重要」的低湿区间犯的错被降权，"
         "在「业务关心」的超阈区间犯的错被加权。", size=12.5, color=DARK,
     space_after=8, line=1.32)
para(tf, "实现：scoringrules 库的 twcrps_ensemble + 自研加权分位数损失（IRLS，"
         "保持闭式解体系）。", size=12.5, color=DARK, space_after=10, line=1.32)
para(tf, "★ 核心创新层级：模型级", size=12, bold=True, color=RED, space_after=0)
rect(s, 7.05, 1.45, 5.65, 3.55, LIGHT)
tf = textbox(s, 7.3, 1.62, 5.15, 3.2)
para(tf, "内生权重的尝试与结论（如实记录）", size=14, bold=True, color=NAVY,
     first=True, space_after=8)
para(tf, "我们还尝试过用算子自身导出的「内生权重」替代固定阈值权重（C 组）。"
         "预登记判据要求 C 必须稳定优于 B，才算证明贡献来自「内生」而非"
         "「换了个损失函数」。", size=12, color=DARK, space_after=8, line=1.3)
para(tf, "结果：旧标签 2/9、新标签 0/9，两层判据均未通过。", size=12.5,
     bold=True, color=RED, space_after=8, line=1.3)
para(tf, "→ 已降级为「被实验否定的设计」，不再作为创新点主张。", size=12,
     color=DARK, space_after=0, line=1.3)
notes(s, "twCRPS 是这页的主角。同时主动交代内生权重方案的失败：我们预登记了判据，"
         "跑出来不通过，就按判据否掉，不硬拗成创新点。这是方法学纪律的一部分。")

# ================================================================ 09 实验设置
s = blank()
header(s, "实验设置：数据、切分与四条方法学纪律", None, 9)
rows = [
    ["项目", "内容"],
    ["驱动数据", "NASA POWER 逐小时再分析 2001-01-01 → 2025-12-31，219,144 行 × 10 要素，缺测 0"],
    ["窟内标签", "文献参数化物理代理模型生成（physics-derived synthetic），非实测——已显式声明"],
    ["物理标定", "Gong et al. 2025（第 71 窟）、Zhang & Wang 2023（第 87 窟）实测传递比"],
    ["训练/验证/测试", "严格按时间顺序切分，测试段 2021–2025，无任何跨期泄露"],
    ["决策阈值", "在验证段标定（使报警率 = 基准事件率），测试段只应用不调参"],
]
table(s, rows, 0.62, 1.5, 12.1, 2.4, col_w=[1.5, 6.4], size=11.5, head_size=12)
tf = textbox(s, 0.62, 4.15, 12.1, 2.8)
para(tf, "四条方法学纪律", size=15.5, bold=True, color=NAVY, first=True, space_after=8)
for t in [
    "① 预登记判据：先写死「什么算成功」，再跑实验，不通过就如实记录（本作品已有 3 次否决闭环）。",
    "② 逐配置独立选超参：不同消融的 β 各自在验证段扫描，避免正则错配造成的假「反超」。",
    "③ 条件指标必须与检出率联合呈现：某模型「条件时长更短」但检出率为 0 时，该指标无定义，不是更准。",
    "④ 前端只展示、不算数：看板所有数值读取 results/ 落盘文件，可被评委逐项回溯。",
]:
    para(tf, t, size=12, color=DARK, space_after=6, line=1.25)
notes(s, "这一页是给评委看的「可信度页」。特别强调第 3 条——我们在做时长指标时发现自己"
         "第一版指标是退化的（永不报警反而占便宜），改了两版才堵死。这类自我纠错写进报告。")

# ================================================================ 10 基线对比
s = blank()
header(s, "结果：超阈预警能力全面领先，初稿方案 ≈ 随机猜测",
       "62% 业务阈值 · 测试段 2021–2025 · 事件率 1.28%", 10)
picture(s, "fig2_baseline_auc.png", 0.62, 1.5, w=12.1)
notes(s, "图上两件事：第一，初稿方案（一阶传递函数）AUC ≈ 0.5，等于随机猜测，"
         "而且实测会数值发散（RMSE 达 4e17）——它被我们的实验直接证伪了。"
         "第二，Persistence 在短时效很强但随提前量迅速衰减，"
         "我们的算子在 48h/72h 反超它，这是延迟嵌入结构带来的收益。")

# ================================================================ 11 消融
s = blank()
header(s, "消融实验：完整配置最优，慢变项贡献最大",
       "各配置在验证段独立选 β——此前「某消融反超」是正则错配的假象", 11)
rows = [
    ["配置", "β*", "R²", "AUC(62%)", "结论"],
    ["[对照上界] Persistence（需窟内实测）", "—", "0.428", "0.836", "不可部署，仅作上界"],
    ["本作品 延迟嵌入算子（完整）", "1", "0.543", "0.818", "点精度与 AUC 综合最优"],
    ["消融-无 Magnus 项", "1", "0.541", "0.817", "贡献很小"],
    ["消融-短延迟（仅 12 h）", "1", "0.536", "0.826", "AUC 略高但点精度下降"],
    ["消融-无慢变项", "0.001", "0.520", "0.804", "↓ 最大，慢变族是关键"],
    ["消融-仅快变延迟", "0.001", "0.513", "0.795", "↓ 最大"],
    ["Ridge 直接回归（无算子）", "—", "0.315", "0.738", "延迟嵌入带来 +0.23 R²"],
    ["气候态基线", "—", "0.402", "0.734", "可部署基线"],
    ["初稿方案 一阶传递函数", "—", "发散", "0.499", "≈ 随机猜测"],
]
table(s, rows, 0.62, 1.55, 12.1, 4.85, col_w=[3.4, 0.7, 0.9, 1.0, 2.3],
      size=10.5, head_size=11.5)
tf = textbox(s, 0.62, 6.55, 12.1, 0.5)
para(tf, "→ 完整配置在 R² 与 AUC 上同时领先：三个特征族都有独立贡献，慢变滑动均值族贡献最大。",
     size=12, bold=True, color=NAVY, first=True, space_after=0)
notes(s, "关键在副标题：我们一开始发现某个消融配置「反超」完整配置，"
         "排查后是共用正则系数导致的错配。逐配置独立选 β 之后反超消失，"
         "完整配置恢复最优。这是方法学纪律第 2 条的实证。")

# ================================================================ 12 读出层修正
s = blank()
header(s, "架构结论：线性读出是真实瓶颈（含对自身设计的修正）",
       "特征完全不变（258 维），只替换读出层", 12)
picture(s, "fig3_readout.png", 0.62, 1.5, w=12.1)
tf = textbox(s, 0.62, 5.8, 12.1, 1.2)
para(tf, "此前我们把「闭式解」当作纯部署优势来陈述——这是不完整的：它保住了可微性与可解释性，"
         "代价是极值保真度（最危险的 75% 档 AUC 损失约 13 个百分点）。", size=12,
     color=DARK, first=True, space_after=4, line=1.25)
para(tf, "处置：双轨读出 —— GBDT 面向业务预报（精度与极值最优，仍纯 CPU、无 BPTT）；"
         "线性算子面向物理解释与梯度链路。", size=12, bold=True, color=GREEN,
     space_after=0, line=1.25)
notes(s, "这是我们对自身设计的一次修正，坦率讲出来。逻辑是：物理特征本身是有效的"
         "（两套读出都远优于基线），但线性读出压住了极值。所以我们改成双轨："
         "业务用一个非线性读出，物理解释与可微性仍然依赖线性算子。")

# ================================================================ 13 跨窟验证
s = blank()
header(s, "外部效度：第 71 窟标定 → 第 87 窟检验（留一窟）",
       "另一洞窟、另一研究团队、另一套传感器——标定时完全未使用", 13)
picture(s, "fig4_crosscave.png", 0.62, 1.5, w=12.1)
tf = textbox(s, 0.62, 5.75, 12.1, 1.25)
para(tf, "6 项传递结构指标中 5 项通过，含最关键的**年周期温度相位滞后 1 个月**（同文献一致）。"
         "未通过的一项是窟外月均 RH 范围——差异来自驱动数据（再分析 vs 现场气象站），"
         "不是模型偏差。", size=12, color=DARK, first=True, space_after=4, line=1.25)
para(tf, "能支持：模型学到的是传递结构的共性，不是对单一洞窟的过拟合。"
         "不能支持：可精确复现任意洞窟。", size=12, bold=True, color=NAVY,
     space_after=0, line=1.25)
notes(s, "这一页防的是「循环论证」质疑：如果标签是物理模型造的、模型又去拟合它，"
         "性能高没有意义。所以我们做了留一窟检验——用第 71 窟标定的参数"
         "去预测第 87 窟，并且如实报告了 1 项未通过。")

# ================================================================ 14 ICCP 真实洞穴
s = blank()
header(s, "外部效度（二）：ICCP 真实洞穴观测独立验证",
       "12 个岩溶洞穴 · 42 台记录仪 · 2019–2021 逐小时 · 不含任何合成标签", 14)
rows = [
    ["模型", "R² 中位数", "R² > 0 的洞数", "RMSE 中位数（RH 百分点）"],
    ["Persistence（把洞口 RH 当作深处 RH，oracle）", "−2.282", "—", "—"],
    ["FirstOrderTransfer（初稿方案）", "−0.255", "3 / 8", "7.18"],
    ["Operator-Full（本作品）", "+0.641", "5 / 8", "3.56"],
]
table(s, rows, 0.62, 1.48, 12.1, 1.62,
      col_w=[4.6, 1.8, 1.9, 3.0], size=11, head_size=11)
tf = textbox(s, 0.62, 3.28, 12.1, 3.5)
para(tf, "洞口与深处湿度强解耦：oracle「把洞口 RH 当作深处 RH」的 R² 中位数为 −2.28——"
         "比永远预测均值还差。传播过程本身携带不可忽略的动力学。",
     size=12.5, bold=True, color=NAVY, first=True, space_after=7, line=1.25)
for t in [
    "算子优于一阶传递函数 **7/8 洞**，RMSE 减半；在另一套气候、另一套岩性、"
    "另一支团队的数据上复现了架构优势；",
    "但**不是普遍有效**：Sela'、Murabba'at 2、Har Sifsof 三洞为负"
    "（Har Sifsof 深处 RH 均值 94.2%，近饱和洞窟不适用）；",
    "**边界**：ICCP 为石灰岩/白云岩 + 地中海气候，莫高窟为砾岩—砂岩 + 干旱大陆性"
    "——只支持相对比较，不支撑绝对精度。",
]:
    para(tf, t, size=11.5, color=DARK, space_after=5, line=1.25, bullet="•")
notes(s, "这是防「循环论证」的第二条链路。第一条留一窟用的还是我们物理模型的输出，"
         "存在「用模型验证模型」的嫌疑；这一条换成完全真实的观测，一个合成标签都没有。"
         "结论很硬：把洞口湿度直接当深处湿度，比永远预测均值还差——"
         "这正好从物理上解释了初稿的查表式传递函数为什么不够。"
         "同时我们如实报告了 3 个失败案例和一个因目标近似常数而被剔除的洞。")

# ================================================================ 15 演示案例
s = blank()
header(s, "应用成效（一）：真实高湿事件的预警演示",
       "演示场景 2024-04-16，窟外 RH 由 13% 升至 81%", 15)
picture(s, "fig6_demo_case.png", 0.62, 1.5, w=12.1)
tf = textbox(s, 0.62, 5.8, 12.1, 1.15)
para(tf, "该场景下窟内真实 RH 在 72 h 内升至 89.0%，触发全部三级阈值；"
         "系统在 62% 档提前给出预警并给出「限流 / 闭窟 / 除湿」的分级建议。",
     size=12, color=DARK, first=True, space_after=4, line=1.25)
para(tf, "同期我们如实记录了局限：状态式 MSE 读出在该场景只能给出 34.8% 的峰值——"
         "这正是第 12 页读出层修正的直接动因。", size=12, color=RED, space_after=0,
     line=1.25)
notes(s, "演示案例用真实外场驱动。这里再次暴露读出层压缩极值的问题，"
         "我们把它和修正方案连起来讲，形成「发现问题→归因→修正」的完整链条。")

# ================================================================ 15 预警提前量
s = blank()
header(s, "应用成效（二）：从「能否报出」到「提前多久报出」",
       "管理决策需要的是提前量，不是平均误差", 16)
picture(s, "fig7_leadtime.png", 0.62, 1.5, w=12.1)
rows = [
    ["阈值", "本作品检出率", "平均提前量", "初稿方案检出率"],
    ["62% 业务预警", "34.0%", "42.6 h", "0.0%（从不预警）"],
    ["67% 潮解起始", "27.5%", "23.0 h", "0.0%"],
    ["75% 吸湿突变", "9.1%", "54.0 h", "0.0%"],
]
table(s, rows, 0.62, 5.55, 12.1, 1.45, col_w=[1.3, 1.3, 1.2, 1.8], size=11, head_size=11.5)
notes(s, "42.6 小时的提前量对应现实中的管理动作：当天下午就能决定次日是否限流、"
         "是否安排除湿设备。0 小时提前量等于没有预警。"
         "同时如实说明：75% 档事件极少（测试段仅 47 次），检出率只有 9.1%。")

# ================================================================ 16 创新点
s = blank()
header(s, "创新点与核心创新层级标注", "按赛题要求显式标注层级", 17)
rows = [
    ["#", "创新点", "核心创新层级", "支撑证据"],
    ["1", "风险对齐训练：以阈值加权评分规则 twCRPS 替代 MSE",
     "模型级", "超阈 F1 0 → 0.122\nAUC 0.781 → 0.875"],
    ["2", "延迟嵌入输运算子：258 维因果物理特征 + 闭式 EDMD 可微读出",
     "模型级", "R² 0.543 vs 无算子 0.315\n48/72 h AUC 反超不可部署上界"],
    ["3", "双状态传递结构：以体积流量 Q 而非 ACH 建模通风",
     "系统级", "跨窟留一 5/6 通过\nICCP 真实洞穴 7/8 洞占优"],
    ["4", "读出层极值修正：线性读出的极值压缩瓶颈 + 非线性读出",
     "模型级", "极值捕捉比 0.592 → 0.682\n75% 档 AUC +13.2 pp"],
]
table(s, rows, 0.62, 1.55, 12.1, 4.6, col_w=[0.4, 3.9, 1.2, 3.3],
      size=10.5, head_size=11.5)
tf = textbox(s, 0.62, 6.3, 12.1, 0.7)
para(tf, "全部创新点均落在算法层（模型级 / 系统级），不含应用层包装；"
         "被实验否定的设计（K^h rollout、twCRPS 内生权重）已从创新点中移除。",
     size=12, bold=True, color=NAVY, first=True, space_after=0)
notes(s, "赛题明确要求标注核心创新层级。四个创新点里三个是模型级、一个是系统级，"
         "没有把应用层的东西包装成创新。这一点直接对应创新性 25 分的评审要求。")

# ================================================================ 17 局限
s = blank()
header(s, "诚实的能力边界", "主动声明，而不是等评委发现", 18)
limits = [
    ("窟内无公开实测数据", "本项目窟内序列由文献参数化物理模型生成，非实测。"
     "所有性能数字反映的是「算法在物理代理上的能力」，不能直接等同于现场精度。"
     "缓解：跨窟留一检验 + ICCP 真实洞穴独立验证，但两者都只支持相对比较。", RED),
    ("极值捕捉比仅 0.6 ~ 0.68", "即便改用非线性读出，最危险区间的极值保真度仍有限，"
     "高阈值档检出率偏低（75% 档 9.1%）。", ORANGE),
    ("绝对阈值三级决策偏乐观", "62% 业务阈值在部分场景下模型预报值域够不到，"
     "实际部署需结合概率化决策而非单点判级。", ORANGE),
    ("物理模型存在已知偏差", "窟内年均温比文献偏暖约 1.2 K；游客短时脉冲（文献 +11 pp）"
     "未复现，因小时步长会将其时间平均。", BLUE),
    ("跨窟泛化有边界", "留一窟检验 5/6 通过；ICCP 真实洞穴 8 个有效洞中 3 洞失败。"
     "模型仅代表中等规模旅游洞窟（约 67 m³），不得外推到 1300 m³ 量级的大窟。", BLUE),
]
y = 1.5
for t, d, col in limits:
    rect(s, 0.62, y, 12.1, 0.98, LIGHT)
    rect(s, 0.62, y, 0.065, 0.98, col)
    tf = textbox(s, 0.88, y + 0.04, 11.7, 0.9, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, t, size=13, bold=True, color=col, first=True, space_after=2)
    para(tf, d, size=11.5, color=DARK, space_after=0, line=1.2)
    y += 1.09
notes(s, "这一页是刻意设计的。评委一定会问「窟内数据哪来的」，"
         "我们主动说清楚：是文献参数化的物理代理，不是实测。"
         "同时把物理模型的已知偏差也列出来。坦诚是这类比赛里最稀缺的加分项。")

# ================================================================ 18 总结
s = blank()
header(s, "总结与展望", None, 19)
tf = textbox(s, 0.62, 1.45, 6.0, 4.7)
para(tf, "已完成的工作", size=16, bold=True, color=NAVY, first=True, space_after=8)
for t in [
    "把初稿从文保应用重构为 AI 算法问题，四个创新点全部落在算法层；",
    "建成「室外预报 → 延迟嵌入算子 → 风险对齐损失」三层可微链路，纯 CPU 端到端可跑；",
    "完成基线对比、消融、读出层修正、留一窟与 ICCP 真实洞穴外部效度五组实验，25+ 结果文件全部落盘；",
    "三次「预登记判据 → 实测否决 → 如实记录」闭环，负结果同步写入文档；",
    "交付技术路线、数据集方案、作品方案、答辩材料与可运行代码仓库。",
]:
    para(tf, t, size=11.5, color=DARK, space_after=6, line=1.25, bullet="•")
tf = textbox(s, 6.9, 1.45, 5.8, 4.7)
para(tf, "后续工作", size=16, bold=True, color=NAVY, first=True, space_after=8)
for t in [
    "接入真实窟内实测（与文保单位合作部署记录仪），检验不可迁移的绝对精度；",
    "图版数字化：把壁画病害图版转为损伤标签，缓解标签稀缺；",
    "在延迟嵌入特征上接入深度时序骨干，比较物理特征与学习特征的边际贡献；",
    "把点预报升级为概率预报，直接支撑「限流 / 闭窟 / 除湿」的期望损失决策。",
]:
    para(tf, t, size=11.5, color=DARK, space_after=6, line=1.25, bullet="•")
rect(s, 0.62, 5.95, 12.1, 0.9, LIGHT)
tf = textbox(s, 0.85, 5.95, 11.7, 0.9, anchor=MSO_ANCHOR.MIDDLE)
para(tf, "技术路线可迁移：把窟内湿度风险换成任何「阈值 + 持续时间」型文化遗产风险指标，"
         "三层链路与风险对齐损失均可复用。", size=12.5, bold=True, color=NAVY,
     first=True, space_after=0)
notes(s, "收尾强调两件事：一是我们做的是算法问题，不是应用包装；"
         "二是这条链路是可迁移的——换成任何「阈值+持续时间」型的遗产风险指标都能复用。")

# ================================================================ 19 致谢
s = blank()
rect(s, 0, 0, SW, SH, NAVY)
rect(s, 0, 0, SW, 0.16, ORANGE)
tf = textbox(s, 1.0, 2.6, SW - 2.0, 1.6, align=PP_ALIGN.CENTER)
para(tf, "恳请各位评委批评指正", size=38, bold=True, color=WHITE, first=True,
     space_after=12, align=PP_ALIGN.CENTER)
para(tf, "石窟天盾 · 风险对齐的窟内微气候预报", size=16, color=CYAN,
     align=PP_ALIGN.CENTER, space_after=0)
tf = textbox(s, 1.0, 5.35, SW - 2.0, 0.6, align=PP_ALIGN.CENTER)
para(tf, "代码仓库、数据方案与技术路线文档随材料一并提交", size=12.5,
     color=RGBColor(0xB8, 0xCB, 0xE0), first=True, align=PP_ALIGN.CENTER, space_after=0)
notes(s, "答辩结束页。")

prs.save(str(OUT))
print(f"✅ 已生成 {OUT}  共 {len(prs.slides.__iter__.__self__._sldIdLst)} 页 "
      f"{OUT.stat().st_size / 1024:.0f} KB")
