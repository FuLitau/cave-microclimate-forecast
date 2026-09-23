"""交付物新鲜度检查：确保每个产物都不早于它的输入。

存在理由（一次真实的静默故障）
------------------------------
`tools/make_video.py` 原先只判断 ``dist/04_答辩PPT.pdf`` 是否存在，
**不比较时间戳**。因此「改了幻灯片 → 重出 PDF → 忘了重跑视频」时，
视频会带着旧版画面被交付出去，而任何脚本都不会报错。
审计代理复现了这个场景（PPT/PDF 在 13:19 更新、mp4 仍是 01:02），
是靠逐帧图像比对才发现的——这个检查把它变成一条命令。

检查的依赖链
------------
===== ============================================ ==========================
产物   依赖                                          违反后果
===== ============================================ ==========================
01     docs/01_技术路线.md                          PDF 与正文不一致
02     docs/02_数据集方案.md                        同上
03     docs/03_作品方案.md                          同上（**参赛主材料**）
06     docs/06_佐证材料.md                          同上
04     tools/build_ppt.py、dist/figs/*.png          PPT 嵌了旧图 / 旧文案
04pdf  dist/04_答辩PPT.pptx                        PDF 与 PPT 不一致
05     dist/04_答辩PPT.pdf                          视频画面是旧版幻灯片
zip    dist/ 下全部参赛文件                         网盘包里的材料过期
===== ============================================ ==========================

用法::

    python tools/check_freshness.py        # 有违反则非零退出
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else -1.0


def stamp(t: float) -> str:
    import datetime as dt

    return "缺失" if t < 0 else f"{dt.datetime.fromtimestamp(t):%Y-%m-%d %H:%M:%S}"


FIGS = sorted((DIST / "figs").glob("*.png")) if (DIST / "figs").exists() else []

# (产物, 依赖列表) —— 产物必须不早于每一个存在的依赖
CHAINS: list[tuple[Path, list[Path]]] = [
    (DIST / "01_技术路线.pdf", [ROOT / "docs" / "01_技术路线.md"]),
    (DIST / "02_数据集方案.pdf", [ROOT / "docs" / "02_数据集方案.md"]),
    (DIST / "03_作品方案.pdf", [ROOT / "docs" / "03_作品方案.md"]),
    (DIST / "06_佐证材料.pdf", [ROOT / "docs" / "06_佐证材料.md"]),
    (DIST / "04_答辩PPT.pptx", [
        ROOT / "tools" / "build_ppt.py",
        ROOT / "tools" / "md2pdf.py",
        *FIGS,
    ]),
    (DIST / "04_答辩PPT.pdf", [DIST / "04_答辩PPT.pptx"]),
    (DIST / "05_演示视频.mp4", [
        DIST / "04_答辩PPT.pdf",
        ROOT / "tools" / "make_video.py",
    ]),
    (DIST / "石窟天盾_参赛材料.zip", [
        DIST / "01_技术路线.pdf",
        DIST / "02_数据集方案.pdf",
        DIST / "03_作品方案.pdf",
        DIST / "04_答辩PPT.pdf",
        DIST / "05_演示视频.mp4",
        DIST / "06_佐证材料.pdf",
    ]),
]


def main() -> int:
    print("交付物新鲜度检查")
    print("=" * 74)
    bad: list[str] = []
    skipped: list[str] = []

    for art, deps in CHAINS:
        if not art.exists():
            skipped.append(f"{art.relative_to(ROOT)} 不存在（尚未生成）")
            continue
        ta = mtime(art)
        stale = [(d, mtime(d)) for d in deps if d.exists() and mtime(d) > ta]
        missing = [d for d in deps if not d.exists()]
        rel = art.relative_to(ROOT)
        if stale:
            print(f"❌ {rel}  ({stamp(ta)})")
            for d, td in stale:
                print(f"     晚于它的输入：{d.relative_to(ROOT)}  {stamp(td)}")
            bad.append(str(rel))
        else:
            extra = f"   （依赖缺失 {len(missing)} 个，已跳过）" if missing else ""
            print(f"✅ {rel}  ({stamp(ta)}){extra}")

    print("=" * 74)
    for s in skipped:
        print(f"· 跳过：{s}")
    if bad:
        print(f"\n❌ {len(bad)} 个产物已过期，必须按下述顺序重出后重新检查：")
        print("   1) python tools/md2pdf.py docs/01_技术路线.md dist/01_技术路线.pdf")
        print("      （02/03/06 同理）")
        print("   2) python code/experiments/make_slides_figs.py")
        print("   3) python tools/build_ppt.py  然后用 PowerPoint 导出 "
              "dist/04_答辩PPT.pdf")
        print("   4) python tools/make_video.py")
        print("   5) python tools/build_netdisk_folder.py && python tools/build_package.py")
        print("   6) python tools/check_freshness.py  # 本脚本，须全绿")
        return 1
    print("\n✅ 全部产物均不早于其输入。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
