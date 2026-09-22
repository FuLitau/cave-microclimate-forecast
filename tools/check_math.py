"""抽取 PDF 中含数学符号的段落，确认 LaTeX 已转为可读 Unicode。"""
from __future__ import annotations

import re
import sys

import pymupdf

SYMS = "ℝΨψΔℒτΣ≤≥≈∈×·ᵀ∫∂αβγδθλμσφω"

LATEX_LEFT = re.compile(r"\\[A-Za-z]+|\^\{|\}_\{|\$")


def main(pdf: str) -> int:
    doc = pymupdf.open(pdf)
    text = "\n".join(p.get_text() for p in doc)
    doc.close()
    print(f"{pdf}: 数学符号命中 {sum(text.count(c) for c in SYMS)} 次 "
          f"（{''.join(sorted({c for c in SYMS if c in text}))}）")
    left = LATEX_LEFT.findall(text)
    print(f"残留 LaTeX 记号: {len(left)} -> {sorted(set(left))[:12]}")
    print("\n--- 含符号的行 ---")
    for ln in text.splitlines():
        if any(c in ln for c in SYMS):
            print("  " + ln.strip()[:150])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
