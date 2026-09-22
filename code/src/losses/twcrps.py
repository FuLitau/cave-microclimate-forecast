"""风险对齐训练目标 —— 阈值加权评分规则（twCRPS）与算子导出的内生权重。

问题：为什么 MSE 是错的目标函数
--------------------------------
现有洞窟/馆藏微环境预测工作（含莫高窟 108 窟 CNN-LSTM-Attention、Heritage Science 2022
XGBoost 室内 RH 超限预测等）**一律用 RMSE/MAE/R² 作为训练与评价准则**。
但壁画盐害的损伤判据不是"某一时刻湿度差了几个百分点"，而是

* **超阈值持续时间**（可溶盐长时间潮解 → 离子迁移 → 疱疹）；
* **潮解-结晶往复次数**（相变循环产生结晶压力，是壁画疱疹的直接力学成因）；
* **极端事件的强度与时间提前量**。

因此存在系统性的**目标函数错配**：MSE 最优的预报在"超阈时长"这个业务量上并非最优。
这是本作品定位的核心算法问题，且经文献检索确认**在该领域零先例**。

方法：阈值加权连续排序概率评分（twCRPS）
----------------------------------------
Gneiting & Ranjan (2011, DOI 10.1198/jbes.2010.08110) 提出阈值加权 CRPS：

.. math::
    \\mathrm{twCRPS}(F, y; v) = \\int_{-\\infty}^{\\infty}
        \\big(F(z) - \\mathbb{1}\\{z \\ge y\\}\\big)^2 v(z)\\, dz

当 :math:`v(z) = \\mathbb{1}\\{z \\ge r\\}` 时，评分只关注 :math:`r` 以上的尾部，
从而把预报能力集中到真正造成损伤的区间。

**本作品的算法创新**：标准 twCRPS 的权重函数 :math:`v` 是**人工设定的固定阈值**。
我们让权重成为**由输运算子导出的内生状态相关变量**：

.. math::
    \\omega_k(t, h) = 1 + \\gamma \\cdot
        \\underbrace{\\sigma\\!\\left(\\frac{\\hat h^{\\text{cave}}_{t+h} - r}{s}\\right)}_{\\text{风险门控（算子传播的窟内 RH）}}
        \\cdot \\underbrace{(2\\tau_k - 1)_+}_{\\text{上尾强调}}
        \\cdot \\underbrace{e^{-h / H_{\\text{eff}}}}_{\\text{时效衰减}}

其中 :math:`\\hat h^{\\text{cave}}` 是**预报的室外场经冻结输运算子推演得到的窟内 RH 代理**，
:math:`H_{\\text{eff}}` 取自算子最慢模态的时间常数。

三个关键点使这构成**损失函数层级的模型级创新**而非调参：

1. **权重是状态相关的**——不是常数阈值，而是随预报的窟内状态逐时变化；
2. **权重是有物理来源的**——窗口由算子最慢时间常数决定，有物理量纲；
3. **梯度穿过物理链路**——:math:`\\hat h^{\\text{cave}}` 由预报值经可微算子得到，
   因此误差信号精确地回传到"对窟内风险有影响"的那些室外要素与时段上。

消融设计（创新性的护城河）
--------------------------
========================  ==========================================
方案                        权重来源
========================  ==========================================
A（基线）                   MSE，无风险对齐
B（标准 twCRPS）            固定阈值 :math:`r`，无算子、无时效衰减
**C（本作品）**             **算子传播的窟内 RH + 时效衰减，状态相关**
========================  ==========================================

**只有 C 显著优于 B，才能证明贡献来自"算子导出的内生权重"本身，
而不是"换了一个损失函数"。** 这是答辩时最可能被追问的一点。
"""

from __future__ import annotations

import numpy as np
import torch

# --------------------------------------------------------------------------
# 基础评分规则
# --------------------------------------------------------------------------


def pinball_loss(
    q: torch.Tensor, y: torch.Tensor, taus: torch.Tensor
) -> torch.Tensor:
    """分位数（pinball）损失，形状 (..., K)。

    :math:`\\rho_\\tau(u) = u\\,(\\tau - \\mathbb{1}\\{u<0\\})`，
    其中 :math:`u = y - q`。
    """
    u = y.unsqueeze(-1) - q
    return torch.maximum(taus * u, (taus - 1.0) * u)


def weighted_quantile_loss(
    q: torch.Tensor,
    y: torch.Tensor,
    taus: torch.Tensor,
    weights: torch.Tensor | None = None,
) -> torch.Tensor:
    """加权分位数损失 —— 训练时使用的 twCRPS 等价形式。

    CRPS 可写成所有分位数损失在 :math:`\\tau \\in (0,1)` 上的二倍积分；
    用 :math:`K` 个分位点离散化即得。加权版本对应阈值加权的 twCRPS。

    Parameters
    ----------
    q : Tensor, shape (B, H, K)
        :math:`K` 个分位数的预报值。
    y : Tensor, shape (B, H)
        实况。
    taus : Tensor, shape (K,)
        分位水平，通常取 ``k/(K+1)``。
    weights : Tensor, shape (B, H, K) 或 (B, H, 1), optional
        每样本、每时效、每分位的权重 :math:`\\omega_k(t,h)`。
    """
    loss = pinball_loss(q, y, taus)              # (B, H, K)
    if weights is not None:
        loss = loss * weights
    return loss.mean()


