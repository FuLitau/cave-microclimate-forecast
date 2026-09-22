"""打包参赛材料 zip（可复现，不要再手工压缩）。

    python tools/build_package.py

产出 ``dist/石窟天盾_参赛材料.zip``，内容：

    01_技术路线.pdf  02_数据集方案.pdf  03_作品方案.pdf
    04_答辩PPT.pdf   05_演示视频.mp4    06_佐证材料.pdf
    README.txt       提交说明（来自 dist/README.txt）
    README.md        仓库首页（问题 / 方法 / 结果 / 诚信声明）
    code/            全部源码、实验脚本与落盘结果（含数据，便于离线复现）
    docs/            作品方案与佐证材料的 Markdown 源文件
    tools/           文档渲染、PPT/视频生成、内容与版式校验脚本

刻意排除：``__pycache__``、``*.pyc``、``dist/``（避免自包含）、``_ref/``/``_lit/``
（第三方获奖报告，版权不属于本项目，不得再分发）、团队内部工作文档。

打包后会**校验** zip 内的 ``code/smoke_cave.py`` 是否与工作区一致，
防止再次把过期文件打进去（历史上发生过一次）。
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
OUT = DIST / "石窟天盾_参赛材料.zip"

# dist 顶层要放进 zip 的交付物（按比赛要求的编号顺序）
DELIVERABLES = [
    "01_技术路线.pdf",
    "02_数据集方案.pdf",
    "03_作品方案.pdf",
    "04_答辩PPT.pdf",
    "05_演示视频.mp4",
    "06_佐证材料.pdf",
    "README.txt",
]

# 目录型内容：(工作区目录, zip 内前缀)
TREES = [
    ("code", "code"),
    ("tools", "tools"),
]

# 单文件（放在 zip 根）
ROOT_FILES = ["README.md"]

# docs/ 里只放提交相关的正文源文件；内部工作文档不进包
DOC_FILES = ["01_技术路线.md", "02_数据集方案.md", "03_作品方案.md", "06_佐证材料.md"]

EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".git"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def _iter_tree(base: Path):
    for p in sorted(base.rglob("*")):
        if p.is_dir():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix in EXCLUDE_SUFFIXES:
            continue
        yield p


def main() -> int:
    if not DIST.is_dir():
        print(f"❌ 找不到 {DIST}，请先渲染交付物", file=sys.stderr)
        return 1

    missing = [f for f in DELIVERABLES if not (DIST / f).is_file()]
    if missing:
        print("❌ dist/ 缺少交付物：" + "、".join(missing), file=sys.stderr)
        return 1

    if OUT.exists():
        OUT.unlink()

    added: list[str] = []
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        # 1) 交付物
        for name in DELIVERABLES:
            z.write(DIST / name, name)
            added.append(name)

        # 2) 根文件
        for name in ROOT_FILES:
            src = ROOT / name
            if src.is_file():
                z.write(src, name)
                added.append(name)

        # 3) 目录树
        for sub, prefix in TREES:
            base = ROOT / sub
            if not base.is_dir():
                continue
            for p in _iter_tree(base):
                arc = f"{prefix}/{p.relative_to(base).as_posix()}"
                z.write(p, arc)
                added.append(arc)

        # 4) docs 正文
        for name in DOC_FILES:
            src = ROOT / "docs" / name
            if src.is_file():
                arc = f"docs/{name}"
                z.write(src, arc)
                added.append(arc)

    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"✅ 已生成 {OUT}")
    print(f"   条目 {len(added)} 个，{size_mb:.1f} MB")

    # ---- 校验：zip 内的关键文件必须与工作区逐字节一致 ----
    checks = ["code/smoke_cave.py", "code/src/physics/cave_model.py", "README.md"]
    with zipfile.ZipFile(OUT) as z:
        names = set(z.namelist())
        ok = True
        for rel in checks:
            if rel not in names:
                print(f"   ❌ zip 内缺少 {rel}")
                ok = False
                continue
            same = z.read(rel) == (ROOT / rel).read_bytes()
            # 工作区为 CRLF、zip 内为 LF 时也算一致（仅换行差异）
            same = same or z.read(rel).replace(b"\r\n", b"\n") == (ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
            print(f"   {'✅' if same else '❌'} {rel} {'一致' if same else '不一致（zip 内容陈旧！）'}")
            ok = ok and same
        if "code/smoke_cave.py" in names:
            body = z.read("code/smoke_cave.py").decode("utf-8", "replace")
            if "ach_open" in body:
                print("   ❌ zip 内的 smoke_cave.py 仍引用已废弃的 ach_open")
                ok = False

    if not ok:
        print("\n❌ 打包校验失败", file=sys.stderr)
        return 1
    print("\n✅ 打包校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
