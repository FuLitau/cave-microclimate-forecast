"""快速自检：驱动列是否存在、全序列特征矩阵能否构造。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.operator.transport import (DEFAULT_DRIVERS, TransportConfig,  # noqa: E402
                                    build_features)

od = pd.read_csv(ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                 index_col=0, parse_dates=True).sort_index()
print("列:", list(od.columns))
print("DEFAULT_DRIVERS =", DEFAULT_DRIVERS)
missing = [c for c in DEFAULT_DRIVERS if c not in od.columns]
print("缺失驱动:", missing or "无")
if missing:
    raise SystemExit(1)
for col in ("PS", "PSC"):
    if col in od.columns:
        print(f"  {col}: mean {od[col].mean():.3f}  std {od[col].std():.3f}  "
              f"min {od[col].min():.3f}  max {od[col].max():.3f}")
Psi = build_features(od, TransportConfig())
print("Psi 形状:", Psi.shape, " 有限值占比:", f"{float((~pd.isna(Psi)).mean()):.4f}")
