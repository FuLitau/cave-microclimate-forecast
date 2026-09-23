"""ISD 站点观测 vs NASA POWER 再分析：外场驱动的真实性交叉核对。

**为什么需要这个脚本**

作品方案 §3.1 把 NOAA ISD 敦煌站（USAF 524180 / WBAN 99999）列为「外场真实性交叉核对」，
但在此之前仓库里只有 9 个原始 CSV（`code/data/raw/isd/isd_dh_2015..2023.csv`）**没有任何
代码消费它们**——也就是说那条声明当时是没有执行证据的。本脚本把它变成可复现实测。

**做什么**

1. 读 ISD 逐时库（FM-12 报文，通常每 3 小时一条），解析 `TMP` / `DEW` / `SLP`
   （均为「值,精度」两段式，`+9999` / `99999` 为缺测哨兵）；
2. 由气温与露点用 Magnus 公式反算相对湿度（站点观测没有直接的 RH 字段）；
3. 与 POWER 逐时再分析按 **UTC 时间戳**内连接；
4. 给出气温、相对湿度、气压三者的相关系数、偏差与 RMSE，落盘
   `code/results/isd_vs_power.csv` + `.json`。

**口径声明（写进材料时必须带上）**

POWER 是**再分析产品而非站点观测**，ISD 是**站点观测**。两者在敦煌的站点距离约 8 km
（POWER 取 40.04N/94.81E，ISD 站 40.15N/94.683E）。本核对只回答「再分析的室外驱动在
统计上是否与真实站点观测一致」，**不构成对窟内标签真实性的任何背书**。

用法：``python code/experiments/check_isd_outdoor.py``
"""

from __future__ import annotations

import json
import csv
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]          # code/
RESULTS = ROOT / "results"
ISD_DIR = ROOT / "data" / "raw" / "isd"
POWER_CSV = ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv"

MISSING = {9999, 99999, -9999}


def _parse_isd_scaled(raw: object, scale: float) -> float:
    """解析 ISD 的「值,精度」字段。返回 NaN 表示缺测。"""
    if not isinstance(raw, str):
        return np.nan
    head = raw.split(",")[0].strip()
    if not head or head in {"", "+9999", "9999", "99999", "+99999"}:
        return np.nan
    try:
        v = int(head)
    except ValueError:
        return np.nan
    if v in MISSING:
        return np.nan
    return v / scale


def _rh_from_t_td(t_c: np.ndarray, td_c: np.ndarray) -> np.ndarray:
    """Magnus 公式：由气温与露点算相对湿度（%）。"""
    def esat(t: np.ndarray) -> np.ndarray:
        return 6.112 * np.exp(17.67 * t / (t + 243.5))      # hPa

    return np.clip(esat(td_c) / esat(t_c) * 100.0, 0.0, 100.0)


def _read_isd_file(path: Path) -> list[tuple]:
    """逐行解析 ISD CSV。

    ISD 的 `REM` 自由文本字段偶尔含**不配对的引号**，整文件交给 `pd.read_csv`
    会在文件尾报 `EOF inside string`。由于每条记录恰好占一行，这里改为**逐行**解析：
    引号个数为奇数的行（就是坏行）直接跳过。这些行只影响 REM/字段对齐，
    与我们要用的 `TMP` / `DEW` / `SLP` 无关。
    """
    rows = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        header = None
        for line in fh:
            if line.count('"') % 2:
                continue
            rec = next(csv.reader([line]))
            if header is None:
                header = rec
                idx = {c: i for i, c in enumerate(header)}
                continue
            if len(rec) < len(header):
                continue
            rows.append((rec[idx["DATE"]], rec[idx["TMP"]], rec[idx["DEW"]], rec[idx["SLP"]]))
    return rows


def load_isd() -> pd.DataFrame:
    files = sorted(ISD_DIR.glob("isd_dh_*.csv"))
    if not files:
        raise SystemExit(
            f"未找到 ISD 原始文件：{ISD_DIR}/isd_dh_*.csv\n"
            "\n"
            "本目录不在版本库内（`.gitignore` 忽略了 code/data/）。请自行下载：\n"
            "  for /L %Y in (2015,1,2023) do curl -o isd_dh_%Y.csv "
            "https://www.ncei.noaa.gov/data/global-hourly/access/%Y/52418099999.csv\n"
            "（敦煌站 USAF 524180 / WBAN 99999，2015–2023 共 9 个文件，"
            "合计约 30 MB；该站 2023-04-28 后停报）\n"
            f"下载后放进：{ISD_DIR}/ 并改名为 isd_dh_<年份>.csv"
        )
    records = []
    for f in files:
        records.extend(_read_isd_file(f))
    isd = pd.DataFrame(records, columns=["DATE", "TMP", "DEW", "SLP"])
    isd["time_utc"] = pd.to_datetime(isd["DATE"], errors="coerce")
    isd["T_isd"] = isd["TMP"].map(lambda x: _parse_isd_scaled(x, 10.0))
    isd["Td_isd"] = isd["DEW"].map(lambda x: _parse_isd_scaled(x, 10.0))
    isd["P_isd"] = isd["SLP"].map(lambda x: _parse_isd_scaled(x, 10.0))   # hPa
    isd = isd.dropna(subset=["time_utc"]).sort_values("time_utc")
    isd["RH_isd"] = _rh_from_t_td(isd["T_isd"].to_numpy(float), isd["Td_isd"].to_numpy(float))
    isd.loc[isd["T_isd"].isna() | isd["Td_isd"].isna(), "RH_isd"] = np.nan
    return isd[["time_utc", "T_isd", "Td_isd", "P_isd", "RH_isd"]]


