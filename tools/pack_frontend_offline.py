"""把前端打成「双击即可打开」的离线单文件 HTML，并组装成发给老师过目的 zip。

为什么不能直接打包 ``frontend/dist``
------------------------------------
Vite 默认产物是 ``index.html`` + 外链的 ES module（``<script type="module" src="./assets/*.js">``）。
用 ``file://`` 双击打开时，浏览器会以 CORS 策略拦掉这个外链模块（origin 为 ``null``），
页面只剩白屏——实测 ``tools/shoot_frontend.mjs --base file:///...`` 四路由全部 FAIL。

做法
----
1. 在每个前端目录里临时写一个 ``vite.singlefile.tmp.mjs``：关掉 manualChunks、
   开 ``inlineDynamicImports``，让产物只剩「一个 app.js + 一个 app.css」；
2. ``npx vite build --config`` 构建到 ``_pack_tmp/<ver>/``（不碰前端源码与 dist）；
3. 把 css 内联进 ``<style>``、js 内联进 ``<script type="module">``，删掉外链标签，
   转义 js 里可能出现的 ``</script``；
4. 生成 ``说明.txt``，带上源码副本，打成一个 zip。

用法::

    python tools/pack_frontend_offline.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "_pack_tmp"
STAGE = TMP / "石窟天盾-前端演示"
NODE_DIR = r"F:\Desktop\tec\openclaw\node.js_about"
NPM = "npx.cmd" if os.name == "nt" else "npx"

# (前端目录, 构建输出子目录, 打包后的 HTML 文件名, 界面标题)
VERSIONS = [
    ("frontend-v2", "v2", "石窟天盾-预警指挥台（备选版）.html"),
    ("frontend", "v1", "石窟天盾-预警指挥台（原版）.html"),
]

CONFIG_TPL = """// 临时配置（由 tools/pack_frontend_offline.py 生成，打包结束即删除）。
// 目的：关掉 manualChunks，让产物只剩「一个 JS + 一个 CSS」，
// 这样才能内联进单个 HTML —— file:// 下浏览器会以 CORS 拦掉外链的 ES module。
import {{ defineConfig }} from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({{
  base: './',
  plugins: [vue()],
  build: {{
    outDir: {outdir!r},
    emptyOutDir: true,
    chunkSizeWarningLimit: 100000,
    cssCodeSplit: false,
    modulePreload: {{ polyfill: false }},
    rollupOptions: {{
      output: {{
        inlineDynamicImports: true,
        entryFileNames: 'app.js',
        assetFileNames: 'app.[ext]',
      }},
    }},
  }},
}})
"""

README_TXT = """石窟天盾 · 窟内微气候风险预报 —— 前端界面演示
====================================================

怎么打开
--------
直接双击 .html 文件即可，不用安装任何东西，也不用联网。
两个文件都是「单文件版」：样式、脚本、数据全部内嵌在一个 HTML 里，可以单独转发。

建议用 Chrome 或 Edge 打开，并把窗口最大化。左侧导航有四个页面：
    风险指挥台 / 效果对照 / 可信度验证 / 方法说明

两个文件的区别
--------------
「备选版」在原版基础上补了一件事：演示一个**真正触发预警**的时间窗口。

原版里的三个演示窗口都是按「真实湿度峰值」挑出来的教学样例，模型的读出峰值
（49.1% / 54.2% / 40.7%）都低于 62% 业务预警线，所以首屏看到的是
「预报 → 风险 → 0 报警」，看不到完整闭环。

备选版新增的窗口是从测试段 34,887 个起报时刻里扫出来的真阳性样本：
2022-05-25 09:00 起报，第 6 小时发出预警，第 30 小时真实湿度越过 62% 业务线
（**提前 24 小时**），预警持续 39 小时，读出峰值 64.3%（未做风险对齐的
线性 MSE 对照只有 50.3%），处置建议为「限流（控制人数与停留时长）」。
时间轴分上下两轨：上轨是真实湿度超阈，下轨是模型预警态，提前量可以直接看出来。

除这一个窗口之外，两个文件的界面、口径与其余数据完全一致。

数据口径（重要）
----------------
1. 窟内湿度序列**不是窟内实测**，而是用文献标定的物理模型、由公开气象数据驱动
   生成的**合成标签**；窟内温湿度实测数据目前不公开。
2. 界面上的「风险读出」是分位数回归的**上分位读出**（τ=0.95），是风险分数，
   不是湿度点预报，也不应读作预测分布的中位数。
3. 四个演示窗口的挑选规则不同（1 个真阳性 + 3 个教学样例），页内已分别标注，
   不可混读。
