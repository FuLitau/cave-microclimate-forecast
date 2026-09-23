"""下载 ICCP（以色列洞穴气候计划）数据集。

Zenodo 会以 403 "unusual traffic" 拦截无浏览器特征的请求，因此这里带上
完整的浏览器请求头，并先用 REST API 解析真实文件名与直链。

数据集：https://zenodo.org/records/17505739
内容：12 个岩溶洞穴逐小时气温 + 相对湿度，2019-2021，CC-BY-4.0
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

RECORD = "17505739"
API = f"https://zenodo.org/api/records/{RECORD}"
# 仓库根锚定：本文件在 <root>/tools/ 下，故 parents[1] 即仓库根。
# （曾用相对路径 Path("code/data/raw/iccp")，依赖 cwd —— 从 code/ 目录执行会
#  写进 code/code/data/raw/iccp，且退出码仍为 0，静默留下错位目录。）
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "code" / "data" / "raw" / "iccp"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    "Referer": f"https://zenodo.org/records/{RECORD}",
    "Connection": "keep-alive",
}


def _get(url: str, *, stream: bool = False, attempts: int = 6, timeout: int = 60):
    """带指数退避的重试请求 —— Zenodo 短时间内会重置连接。"""
    import time

    last: Exception | None = None
    for k in range(attempts):
        try:
            r = requests.get(url, headers=HEADERS, stream=stream, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                print(f"       HTTP {r.status_code}，退避重试 {k + 1}/{attempts}")
                r.close()
                time.sleep(5 * (k + 1))
                continue
            return r
        except Exception as exc:  # noqa: BLE001
            last = exc
            wait = 5 * (k + 1)
            print(f"       {type(exc).__name__}，{wait}s 后退避重试 {k + 1}/{attempts}")
            time.sleep(wait)
    if last:
        raise last
    raise RuntimeError("重试耗尽")


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) 解析元数据
    try:
        r = _get(API, timeout=45)
        print(f"[API] HTTP {r.status_code}  {len(r.content)} bytes")
        if r.status_code != 200:
            print(r.text[:400])
            return 1
        meta = r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[API] 失败: {exc}")
        return 1

    files = meta.get("files", [])
    print(f"记录标题: {meta.get('metadata', {}).get('title', '?')[:90]}")
    print(f"文件数: {len(files)}")
    for f in files:
        key = f.get("key")
        size = f.get("size", 0)
        print(f"  - {key}  {size / 1e6:.2f} MB")

    # 2) 下载
    failed: list[str] = []
    ok = 0
    for f in files:
        key = f.get("key")
        url = (f.get("links") or {}).get("self")
        if not url or (only and only not in key):
            continue
        dest = OUT / key
        if dest.exists() and dest.stat().st_size == f.get("size"):
            print(f"[跳过] {key} 已完整")
            ok += 1
            continue
        print(f"[下载] {key} <- {url}")
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            with _get(url, stream=True, timeout=180) as resp:
                print(f"       HTTP {resp.status_code}")
                if resp.status_code != 200:
                    print("       " + resp.text[:300])
                    failed.append(f"{key}: HTTP {resp.status_code}")
                    continue
                got = 0
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_content(1 << 20):
                        fh.write(chunk)
                        got += len(chunk)
            # 长度校验：requests 的 IncompleteRead 只在读取时抛出，
            # 若服务端提前断流且未抛异常，靠期望长度兜底。
            want = f.get("size") or 0
            if want and got != want:
                failed.append(f"{key}: 只有 {got} B / 期望 {want} B")
                print(f"       长度不符 {got} / {want}")
                continue
            tmp.replace(dest)
            ok += 1
            print(f"       完成 {got / 1e6:.2f} MB -> {dest}")
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{key}: {type(exc).__name__} {exc}")
            print(f"       失败: {exc}")
        finally:
            # 不留 .part 残档，避免下游误把半截文件当数据
            if tmp.exists() and not dest.exists():
                tmp.unlink(missing_ok=True)

    print(f"\n成功 {ok} 个 / 失败 {len(failed)} 个")
    for msg in failed:
        print(f"  ✗ {msg}")

    print("\n目录内容:")
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            print(f"  {p}  {p.stat().st_size / 1e6:.2f} MB")

    if failed:
        print("\n[FAIL] 存在未完成/长度不符的下载：请重跑本脚本。"
              "（旧版本在此情形下仍返回 0，会让调用方误以为数据就绪。）")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
