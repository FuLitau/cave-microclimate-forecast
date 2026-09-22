"""检查所有交付 PDF 是否有标记泄漏（RST/Markdown 残留）与渲染缺陷。"""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

LEAKS = [":math:", ".. math::", "@@", "**", "```", "\\mathbb", "\\mathcal", "\\text{"]

PDFS = [
    "dist/01_技术路线.pdf",
    "dist/02_数据集方案.pdf",
    "dist/03_作品方案.pdf",
    "dist/04_答辩PPT.pdf",
    "dist/06_佐证材料.pdf",
]


def main() -> int:
    bad = 0
    for name in PDFS:
        p = Path(name)
        if not p.exists():
            print(f"{name:28s} 缺失")
            bad += 1
            continue
        doc = pymupdf.open(str(p))
        text = "\n".join(page.get_text() for page in doc)
        repl = text.count("\ufffd")
        hits = {k: text.count(k) for k in LEAKS if text.count(k) > 0}
        size_kb = p.stat().st_size / 1024
        status = "OK" if (repl == 0 and not hits) else "WARN"
        if status != "OK":
            bad += 1
        print(f"{name:28s} {doc.page_count:>3d}页 {size_kb:>7.0f}KB  {len(text):>6d}字  "
              f"U+FFFD={repl}  {status}")
        for k, v in hits.items():
            print(f"    泄漏 {k!r} x{v}")
        doc.close()
    print()
    print("全部通过" if bad == 0 else f"{bad} 个文件需处理")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
