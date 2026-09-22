"""生成 3–5 分钟演示视频（1920×1080 H.264 MP4）。

不依赖任何录屏软件：把答辩 PPT 的 PDF 逐页栅格化作为画面，
叠加字幕条与淡入淡出转场，并插入一段**直接读取实验结果**的动画演示，
全程可复现、可重跑。

用法::

    python tools/make_video.py                  # 全流程
    python tools/make_video.py --demo-only      # 只渲染动画段（调试用）
"""

from __future__ import annotations

import argparse
import math
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pymupdf
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PDF = DIST / "04_答辩PPT.pdf"
OUT = DIST / "05_演示视频.mp4"
RES = ROOT / "code" / "results"

W, H = 1920, 1080
FPS = 15
FONT_PATH = r"C:\Windows\Fonts\Deng.ttf"
FONT_BOLD = r"C:\Windows\Fonts\Dengb.ttf"

NAVY = (27, 58, 99)
CYAN = (56, 163, 201)
RED = (192, 57, 43)
GREEN = (46, 139, 87)
ORANGE = (224, 138, 30)
WHITE = (255, 255, 255)


# ------------------------------------------------------------------ 幻灯片栅格化
def render_slides(tmp: Path) -> list[Path]:
    """把 PPT 导出的 PDF 逐页渲染成 1920×1080 PNG。"""
    doc = pymupdf.open(str(PDF))
    paths = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=pymupdf.Matrix(W / page.rect.width,
                                                    H / page.rect.height))
        p = tmp / f"slide_{i + 1:02d}.png"
        pix.save(str(p))
        paths.append(p)
    doc.close()
    print(f"  栅格化 {len(paths)} 页幻灯片")
    return paths


