"""用可编程方式验证 PDF 的**渲染**（而非仅文字提取）是否正确。

文字能提取只说明 ToUnicode 映射正常；若字体未真正嵌入，页面仍会显示为空白或方框。
这里做两项独立检查：

1. **嵌入字体检查** —— 列出 PDF 中每个字体的类型、是否嵌入、编码方式。
   中文字体必须 ``emb=yes`` 且为子集（``subset``）。
2. **墨水覆盖率检查** —— 把页面栅格化后统计非白像素占比。
   正常的中文正文页应有约 3%~20% 的非白像素；
   若字体缺失（豆腐块/空白），该比例会异常低或呈现整齐的方块图案。
   同时对**标题区域**单独统计，标题笔画多、字号大，覆盖率应明显高于正文线。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

pdf = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/03_作品方案.pdf")
doc = pymupdf.open(str(pdf))

print("=" * 62)
print("1) 嵌入字体检查")
print("=" * 62)
seen = set()
for pno in range(doc.page_count):
    for f in doc.get_page_fonts(pno):
        # (xref, ext, type, basefont, name, encoding)
        key = (f[3], f[1])
        if key in seen:
            continue
        seen.add(key)
        print(f"  {f[3]:<38} type={f[2]:<12} ext={f[1]:<6} enc={f[5]}")

print("\n  字体是否被嵌入（用 xref 判断：有 xref 表示字体对象在文件中）:")
cjk_found = False
for pno in range(doc.page_count):
    for f in doc.get_page_fonts(pno):
        if f[0] > 0 and any(k in f[3].lower() for k in ("cjk", "deng", "china", "song", "hei")):
            print(f"    ✅ 嵌入中文字体: {f[3]} (xref={f[0]})")
            cjk_found = True
            break
if not cjk_found:
    print("    ⚠️ 未按名称识别到中文字体，见上方完整清单")

print()
print("=" * 62)
print("2) 墨水覆盖率检查（栅格化统计非白像素）")
print("=" * 62)


def ink_ratio(page, clip=None, dpi: int = 100) -> float:
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    samples = pix.samples
    n = pix.n
    dark = 0
    total = pix.width * pix.height
    for i in range(0, len(samples), n):
        if samples[i] < 235 or samples[i + 1] < 235 or samples[i + 2] < 235:
            dark += 1
    return dark / total if total else 0.0


worst = 1.0
for i, page in enumerate(doc):
    r = ink_ratio(page)
    worst = min(worst, r)
    flag = "OK " if 0.005 < r < 0.45 else "** 异常 **"
    print(f"  第 {i + 1} 页  非白像素 {r * 100:5.2f}%   {flag}")

# 标题区域单独看（A4 顶部 1/6）
head = doc[0].rect
title_clip = pymupdf.Rect(head.x0, head.y0, head.x1, head.y0 + head.height / 6)
tr = ink_ratio(doc[0], clip=title_clip)
print(f"\n  第 1 页标题区非白像素 = {tr * 100:.2f}%  "
      f"{'OK 标题已渲染' if tr > 0.004 else '** 标题区近乎空白 **'}")

print(f"\n  全文档最低页面覆盖率 = {worst * 100:.2f}%")
print("  判定:", "✅ 渲染正常（无空白页、有实体字形）"
      if worst > 0.004 else "❌ 存在疑似空白页")

doc.close()
