"""NASA POWER 逐小时气象数据抓取（莫高窟点位）。

数据来源
--------
NASA Prediction of Worldwide Energy Resources (POWER), Hourly API v2.10.2
https://power.larc.nasa.gov/api/temporal/hourly/point

底层为 MERRA-2 再分析 + POWER 偏差订正产品。**这不是站点观测**，
在方案与论文中必须表述为 "reanalysis"，不得称为 "观测真值"。

已实测确认的工程要点（踩过的坑）
--------------------------------
1. 逐小时接口历史起点为 2001-01-01，更早年份返回 HTTP 422。
2. 接口默认 ``time-standard=LST``（局地太阳时）。做机器学习必须显式指定
   ``UTC``，否则与中国本地时/观测序列存在 2 小时以上错位。
3. **格点海拔偏差与 PSC 字段（重要，且极易误判）**：POWER 返回的格点海拔为 1639.24 m，
   比莫高窟实际（约 1140 m）高约 500 m，故 ``PS`` 系统性偏低。

   必须传 ``site-elevation``——但**它不会修改 `PS`，而是额外返回一个 `PSC` 字段**
   （corrected station pressure）。实测对照（2024-01-01，莫高窟点位）：

   ==========================  ==========  ==========
   请求                         返回字段     数值
   ==========================  ==========  ==========
   不带 site-elevation           ``PS``      84.17 kPa
   带 site-elevation=1140       ``PS``      84.17 kPa（不变）
   带 site-elevation=1140       ``PSC``     89.62 kPa
   ==========================  ==========  ==========

   标准大气压公式在 1140 m 给出 88.36 kPa，与 ``PSC`` 吻合
   （全期均值 ``PSC`` = 88.69 kPa，``PS`` = 83.53 kPa，差 +5.16 kPa）。

   ⚠️ **只检查 `PS` 列会得出"site-elevation 无效"的错误结论**——本模块早期版本
   就犯过这个错。**气压应使用 `PSC`，不要用 `PS`。**
   报告中表述为"以 site-elevation 获取订正本站气压 PSC"，而非"已知偏差"。
   同时仍须注明：``PSC`` 是 POWER 内部订正产品，不是站点实测；莫高窟 25 km 内
   无同海拔实测气压真值可校验。
4. 缺失值填充标记为 ``-999.0``。
5. 单次请求参数上限 15 个。
6. PRECTOTCORR 是偏差订正降水产品。敦煌年降水仅约 25 mm，信噪比极低，
   **不应把"降水预测精度"作为核心评价指标**。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

# --------------------------------------------------------------------------
# 站点与请求配置
# --------------------------------------------------------------------------

#: 莫高窟（敦煌）中心点。经纬度取 0.1° 网格中心，与 POWER 的 MERRA-2 分辨率对齐。
SITE = {
    "name": "Mogao_Grottoes",
    "latitude": 40.04,
    "longitude": 94.81,
    # 莫高窟崖体实际海拔（m）。莫高窟位于大泉河下游砾岩崖壁上，约 1130-1150 m。
    "elevation_m": 1140,
}

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/hourly/point"

#: 请求参数（≤15 个）。覆盖热、湿、风、压、辐射五类驱动量。
#: 注意：``PS`` 是格点（约 1639 m）气压，**建模应使用 ``PSC``**
#: （传 site-elevation 后返回的订正本站气压），见模块文档第 3 条。
PARAMETERS = [
    "T2M",               # 2 m 气温 (degC)
    "T2MDEW",            # 2 m 露点温度 (degC)
    "RH2M",              # 2 m 相对湿度 (%)
    "PRECTOTCORR",       # 偏差订正降水 (mm/hr)
    "WS10M",             # 10 m 风速 (m/s)
    "WS2M",              # 2 m 风速 (m/s)
    "WD10M",             # 10 m 风向 (deg)
    "PS",                # 格点地表气压 (kPa) —— 仅作参考/对照
    "ALLSKY_SFC_SW_DWN", # 全天空短波下行辐射
]

#: 建模实际使用的气压字段。传了 site-elevation 后由服务端额外返回。
PRESSURE_VARIABLE = "PSC"

#: 逐小时接口最早可用日期。
EARLIEST_HOURLY = "20010101"

FILL_VALUE = -999.0


def build_url(start: str, end: str, parameters: list[str] | None = None) -> str:
    """构造 POWER hourly point 请求 URL。

    Parameters
    ----------
    start, end : str
        ``YYYYMMDD`` 格式的起止日期（含）。
    parameters : list[str], optional
        要素名列表，默认使用 :data:`PARAMETERS`。
    """
    params = parameters or PARAMETERS
    if len(params) > 15:
        raise ValueError(f"POWER 单次请求参数上限为 15 个，当前 {len(params)} 个")

    query = (
        f"parameters={','.join(params)}"
        f"&community=RE"
        f"&longitude={SITE['longitude']}"
        f"&latitude={SITE['latitude']}"
        f"&start={start}"
        f"&end={end}"
        f"&format=JSON"
        f"&time-standard=UTC"
        # 关键：修正格点海拔偏高导致的 PS 系统偏差
        f"&site-elevation={SITE['elevation_m']}"
    )
    return f"{ENDPOINT}?{query}"


def fetch_range(
    start: str,
    end: str,
    *,
    max_retries: int = 5,
    backoff_s: float = 2.0,
    sleep_s: float = 1.0,
) -> pd.DataFrame:
    """抓取指定日期区间的逐小时数据，返回以 UTC 时间为索引的 DataFrame。

    服务端未公布数值化的速率限制。这里采取保守策略：请求之间 sleep，
    失败按指数退避重试。
    """
    url = build_url(start, end)
    last_err: Exception | None = None

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            payload = resp.json()
            break
        except Exception as exc:  # noqa: BLE001 - 网络层需要兜住所有异常
            last_err = exc
            wait = backoff_s * (2**attempt)
            print(f"  [retry {attempt + 1}/{max_retries}] {exc} -> sleep {wait:.0f}s")
            time.sleep(wait)
    else:
        raise RuntimeError(f"POWER 抓取失败 {start}-{end}: {last_err}")

    time.sleep(sleep_s)

    # 实测确认的响应结构（API v2.10.2）：
    #   payload["parameters"]["T2M"] -> {"units": "C", "longname": "..."}   # 仅元数据！
    #   payload["properties"]["parameter"]["T2M"] -> {"2024010100": -6.81, ...}  # 真正的数据
    # 注意：服务端会额外附加 PSC（降水订正）等未请求的要素，解析时以返回内容为准。
    raw = payload.get("properties", {}).get("parameter", {})
    if not raw:
        raise RuntimeError(f"POWER 返回空 properties.parameter: {start}-{end}")

    df = pd.DataFrame(raw)
    # key 形如 "2024010100"（UTC 小时）
    df.index = pd.to_datetime(df.index, format="%Y%m%d%H", utc=True)
    df.index.name = "time_utc"

    # 填充值 -> NaN
    df = df.replace(FILL_VALUE, pd.NA).astype(float)
    return df.sort_index()


def fetch_yearly(
    start_year: int,
    end_year: int,
    cache_dir: str | Path,
    *,
    force: bool = False,
) -> pd.DataFrame:
    """按年抓取并缓存为 CSV，最后合并返回。

    按年切分有两个好处：单次请求体量可控；某一年失败时不必重跑全部年份。
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    for year in range(start_year, end_year + 1):
        cache_file = cache_dir / f"power_hourly_{SITE['name']}_{year}.csv"

        if cache_file.exists() and not force:
            print(f"[cache] {cache_file.name}")
            frames.append(pd.read_csv(cache_file, index_col=0, parse_dates=True))
            continue

        print(f"[fetch] {year} ...")
        df = fetch_range(f"{year}0101", f"{year}1231")
        df.to_csv(cache_file)
        print(f"        {len(df):,} rows, {df.shape[1]} vars -> {cache_file.name}")
        frames.append(df)

    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated(keep="first")]
    return out


