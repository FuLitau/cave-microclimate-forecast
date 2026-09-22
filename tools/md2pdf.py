"""Markdown → PDF 渲染器（中文友好、无外部依赖链）。

为什么自己写而不用 pandoc/wkhtmltopdf
------------------------------------
本机没有 pandoc，也没有 wkhtmltopdf；weasyprint 需要 GTK 运行库。
但环境里已有 **PyMuPDF 1.28**，其 ``Story`` 支持 HTML + CSS 排版，
配合本地中文字体即可产出可提交的 PDF，且**完全离线**。

用法::

    python tools/md2pdf.py docs/03_作品方案.md dist/03_作品方案.pdf

设计要点
--------
* 中文字体从系统字体目录取**单文件 TTF**（``Deng.ttf`` 等），
  避免 ``.ttc`` 字体集合在 PyMuPDF 归档中的兼容问题。
* ``.ttc`` 找不到时回退到 PyMuPDF 内置 CJK 字体 ``china-s``。
* 支持标题 / 段落 / 表格 / 代码块 / 列表 / 引用 / 分隔线 / 行内粗体斜体与行内代码。
* RST 的 ``.. math::`` 指令会转成代码块，避免原样漏出。
"""

from __future__ import annotations

import html as _html
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import markdown
import pymupdf
from pymupdf import Story

# 优先使用单文件 TTF（.ttc 集合在归档字体加载时不可靠）
_FONT_CANDIDATES = [
    ("Deng.ttf", "Dengb.ttf"),      # 等线 / DengXian
    ("simhei.ttf", None),           # 黑体
    ("simkai.ttf", None),           # 楷体
    ("simsun.ttc", None),           # 宋体（回退）
]
_FONT_DIRS = [Path(r"C:\Windows\Fonts"), Path("/usr/share/fonts")]

CSS_TEMPLATE = """
@font-face {{ font-family: "CJK"; src: url("{reg}"); }}
{extra_face}
* {{ font-family: "CJK", sans-serif; }}
body {{ font-size: 10pt; line-height: 1.55; color: #1a1a1a; }}
h1 {{ font-size: 19pt; color: #0b3d6b; margin: 0 0 14pt 0; line-height: 1.3; }}
h2 {{ font-size: 14pt; color: #0b3d6b; margin: 20pt 0 8pt 0;
      border-bottom: 1.2pt solid #0b3d6b; padding-bottom: 3pt; }}
h3 {{ font-size: 11.5pt; color: #14507f; margin: 14pt 0 6pt 0; }}
h4 {{ font-size: 10.5pt; color: #14507f; margin: 11pt 0 5pt 0; }}
p {{ margin: 0 0 7pt 0; text-align: justify; }}
ul, ol {{ margin: 0 0 7pt 0; padding-left: 16pt; }}
li {{ margin-bottom: 3pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 8pt 0 12pt 0;
         font-size: 8.6pt; }}
th {{ background: #e8eef5; border: 0.6pt solid #9bb3c9; padding: 4pt 5pt;
      text-align: left; font-weight: bold; }}
td {{ border: 0.6pt solid #c2cfdb; padding: 4pt 5pt; vertical-align: top; }}
tr:nth-child(even) td {{ background: #f7fafd; }}
code {{ font-family: "CJK"; background: #f2f4f7; font-size: 8.8pt; }}
pre {{ background: #f6f8fa; border-left: 2.5pt solid #0b3d6b; padding: 6pt 8pt;
       font-size: 8.2pt; line-height: 1.35; margin: 7pt 0 10pt 0; }}
pre code {{ background: none; font-size: 8.2pt; }}
blockquote {{ margin: 7pt 0 7pt 10pt; padding-left: 9pt;
              border-left: 2.5pt solid #b9c6d4; color: #40566b; }}
hr {{ border: none; border-top: 0.6pt solid #c2cfdb; margin: 12pt 0; }}
strong {{ font-weight: bold; }}
"""


def _pick_fonts() -> tuple[str, str | None, Path | None, Path | None]:
    """返回 (注册名, 粗体名, 常规字体路径, 粗体字体路径)。"""
    for reg, bold in _FONT_CANDIDATES:
        for d in _FONT_DIRS:
            rp = d / reg
            if not rp.exists():
                continue
            if rp.suffix.lower() == ".ttc":
                return "china-s", None, None, None   # 交给内置 CJK
            bp = (d / bold) if bold else None
            return "cjk.ttf", ("cjkb.ttf" if bp and bp.exists() else None), rp, \
                   (bp if bp and bp.exists() else None)
    return "china-s", None, None, None


_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "kappa": "κ", "lambda": "λ",
    "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ",
    "tau": "τ", "phi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ",
    "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}

_SYMBOL = {
    "in": "∈", "notin": "∉", "subset": "⊂", "le": "≤", "leq": "≤",
    "ge": "≥", "geq": "≥", "neq": "≠", "approx": "≈", "equiv": "≡",
    "times": "×", "cdot": "·", "pm": "±", "to": "→", "rightarrow": "→",
    "infty": "∞", "partial": "∂", "nabla": "∇", "sum": "Σ", "prod": "Π",
    "int": "∫", "forall": "∀", "exists": "∃", "top": "ᵀ", "perp": "⊥",
    "Vert": "‖", "vert": "|", "rangle": "⟩", "langle": "⟨",
    "quad": " ", "qquad": " ", "log": "log", "exp": "exp", "max": "max",
    "min": "min", "argmax": "argmax", "argmin": "argmin", "det": "det",
    "mathrm": "", "mathcal": "", "mathbb": "", "text": "", "hat": "",
}


