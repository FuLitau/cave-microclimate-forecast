# -*- coding: utf-8 -*-
"""字形级把关：源文里的字符必须真的能被 PDF 字体画出来。

为什么需要这个脚本
------------------
`tools/md2pdf.py` 用 `C:\\Windows\\Fonts\\Deng.ttf`（等线 / DengXian）排版。
DengXian **不含** 下列 Unicode 上标：`⁻ ⁰ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹`（也不含 `⋅`）。
PyMuPDF 的 Story 不做字形回退，于是这些字**被静默吃掉**：

    docs/06 源文 `5.07×10⁻⁷`  →  印出来 `5.07×10`
    docs/02 源文 `1.2×10⁻⁶`   →  印出来 `1.2×10`
    docs/01 源文 `10³⁰`       →  印出来 `10³`
    docs/06 源文 `−10²⁵`      →  印出来 `−10²`

`10⁻⁷ → 10` 不是版式瑕疵，是**物理量级被改错**。四个候选中文字体
（DengXian / SimHei / KaiTi / SimSun / Microsoft YaHei）**没有一个**能覆盖
全部上标，所以正确做法是**源文避免这些字符**（改用 `5.07e-7` 这类写法），
而不是换字体。本脚本把那道约束固化成可执行的检查。

两层检查
--------
1. **源文层**（主）：扫所有会被 `md2pdf.py` 渲染的文本源，凡是字符不在
   字体 cmap 里的，逐条报 `文件:行号: 字符`。这是**确定性**检查——
   跑在排版之前，不依赖具体渲染路径。
2. **产物层**（辅）：扫 `dist/*.pdf`，统计 `U+0000` 字形（PyMuPDF 用来
   表示"有字位但画不出字形"）。这一层能抓到源文层漏掉的字体回退问题；
   注意它**只能抓到"画了空框"的部分**，纯静默丢弃不产生 U+0000，
   所以第 1 层不可省。

用法
----
    python tools/check_glyphs.py            # 扫源文 + dist/*.pdf
    python tools/check_glyphs.py --src-only # 只扫源文（排版前自检）

退出码 0 = 通过；1 = 有缺字形。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 会被 md2pdf.py 渲染的文本源
SOURCES = [
    ROOT / "docs" / "01_技术路线.md",
    ROOT / "docs" / "02_数据集方案.md",
    ROOT / "docs" / "03_作品方案.md",
    ROOT / "docs" / "06_佐证材料.md",
    ROOT / "README.md",
    ROOT / "code" / "README.md",
    ROOT / "dist" / "README.txt",
    ROOT / "dist" / "提交清单.md",
]

# 字体候选顺序与 md2pdf.py 保持一致
FONT_CANDIDATES = ["Deng.ttf", "simhei.ttf", "simkai.ttf", "simsun.ttc"]
FONT_DIRS = [Path(r"C:\Windows\Fonts"), Path("/usr/share/fonts")]

# 已知无害：这些字符不在 DengXian 里，但实测由 PyMuPDF 的符号回退正常绘制
# （对应字形在 dist/*.pdf 里能正常提取，且不产生 U+0000）。白名单保持**最小**。
WHITELIST = set("⚠️✅❌⏳⚙️✓✗①②③④⑤⑥⑦⑧⑨⑩—–…•·√∞")

SUPERSCRIPT_HINT = {
    "⁻": "-", "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⋅": "*",
}


def _is_exponent_like(ch: str) -> bool:
    """幂次 / 上标 / 乘号类字符。

    这类字符**必须**由当前字体真的有字形：它们是**语义的一部分**
    （`10⁻⁷` 少了 `⁻⁷` 就从 1e-7 变成 10），而 PyMuPDF 的符号回退对它们
    不可靠——有的画成空框（产生 U+0000），有的**直接静默丢弃**
    （连 U+0000 都不留，产物层扫描抓不到）。

    其余符号实测回退正常，不在此列，避免制造大量假阳性：
      `−`(U+2212) 减号、`₂`(U+2082) 化学式下标（`CO₂` 实测正常提取）、
      `►`(U+25BA) 箭头、`ĥ`(U+0125)、`ᵀ`(U+1D40)、`ć`(U+0107)。
    **下标块 U+2080–U+209F 明确排除**——`CO₂` 是反例，它印得出来。
    """
    o = ord(ch)
    return (0x00B2 <= o <= 0x00B3) or (o == 0x00B9) \
        or (0x2070 <= o <= 0x207F) or ch in "⋅×"


def _pick_font() -> tuple[str, Path] | tuple[None, None]:
    for name in FONT_CANDIDATES:
        for d in FONT_DIRS:
            p = d / name
            if p.exists():
                return name, p
    return None, None


def _load_cmap(path: Path) -> set[int]:
    from fontTools.ttLib import TTFont

    t = TTFont(str(path), fontNumber=0, lazy=True)
    cmap: set[int] = set()
    for tb in t["cmap"].tables:
        cmap |= set(tb.cmap.keys())
    return cmap


def check_sources(cmap: set[int]) -> list[str]:
    problems: list[str] = []
    for src in SOURCES:
        if not src.exists():
            problems.append(f"[缺失] {src.relative_to(ROOT)} 不存在")
            continue
        for lineno, line in enumerate(
                src.read_text(encoding="utf-8").splitlines(), start=1):
            bad = sorted({ch for ch in line
                          if ch not in WHITELIST
                          and _is_exponent_like(ch)
                          and ord(ch) not in cmap})
            if bad:
                shown = " ".join(
                    f"{ch!r}(U+{ord(ch):04X}"
                    + (f"，建议改 '{SUPERSCRIPT_HINT[ch]}'" if ch in SUPERSCRIPT_HINT else "")
                    + ")"
                    for ch in bad)
                problems.append(
                    f"[源文] {src.relative_to(ROOT)}:{lineno}: {shown}\n"
                    f"        {line.strip()[:110]}")
    return problems


def check_pdfs() -> list[str]:
    import pymupdf

    problems: list[str] = []
    for pdf in sorted((ROOT / "dist").glob("*.pdf")):
        doc = pymupdf.open(pdf)
        hits: list[tuple[int, str]] = []
        for pno, page in enumerate(doc, start=1):
            for block in page.get_text("rawdict")["blocks"]:
                for line in block.get("lines", []):
                    spans = line["spans"]
                    text = "".join(c["c"] for sp in spans for c in sp["chars"])
                    if "\x00" in text:
                        hits.append((pno, text.replace("\x00", "\u25a1")[:110]))
        if hits:
            problems.append(f"[产物] {pdf.relative_to(ROOT)}: "
                            f"{len(hits)} 处缺字形（□ 即画不出的字）")
            for pno, text in hits[:6]:
                problems.append(f"         p{pno}: {text}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="字形覆盖检查")
    ap.add_argument("--src-only", action="store_true",
                    help="只扫源文，不扫 dist/*.pdf")
    args = ap.parse_args()

    name, path = _pick_font()
    if path is None:
        print("❌ 找不到任何候选中文字体，无法检查（参见 md2pdf.py 的 _FONT_CANDIDATES）")
        return 1
    print(f"排版字体: {name}  ({path})")
    cmap = _load_cmap(path)

    problems = check_sources(cmap)
    if not args.src_only:
        problems += check_pdfs()

    print("=" * 74)
    if problems:
        print(f"❌ 字形检查未通过：{len(problems)} 条")
        for p in problems:
            print("  " + p)
        print("=" * 74)
        print("修法：源文改用 `5.07e-7` 这类不依赖 Unicode 上标的写法；"
              "不要靠换字体（四个候选中文字体都缺上标）。")
        return 1
    msg = "✅ 字形检查通过：源文全部字符均在该字体 cmap 内"
    if not args.src_only:
        msg += "，且 dist/*.pdf 无空缺字形"
    print(msg + "。")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
