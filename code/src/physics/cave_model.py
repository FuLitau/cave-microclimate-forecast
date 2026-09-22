"""文献参数化的窟内热湿耦合模型 —— 生成窟内 T/RH 物理合成标签。

为什么需要这个模型
------------------
**莫高窟（及中国其他石窟、古墓）的窟内温湿度实测序列没有公开数据集。**
团队已检索 figshare / Zenodo / Scientific Data / ESSD / 国家青藏高原科学数据中心
(TPDC) / 甘肃省科学数据中心 / CNKI 数据可用性声明，均未发现可下载的窟内 T/RH 序列。
敦煌研究院自 1990 年代起确有长期窟内监测（Getty Conservation Institute 合作，
Campbell CR10，6 个洞窟），但数据从未公开。

因此本模块的作用是：**构造物理可解释、参数可追溯的窟内合成标签**，
并在所有产出物中显式标注为 ``physics-derived synthetic``，绝不表述为"实测"。

模型结构
--------
两个耦合子系统，分别对应两条被实测证据支持的物理通道：

1. **岩体导热通道（慢通道）**。洞窟开凿在崖体内部，窟壁与崖面之间存在厚度为
   ``pillar_depth`` 的岩体。崖面受外场气温与太阳辐射驱动，热量经一维导热传入
   窟壁。这条通道给出**强衰减 + 大滞后**（季节尺度滞后可达数十天），
   是洞窟"冬暖夏凉、季节滞后"的来源。

2. **通风平流通道（快通道）**。窟门开启时换气次数陡增（实测 9-13 /h 对 1.6 /h），
   外场空气近乎无滞后地直接进入洞窟。这条通道是洞窟对环境**快速响应**的来源。

**为什么必须两条都有**：若只有导热，按 α≈5e-7~1.2e-6 m²/s 计算，
数米厚岩体可使年周期振幅衰减到 1% 量级、滞后超过 8 个月，洞窟将几乎没有季节变化；
而莫高窟这类带窟门、有游客的旅游洞窟实测存在明显季节变化。故通风项是**必需**而非可选。
这一"纯导热无法解释"的论证本身也是方案中的物理洞察点。

由于两个子系统在**每种门状态内都是 LTI（线性时不变）**，本模块用矩阵指数
精确离散化（``scipy.linalg.expm``），按门开/关两种模式切换。
这样得到的是**解析精确解而非数值近似**，无条件稳定，且可以逐时步快速推进。

参数与出处
----------
所有物理参数集中在 :class:`CaveParams`，并在 :data:`PARAM_SOURCES` 中给出
文献 DOI / 取值区间 / 是否直接适用。**未取得一手文献支撑的参数一律标注为假设**。

重要声明
--------
- 本模型输出为 **scenario / synthetic labels**，不是观测。
- 窟体几何（体积、壁面积、岩体厚度）为**代表性假设**，未取得莫高窟逐窟实测几何。
- 岩体热扩散率 α 的一手文献取自**碳酸盐岩岩溶洞穴**（Domínguez-Villar et al. 2023,
  DOI 10.1016/j.ijthermalsci.2023.108282，α = 5.07e-7 ± 1.27e-7 m²/s）。
  莫高窟为**砾岩/砂岩**，故本模块默认取 α = 1.2e-6 m²/s 并做区间敏感性分析。
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.linalg import expm

# --------------------------------------------------------------------------
# 物理常数
# --------------------------------------------------------------------------

RHO_AIR = 1.2          # kg/m^3，窟内空气密度（约 15 degC, 88 kPa）
CP_AIR = 1005.0        # J/(kg*K)，定压比热
R_V = 461.5            # J/(kg*K)，水汽气体常数
P_ATM = 88_000.0       # Pa，敦煌海拔约 1140 m 的大气压

#: Magnus 公式系数（Alduchov & Eskridge 1996 推荐形式），e_sat 单位 Pa，T 单位 degC。
MAGNUS_A = 610.94
MAGNUS_B = 17.625
MAGNUS_C = 243.04


# --------------------------------------------------------------------------
# 参数
# --------------------------------------------------------------------------


@dataclass
class CaveParams:
    """窟体几何、岩体热物性与通风参数。

    几何默认值代表一个"中等规模旅游洞窟"的等效体：
    12 m x 8 m x 5 m。**这是假设，不是莫高窟实测几何。**
    """

    # --- 几何 ---
    # 取**已有实测通风数据的洞窟量级**（第 71 窟：面积约 18 m^2、体积约 67 m^3；
    # 第 45 窟 82.24 m^3；第 46 窟 70.40 m^3）。使用与标定数据同量级的洞窟，
    # 才能保证换气量参数在口径上自洽。
    # ⚠️ 莫高窟洞窟体积差异极大（大窟可达 1300 m^3 量级），本模型只代表
    # "中等规模旅游洞窟"，不得外推到大窟。
    length_m: float = 5.0
    width_m: float = 3.6
    height_m: float = 3.7          # 体积约 66.6 m^3

    # --- 岩体热物性 ---
    #: 热扩散率 m^2/s。默认 1.2e-6（砂岩/砾岩量级），
    #: 碳酸盐岩实测下界 5.07e-7（Domínguez-Villar et al. 2023）。
    alpha_m2_s: float = 1.2e-6
    rho_rock: float = 2400.0     # kg/m^3，砂岩/砾岩
    cp_rock: float = 900.0       # J/(kg*K)
    #: **崖面到窟壁的岩体厚度 m（立柱厚度）**。莫高窟洞窟之间留有岩柱，
    #: 典型数米量级。**假设值**，由文献报导的窟内外衰减/滞后规律标定，
    #: 并做 2-6 m 敏感性分析（见 experiments/calib_cave_params.py）。
    pillar_depth_m: float = 5.0
    n_rock_nodes: int = 40       # 导热链节点数

    # --- 窟壁面对流换热 ---
    #: 窟内空气与壁面的对流换热系数 W/(m^2*K)。自然对流典型 2-5。
    h_cave_wall: float = 3.0
    #: 崖面与外场空气的对流换热系数 W/(m^2*K)（受迫对流，风速较高）。
    h_cliff_air: float = 15.0
    #: 崖面太阳辐射吸收率（浅色砂砾岩，取 0.6）。
    absorptivity: float = 0.6
    #: **净辐射折减系数** —— 用于校正"未显式建模长波辐射冷却"带来的系统性偏暖。
    #:
    #: 本模型只把吸收的短波辐射计入崖面能量平衡，未建模夜间崖面向天空的长波辐射冷却，
    #: 因而会高估崖面平均温度。实测对照：Cave 87 的窟内月均温年均约 11.7 °C，
    #: 窟外约 10.9 °C，即**窟内仅比窟外高约 0.75 °C**；而取折减系数 1.0 时
    #: 本模型窟内年均温高达 15.3 °C（偏高约 4 °C）。
    #: 该系数按"窟内年均温 - 窟外年均温 ≈ +0.75 °C"这一实测约束标定。
    #: ⚠️ 这是对缺失物理过程的**等效补偿**，不是实测参数，须在报告中声明。
    cliff_net_radiation_factor: float = 0.25

    # --- 通风（关键实测参数）---
    # **改用体积流量 Q (m^3/h) 而非换气次数 ACH (1/h)。**
    # 理由：实测 ACH 只来自第 45/46 窟（V≈70-82 m^3），而 ACH = Q/V 强依赖洞窟体积，
    # 直接搬用到别的体积会错；体积流量 Q 才是可迁移量。
    #
    # 出处：Zhao et al. 2026, npj Heritage Science 2026（"Article in Press"，
    # 正文只在 PDF 中），DOI 10.1038/s40494-026-02955-0。
    #   * 示踪衰减法（Table 7，仅第 45/46 窟，开门）：
    #       45 窟 12.97/10.88/9.46/10.73 /h，V=82.24 m^3 -> Q≈905 m^3/h
    #       46 窟 13.61/13.20/10.92/8.90 /h，V=70.40 m^3 -> Q≈821 m^3/h
    #   * 关门（Table 7，仅第 45 窟一次）：1.59±0.03 /h，V=82.24 -> Q≈131 m^3/h
    # ⚠️ 摘要里的"开门 9-13 /h、关门 1.6 /h"**只代表第 45/46 窟**，不是全窟通用值。
    #    12 窟逐窟 ACH（Table 4，风速积分法，口径不同不可混用）跨度 0.59-43.85 /h。
    q_open_m3h: float = 860.0
    q_closed_m3h: float = 131.0
    #: 开放时段（当地时间小时，闭区间起、开区间止）。
    open_hour_start: int = 8
    open_hour_end: int = 18
    #: 强制全天闭窟（门始终关闭、无游客）。
    #: 用于复现文献的对照条件——Gong et al. 2025 的第 71 窟在 2020 年因疫情闭窟，
    #: 构成天然的"门开 / 门关"双状态实验，是标定**门态增益**的唯一直接实测约束。
    force_door_closed: bool = False
    #: **有效混合系数** :math:`\\eta` —— 参与主体空气热/湿交换的换气份额。
    #:
    #: 名义换气量取上文的实测 Q。作者明确指出其 AER 是**全窟体均值、会高估主室**
    #: （入口为动态区、主室为准静态区；主室中心/入口风速比 0.08-0.35，均值 0.17）。
    #: η 以该风速比为**量级锚点**，但最终取值由**实测日较差比**标定：
    #: 开门日窟内/窟外日较差比 = 0.276、闭窟日 = 0.043（Gong et al. 2025 Table 1）。
    #: 标定得 η = 0.30（约为风速比锚点的 1.8 倍——锚点只用于量级判断，
    #: 不作为等式约束）。敏感性见 results/calib_cave_params.csv。
    ventilation_mixing_efficiency: float = 0.30

    # --- 湿交换 ---
    #: 壁面/地仗层吸放湿的等效传质系数 m/s。
    #: 由窟内 RH 年均标定。量级与室内表面对流质传系数相当
    #: （h_m ≈ h_c/(rho*cp) ≈ 2.5e-3 m/s 为上界；多孔吸附面另有吸附阻力，故取更小值）。
    k_sorption_m_s: float = 8.0e-5
    #: **深部岩体孔隙特征相对湿度 %**。
    #: 由窟内 RH 年均标定。窟内水汽由"开门带入的窟外湿空气平流"与
    #: "壁面吸放湿"共同控制，二者相对强弱由 k_sorption 与 Q·η 之比决定。
    wall_pore_rh: float = 50.0
    #: 单个游客产湿速率 kg/h（静坐/缓行的呼吸与皮肤蒸发，约 40-60 g/h）。
    visitor_moisture_kg_h: float = 0.05
    #: **等效连续在窟人数**。这是按小时平均的等效值，不是瞬时人数。
    #:
    #: ⚠️ **已知未复现项（须在报告中声明）**：Gong et al. 2025 报告游客使窟内
    #: RH 峰值抬升约 +11 个百分点（常态日 34.6% -> 46%）。本模型在 67 m^3 洞窟内
    #: 用**连续**游客源无法复现该峰值——要复现需等效约 110 人同时在窟，物理上不可能。
    #: 合理解释是：该峰值是"约 30 人入窟 5-6 min"的**短时脉冲**（按 0.05 kg/h 估算，
    #: 一次 5.5 min 的 30 人团约带入 0.14 kg 水汽，足以造成 ~11 个百分点的瞬时抬升），
    #: 而本模型用小时步长的连续源，把它时间平均掉了。
    #: 另一条佐证：同文指出呼吸排汗湿量占比仅约 5%（且系转引 Demas），
    #: 与"11 个百分点峰值"只有在脉冲解释下才自洽。
    #: **本参数按窟内 RH 年均与日较差比标定，不追求复现脉冲峰值。**
    visitor_occupancy: float = 1.0
    #: 降雨期间崖体入渗增强的等效附加通风系数（倍率）。**假设值。**
    rain_infiltration_gain: float = 0.5

    # --- 数值 ---
    #: 时间步长（小时）。模型按小时推进。
    dt_hours: float = 1.0

    @property
    def volume_m3(self) -> float:
        return self.length_m * self.width_m * self.height_m

    @property
    def wall_area_m2(self) -> float:
        """窟内可交换表面积（四壁 + 顶 + 地）。"""
        l, w, h = self.length_m, self.width_m, self.height_m
        return 2 * (l * w) + 2 * (l + w) * h

    @property
    def thermal_diffusivity_rock(self) -> float:
        return self.alpha_m2_s

    @property
    def conductivity_rock(self) -> float:
        """由 α = k/(rho*cp) 反推导热系数，用于一致性检查。"""
        return self.alpha_m2_s * self.rho_rock * self.cp_rock


#: 参数出处表。供方案/论文附录直接引用。
PARAM_SOURCES: dict[str, dict[str, str]] = {
    "q_open_m3h / q_closed_m3h": {
        "value": "开门 860 / 关门 131 m^3/h（= 实测 ACH x 该窟体积）",
        "source": "Zhao et al. 2026, npj Heritage Science",
        "doi": "10.1038/s40494-026-02955-0",
        "note": "示踪衰减法实测 ACH：45 窟 12.97/10.88/9.46/10.73 /h x 82.24 m^3、"
                "46 窟 13.61/13.20/10.92/8.90 /h x 70.40 m^3 -> 约 860；"
                "关门 1.59 +/- 0.03 /h x 82.24 -> 约 131。"
                "建模用体积流量 Q 而非 ACH：ACH = Q/V 强依赖洞窟体积，"
                "而已有实测 ACH 只来自 70-82 m^3 小窟，Q 才是可迁移量。",
    },
    "pillar_depth_m": {
        "value": "5.0 m（取「波动基本消失」的深度量级）",
        "source": "林波等 2013（第 108 窟岩体内温度/湿度监测）",
        "doi": "",
        "note": "108 窟实测：温度衰减随深度加剧，大于 4.7 m 基本平稳；"
                "湿度约 2.5 m 达 100%、4.7 m 稳定 100%、波动基本消失。"
                "**原文未给出具体滞后时间/相位差**（如实记录，不作推断）。"
                "本参数取 5.0 m，与上述 4.7 m 同量级。"
                "期刊名与卷期待补（人工检索仅记录到页码 P89-91）。",
    },
    "alpha_m2_s": {
        "value": "5.07e-7 +/- 1.27e-7 m^2/s",
        "source": "Dominguez-Villar, Krklec & Sierro 2023, Int. J. Thermal Sciences 189:108282",
        "doi": "10.1016/j.ijthermalsci.2023.108282",
        "note": "碳酸盐岩岩溶洞穴反演；莫高窟为砾岩/砂岩，本模型改为 1.2e-6 并做区间敏感性",
    },
    "RH 盐害阈值": {
        "value": "67%（潮解起始）/ 75%、75.47%（吸湿突变）",
        "source": "Demas et al. 2015 (Springer, 转引自 Gong et al. 2025 npj HS 13:173); "
                  "npj Heritage Science 2025",
        "doi": "10.1007/978-3-319-09000-9 ; 10.1038/s40494-025-01756-1",
        "note": "初稿所用 62-65% 无文献出处，已弃用。"
                "62% 另有两条第三方独立出处：中国气象局《中国气象报》(2021-11-03)；"
                "陈海玲等莫高窟监测文献（原文表述为「超过激活盐害的临界值 62%」）。",
    },
    "窟内外 RH 相位滞后": {
        "value": ">=24 h 尺度相位差 pi/4（日尺度约 3 h）；降雨期近同相位",
        "source": "Gong et al. 2025, npj Heritage Science 13:173",
        "doi": "10.1038/s40494-025-01756-1",
        "note": "用于物理一致性检验",
    },
    "游客对窟内温湿度影响": {
        "value": "日最高温与日较差各 +1.4 degC；游客呼吸排汗约占湿量 5%",
        "source": "Gong et al. 2025 (npj HS 13:173); Demas et al. 2015",
        "doi": "10.1038/s40494-025-01756-1",
        "note": "本模型的游客产湿项按此量级标定",
    },
    "窟内水汽来源": {
        "value": "窟内存在净水汽输入，但水汽不经窟门进入，源头在东侧上层",
        "source": "周启友等 2018, 文物保护与考古科学 30(3):51-60",
        "doi": "",
        "note": "108 窟夏季实测。这是本模型「以门为唯一水汽通道」的**已知边界**："
                "在裂隙发育的洞窟中该假设不完整，已在方案局限表中声明。"
                "本模型的门通道是按 Gong et al. 2025 第 71 窟的门开/门关对照标定的，"
                "两者描述的是不同洞窟的不同通道，不可互相否定。",
    },
    "门开/门关对窟内 RH 日波动的影响": {
        "value": "2008 年 5 月关闭第 26 窟后其 RH 日较差月均值明显下降，"
                 "同时开放第 25 窟后其日较差显著上升",
        "source": "陈海玲等（敦煌研究院，莫高窟第 25/26/29/35 窟监测，2007-2009）",
        "doi": "",
        "note": "与第 71 窟 2020 年疫情闭窟是**两次完全独立的天然门开/门关对照**，"
                "共同支撑「通风换气是窟内湿度日波动主控」这一建模前提。"
                "同文 2007 年 5-10 月 RH 日较差月均值：第 26 窟 9.2-14.2%、"
                "第 29 窟 11.8-15.6%（开放），第 25 窟 4.1-6.8%、第 35 窟 2.1-3.9%"
                "（低强度/关闭）——开放窟日波动约为关闭窟的 2-4 倍。"
                "期刊名与卷期待补。",
    },
}


# --------------------------------------------------------------------------
# 湿度换算工具
# --------------------------------------------------------------------------


def esat_pa(t_c: np.ndarray | float) -> np.ndarray | float:
    """饱和水汽压（Magnus 公式，Alduchov & Eskridge 1996），单位 Pa。"""
    return MAGNUS_A * np.exp(MAGNUS_B * np.asarray(t_c) / (MAGNUS_C + np.asarray(t_c)))


def rh_to_vapor_density(rh_pct, t_c):
    """相对湿度 (%) + 气温 (degC) -> 水汽密度 (kg/m^3)。"""
    e = np.clip(np.asarray(rh_pct), 0, 100) / 100.0 * esat_pa(t_c)
    return e / (R_V * (np.asarray(t_c) + 273.15))


def vapor_density_to_rh(rho_v, t_c):
    """水汽密度 (kg/m^3) + 气温 (degC) -> 相对湿度 (%)，截断到 [0, 100]。"""
    e = np.asarray(rho_v) * R_V * (np.asarray(t_c) + 273.15)
    return np.clip(e / esat_pa(t_c) * 100.0, 0.0, 100.0)


# --------------------------------------------------------------------------
# 主体模型
# --------------------------------------------------------------------------


@dataclass
class CaveModel:
    """窟内热湿耦合模型。

    Examples
    --------
    >>> model = CaveModel(CaveParams())
    >>> cave = model.simulate(outdoor_df)   # 需要列 T2M, RH2M, ALLSKY_SFC_SW_DWN
    >>> cave[["T_in", "RH_in"]].describe()
    """

    params: CaveParams = field(default_factory=CaveParams)

    # ---------------- 内部：构建并精确离散化 LTI 系统 ----------------

    def _build_thermal_system(self, q_m3h: float) -> tuple[np.ndarray, np.ndarray]:
        """构建温度子系统 ``dX/dt = A X + B u``，状态 ``X = [T_rock..., T_in]``。

        节点 0 位于**崖面**（外侧），节点 N-1 位于**窟壁内表面**（内侧），
        中间为厚度 ``pillar_depth_m`` 的岩体。崖面接受外场气温与太阳辐射，
        窟壁与窟内空气对流换热，窟内空气另与外界通风换气。

        Parameters
        ----------
        q_m3h : float
            该门态下的**体积通风流量** (m^3/h)。

        返回 (A, B)，其中输入 ``u = [T_out, SW_absorbed]``。
        """
        p = self.params
        n = p.n_rock_nodes
        depth = p.pillar_depth_m

        # --- 岩体导热链（控制体有限差分）---
        # 网格必须能分辨**日周期**的温度波，否则快变通道失真。
        # 日周期阻尼深度 delta_d = sqrt(2*alpha/omega_d)；
        # 取 delta_d/8 作为最小网格间距。
        omega_d = 2 * np.pi / 86400.0
        delta_daily = np.sqrt(2.0 * p.alpha_m2_s / omega_d)
        dz_min = min(0.02, delta_daily / 8.0)

        # 等比网格：n 个节点（节点 0 在崖面 z=0，节点 n-1 在窟壁 z=depth），
        # 共 n-1 个区间，区间厚度 dz_i = a * r^i。
        # 早期版本用固定 ratio=1.12，40 节点下首层薄至 0.63 mm，
        # 导致控制体热容过小、离散算子失去对角占优，矩阵指数离散化后发散。
        # 这里改为「给定最小网格、二分反解增长率」，从结构上杜绝该问题。
        n_int = n - 1
        lo, hi = 1.0 + 1e-9, 2.0
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            total = (dz_min * (mid**n_int - 1.0) / (mid - 1.0)
                     if abs(mid - 1.0) > 1e-12 else dz_min * n_int)
            if total < depth:
                lo = mid
            else:
                hi = mid
        r = 0.5 * (lo + hi)
        dz = dz_min * r ** np.arange(n_int, dtype=float)
        dz = dz * (depth / dz.sum())                 # 归一化，总厚恰为 depth

        k = p.conductivity_rock
        rho_cp = p.rho_rock * p.cp_rock

        # 节点控制体厚度：端点为半格（边界节点），内部为相邻区间各半。
        ctrl = np.empty(n)
        ctrl[0] = dz[0] / 2.0
        ctrl[-1] = dz[-1] / 2.0
        ctrl[1:-1] = (dz[:-1] + dz[1:]) / 2.0

        # **统一用总热容/总热导（W/K、J/K）**，与窟内空气节点、通风热导同量纲。
        # 早期版本岩体链用单位面积量（J/(m^2*K)、W/(m^2*K)），而空气节点用总量，
        # 导致窟壁节点相对窟内空气"响应快 392 倍"（壁面积），岩体丧失热锚定作用、
        # 窟内气温衰减特征消失。热交换面积取窟内可交换表面积。
        a_rock = p.wall_area_m2
        cond = k / dz * a_rock                       # W/K，相邻节点间总热导
        C_node = rho_cp * ctrl * a_rock              # J/K，节点总热容

        A = np.zeros((n + 1, n + 1))                 # 末位为窟内空气
        B = np.zeros((n + 1, 2))

        # 崖面 (i=0)：对外场对流 + 吸收太阳辐射 + 向岩体内部导热
        # 注意：对角项必须同时含对流与导热两个汇，否则该行行和为正、系统发散。
        A[0, 0] += (-p.h_cliff_air * a_rock - cond[0]) / C_node[0]
        A[0, 1] += cond[0] / C_node[0]
        B[0, 0] += p.h_cliff_air * a_rock / C_node[0]
        B[0, 1] += p.absorptivity * p.cliff_net_radiation_factor * a_rock / C_node[0]

        # 内部节点
        for i in range(1, n - 1):
            A[i, i - 1] += cond[i - 1] / C_node[i]
            A[i, i] += -(cond[i - 1] + cond[i]) / C_node[i]
            A[i, i + 1] += cond[i] / C_node[i]

        # 窟壁内表面 (i=n-1)：与窟内空气对流
        hA = p.h_cave_wall * a_rock                  # W/K
        A[n - 1, n - 2] += cond[-1] / C_node[n - 1]
        A[n - 1, n - 1] += -(cond[-1] + hA) / C_node[n - 1]
        A[n - 1, n] += hA / C_node[n - 1]

        # 窟内空气节点：与窟壁对流 + 与外场通风换气
        C_air = RHO_AIR * CP_AIR * p.volume_m3                 # J/K
        # 通风热导：Q [m^3/h] -> [m^3/s] -> 乘 rho*cp 得 W/K。
        # 早期版本把 ACH(1/h) 当成 1/s 用，通风热导虚高 3600 倍；
        # 现改用体积流量，单位链条为 Q/3600*eta*rho*cp，量纲清晰。
        vent = RHO_AIR * CP_AIR * (q_m3h * p.ventilation_mixing_efficiency / 3600.0)

        A[n, n - 1] += hA / C_air
        A[n, n] += -(hA + vent) / C_air
        B[n, 0] += vent / C_air

        return A, B

    def _discretize(self, A: np.ndarray, B: np.ndarray, dt_s: float):
        """用矩阵指数对 LTI 系统做**精确**离散化，得到 X_{k+1} = Ad X_k + Bd u_k。

        并断言连续算子稳定（谱横坐标 < 0）。若不满足，矩阵指数会溢出为 inf，
        症状是窟内温度变成 -inf 这种难以定位的数值污染。这里显式拦截，
        把静默的数值事故变成可读的报错。
        """
        abscissa = float(np.max(np.linalg.eigvals(A).real))
        if abscissa >= 0.0:
            raise RuntimeError(
                f"导热-通风耦合系统不稳定：谱横坐标 = {abscissa:.6g} >= 0。"
                f"请检查网格分辨率（n_rock_nodes / pillar_depth_m）与对流换热系数。"
            )
        # 若最慢与最快模态跨越过大，矩阵指数仍可能在大 dt 下损失精度，给出提示。
        tau_min_s = -1.0 / abscissa if abscissa < 0 else np.inf
        if dt_s > 200.0 * tau_min_s:
            warnings.warn(
                f"时间步长 {dt_s:.0f}s 远大于最快模态时间常数 {tau_min_s:.3g}s，"
                f"矩阵指数精度可能下降。",
                stacklevel=2,
            )

        m = A.shape[0]
        aug = np.zeros((m + B.shape[1], m + B.shape[1]))
        aug[:m, :m] = A
        aug[:m, m:] = B
        ed = expm(aug * dt_s)
        return ed[:m, :m], ed[:m, m:]

    # ---------------- 对外接口 ----------------

    def simulate(self, outdoor: pd.DataFrame) -> pd.DataFrame:
        """由外场气象序列推演窟内微环境。

        Parameters
        ----------
        outdoor : DataFrame
            索引为 UTC DatetimeIndex，需含列 ``T2M``(degC)、``RH2M``(%)、
            ``ALLSKY_SFC_SW_DWN``。可选 ``PRECTOTCORR``(mm/hr)、``WS10M``(m/s)。

        Returns
        -------
        DataFrame
            含 ``T_in``(degC)、``RH_in``(%)、``rho_v_in``、``T_wall``(窟壁温度)、
            ``ACH``、``T_out``、``RH_out`` 等列。
        """
        p = self.params
        dt_s = p.dt_hours * 3600.0

        t_out = outdoor["T2M"].to_numpy(dtype=float)
        rh_out = outdoor["RH2M"].to_numpy(dtype=float)
        sw = outdoor.get("ALLSKY_SFC_SW_DWN", pd.Series(0.0, index=outdoor.index))
        sw = sw.to_numpy(dtype=float)
        rain = outdoor.get("PRECTOTCORR", pd.Series(0.0, index=outdoor.index))
        rain = np.nan_to_num(rain.to_numpy(dtype=float), nan=0.0)

        # --- 门开 / 关两种通风模式 ---
        hours = outdoor.index.tz_convert("Asia/Shanghai").hour if outdoor.index.tz is not None \
            else outdoor.index.hour
        is_open = (hours >= p.open_hour_start) & (hours < p.open_hour_end)
        if p.force_door_closed:
            is_open = np.zeros_like(is_open, dtype=bool)

        # 通风模式：开门 / 关门两种体积流量；降雨期崖体入渗增强（等效附加换气）
        q = np.where(is_open, p.q_open_m3h, p.q_closed_m3h)
        q = q * (1.0 + p.rain_infiltration_gain * (rain > 0.0))
        # 等效换气次数仅用于输出与核对（ACH = Q/V）
        ach = q / p.volume_m3

        # 两种模式各离散化一次（LTI，精确）
        A_open, B_open = self._build_thermal_system(p.q_open_m3h)
        A_cl, B_cl = self._build_thermal_system(p.q_closed_m3h)
        Ad_open, Bd_open = self._discretize(A_open, B_open, dt_s)
        Ad_cl, Bd_cl = self._discretize(A_cl, B_cl, dt_s)

        n = p.n_rock_nodes
        X = np.zeros(n + 1)
        # 初值：岩体与窟内空气取前 30 天外场气温均值，避免瞬态
        warm = np.nanmean(t_out[: min(len(t_out), 24 * 30)])
        X[:] = warm

        # --- 水汽子系统 ---
        # 壁面吸放湿的等效容积传质系数 (1/s)
        k_wall = p.k_sorption_m_s * p.wall_area_m2 / p.volume_m3
        # 游客产湿 (kg/(m^3*s))，仅开放时段
        e_visitor = np.where(
            is_open,
            p.visitor_occupancy * p.visitor_moisture_kg_h / 3600.0 / p.volume_m3,
            0.0,
        )

        rho_v_in = rh_to_vapor_density(np.nanmean(rh_out[: min(len(rh_out), 240)]),
                                       float(warm))

        n_t = len(outdoor)
        out = np.empty((n_t, 7))
        # 预计算：深部岩体孔隙水汽密度由窟壁温度与特征孔隙 RH 决定（慢变边界）
        for t in range(n_t):
            Ad, Bd = (Ad_open, Bd_open) if is_open[t] else (Ad_cl, Bd_cl)
            u = np.array([0.0 if np.isnan(t_out[t]) else t_out[t],
                          0.0 if np.isnan(sw[t]) else sw[t]])
            X = Ad @ X + Bd @ u

            t_wall = X[n - 1]
            # 深部岩体孔隙水汽密度（与窟壁温度平衡）
            rho_v_wall = rh_to_vapor_density(p.wall_pore_rh, t_wall)
            rho_v_out = rh_to_vapor_density(0.0 if np.isnan(rh_out[t]) else rh_out[t],
                                            0.0 if np.isnan(t_out[t]) else t_out[t])

            # 合并线性弛豫：d(rho_v)/dt = ach_s*(rho_out - rho_v) + k_wall*(rho_wall - rho_v) + e_vis
            # 体积流量换成等效弛豫率：Q[m^3/h] * eta / 3600 / V[m^3] -> 1/s
            ach_s = q[t] * p.ventilation_mixing_efficiency / 3600.0 / p.volume_m3
            k_eff = ach_s + k_wall
            rho_eq = (ach_s * rho_v_out + k_wall * rho_v_wall + e_visitor[t]) / k_eff
            # 该小时内的**解析精确解**
            rho_v_in = rho_eq + (rho_v_in - rho_eq) * np.exp(-k_eff * dt_s)

            # --- 凝结汇 ---
            # 相对湿度不可能超过 100%：超出饱和的部分在壁面凝结析出。
            # 若不设此限，模型会给出 RH>100% 的非物理结果（早期版本 RH 触顶 100%），
            # 而凝结恰恰是洞窟维持高湿环境的重要机制，不能简单截断。
            t_air = X[n]
            rho_sat = esat_pa(t_air) / (R_V * (t_air + 273.15))
            condensate = 0.0
            if rho_v_in > rho_sat:
                condensate = (rho_v_in - rho_sat) * p.volume_m3 / dt_s   # kg/s
                rho_v_in = rho_sat

            out[t, 0] = t_air                        # T_in
            out[t, 1] = vapor_density_to_rh(rho_v_in, t_air)
            out[t, 2] = rho_v_in
            out[t, 3] = t_wall                       # T_wall
            out[t, 4] = ach[t]
            out[t, 5] = rho_v_wall
            out[t, 6] = condensate

        df = pd.DataFrame(
            out,
            index=outdoor.index,
            columns=["T_in", "RH_in", "rho_v_in", "T_wall", "ACH", "rho_v_wall",
                     "condensate_kg_s"],
        )
        df["Q_m3h"] = q
        df["T_out"] = t_out
        df["RH_out"] = rh_out
        return df

    def sensitivity(self, outdoor: pd.DataFrame,
                    alpha_grid=(5.07e-7, 8.0e-7, 1.2e-6, 1.5e-6),
                    depth_grid=(2.0, 3.0, 4.0, 6.0)) -> pd.DataFrame:
        """对两个**假设性最强**的参数做敏感性分析。

        岩体热扩散率 α 与立柱厚度 ``pillar_depth_m`` 都没有莫高窟实测支撑，
        必须报告取值区间对窟内微环境统计量的影响，否则结论不可辩护。
        """
        rows = []
        for a in alpha_grid:
            for d in depth_grid:
                prm = CaveParams(**{**self.params.__dict__,
                                    "alpha_m2_s": float(a), "pillar_depth_m": float(d)})
                sim = CaveModel(prm).simulate(outdoor)
                rows.append({
                    "alpha_m2_s": a,
                    "pillar_depth_m": d,
                    "T_in_mean": round(float(sim["T_in"].mean()), 2),
                    "T_in_std": round(float(sim["T_in"].std()), 2),
                    "T_in_min": round(float(sim["T_in"].min()), 2),
                    "T_in_max": round(float(sim["T_in"].max()), 2),
                    "RH_in_mean": round(float(sim["RH_in"].mean()), 2),
                    "RH_in_std": round(float(sim["RH_in"].std()), 2),
                    "RH_in_p95": round(float(sim["RH_in"].quantile(0.95)), 2),
                    "frac_RH_gt_67": round(float((sim["RH_in"] > 67).mean()), 4),
                    "frac_RH_gt_75": round(float((sim["RH_in"] > 75).mean()), 4),
                })
        return pd.DataFrame(rows)