def load_cached(cache_dir: str | Path) -> pd.DataFrame:
    """从缓存目录读取所有年份并合并。"""
    cache_dir = Path(cache_dir)
    files = sorted(cache_dir.glob(f"power_hourly_{SITE['name']}_*.csv"))
    if not files:
        raise FileNotFoundError(f"{cache_dir} 下没有 POWER 缓存文件")
    frames = [pd.read_csv(f, index_col=0, parse_dates=True) for f in files]
    return pd.concat(frames).sort_index().pipe(lambda d: d[~d.index.duplicated(keep="first")])


def basic_quality_report(df: pd.DataFrame) -> pd.DataFrame:
    """输出各要素的缺测率与基本统计量，用于数据质量说明。"""
    report = pd.DataFrame(
        {
            "n_total": len(df),
            "n_missing": df.isna().sum(),
            "missing_rate": df.isna().mean().round(4),
            "min": df.min().round(3),
            "mean": df.mean().round(3),
            "max": df.max().round(3),
        }
    )
    return report


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    cache = root / "data" / "raw" / "power"

    df = fetch_yearly(2001, 2025, cache)
    print(f"\n合并后: {df.shape[0]:,} 行 x {df.shape[1]} 要素")
    print(f"时间范围: {df.index.min()} -> {df.index.max()}")
    print("\n质量报告:")
    print(basic_quality_report(df).to_string())

    out = root / "data" / "interim" / "power_hourly_mogao_2001_2025.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out)
    print(f"\n已写出 {out}")

    meta = {"site": SITE, "parameters": PARAMETERS, "source": ENDPOINT,
            "time_standard": "UTC", "product": "MERRA-2 reanalysis + POWER bias correction"}
    (root / "data" / "interim" / "power_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