4. 页面上所有数字都由 code/results/*.csv 自动生成，前端只做展示，不含手工填写的数值。
5. 决策建议为模型辅助建议，供管理人员研判，不构成自动控制指令。

源码
----
源码/ 目录下是 Vue 3 + TypeScript 的完整前端源码，仅供查阅，不需要运行。
构建与运行方式见各目录下的 README.md。
"""


def run(cmd: list[str], cwd: Path) -> None:
    env = dict(os.environ)
    env["PATH"] = env.get("PATH", "") + os.pathsep + NODE_DIR
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = (r.stdout or "").strip().splitlines()[-4:]
    for line in tail:
        print("      " + line)
    if r.returncode != 0:
        print((r.stderr or "")[-2000:], file=sys.stderr)
        raise SystemExit(f"构建失败：{' '.join(cmd)}（exit {r.returncode}）")


def build_single(ver_dir: str, tag: str) -> Path:
    """构建出只剩一个 js + 一个 css 的产物，返回该产物目录。"""
    src = ROOT / ver_dir
    outdir = TMP / tag
    cfg = src / "vite.singlefile.tmp.mjs"
    print(f"[{tag}] 单文件构建 {ver_dir} → {outdir.relative_to(ROOT)}")
    cfg.write_text(CONFIG_TPL.format(outdir=str(outdir).replace("\\", "/")), encoding="utf-8")
    try:
        run([NPM, "vite", "build", "--config", cfg.name], cwd=src)
    finally:
        cfg.unlink(missing_ok=True)          # 前端源码目录必须恢复原样
    return outdir


def inline(outdir: Path, dst: Path) -> tuple[int, int]:
    html = (outdir / "index.html").read_text(encoding="utf-8")
    css = (outdir / "app.css").read_text(encoding="utf-8")
    js = (outdir / "app.js").read_text(encoding="utf-8")

    # 删掉外链资源标签
    html, n_s = re.subn(r'<script[^>]*\ssrc="[^"]*"[^>]*>\s*</script>', "", html)
    html, n_l = re.subn(r'<link[^>]*\srel="stylesheet"[^>]*>', "", html)
    html = re.sub(r'<link[^>]*\srel="modulepreload"[^>]*>', "", html)
    assert n_s == 1 and n_l == 1, f"{dst.name}: 外链标签数量异常 script={n_s} link={n_l}"

    # js 里一旦出现 </script 会把 HTML 提前截断；在 JS 字符串里 <\/ 与 </ 等价
    js_safe = js.replace("</script", "<\\/script")
    assert "</style" not in css

    html = html.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)
    html = html.replace("</body>", f'<script type="module">\n{js_safe}\n</script>\n</body>', 1)

    # 内联后不应再有任何外部引用
    leftovers = re.findall(r'(?:src|href)="(?!data:|#)[^"]*"', html)
    assert not leftovers, f"{dst.name}: 仍有外链引用 {leftovers[:5]}"

    dst.write_text(html, encoding="utf-8")
    return len(css), len(js)


def copy_sources() -> int:
    """把两个前端目录的源码复制进包里（排除 node_modules / dist / 临时配置）。"""
    skip_dirs = {"node_modules", "dist", ".vite"}
    skip_files = {"vite.singlefile.tmp.mjs"}
    n = 0
    for ver_dir, _, _ in VERSIONS:
        s = ROOT / ver_dir
        d = STAGE / "源码" / ver_dir
        for p in sorted(s.rglob("*")):
            if any(part in skip_dirs for part in p.relative_to(s).parts):
                continue
            if p.name in skip_files or p.suffix in {".log", ".tsbuildinfo"}:
                continue
            if p.is_dir():
                continue
            rel = p.relative_to(s)
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, d / rel)
            n += 1
    return n


def main() -> None:
    if TMP.exists():
        shutil.rmtree(TMP)
    STAGE.mkdir(parents=True)

    sizes: list[tuple[str, int]] = []
    for ver_dir, tag, html_name in VERSIONS:
        outdir = build_single(ver_dir, tag)
        c, j = inline(outdir, STAGE / html_name)
        sizes.append((html_name, (STAGE / html_name).stat().st_size))
        print(f"      内联完成：css {c:,} B + js {j:,} B → {html_name}")

    (STAGE / "说明.txt").write_text(README_TXT, encoding="utf-8-sig")
    n_src = copy_sources()
    print(f"源码副本 {n_src} 个文件")

    zip_path = ROOT / "dist" / "石窟天盾-前端演示.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(STAGE.rglob("*")):
            if p.is_file():
                z.write(p, arcname=str(Path(STAGE.name) / p.relative_to(STAGE)))

    print("\n=== 打包结果 ===")
    for name, sz in sizes:
        print(f"  {name}   {sz / 1024 / 1024:.2f} MB")
    with zipfile.ZipFile(zip_path) as z:
        print(f"  zip 条目 {len(z.namelist())} 个，{zip_path.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"  → {zip_path}")


if __name__ == "__main__":
    main()
