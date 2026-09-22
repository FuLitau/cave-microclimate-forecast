"""版式审计：检测文字块溢出边界与文字互相重叠。

这是「目视检查」的可编程替代——渲染正常（墨水覆盖率合格）不代表版式没问题：
文字可能越界、可能与另一段文字叠在一起，而两者都不影响字符提取。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf


def rects_overlap(a, b) -> float:
    """返回较小块被覆盖的面积比例（0~1）。"""
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    smaller = min(area_a, area_b)
    return inter / smaller if smaller > 0 else 0.0


def audit(pdf: str, margin_frac: float = 0.012, overlap_thr: float = 0.35) -> int:
    doc = pymupdf.open(pdf)
    total_bad = 0
    print(f"\n{'=' * 74}\n{pdf}  共 {doc.page_count} 页\n{'=' * 74}")
    for pno, page in enumerate(doc):
        W, H = page.rect.width, page.rect.height
        mx, my = W * margin_frac, H * margin_frac
        blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
        issues: list[str] = []

        # 1) 越界
        for b in blocks:
            x0, y0, x1, y1 = b[:4]
            if x0 < mx - 1 or x1 > W - mx + 1 or y0 < my - 1 or y1 > H - my + 1:
                txt = b[4].strip().replace("\n", " ")[:46]
                issues.append(
                    f"越界 bbox=({x0:5.1f},{y0:5.1f},{x1:5.1f},{y1:5.1f}) "
                    f"页面={W:.0f}x{H:.0f}  «{txt}»")

        # 2) 文字重叠 —— 用 span 级 bbox（PyMuPDF 对 span 给出精确几何，
        #    而 word 级 bbox 对中日韩+拉丁混排是近似值，会产生假阳性）
        spans = []
        for blk in page.get_text("dict")["blocks"]:
            if blk.get("type") != 0:
                continue
            for line in blk["lines"]:
                for s in line["spans"]:
                    if s["text"].strip():
                        spans.append((s["bbox"], s["text"].strip(), line["bbox"][1]))

        # 2a) 同一行内：span 必须顺序衔接，不得回退
        for i in range(1, len(spans)):
            (a, ta, ya), (b, tb, yb) = spans[i - 1], spans[i]
            if abs(ya - yb) < 0.5 and b[0] < a[2] - 0.6:
                issues.append(
                    f"同行回退 {a[2] - b[0]:.1f}pt  «{ta[:20]}» -> «{tb[:20]}»")

        # 2b) 不同基线之间：bbox 实质相交才算真重叠
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                (a, ta, ya), (b, tb, yb) = spans[i], spans[j]
                if abs(ya - yb) < 0.5:
                    continue  # 同一行交给 2a
                r = rects_overlap(a, b)
                if r >= 0.5:
                    issues.append(
                        f"跨行重叠 {r:.0%}  «{ta[:24]}»(y={ya:.0f}) ⋈ «{tb[:24]}»(y={yb:.0f})")

        if issues:
            total_bad += len(issues)
            print(f"\n  第 {pno + 1:02d} 页  ⚠️  {len(issues)} 处")
            for s in issues[:10]:
                print("      " + s)
            if len(issues) > 10:
                print(f"      … 另有 {len(issues) - 10} 处")
    doc.close()
    print(f"\n合计 {total_bad} 处版式问题")
    return total_bad


if __name__ == "__main__":
    total = 0
    for path in sys.argv[1:]:
        total += audit(path)
    sys.exit(0 if total == 0 else 1)