# ------------------------------------------------------------------ 字幕条
def make_subtitle(text: str) -> Image.Image:
    """生成一条半透明底的字幕 PNG（1080 高的底部区域）。"""
    bar_h = 132
    img = Image.new("RGBA", (W, bar_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([90, 12, W - 90, bar_h - 12], radius=14,
                        fill=(12, 24, 42, 205))
    font = ImageFont.truetype(FONT_PATH, 36)
    # 自动折行
    max_w = W - 240
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=font) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    lines = lines[:2]
    y = bar_h / 2 - (len(lines) * 44) / 2
    for ln in lines:
        tw = d.textlength(ln, font=font)
        d.text(((W - tw) / 2, y), ln, font=font, fill=WHITE)
        y += 44
    return img


def compose(base: Image.Image, sub: Image.Image | None) -> np.ndarray:
    frame = base.copy()
    if sub is not None:
        frame.paste(sub, (0, H - sub.height), sub)
    return np.asarray(frame.convert("RGB"))


# ------------------------------------------------------------------ 动画演示段
def render_demo_frames(tmp: Path, seconds: float) -> list[Path]:
    """把 72 h 预报动画逐帧渲染成 PNG。

    画面内容全部来自 ``code/results/demo_forecast.csv``，
    不做任何重新计算。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    for cand in (FONT_PATH, FONT_BOLD):
        if Path(cand).exists():
            font_manager.fontManager.addfont(cand)
    fam = font_manager.FontProperties(fname=FONT_PATH).get_name()
    plt.rcParams["font.family"] = fam
    plt.rcParams["axes.unicode_minus"] = False

    df = pd.read_csv(RES / "demo_forecast.csv", encoding="utf-8-sig")
    d = df[df.scenario == "高湿事件"].sort_values("step_h")
    if d.empty:
        d = df[df.scenario == df.scenario.iloc[0]].sort_values("step_h")
    d = d.reset_index(drop=True)

    n = int(seconds * FPS)
    step = max(1, len(d) // n) if len(d) < n else 1
    total = len(d)
    paths = []

    for fi in range(n):
        # 用「已推进的预报时长」作为动画进度，循环覆盖到 72 h
        prog = int(min(total, (fi / max(1, n - 1)) * total)) + 1
        prog = min(prog, total)
        sub = d.iloc[:prog]

        fig, ax = plt.subplots(figsize=(W / 100, (H - 90) / 100), dpi=100)
        ax.plot(sub.step_h, sub.RH_true, color="#2e8b57", lw=3.2,
                label="窟内真实 RH（合成标签）")
        ax.plot(sub.step_h, sub.RH_pred, color="#1b3a63", lw=3.2, ls="--",
                label="本作品 72 h 滚动预报")
        for lab, val, col in [("62% 业务预警", 62.0, "#e08a1e"),
                              ("67% 潮解起始", 67.0, "#b8860b"),
                              ("75% 吸湿突变", 75.0, "#c0392b")]:
            ax.axhline(val, color=col, lw=1.8, ls=":")
            ax.text(72.4, val + 0.9, lab, color=col, fontsize=11,
                    fontweight="bold", va="bottom", ha="right")

        # 已越过 62% 时给出预警横幅
        crossed = float(sub.RH_pred.max()) >= 62.0
        if crossed:
            ax.text(0.5, 0.955,
                    "触发 62% 业务预警 · 建议限流",
                    transform=ax.transAxes, ha="center", va="top",
                    fontsize=20, fontweight="bold", color="white",
                    bbox=dict(boxstyle="round,pad=0.55", facecolor="#c0392b",
                              edgecolor="none"))

        ax.set_xlim(-1, 73)
        ax.set_ylim(0, 100)
        ax.set_xlabel("预报提前量（小时）", fontsize=13)
        ax.set_ylabel("窟内相对湿度 RH (%)", fontsize=13)
        ax.set_title(f"演示场景：2024-04-16 高湿事件   |   预报已推进 {sub.step_h.iloc[-1]:.0f} h",
                     fontsize=16, color="#1b3a63", fontweight="bold", pad=12)
        ax.legend(fontsize=12, loc="upper left", framealpha=0.92)
        ax.grid(alpha=0.25, ls="--")
        ax.set_axisbelow(True)
        fig.tight_layout()
        p = tmp / f"demo_{fi:05d}.png"
        fig.savefig(p, dpi=100)
        plt.close(fig)
        paths.append(p)
        if fi % 60 == 0:
            print(f"    动画帧 {fi}/{n}")
    print(f"  动画帧共 {len(paths)} 帧")
    return paths


# ------------------------------------------------------------------ 主流程
SEGMENTS = [
    # (页号, 秒数, 字幕, 是否淡入淡出)  —— 总长 289 s（4:49），与页数严格一一对应
    (1, 10, "石窟天盾——风险对齐的窟内微气候预报。一个把气象数据变成文化遗产保护决策的 AI 算法方案。", True),
    (2, 6, "汇报分六个部分：问题、方法、实验、实施、成效与边界。", True),
    (3, 14, "壁画盐害由湿度超过临界值的累积时长触发。三级阈值 62%、67%、75% 均有文献出处，"
            "而限流与闭窟决策不可逆。", True),
    (4, 14, "我们把问题重定义为三个可检验的命题：目标不可观测、目标函数错配、多步误差在极值处最大。", True),
    (5, 16, "这是最关键的实证：只用 MSE 训练时，点精度 R² 达到 0.431，"
            "但预报可达最高值只有 52.8%，永远够不到阈值，超阈 F1 恒为 0。", True),
    (6, 14, "技术路线是三层可微链路：室外多步预报、延迟嵌入输运算子、风险对齐训练。", True),
    (7, 14, "算子使用 258 维严格因果的延迟嵌入特征，闭式解求解，可微、可解释、无需反向传播。", True),
    (8, 14, "训练目标改用阈值加权评分规则 twCRPS，让损失与业务风险同构。", True),
    (9, 13, "四条方法学纪律：预登记判据、逐配置独立选超参、条件指标联合检出率阅读、前端只展示不算数。", True),
    (10, 14, "基线对比：初稿方案 AUC 约等于 0.5，等于随机猜测；本作品在各时效稳定领先。", True),
    (11, 13, "消融实验中完整配置最优，慢变滑动均值特征族贡献最大。", True),
    (12, 14, "我们还发现并修正了自身设计的一个缺陷：线性读出会系统性压缩极值。", True),
    (13, 14, "留一窟外部效度检验，用第 71 窟标定去预测第 87 窟，六项中五项通过。", True),
    (14, 14, "同窟同期对照：温度统计量从未参与标定，窟内年均气温与实测只差 0.45 度；"
             "冷端极值低估 5.35 度这一真实偏差也如实报告。", True),
    (15, 14, "第三条外部链路换成完全真实的观测：ICCP 十二个岩溶洞穴。把洞口湿度直接当深处湿度，"
             "比永远预测均值还差；算子优于一阶传递函数七比八洞。", True),
    (16, 28, "这段动画演示 2024 年 4 月 16 日的高湿事件：窟外相对湿度由 13% 升至 81%，"
             "系统在预报推进中给出分级预警。", False),   # 动画段
    (17, 15, "业务价值不在平均误差，而在提前量：62% 档平均提前 42.6 小时，初稿方案为零。", True),
    (18, 15, "四个创新点全部落在算法层，核心创新层级为三个模型级、一个系统级。", True),
    (19, 14, "我们主动声明能力边界：窟内无公开实测数据，极值捕捉比仅 0.6 到 0.68。", True),
    (20, 12, "后续将接入真实窟内实测、图版数字化标签，并把点预报升级为概率预报。", True),
    (21, 7, "恳请各位评委批评指正。", True),
]

# 动画演示段所在的页号（改动幻灯片顺序时必须同步）
ANIMATION_PAGE = 16


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo-only", action="store_true")
    args = ap.parse_args()

    if not PDF.exists():
        sys.exit(f"缺少 {PDF}，请先运行 tools/build_ppt.py 并导出 PDF")

    tmp = Path(tempfile.mkdtemp(prefix="vid_"))
    try:
        slides = render_slides(tmp)
        # 硬校验：SEGMENTS 必须与幻灯片一一对应，否则字幕会整体错位（曾真的发生过）
        expected = list(range(1, len(slides) + 1))
        got = [p for p, _, _, _ in SEGMENTS]
        if got != expected:
            sys.exit(f"SEGMENTS 与幻灯片不匹配：PDF 共 {len(slides)} 页，"
                     f"SEGMENTS 页号={got}（应为 {expected}）。"
                     f"请同步更新 tools/make_video.py 的 SEGMENTS。")
        demo_secs = next(s for p, s, _, _ in SEGMENTS if p == ANIMATION_PAGE)
        demo_frames = render_demo_frames(tmp, demo_secs)

        if args.demo_only:
            print("仅渲染动画段，已完成 ->", tmp)
            return

        import imageio.v2 as imageio

        subs = {p: make_subtitle(t) for p, _, t, _ in SEGMENTS}
        fade_frames = int(0.55 * FPS)

        writer = imageio.get_writer(
            str(OUT), fps=FPS, codec="libx264", quality=8,
            macro_block_size=None, ffmpeg_log_level="error",
            output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        )

        total_frames = 0
        prev_last: Image.Image | None = None

        for idx, (page, secs, _, fade) in enumerate(SEGMENTS):
            n_frames = int(secs * FPS)
            if page == ANIMATION_PAGE:
                # 动画段：逐帧读取
                for fp in demo_frames:
                    frame = Image.open(fp).convert("RGB")
                    frame = frame.resize((W, H))
                    sub_img = subs[14]
                    frame.paste(sub_img, (0, H - sub_img.height), sub_img)
                    writer.append_data(np.asarray(frame))
                    total_frames += 1
                prev_last = frame.copy()
                print(f"  ✓ 段 {idx + 1:02d} 动画  {len(demo_frames)} 帧")
                continue

            base = Image.open(slides[page - 1]).convert("RGB")
            if base.size != (W, H):
                base = base.resize((W, H))
            still = compose(base, subs[page])

            # 与上一段末帧做交叉淡入
            if fade and prev_last is not None and idx > 0:
                prev_arr = np.asarray(prev_last.convert("RGB"), dtype=np.float32)
                for k in range(fade_frames):
                    a = (k + 1) / (fade_frames + 1)
                    blended = (prev_arr * (1 - a) + still.astype(np.float32) * a)
                    writer.append_data(blended.astype(np.uint8))
                    total_frames += 1
                hold = max(0, n_frames - fade_frames)
            else:
                hold = n_frames

            for _ in range(hold):
                writer.append_data(still)
                total_frames += 1
            prev_last = Image.fromarray(still)
            print(f"  ✓ 段 {idx + 1:02d} 第 {page:02d} 页  {n_frames} 帧")

        writer.close()
        secs_total = total_frames / FPS
        print(f"\n✅ 视频已生成 {OUT}")
        print(f"   时长 {int(secs_total // 60)} 分 {secs_total % 60:.1f} 秒 "
              f"| {total_frames} 帧 @ {FPS}fps")
        print(f"   体积 {OUT.stat().st_size / 1024 / 1024:.1f} MB")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
