"""诊断：转储指定页某条 y 线上所有 text span 的几何，判断「重叠」是真碰撞还是 bbox 假阳性。

判据：把一行内所有 span 按 x0 排序，若某个 span 的 x0 明显早于前一个 span 的 x1，
且两者基线相同，则为真碰撞；若 x0 与前一 span 的 x1 相差很小（< 0.5pt）或正好衔接，
则是 PyMuPDF 对混合字体 run 的 bbox 近似误差。
"""
from __future__ import annotations

import sys

import pymupdf


def dump(pdf: str, pno: int, y_target: float | None = None) -> None:
    doc = pymupdf.open(pdf)
    page = doc[pno - 1]
    print(f"{pdf} 第 {pno} 页  页面 {page.rect.width:.0f}x{page.rect.height:.0f}")
    d = page.get_text("dict")
    for blk in d["blocks"]:
        if blk.get("type") != 0:
            continue
        for line in blk["lines"]:
            y0 = line["bbox"][1]
            if y_target is not None and abs(y0 - y_target) > 14:
                continue
            spans = sorted(line["spans"], key=lambda s: s["bbox"][0])
            print(f"\n  line bbox={line['bbox']}  spans={len(spans)}")
            prev_x1 = None
            for s in spans:
                x0, sy0, x1, sy1 = s["bbox"]
                gap = "" if prev_x1 is None else f"  (与前 span 间隙 {x0 - prev_x1:+.2f})"
                flag = ""
                if prev_x1 is not None and x0 < prev_x1 - 0.6:
                    flag = "   <<< 真碰撞"
                print(f"    x[{x0:6.1f},{x1:6.1f}] y[{sy0:6.1f},{sy1:6.1f}] "
                      f"{s['size']:4.1f}pt {s['font'][:22]:22s} {s['text'][:40]!r}{gap}{flag}")
                prev_x1 = x1
    doc.close()


if __name__ == "__main__":
    dump(sys.argv[1], int(sys.argv[2]),
         float(sys.argv[3]) if len(sys.argv) > 3 else None)
