"""生成百度网盘上传所需的目录与文件命名。

赛题规则原文（_ref/规则及提交要求.txt 三、作品材料规范 第 7 条）：

    7. 作品其他材料链接：将完整代码包、大型工程文件、高清图纸等大容量文件
    存放在一个文件夹中并上传至百度网盘，在相应栏目中提交有效分享链接，网盘内所
    有文件统一命名格式为：参赛团队编号-赛题名称-作品名称-XX（材料名称）。
    （分享时设置永久有效、自动生成提取码）
    参赛团队编号-赛题名称-作品名称/（根目录文件夹）
    ├─参赛团队编号-赛题名称-作品名称-XX（材料名称）

用法：

    python tools/build_netdisk_folder.py AIC-2026-12345678

或用环境变量：

    $env:AIC_TEAM_ID="AIC-2026-12345678"; python tools/build_netdisk_folder.py

产出：dist/网盘上传/<根目录名>/  内含按规则命名的全部大容量材料。
该目录只做**复制与重命名**，不改动任何源文件，因此可反复重跑。
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

THEME = "智慧气象"                     # 赛题名称
WORK = "石窟天盾-风险对齐的窟内微气候预报"   # 作品名称（冒号在 Windows 文件名中非法，故用连字符）
DEST_ROOT = ROOT / "dist" / "网盘上传"

# (源文件, 材料名称)
FILES: list[tuple[str, str]] = [
    ("dist/03_作品方案.pdf", "作品方案"),
    ("dist/04_答辩PPT.pdf", "答辩PPT"),
    ("dist/05_演示视频.mp4", "演示视频"),
    ("dist/06_佐证材料.pdf", "佐证材料"),
    ("dist/01_技术路线.pdf", "技术路线"),
    ("dist/02_数据集方案.pdf", "数据集方案"),
    ("dist/石窟天盾_参赛材料.zip", "完整材料与代码包"),
    ("dist/README.txt", "材料说明"),
    # ⚠️ 不要把 `dist/提交清单.md` 放进来：该文件自带「不要上传到网盘、
    # 不要作为参赛材料」的声明，且含「已知局限与风险（最大攻击面）」
    # 与「答辩预判问答」，属团队内部工作文件。
]


def resolve_team_id() -> str:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    env = os.environ.get("AIC_TEAM_ID", "").strip()
    if env:
        return env
    sys.exit(
        "缺少参赛团队编号。\n"
        "用法：python tools/build_netdisk_folder.py AIC-2026-XXXXXXXX\n"
        "或：  $env:AIC_TEAM_ID=\"AIC-2026-XXXXXXXX\"; python tools/build_netdisk_folder.py\n"
        "（编号见大赛报名系统「我的作品」页，格式形如 AIC-2026-XXXXXXXX）"
    )


def main() -> int:
    team_id = resolve_team_id()
    prefix = f"{team_id}-{THEME}-{WORK}"
    dest = DEST_ROOT / prefix

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    missing: list[str] = []
    total = 0
    for rel, label in FILES:
        src = ROOT / rel
        if not src.exists():
            missing.append(rel)
            continue
        suffix = src.suffix
        # 重命名时把材料名里的非法字符清掉，并保留原扩展名
        safe = label.replace("/", "-").replace("\\", "-")
        out = dest / f"{prefix}-{safe}{suffix}"
        shutil.copy2(src, out)
        total += out.stat().st_size
        print(f"  {out.name}    {out.stat().st_size / 1024 / 1024:.1f} MB")

    print()
    print(f"✅ 已生成 {dest}")
    print(f"   {len(FILES) - len(missing)} 个文件，合计 {total / 1024 / 1024:.1f} MB")
    if missing:
        print("   缺失（请先生成）：" + "、".join(missing))
        return 1

    print()
    print("下一步（需人工在浏览器完成，浏览器无法驱动系统文件选择框）：")
    print("  1) 打开 https://pan.baidu.com ，新建文件夹，名称：")
    print(f"     {prefix}")
    print("  2) 把上面目录里的文件全部上传进该文件夹")
    print("  3) 右键文件夹 → 分享 → 有效期选「永久有效」→ 勾选「自动填充提取码」")
    print("  4) 把分享链接填回报名系统的「作品其他材料链接」栏")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
