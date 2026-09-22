"""颜色审计：扫描 PDF 中所有「接近纯黑/深色」的填充块。

动机：`tools/md2pdf.py` 的 CSS 里若把代码块内层背景写成 `background: none`，
PyMuPDF Story 会把它当成黑色，逐行画出纯黑矩形盖住代码文字——表现为
「背景色与文字颜色相近、看不清」。纯文本提取完全看不出这类问题，
版式审计（`tools/check_layout.py`）也看不出（几何上并不重叠）。

本脚本的法则是：本项目的排版调色板里**不存在纯黑填充**（正文黑是文字颜色，
不是填充），因此任何近黑填充都视为缺陷。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

DARK_THR = 0.22  # 三个通道均低于此值即判为「深色填充」


def audit(pdf: str) -> int:
    doc = pymupdf.open(pdf)
    bad: list[str] = []
    for pno in range(doc.page_count):
        page = doc[pno]
        for dr in page.get_drawings():
            fill = dr.get("fill")
            if not fill:
                continue
            if all(c < DARK_THR for c in fill):
                r = dr["rect"]
                bad.append(
                    f"  第 {pno + 1} 页  深色填充 fill={tuple(round(c, 3) for c in fill)} "
                    f"rect=[{r.x0:.0f},{r.y0:.0f},{r.x1:.0f},{r.y1:.0f}]"
                )
    doc.close()
    total = len(bad)
    print(f"\n{'=' * 74}\n{pdf}  深色填充 {total} 处\n{'=' * 74}")
    for s in bad[:12]:
        print(s)
    if total > 12:
        print(f"  … 另有 {total - 12} 处")
    return total


if __name__ == "__main__":
    paths = sys.argv[1:]
    if not paths:
        paths = sorted(str(p) for p in Path("dist").glob("*.pdf"))
    grand = 0
    for p in paths:
        grand += audit(p)
    print(f"\n合计 {grand} 处深色填充")
    sys.exit(0 if grand == 0 else 1)