def load_power() -> pd.DataFrame:
    pw = pd.read_csv(POWER_CSV)
    tcol = "time_utc" if "time_utc" in pw.columns else pw.columns[0]
    pw["time_utc"] = pd.to_datetime(pw[tcol], errors="coerce", utc=True)
    pw = pw.dropna(subset=["time_utc"])
    if getattr(pw["time_utc"].dt, "tz", None) is not None:
        pw["time_utc"] = pw["time_utc"].dt.tz_convert("UTC").dt.tz_localize(None)
    out = pd.DataFrame({"time_utc": pw["time_utc"]})
    out["T_pw"] = pw["T2M"] if "T2M" in pw.columns else np.nan
    out["RH_pw"] = pw["RH2M"] if "RH2M" in pw.columns else np.nan
    # ⚠️ 单位与变量选择：POWER 的气压是 **kPa**，且 `PS` 是模式地形面上的气压
    # （均值 835.3 hPa），而 `PSC` 才是订正到窟址高程 1140 m 的站压（均值 886.9 hPa，
    # 与标准大气在 1140 m 的 883.0 hPa 吻合）。ISD 只有海平面气压 `SLP`，
    # 因此这里取 `PSC` 并把 ISD 的 SLP 按下式还原到 1140 m 站压后再比较。
    out["P_pw"] = (pw["PSC"] * 10.0) if "PSC" in pw.columns else np.nan
    return out


def slp_to_station(slp_hpa: np.ndarray, t_c: np.ndarray, height_m: float = 1140.0) -> np.ndarray:
    """海平面气压 → 站压（标准大气温度递减率 0.0065 K/m）。"""
    t_k = t_c + 273.15
    return slp_hpa * (1.0 - (0.0065 * height_m) / (t_k + 0.0065 * height_m)) ** 5.257


def _stats(a: pd.Series, b: pd.Series) -> dict:
    m = a.notna() & b.notna()
    if m.sum() < 10:
        return {"n": int(m.sum()), "r": np.nan, "bias": np.nan, "rmse": np.nan, "mae": np.nan}
    x = a[m].to_numpy(float)
    y = b[m].to_numpy(float)
    d = x - y
    return {
        "n": int(m.sum()),
        "r": float(np.corrcoef(x, y)[0, 1]),
        "bias": float(d.mean()),
        "rmse": float(np.sqrt((d ** 2).mean())),
        "mae": float(np.abs(d).mean()),
    }


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    isd = load_isd()
    pw = load_power()

    # ISD 的整点时间戳可能与 POWER 的整点不完全对齐，用最近邻 30 min 内匹配
    merged = pd.merge_asof(
        isd.sort_values("time_utc"),
        pw.sort_values("time_utc"),
        on="time_utc",
        direction="nearest",
        tolerance=pd.Timedelta("30min"),
    ).dropna(subset=["T_pw"])
    merged["P_st_isd"] = slp_to_station(
        merged["P_isd"].to_numpy(float), merged["T_isd"].to_numpy(float)
    )

    rows = [
        {"var": "T2M (°C)", "isd_col": "T_isd", "pw_col": "T_pw"},
        {"var": "RH2M (%)", "isd_col": "RH_isd", "pw_col": "RH_pw"},
        {"var": "站压 @1140 m (hPa)", "isd_col": "P_st_isd", "pw_col": "P_pw"},
    ]
    records = []
    for r in rows:
        s = _stats(merged[r["isd_col"]], merged[r["pw_col"]])
        records.append({"variable": r["var"], **s})
    out = pd.DataFrame(records)

    print("=" * 72)
    print("ISD 敦煌站观测 vs NASA POWER 再分析（外场驱动真实性交叉核对）")
    print("=" * 72)
    print(f"ISD 记录数           : {len(isd)}")
    print(f"ISD 时间跨度         : {isd['time_utc'].min()} → {isd['time_utc'].max()}")
    print(f"与 POWER 匹配上的样本: {len(merged)}")
    print(f"匹配时段             : {merged['time_utc'].min()} → {merged['time_utc'].max()}")
    print()
    print(out.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print()
    print("口径：POWER 为再分析产品（非站点观测），ISD 为站点观测，站距约 8 km。")
    print("      本核对只支持「再分析驱动在统计上与真实站点观测一致」，")
    print("      **不构成对窟内标签真实性的任何背书**（窟内序列是物理代理合成标签）。")

    out.to_csv(RESULTS / "isd_vs_power.csv", index=False, encoding="utf-8")
    summary = {
        "n_isd": int(len(isd)),
        "isd_start": str(isd["time_utc"].min()),
        "isd_end": str(isd["time_utc"].max()),
        "n_matched": int(len(merged)),
        "matched_start": str(merged["time_utc"].min()),
        "matched_end": str(merged["time_utc"].max()),
        "stats": records,
        "note": "POWER 是再分析产品；本核对不支持窟内标签的真实性。",
    }
    (RESULTS / "isd_vs_power.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n已落盘：{RESULTS / 'isd_vs_power.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
