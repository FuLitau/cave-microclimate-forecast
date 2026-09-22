"""诊断：转储指定 PDF 中命中关键词的页面上每个 span 的颜色/字号/字体，以及所有填充矩形。

用途：排查「背景色与文字颜色相近」这类渲染问题——纯文本提取看不出颜色，
必须同时看 span 颜色和它背后的填充块。
"""
from __future__ import annotations

import sys

import pymupdf


def dump(pdf: str, needles: list[str]) -> None:
    doc = pymupdf.open(pdf)
    for pno in range(doc.page_count):
        page = doc[pno]
        text = page.get_text()
        if not any(n in text for n in needles):
            continue
        print(f"\n===== {pdf}  第 {pno + 1} 页 =====")
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    print(
                        f"  span color=#{span['color']:06x} size={span['size']:.1f} "
                        f"font={span['font'][:24]:24} bbox={[round(v) for v in span['bbox']]} "
                        f"{span['text'][:70]!r}"
                    )
        print("  --- drawings (fill / stroke) ---")
        for dr in page.get_drawings():
            fill = dr.get("fill")
            stroke = dr.get("color")
            if fill or stroke:
                print(
                    f"    fill={fill} stroke={stroke} "
                    f"rect={[round(v) for v in dr['rect']]}"
                )
    doc.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(2)
    dump(sys.argv[1], sys.argv[2:])
