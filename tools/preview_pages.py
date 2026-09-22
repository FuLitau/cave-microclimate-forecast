"""导出指定 PDF 的指定页为 PNG，用于人工目视核对排版。"""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf


def export(pdf: str, pages, outdir: str = "dist/_preview", dpi: int = 105) -> None:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(pdf).stem
    doc = pymupdf.open(pdf)
    for n in pages:
        if not (0 <= n < doc.page_count):
            continue
        pix = doc[n].get_pixmap(dpi=dpi)
        p = out / f"{stem}_p{n + 1:02d}.png"
        pix.save(str(p))
        print(f"{p}  {pix.width}x{pix.height}")
    doc.close()


if __name__ == "__main__":
    pdf = sys.argv[1]
    pages = [int(x) for x in sys.argv[2].split(",")]
    export(pdf, pages)