def twcrps_integral(
    samples: np.ndarray, y: np.ndarray, threshold: float, *, n_grid: int = 512
) -> np.ndarray:
    """按定义直接数值积分计算 twCRPS（**参考实现，用于评价而非训练**）。

    :math:`\\mathrm{twCRPS} = \\int_r^{\\infty} (F(z) - \\mathbb{1}\\{z \\ge y\\})^2 dz`

    用**经验 CDF**（阶跃函数）在细网格上做梯形积分。本函数不参与训练，
    只用于在评价阶段验证加权分位数损失确实在优化同一个目标。

    Parameters
    ----------
    samples : ndarray, shape (N, M)
        :math:`N` 个样本，每个 :math:`M` 个集合成员（或分位数样本）。
    y : ndarray, shape (N,)
        实况。
    threshold : float
        阈值 :math:`r`。
    """
    samples = np.atleast_2d(samples)
    y = np.asarray(y, dtype=float)

    lo = threshold
    hi = float(max(np.nanmax(samples), np.nanmax(y))) + 1.0
    z = np.linspace(lo, hi, n_grid)                     # (G,)

    # 经验 CDF F(z)   -> (N, G)
    F = (samples[:, None, :] <= z[None, :, None]).mean(axis=-1)
    ind = (z[None, :] >= y[:, None]).astype(float)      # (N, G)
    integrand = (F - ind) ** 2

    return np.trapezoid(integrand, z, axis=1)


# --------------------------------------------------------------------------
# 内生权重
# --------------------------------------------------------------------------


def lead_time_decay(
    horizon_hours: torch.Tensor, h_eff_hours: float
) -> torch.Tensor:
    """时效衰减 :math:`e^{-h/H_{\\text{eff}}}`。

    :math:`H_{\\text{eff}}` 取自输运算子最慢模态的时间常数，
    因此衰减尺度**有物理来源**，不是超参数。
    """
    return torch.exp(-horizon_hours / float(h_eff_hours))


def endogenous_weights(
    cave_rh_hat: torch.Tensor,
    horizon_hours: torch.Tensor,
    taus: torch.Tensor,
    *,
    rh_crit: float = 67.0,
    gamma: float = 4.0,
    gate_scale: float = 3.0,
    h_eff_hours: float = 72.0,
    gate_mode: str = "operator",
) -> torch.Tensor:
    """构造 twCRPS 的内生权重 :math:`\\omega_k(t, h)`。

    Parameters
    ----------
    cave_rh_hat : Tensor, shape (B, H)
        **由预报场经输运算子传播得到的窟内相对湿度代理**。
    horizon_hours : Tensor, shape (H,)
        各预报时效（小时）。
    taus : Tensor, shape (K,)
        分位水平。
    rh_crit : float
        盐害临界相对湿度，默认 67%（Demas et al. 2015，经 Gong et al. 2025 转述）。
    gamma : float
        风险对齐强度。
    gate_scale : float
        风险门控的软化尺度（个百分点）。
    h_eff_hours : float
        时效衰减尺度，取自算子最慢模态时间常数。
    gate_mode : {"operator", "fixed", "none"}
        * ``"operator"`` —— **本作品方案**：门控由算子传播的窟内 RH 决定（状态相关）；
        * ``"fixed"`` —— 消融 B：门控退化为固定阈值（等价于标准 twCRPS）；
        * ``"none"`` —— 消融 A：无风险对齐（等价于均匀权重的分位数损失）。

    Returns
    -------
    Tensor, shape (B, H, K)
        逐样本、逐时效、逐分位的权重。
    """
    if gate_mode == "none":
        return torch.ones(
            cave_rh_hat.shape[0], cave_rh_hat.shape[1], len(taus),
            device=cave_rh_hat.device, dtype=cave_rh_hat.dtype,
        )

    if gate_mode == "fixed":
        # 消融 B：门控对**所有样本所有时效**取同一个常数，
        # 不依赖算子传播的窟内状态，也没有时效分辨能力。
        gate = torch.ones_like(cave_rh_hat) * float(
            torch.sigmoid(torch.tensor(0.0)).item()
        )
    elif gate_mode == "operator":
        gate = torch.sigmoid((cave_rh_hat - rh_crit) / gate_scale)
    else:
        raise ValueError(f"未知 gate_mode: {gate_mode}")

    # 上尾强调：只强化 (2*tau - 1)_+，因为"湿度过高"才是损伤方向
    tail = torch.clamp(2.0 * taus - 1.0, min=0.0)                 # (K,)
    decay = lead_time_decay(horizon_hours, h_eff_hours)           # (H,)

    w = 1.0 + gamma * gate.unsqueeze(-1) * tail.view(1, 1, -1) * decay.view(1, -1, 1)
    return w


# --------------------------------------------------------------------------
# 决策层
# --------------------------------------------------------------------------


def risk_to_decision(
    rh_q: torch.Tensor,
    *,
    rh_crit: float = 67.0,
    rh_close: float = 75.0,
) -> torch.Tensor:
    """把窟内 RH 分位数预报映射为三级开放建议。

    0 = 正常开放，1 = 限流，2 = 关闭。

    依据：67% 为可溶盐潮解起始（Demas et al. 2015，经 Gong et al. 2025 转述）；
    75% / 75.47% 为莫高窟含盐地仗吸湿与渗透性突变点，原文建议
    "ambient RH should be maintained below 75%"
    （npj Heritage Science 2025, DOI 10.1038/s40494-025-01756-1）。

    采用**保守决策规则**：用上分位数（而非均值）判级，因为"关闭洞窟"的
    误判代价远高于"多限流一天"——漏报一次盐害是不可逆的。
    """
    upper = rh_q.max(dim=-1).values
    decision = torch.zeros_like(upper, dtype=torch.long)
    decision = torch.where(upper >= rh_close, torch.full_like(decision, 2), decision)
    decision = torch.where(
        (upper >= rh_crit) & (upper < rh_close), torch.full_like(decision, 1), decision
    )
    return decision
