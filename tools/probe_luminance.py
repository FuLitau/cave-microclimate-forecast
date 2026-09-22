"""数值化诊断：统计 PDF 中某个区域的平均亮度与近黑像素占比。

用于判定「背景色与文字颜色相近」到底是哪种成因：
  - 若整块区域平均亮度低（<100/255）→ 背景本身是深的；
  - 若只有文字行位置亮度低、背景亮 → 是文字被黑色填充块盖住；
  - 若两者都亮 → 只是对比度不足。
"""
from __future__ import annotations

import sys

import pymupdf


def analyse(pdf: str, page_no: int, rect: tuple[float, float, float, float], dpi: int = 300) -> None:
    doc = pymupdf.open(pdf)
    page = doc[page_no - 1]
    pix = page.get_pixmap(clip=pymupdf.Rect(*rect), dpi=dpi, colorspace=pymupdf.csRGB)
    w, h, n = pix.width, pix.height, pix.n
    samples = pix.samples
    print(f"区域 {rect}  ->  {w}x{h} px @ {dpi}dpi, n={n}")
    # 逐行统计
    print(f"{'row':>5} {'y_pdf':>7} {'meanLum':>8} {'fracDark':>9}  直方图")
    for row in range(h):
        base = row * w * n
        tot = 0
        dark = 0
        for col in range(w):
            i = base + col * n
            r, g, b = samples[i], samples[i + 1], samples[i + 2]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            tot += lum
            if lum < 100:
                dark += 1
        mean = tot / w
        frac = dark / w
        bar = "#" * int(frac * 40)
        print(f"{row:>5} {rect[1] + row * 72 / dpi:>7.1f} {mean:>8.1f} {frac:>9.3f}  {bar}")
    doc.close()


if __name__ == "__main__":
    pdf = sys.argv[1]
    page_no = int(sys.argv[2])
    rect = tuple(float(v) for v in sys.argv[3:7])
    analyse(pdf, page_no, rect)  # type: ignore[arg-type]