def _latex(s: str) -> str:
    """把常见 LaTeX 片段转成可读的 Unicode（PDF 里不做真排版）。"""
    # 去花括号包裹命令
    s = re.sub(r"\\(?:text|mathrm|mathit|operatorname)\{([^{}]*)\}", r"\1", s)
    s = s.replace(r"\mathbb{R}", "ℝ").replace(r"\mathbb{1}", "𝟙")
    s = s.replace(r"\mathbb{E}", "𝔼").replace(r"\mathcal{L}", "ℒ")
    s = s.replace(r"\mathcal{K}", "𝒦").replace(r"\mathcal{D}", "𝒟")
    # 分数
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    # \hat{x} -> x̂（组合抑扬符）  \hat h -> ĥ
    s = re.sub(r"\\hat\{([^{}])\}", lambda m: m.group(1) + "\u0302", s)
    s = re.sub(r"\\hat\s+([A-Za-z])", lambda m: m.group(1) + "\u0302", s)
    # 间距与定界符（必须在「命令 -> 符号」之前，否则 \big 先被拆成 big）
    for a, b in (("\\,", " "), ("\\;", " "), ("\\:", " "), ("\\!", ""),
                 ("\\left", ""), ("\\right", ""), ("\\big", ""), ("\\Big", ""),
                 ("\\underbrace", ""), ("\\mathbf", ""), ("\\bm", ""),
                 ("\\{", "{"), ("\\}", "}"), ("\\|", "‖")):
        s = s.replace(a, b)
    # 命令 -> 符号
    s = re.sub(r"\\([A-Za-z]+)",
               lambda m: _GREEK.get(m.group(1)) or _SYMBOL.get(m.group(1), m.group(1)),
               s)
    s = s.replace("{", "").replace("}", "")
    # 组合抑扬符后紧跟的下标标记整理
    s = s.replace("\u0302 ", "\u0302")
    return re.sub(r"\s{2,}", " ", s).strip()


def _preprocess(md: str) -> str:
    """把 RST 遗留指令与新式标记整理成 markdown 能懂的形式。"""
    # .. math::\n\n    <formula>  ->  围栏代码块
    def _math(m: re.Match) -> str:
        body = m.group(1)
        lines = [_latex(ln.strip()) for ln in body.strip().splitlines() if ln.strip()]
        return "```\n" + "\n".join(lines) + "\n```\n"
    md = re.sub(r"\.\. math::\s*\n((?:\s{2,}.*\n?)+)", _math, md)
    # 行内角色 :math:`...` -> 行内代码（否则字面漏出 ":math:"）
    md = re.sub(r":math:`([^`]+)`", lambda m: "`" + _latex(m.group(1)) + "`", md)
    # 段落中被 markdown 忽略的软换行：保留换行以便阅读
    return md


def convert(md_path: Path, pdf_path: Path) -> None:
    md_text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(
        _preprocess(md_text),
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
    )

    reg_name, bold_name, reg_path, bold_path = _pick_fonts()

    tmpdir = Path(tempfile.mkdtemp(prefix="md2pdf_"))
    extra_face = ""
    try:
        if reg_path is not None:
            shutil.copy2(reg_path, tmpdir / "cjk.ttf")
        if bold_path is not None:
            shutil.copy2(bold_path, tmpdir / "cjkb.ttf")
            extra_face = (
                '@font-face { font-family: "CJK"; font-weight: bold; '
                'src: url("cjkb.ttf"); }'
            )
        css = CSS_TEMPLATE.format(
            reg=("cjk.ttf" if reg_path is not None else "china-s.ttf"),
            extra_face=extra_face,
        )
        doc_html = f"<html><body>{body}</body></html>"

        # 注意：PyMuPDF 的 Archive 接受**目录路径**，不接受 zip 文件路径
        story = Story(html=doc_html, user_css=css, archive=str(tmpdir))
        raw_path = tmpdir / "raw.pdf"
        writer = pymupdf.DocumentWriter(str(raw_path))
        mediabox = pymupdf.paper_rect("a4")
        where = mediabox + (42, 40, -42, -44)      # 左右 42pt、上下 40/44pt 页边距

        pages = 0
        more = 1
        while more:
            dev = writer.begin_page(mediabox)
            more, _ = story.place(where)
            story.draw(dev)
            writer.end_page()
            pages += 1
            if pages > 400:                         # 安全上限
                break
        writer.close()

        # ---- 关键：字体子集化 ----
        # Story 会把**整个中文字体**嵌进 PDF（等线字体约 30 MB），
        # 远超赛题"作品方案 PDF ≤ 10 MB"的硬限制。
        # subset_fonts() 只保留文档中实际用到的字形，通常能把体积压到 1 MB 内。
        # 注意：从 raw.pdf 读、写到最终路径，**全程不打开最终文件**——
        # Windows 下对已打开的文件做 os.replace 会抛 PermissionError。
        _shrink(raw_path, pdf_path)

        print(f"[md2pdf] {md_path.name} -> {pdf_path.name}  "
              f"字体={reg_name}  页数={pages}  "
              f"{pdf_path.stat().st_size / 1024:.0f} KB")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _shrink(raw_path: Path, pdf_path: Path) -> None:
    """字体子集化 + 对象清理 + 流压缩，把 PDF 压到可提交体积。"""
    doc = pymupdf.open(str(raw_path))
    try:
        try:
            doc.subset_fonts()
        except Exception as exc:  # noqa: BLE001
            print(f"[md2pdf] 字体子集化失败（将继续压缩）: {exc}")
        doc.save(str(pdf_path), garbage=4, deflate=True, clean=True,
                 deflate_fonts=True, deflate_images=True)
    finally:
        doc.close()


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    src = Path(argv[1])
    dst = Path(argv[2])
    dst.parent.mkdir(parents=True, exist_ok=True)
    convert(src, dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
