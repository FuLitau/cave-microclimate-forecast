"""石窟微气候风险预报与决策支持看板（Flask + ECharts）。

设计要点
--------
* **前端只做展示，不做计算。** 所有数值来自 `results/` 下已落盘、可审计的结果文件，
  保证"界面看到的 = 实验算出的"，不会出现前端自己算一套的情况。
* **在线 / 离线双模式**：所有数据来自本地文件，**无任何外部网络依赖**，
  断网也能完整运行（面向野外台站与应急场景）。
* **诚实标注**：窟内序列一律标注为 `physics-derived synthetic`，
  页脚固定声明窟内无公开实测数据。界面绝不把合成标签表述为实测。

启动
----
    python src/web/app.py
默认 http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "results"
INTERIM = ROOT / "data" / "interim"

app = Flask(__name__)

#: 三级阈值（逐级独立出处，见 docs/02_数据集方案.md §3.5）
THRESHOLDS = {"warn": 62.0, "crit": 67.0, "close": 75.0}

#: 三级决策建议（0 正常 / 1 限流 / 2 关闭）
ADVICE = ["正常开放", "限流（控制人数与停留时长）", "关闭高危洞窟"]


# --------------------------------------------------------------------------
# 数据加载（带缓存，全部来自本地文件）
# --------------------------------------------------------------------------


def _read_csv(path: Path, **kw) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kw)


@lru_cache(maxsize=1)
def load_stats() -> dict:
    p = RESULTS / "demo_stats.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@lru_cache(maxsize=1)
def load_forecast() -> pd.DataFrame:
    return _read_csv(RESULTS / "demo_forecast.csv")


@lru_cache(maxsize=1)
def load_history() -> pd.DataFrame:
    df = _read_csv(RESULTS / "demo_history.csv")
    if not df.empty:
        # demo_history.csv 的时间列带 UTC 偏移（`2021-12-31 01:00:00+00:00`）。
        # 必须显式归一化为 **naive UTC**，否则 `load_history()` 出来的是
        # `datetime64[ns, UTC]`，与 /api/history 里 naive 的 `pd.Timestamp(start)`
        # 比较会抛 `TypeError: Invalid comparison between dtype=datetime64[ns, UTC]
        # and Timestamp` → 该接口 HTTP 500，回放页开箱即坏。
        df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)
    return df


@lru_cache(maxsize=1)
def load_accuracy() -> pd.DataFrame:
    return _read_csv(RESULTS / "derisk02_accuracy.csv")


@lru_cache(maxsize=1)
def load_events() -> pd.DataFrame:
    return _read_csv(RESULTS / "derisk02_events.csv")


@lru_cache(maxsize=1)
def load_duration() -> pd.DataFrame:
    return _read_csv(RESULTS / "derisk02_duration.csv")


@lru_cache(maxsize=1)
def load_calibration() -> pd.DataFrame:
    return _read_csv(RESULTS / "calib_cave_params.csv")


@lru_cache(maxsize=1)
def load_crosscave() -> pd.DataFrame:
    return _read_csv(RESULTS / "validate_crosscave.csv")


@lru_cache(maxsize=1)
def load_abc() -> pd.DataFrame:
    return _read_csv(RESULTS / "exp03_abc_ablation.csv")


# --------------------------------------------------------------------------
# 页面
# --------------------------------------------------------------------------


@app.route("/")
@app.route("/overview")
def overview():
    return render_template("overview.html", thresholds=THRESHOLDS,
                           stats=load_stats(), active="overview")


@app.route("/comparison")
def comparison():
    return render_template("comparison.html", active="comparison")


@app.route("/validation")
def validation():
    return render_template("validation.html", active="validation")


@app.route("/replay")
def replay():
    return render_template("replay.html", thresholds=THRESHOLDS, active="replay")


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


@app.get("/api/stats")
def api_stats():
    return jsonify(load_stats())


@app.get("/api/forecast")
def api_forecast():
    """24–72 h 窟内 RH 预报（按场景分组）。"""
    df = load_forecast()
    if df.empty:
        return jsonify({"scenarios": [], "thresholds": THRESHOLDS})
    out = []
    for name, g in df.groupby("scenario", sort=False):
        g = g.sort_values("step_h")
        # 预警系统应报告**整个预报窗口内的最高风险**，而不是终点时刻的瞬时值
        lv = int(g["level"].max())
        # 天真口径（直接拿物理阈值 62/67/75 比预报值）作为对照同时给出
        lv_raw = int(g["level_raw"].max()) if "level_raw" in g.columns else 0
        row = {
            "scenario": name,
            "origin": g["origin"].iloc[0],
            "step_h": g["step_h"].tolist(),
            "time": g["time"].tolist(),
            "RH_pred": g["RH_pred"].tolist(),
            "RH_true": g["RH_true"].tolist(),
            "level": g["level"].tolist(),
            "max_level": lv,
            "advice": ADVICE[lv],
            "peak_RH_pred": round(float(g["RH_pred"].max()), 2),
            "peak_RH_true": round(float(g["RH_true"].max()), 2),
            # 首次达到限流级别的提前量（小时）；未触发则为 None
            "lead_time_h": (int(g.loc[g["level"] >= 1, "step_h"].iloc[0])
                            if (g["level"] >= 1).any() else None),
            "T_out": g["T_out"].tolist(),
            "RH_out": g["RH_out"].tolist(),
        }
        # ---- 读出层对照与标定口径（指标化演示的一部分，非装饰） ----
        for col, key in (("RH_pred_lin", "RH_pred_lin"), ("RH_pred_tau90", "RH_pred_tau90"),
                         ("level_raw", "level_raw")):
            if col in g.columns:
                row[key] = g[col].tolist()
        if "RH_pred_lin" in g.columns:
            row["peak_RH_pred_lin"] = round(float(g["RH_pred_lin"].max()), 2)
        if "level_raw" in g.columns:
            row["max_level_raw"] = lv_raw
            row["advice_raw"] = ADVICE[lv_raw]
        for col in ("cut_62", "cut_67", "cut_75"):
            if col in g.columns:
                row[col] = [round(float(v), 2) for v in g[col].tolist()]
        out.append(row)
    return jsonify({"scenarios": out, "thresholds": THRESHOLDS,
                    "readout": load_stats().get("readout", "linear-MSE"),
                    "calib_year": load_stats().get("calib_year")})


@app.get("/api/history")
def api_history():
    """离线回放：按时间范围返回历史序列（默认最近 30 天）。"""
    df = load_history()
    if df.empty:
        return jsonify({"time": []})
    start = request.args.get("start")
    end = request.args.get("end")
    if start:
        ts = pd.to_datetime(start, errors="coerce")
        if pd.notna(ts):
            df = df[df["time"] >= ts]
    if end:
        ts = pd.to_datetime(end, errors="coerce")
        if pd.notna(ts):
            df = df[df["time"] <= ts]
    if not start and not end:
        df = df.tail(24 * 30)
    # 抽样以降传输量（前端画图不需要逐时全量）
    step = max(1, len(df) // 2000)
    df = df.iloc[::step]
    return jsonify({
        "time": df["time"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
        "T_out": df["T_out"].tolist(), "RH_out": df["RH_out"].tolist(),
        "T_in": df["T_in"].tolist(), "RH_in": df["RH_in"].tolist(),
        "Q_m3h": df["Q_m3h"].tolist(),
        "n_total": int(len(df)), "step": int(step),
    })


@app.get("/api/comparison")
def api_comparison():
    """模型对比：逐点精度 + 事件指标（含验证段标定的决策阈值）。"""
    acc = load_accuracy()
    ev = load_events()
    dur = load_duration()
    if acc.empty:
        return jsonify({"accuracy": [], "events": []})
    a = acc.to_dict(orient="records")
    e = ev.to_dict(orient="records") if not ev.empty else []
    d = dur.to_dict(orient="records") if not dur.empty else []
    return jsonify({"accuracy": a, "events": e, "duration": d})


@app.get("/api/abc")
def api_abc():
    """A/B/C 消融：MSE vs 固定阈值 twCRPS vs 算子内生权重。"""
    df = load_abc()
    return jsonify([] if df.empty else df.to_dict(orient="records"))


@app.get("/api/validation")
def api_validation():
    """标定结果 + 跨窟外部效度验证。"""
    cal = load_calibration()
    cc = load_crosscave()
    out = {"calibration": [], "crosscave": []}
    if not cal.empty:
        # 只回传与文献目标相关的最优行，避免前端堆整张扫描表
        cols = [c for c in ["eta", "k_sorption", "wall_pore_rh", "depth_m",
                            "diurnal_ratio_open", "diurnal_ratio_closed",
                            "annual_range_ratio_T", "annual_range_ratio_RH",
                            "RH_in_mean", "score"] if c in cal.columns]
        out["calibration"] = cal.sort_values("score").head(5)[cols].to_dict(orient="records")
    if not cc.empty:
        out["crosscave"] = cc.to_dict(orient="records")
    return jsonify(out)


if __name__ == "__main__":
    print("石窟微气候风险预报看板  →  http://127.0.0.1:5000")
    print("数据源：results/ 下的本地结果文件（无外部网络依赖，支持离线运行）")
    app.run(host="127.0.0.1", port=5000, debug=False)
