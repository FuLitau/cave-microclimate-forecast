"""从 Gong et al. 2025 的 PDF 中提取图片，用于图版数字化。

注意：该刊 PDF 的图版是**位图**（每页 1 张嵌入图 + 少量矢量装饰），
不是矢量曲线，因此无法直接读路径坐标，只能用图像分割方式数字化。
"""

import os
import sys
from pathlib import Path

import pymupdf

PDF = Path(__file__).resolve().parents[2] / "_lit" / "gong2025.pdf"
OUT = Path(__file__).resolve().parents[2] / "_lit" / "figs"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(PDF)

    pno = 9  # 第 10 页 —— 正文提到 Fig. 13
    page = doc[pno]
    print(f"=== page {pno + 1} text (first 800 chars) ===")
    print(page.get_text()[:800])
    print("\n=== embedded images ===")
    for i, im in enumerate(page.get_images(full=True)):
        xref = im[0]
        info = doc.extract_image(xref)
        ext = info["ext"]
        fn = OUT / f"p{pno + 1}_img{i}.{ext}"
        fn.write_bytes(info["image"])
        print(f"  {fn.name}  {info['width']}x{info['height']}  ext={ext}  "
              f"{len(info['image']) / 1024:.0f} KB")

    # 顺带把提到 Fig.13 的页都导一遍图
    for p in (4, 5, 8, 9, 11):
        pg = doc[p]
        for i, im in enumerate(pg.get_images(full=True)):
            info = doc.extract_image(im[0])
            fn = OUT / f"p{p + 1}_img{i}.{info['ext']}"
            if not fn.exists():
                fn.write_bytes(info["image"])
                print(f"  extra: {fn.name} {info['width']}x{info['height']}")


if __name__ == "__main__":
    main()
