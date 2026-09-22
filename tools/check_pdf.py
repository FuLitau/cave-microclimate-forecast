"""检查生成的 PDF：文字可提取性、中文是否真的渲染、并导出首页预览图。"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

pdf = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/03_作品方案.pdf")
doc = pymupdf.open(str(pdf))

print(f"文件      = {pdf}")
print(f"页数      = {doc.page_count}")
print(f"大小      = {pdf.stat().st_size / 1024:.0f} KB")

full = "".join(p.get_text() for p in doc)
print(f"可提取字符 = {len(full)}")

print("\n--- 第 1 页文字（前 380 字） ---")
print(doc[0].get_text()[:380])

print("\n--- 中文渲染抽查 ---")
probes = ["石窟天盾", "风险对齐", "延迟嵌入", "阈值加权", "合成标签",
          "42.6 h", "0.122", "FirstOrderTransfer", "twCRPS"]
for probe in probes:
    print(f"  {probe:<20} {'OK' if probe in full else '** MISSING **'}")

print("\n--- 豆腐块检测（替代字符 U+FFFD / 空白页） ---")
bad = full.count("\ufffd")
print(f"  替代字符数量 = {bad}  {'OK' if bad == 0 else '** 字体缺字 **'}")
empty = [i + 1 for i, p in enumerate(doc) if len(p.get_text().strip()) < 20]
print(f"  近乎空白页   = {empty if empty else '无'}")

out = pdf.with_name("_page1.png")
doc[0].get_pixmap(dpi=110).save(str(out))
print(f"\n首页预览已保存 = {out}")

doc.close()
