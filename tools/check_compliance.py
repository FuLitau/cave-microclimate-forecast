"""赛题硬约束扫描：参赛材料中不得出现学校名称与指导教师信息。

    python tools/check_compliance.py

对 ``dist/`` 下全部参赛 PDF/PPTX 与文档源文件抽取全文，按敏感词表扫描。
命中第三方文献作者单位属正常（引用许可），但必须人工确认**不是本团队**归属。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

# 提交物（不含内部工作文档）
TARGETS = [
    DIST / "01_技术路线.pdf",
    DIST / "02_数据集方案.pdf",
    DIST / "03_作品方案.pdf",
    DIST / "04_答辩PPT.pdf",
    DIST / "06_佐证材料.pdf",
    ROOT / "README.md",
    ROOT / "code" / "README.md",
    DIST / "README.txt",
]

# 硬约束：本团队学校名 / 指导教师称呼
# 负向先行断言排除「指导教师信息」这类**合规声明本身**的元表述
FORBIDDEN = re.compile(
    r"指导教[师授](?!信息)|指导教师?姓名|指导老师(?!信息)|本团队.{0,6}(大学|学院)|我校(大学|学院)?|课题组导师"
)

# 提示词：第三方单位名（引用中出现是正常的，需人工判断）
NOTICE = re.compile(r"[\u4e00-\u9fa5]{2,10}(大学|学院|研究院|研究所|博物馆)")


def _text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        with fitz.open(path) as doc:
            return "\n".join(p.get_text() for p in doc)
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    bad = 0
    for path in TARGETS:
        if not path.is_file():
            print(f"⚠️  缺少 {path.relative_to(ROOT)}")
            continue
        text = _text(path)
        hits = FORBIDDEN.findall(text)
        notices = sorted(set(NOTICE.findall(text)))
        rel = path.relative_to(ROOT)
        if hits:
            bad += 1
            print(f"❌ {rel} 命中硬约束 {len(hits)} 处：{sorted(set(hits))}")
        else:
            print(f"✅ {rel} 无学校/指导教师信息")
        if notices:
            print(f"      （引用中的第三方机构，需人工确认非本团队：{', '.join(notices[:8])}）")
    print()
    if bad:
        print(f"❌ {bad} 个文件需处理", file=sys.stderr)
        return 1
    print("✅ 硬约束扫描通过（第三方机构名请再人工过目）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
