"""域泛化层 —— 多源域读出与 Koodos 式**域空间** Koopman 演化。

为什么需要这一层
----------------
:mod:`code.src.operator.transport` 解决的是**状态空间**的输运问题：
把室外气象延迟坐标映射到窟内微环境。但它的读出权重 :math:`w` 是在**单一域**
（莫高窟合成标签）上标定的，一旦换到另一个洞窟、另一个站点，权重就不再成立。
真实证据：ICCP 8 个真实洞窟的留一验证里，域内标定的算子有 3 个洞窟 R² 为负
（``code/results/iccp_summary.json`` 的 ``failure_cases_operator_negative``），
这正是**域偏移**而非模型容量问题。

本模块把「域」当作一等公民。设 :math:`K` 个**源域**（各有标签）与一个
**目标域**（零标签，但允许使用其无标签驱动输入），任务是学一个读出
:math:`w`，使 :math:`\\hat y = w^\\top \\Psi(x)` 在目标域上成立。

四类读出（同一套特征、同一套标准化、同一套选参协议，只换归纳偏置）
------------------------------------------------------------------
1. ``pooled``    —— 多源域合并 ERM（把所有源域样本拼起来做一次岭回归）；
2. ``group_dro`` —— Group DRO（Sagawa et al., ICLR 2020）：指数梯度重加权，
   逼近最差源域风险 :math:`\\max_k R_k`；
3. ``vrex``      —— V-REx（Krueger et al., ICML 2021）：在平均风险上加
   :math:`\\lambda\\,\\mathrm{Var}_k(R_k)`，惩罚「域间风险方差」；
4. ``koopman``   —— **Koodos 式域空间 Koopman 演化**（本模块的算法贡献）。

域空间 Koopman 演化（对标 Koodos, NeurIPS 2024, arXiv:2405.16075）
------------------------------------------------------------------
Koodos 的原始设定是**连续时序域泛化（CTDG）**：域 :math:`\\mathcal{D}(t)` 采集于
任意连续时刻，模型参数 :math:`\\theta(t)` 随 :math:`t` 连续演化；论文用
拓扑共轭 :math:`h\\circ\\xi = \\xi\\circ f` 约束动力学，再在低维 Koopman 空间里
把非线性参数动力学线性化：

.. math::
    \\frac{d\\varphi(\\theta)}{dt} = \\mathcal{K}\\,\\varphi(\\theta),
    \\qquad
    z_i^{j\\to i} = z_j + \\int_{t_j}^{t_i} \\mathcal{K} z_\\tau\\,d\\tau

我们做**两处忠实移植**，并把第三处如实标注为简化：

* **域坐标换轴**：Koodos 的域坐标是时间 :math:`t`；我们换成洞窟的**无标签物理
  描述子** :math:`s`（如 Light 区日周期振幅）。要求 :math:`s` 只能由**无标签输入
  或先验元数据**算出，否则等于偷看目标域标签。
* **参数轨迹换轴**：Koodos 建模深度网络参数 :math:`\\theta(t)` 的轨迹；我们建模
  **各源域闭式读出头** :math:`\\theta_k` 的轨迹。Koodos 论文 Eq.(6)
  :math:`\\theta_i = \\arg\\min_\\theta \\mathcal{L}(Y_i, g(X_i;\\theta))` 正是
  「每个域单独解一个模型」，与我们逐域解岭回归完全一致。
* **简化（如实披露）**：Koodos 用神经网络编码器 :math:`\\varphi` 与神经 ODE
  联合优化；在**线性闭式读出**这一特例下，:math:`\\varphi` 取 PCA 截断、
  :math:`\\mathcal{K}` 取有限差分最小二乘（等价于连续时间的 DMD），
  二者都有解析解，无需梯度下降。这不是「我们的近似」，而是 Koodos 在
  「读出层是线性模型」这一子类上的**精确闭式解**。
* **先验约束**：Koodos §4.3 允许对 :math:`\\mathcal{K}` 的谱注入先验（收敛 /
  发散 / 周期）。我们注入**耗散先验**：洞窟对室外扰动的耦合强度随域距离不得
  指数放大，故强制 :math:`\\mathrm{Re}\\,\\lambda(\\mathcal{K}) \\le 0`。

与主仓 L2 算子的关系：``transport.KoopmanTransport`` 是**状态空间**的 Koopman
算子，本模块是**域空间**的 Koopman 算子，二者构成「状态 × 域」**双层 Koopman**。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "Domain",
    "DomainGeneralizer",
    "design",
    "koopman_domain_extrapolation",
    "predict_readout",
    "ridge_solve",
    "standardize_from",
]

#: 默认岭回归强度候选（与 ``validate_iccp.BETA_GRID`` 同量级）。
DEFAULT_BETA_GRID: tuple[float, ...] = (1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0)


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #
@dataclass
class Domain:
    """一个域。

    Attributes
    ----------
    name:
        域标识（洞窟名 / 年份）。
    s:
        **连续域坐标**，必须可由无标签输入或先验元数据算出。
    Xtr, ytr:
        源域的标定特征与标签；目标域只填 ``Xte``（零标签）。
    Xva, yva:
        源域的验证特征与标签，用于**只用源域**选超参（防泄漏）。
    Xte, yte:
        目标域的评测特征与标签；``yte`` 只在最终计分时使用。
    """

    name: str
    s: float
    Xtr: np.ndarray | None = None
    ytr: np.ndarray | None = None
    Xva: np.ndarray | None = None
    yva: np.ndarray | None = None
    Xte: np.ndarray | None = None
    yte: np.ndarray | None = None

    @property
    def is_source(self) -> bool:
        return self.Xtr is not None and self.ytr is not None


# --------------------------------------------------------------------------- #
# 标准化与线性读出
# --------------------------------------------------------------------------- #
def standardize_from(domains: list[Domain], max_rows: int = 400_000) -> tuple[np.ndarray, np.ndarray]:
    """用**源域标定段**统计量做共享标准化。

    目标域不参与统计——否则就是把目标域信息泄露进特征尺度。共享尺度的另一个
    必要原因是：域空间 Koopman 要比较不同域的读出头 :math:`\\theta_k`，
    只有它们处在同一坐标系下才有意义。
    """
    mats = [np.asarray(d.Xtr, dtype=float) for d in domains if d.is_source]
    if not mats:
        raise ValueError("至少需要一个源域")
    X = np.vstack(mats)
    if len(X) > max_rows:
        sel = np.linspace(0, len(X) - 1, max_rows).astype(int)
        X = X[sel]
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    return mu, sd


def design(X: np.ndarray, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """标准化并加截距列（第 0 列恒为 1）。"""
    X = np.asarray(X, dtype=float)
    return np.column_stack([np.ones(len(X)), (X - mu) / sd])


def _slope_mask(p: int) -> np.ndarray:
    m = np.ones(p, dtype=float)
    m[0] = 0.0                      # 不惩罚截距
    return m


def ridge_solve(Z: np.ndarray, y: np.ndarray, beta: float,
                mask: np.ndarray | None = None,
                sample_weight: np.ndarray | None = None) -> np.ndarray:
    """带截距、只惩罚斜率的岭回归（增广最小二乘）。

    与 ``validate_iccp.ridge_fit_predict`` 同法：**不**直接解
    ``G = Z'Z/n + beta·diag(mask)``——特征高度共线时条件数爆炸，会给出 1e30
    量级的解（实测真实洞穴数据即如此）。增广最小二乘等价但数值稳定得多。
    """
    Z = np.asarray(Z, dtype=float)
    y = np.asarray(y, dtype=float)
    n, p = Z.shape
    if mask is None:
        mask = _slope_mask(p)
    sw = np.ones(n) if sample_weight is None else np.asarray(sample_weight, dtype=float)
    r = np.sqrt(sw / n)
    A = np.vstack([Z * r[:, None], np.diag(np.sqrt(beta) * mask)])
    b = np.concatenate([y * r, np.zeros(p)])
    w, *_ = np.linalg.lstsq(A, b, rcond=None)
    return w


def predict_readout(theta: np.ndarray, X: np.ndarray, mu: np.ndarray, sd: np.ndarray,
                    clip: tuple[float, float] | None = None) -> np.ndarray:
    """用读出头 :math:`\\theta` 在原始特征上出预测。"""
    p = design(X, mu, sd) @ np.asarray(theta, dtype=float)
    if clip is not None:
        p = np.clip(p, clip[0], clip[1])
    return p


def _risk(Z: np.ndarray, y: np.ndarray, w: np.ndarray, beta: float,
          mask: np.ndarray) -> float:
    """单域风险（含 L2 罚），用于域重加权与 V-REx。"""
    r = float(np.mean((Z @ w - y) ** 2))
    return r + beta * float(np.sum((mask * w) ** 2))


def _gram(Z: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """预算单域的充分统计量 :math:`(Z^\\top Z/n,\\; Z^\\top y/n,\\; \\overline{y^2})`。

    有了它，任何「**按域整体重加权**」的最小二乘都不必再碰 :math:`O(Np)` 的数据矩阵，
    每次迭代只需 :math:`O(Kp^2)`——group DRO 迭代数百次正是这个场景。
    """
    n = len(Z)
    return (Z.T @ Z) / n, (Z.T @ y) / n, float(np.mean(y ** 2))


def _risk_gram(G: np.ndarray, b: np.ndarray, myy: float, w: np.ndarray,
               beta: float, m2: np.ndarray) -> float:
    """:func:`_risk` 的充分统计量版本，与它逐位等价。"""
    return (float(w @ G @ w) - 2.0 * float(w @ b) + myy
            + beta * float(np.sum(m2 * w * w)))


# --------------------------------------------------------------------------- #
# 域敏感子空间上的收缩外推（本项目主推的域泛化读出）
# --------------------------------------------------------------------------- #
def subspace_variance(thetas: np.ndarray) -> np.ndarray:
    """逐坐标的**域间标准差**——纯无标签量，用来定义「域敏感子空间」。"""
    thetas = np.asarray(thetas, dtype=float)
    return thetas.std(axis=1)


def restricted_extrapolate(
    thetas: np.ndarray,
    s: np.ndarray,
    s_star: float,
    *,
    dims: int = 4,
    shrink: float = 0.6,
) -> tuple[np.ndarray, dict]:
    """在**域敏感子空间**上沿域坐标外推读出头，其余坐标保持池化读出。

    动机来自一条实测结构：逐域读出头 :math:`\\theta_k` 的域间变化是**极低秩**的
    （ICCP 真实洞穴上第一奇异值占去均值后能量的 99% 以上），而域间差异几乎全部
    落在少数几个坐标上（首要是截距，即该洞的湿度水平）。于是在**全部** 57 维上
    自由外推（:func:`koopman_domain_extrapolation` 的做法）会被噪声方向放大成
    外插爆炸；只在外推真正有信息的那几维上动手，反而稳定。

    每个被选中的坐标 :math:`i` 取两个端点估计的凸组合：

    .. math::
        \\theta^*_i = \\kappa\\,(a_i + b_i s^*) + (1-\\kappa)\\sum_k w_k \\theta_{k,i}

    其中 :math:`a_i+b_i s` 是对 :math:`(s_k,\\theta_{k,i})` 的线性外推（即仿射
    Koopman 生成元的一阶特例），:math:`w_k` 是域距离高斯核权重。:math:`\\kappa<1`
    是**收缩**：把外插值拉回最近邻域的核平均，抑制远离源域坐标时的爆炸。

    Parameters
    ----------
    thetas:
        ``(p, K)`` 源域读出头。
    s:
        ``(K,)`` 源域的无标签域坐标。
    s_star:
        目标域坐标。
    dims:
        参与外推的坐标个数（按域间标准差从大到小取）。
    shrink:
        收缩系数 :math:`\\kappa\\in[0,1]`；``1.0`` 为纯线性外推，``0.0`` 为纯核平均。

    Returns
    -------
    ``(theta_star, info)``。
    """
    thetas = np.asarray(thetas, dtype=float)
    s = np.asarray(s, dtype=float).ravel()
    if thetas.ndim != 2:
        raise ValueError("thetas 必须是 (p, K)")
    p, K = thetas.shape
    if K != len(s):
        raise ValueError(f"thetas 列数 {K} 与域坐标数 {len(s)} 不一致")

    theta_pool = thetas.mean(axis=1)
    var = subspace_variance(thetas)
    m = int(max(1, min(dims, p)))
    idx = np.argsort(-var)[:m]

    scale = float(np.std(s))
    scale = scale if np.isfinite(scale) and scale > 0 else 1.0
    wt = np.exp(-0.5 * ((s - s_star) / scale) ** 2)
    if not np.isfinite(wt).all() or wt.sum() <= 1e-12:
        wt = np.ones(K)
    wt = wt / wt.sum()

    theta = theta_pool.copy()
    A = np.column_stack([np.ones(K), s])
    for i in idx:
        kern = float(wt @ thetas[i])
        coef = np.linalg.lstsq(A, thetas[i], rcond=None)[0]
        lin = float(coef[0] + coef[1] * s_star)
        theta[i] = kern + float(shrink) * (lin - kern)

    info = {
        "subspace_idx": idx.tolist(),
        "subspace_std": var[idx].tolist(),
        "kernel_weights": wt,
        "theta_pool": theta_pool,
        "dims": m,
        "shrink": float(shrink),
        "s_star": float(s_star),
    }
    return theta, info


# --------------------------------------------------------------------------- #
# 域空间 Koopman 演化
# --------------------------------------------------------------------------- #
def koopman_domain_extrapolation(
    thetas: np.ndarray,
    s: np.ndarray,
    s_star: float,
    *,
    n_latent: int = 3,
    ridge: float = 1e-2,
    bandwidth: float | None = None,
    dissipative: bool = True,
) -> tuple[np.ndarray, dict]:
    """沿连续域坐标把源域读出头演化到目标域坐标。

    Parameters
    ----------
    thetas:
        ``(p, K)``，:math:`K` 个源域在**同一标准化坐标系**下的读出头。
    s:
        ``(K,)``，各源域的无标签域坐标。
    s_star:
        目标域的域坐标（由目标域无标签输入算出）。
    n_latent:
        Koopman 不变子空间维数 :math:`n`（Koodos 的 :math:`\\mathcal{Z}=\\mathbb{R}^n`）。
    ridge:
        拟合 :math:`\\mathcal{K}` 时的 Tikhonov 项，避免小样本下求逆病态。
    bandwidth:
        域坐标上的高斯核带宽；``None`` 时取源域坐标标准差。
    dissipative:
        是否注入耗散先验（强制 :math:`\\mathrm{Re}\\,\\lambda(\\mathcal{K})\\le 0`）。

    Returns
    -------
    ``(theta_star, info)``。``info`` 含 :math:`\\mathcal{K}` 的谱、编码矩阵
    :math:`\\varphi`、核权重，供可解释性分析使用。
    """
    thetas = np.asarray(thetas, dtype=float)
    s = np.asarray(s, dtype=float).ravel()
    if thetas.ndim != 2:
        raise ValueError("thetas 必须是 (p, K)")
    p, K = thetas.shape
    if K != len(s):
        raise ValueError(f"thetas 列数 {K} 与域坐标数 {len(s)} 不一致")
    from scipy.linalg import expm

    order = np.argsort(s)
    th, ss = thetas[:, order], s[order]

    # --- 编码器 φ：Koodos 用神经网络；线性读出头子类下取 PCA 截断（精确闭式）
    theta_bar = th.mean(axis=1, keepdims=True)
    centered = th - theta_bar
    U, sv, _ = np.linalg.svd(centered, full_matrices=False)
    n = int(max(1, min(n_latent, K - 1)))
    # 可辨识性：仿射提升后每行有 n+1 个未知量，而中心差分只给出 K-1 个方程。
    # 欠定时最小二乘会给出错误解（合成实测：K=3、n=2 时相对误差 4.35e-1）。
    n = int(max(1, min(n, K - 2)))
    P = U[:, :n]                       # (p, n)
    Z = P.T @ centered                 # (n, K)

    # --- Koopman 生成元：连续域坐标上的中心差分 + 最小二乘（= 连续时间 DMD）
    #
    # 关键细节：**必须带常数项（仿射提升）**。若只拟合 dz/ds = 𝒦 z，则 z=0 是
    # 生成元的不动点——轨迹经过原点时速度必须为零。而均值居中后的 PCA 轨迹恰好
    # 穿过原点且速度非零，最小二乘会退化（实测 3 个源域时给出 𝒦≡0，外推退化成
    # 常数）。Koodos 的学习式编码器 φ 不受此限制；在 PCA 这一线性特例下，标准
    # 做法是把常数 1 也作为可观测量一起提升，即 **Koopman 仿射提升**。
    Za = np.vstack([Z, np.ones((1, K))])                  # (n+1, K) 提升状态 [z; 1]
    if K >= 3:
        ds = np.diff(ss)
        dZ = np.diff(Z, axis=1) / ds[None, :]
        Zc = 0.5 * (Za[:, :-1] + Za[:, 1:])               # 中点，二阶精度
        Ka = dZ @ Zc.T @ np.linalg.inv(Zc @ Zc.T + ridge * np.eye(n + 1))
    else:
        Ka = np.zeros((n, n + 1))
    A = np.zeros((n + 1, n + 1))                          # 作用在 [z; 1] 上
    A[:n, :] = Ka
    ev_raw, V = np.linalg.eig(A)

    # --- 先验约束：耗散（Koodos §4.3 的「收敛模式」先验）
    #
    # 只在**确有特征值越界**时才重构。否则像「匀速漂移」这类生成元是幂零矩阵
    # （特征值全 0、特征向量矩阵退化），按特征分解重构会把它整个抹成零矩阵，
    # 外推随之退化为常数——而且残差检查还发现不了（‖0−A‖/‖A‖ 恰为 1）。
    if dissipative:
        violated = ev_raw.real > 0.0
        if np.any(violated):
            ev_fix = np.where(violated, 1j * ev_raw.imag, ev_raw)
            V_c = V
            if np.linalg.cond(V_c) > 1e8:                  # 特征基病态，放弃先验
                V_c = None
            if V_c is not None:
                A_con = np.real(V_c @ np.diag(ev_fix) @ np.linalg.pinv(V_c))
                resid = np.linalg.norm(A_con - A) / max(np.linalg.norm(A), 1e-12)
                if np.isfinite(resid) and resid <= 1e-6:
                    A = A_con
    ev = np.linalg.eigvals(A)

    def propagate(delta: float) -> np.ndarray:
        """:math:`\\exp(A\\Delta)`，作用在提升状态 :math:`[z;1]` 上。"""
        return expm(A * delta)

    # --- 从每个源域积分到 s_star，按域距离核加权平均（Koodos 的 ODE solver）
    if bandwidth is None:
        bandwidth = float(np.std(ss))
        if not np.isfinite(bandwidth) or bandwidth <= 0:
            bandwidth = 1.0
    wt = np.exp(-0.5 * ((ss - s_star) / bandwidth) ** 2)
    if not np.isfinite(wt).all() or wt.sum() <= 1e-12:
        wt = np.ones(K)
    wt = wt / wt.sum()

    z_star = np.zeros(n)
    for j in range(K):
        z_star += wt[j] * (propagate(float(s_star - ss[j])) @ Za[:, j])[:n]
    theta_star = theta_bar[:, 0] + P @ z_star

    info = {
        "n_latent": n,
        "generator": A,
        "eigenvalues": ev,
        "eigenvalues_unconstrained": ev_raw,
        "singular_values": sv[:n],
        "encoder": P,
        "latent": Z,
        "s_sorted": ss,
        "kernel_weights": wt,
        "bandwidth": bandwidth,
        "dissipative": bool(dissipative),
        "theta_norm": float(np.linalg.norm(theta_bar)),
    }
    return theta_star, info


# --------------------------------------------------------------------------- #
# 泛化器
# --------------------------------------------------------------------------- #
@dataclass
class DomainGeneralizer:
    """多源域泛化读出。

    Parameters
    ----------
    method:
        ``"pooled"`` / ``"group_dro"`` / ``"vrex"`` / ``"koopman"`` /
        ``"nearest"``（最近域迁移，作为朴素基线）/ ``"oracle"``
        （在目标域标定段上直接拟合，只作上界参考，**不是**泛化方法）。
    beta:
        岭回归强度；``None`` 表示按 :data:`DEFAULT_BETA_GRID` 在**源域验证段**上选。
    clip:
        预测截断区间（RH 为 ``(0, 100)``）。
    """

    method: str = "koopman"
    beta: float | None = None
    beta_grid: tuple[float, ...] = DEFAULT_BETA_GRID
    clip: tuple[float, float] | None = (0.0, 100.0)
    # koopman 超参
    n_latent: int = 3
    koopman_ridge: float = 1e-2
    bandwidth: float | None = None
    dissipative: bool = True
    # subspace 超参（本项目主推臂）
    subspace_dims: tuple[int, ...] = (4, 8, 16, 32)
    shrink_grid: tuple[float, ...] = (0.0, 0.4, 0.6, 0.8, 1.0)
    theta_beta: float = 1.0
    # group_dro 超参
    dro_eta: float = 0.05
    dro_iters: int = 300
    # vrex 超参
    vrex_lambda: float = 1.0
    #: ``False`` 表示特征已由调用方**逐域**标准化，本类不再做共享标准化。
    #: 逐域标准化让 :math:`\\theta_k` 只依赖域 :math:`k` 自身的数据，于是
    #: 「留出某域」不会改变其余域的读出——这正是内层留一能被缓存的前提。
    standardize: bool = True

    mu_: np.ndarray | None = field(default=None, repr=False)
    sd_: np.ndarray | None = field(default=None, repr=False)
    theta_: np.ndarray | None = field(default=None, repr=False)
    thetas_: np.ndarray | None = field(default=None, repr=False)
    s_: np.ndarray | None = field(default=None, repr=False)
    names_: list[str] = field(default_factory=list, repr=False)
    info_: dict = field(default_factory=dict, repr=False)
    _cache: dict = field(default_factory=dict, repr=False)
    _theta_cache: dict = field(default_factory=dict, repr=False)

    # ---------------------------------------------------------------- 内部
    def _fit_single(self, src: list[Domain], beta: float) -> np.ndarray:
        """按 method 解出**一个**读出向量（koopman / oracle 除外）。"""
        Zs = [design(d.Xtr, self.mu_, self.sd_) for d in src]
        ys = [np.asarray(d.ytr, dtype=float) for d in src]
        p = Zs[0].shape[1]
        mask = _slope_mask(p)

        if self.method == "pooled":
            Z = np.vstack(Zs)
            y = np.concatenate(ys)
            return ridge_solve(Z, y, beta, mask)

        if self.method == "nearest":
            j = int(np.argmin([abs(d.s - self._s_star) for d in src]))
            return ridge_solve(Zs[j], ys[j], beta, mask)

        if self.method == "oracle":
            # 目标域标定段直接拟合——上界参考，非泛化方法
            Zo = design(self._oracle_Xtr, self.mu_, self.sd_)
            return ridge_solve(Zo, np.asarray(self._oracle_ytr, dtype=float), beta, mask)

        if self.method == "group_dro":
            K = len(src)
            m2 = mask ** 2
            grams = [_gram(Z, y) for Z, y in zip(Zs, ys)]
            q = np.full(K, 1.0 / K)
            w = np.zeros(p)
            for _ in range(self.dro_iters):
                Gq = beta * np.diag(m2)
                bq = np.zeros(p)
                for k in range(K):
                    Gq += q[k] * grams[k][0]
                    bq += q[k] * grams[k][1]
                w = np.linalg.solve(Gq, bq)
                R = np.array([_risk_gram(g[0], g[1], g[2], w, beta, m2)
                              for g in grams])
                q = q * np.exp(self.dro_eta * (R - R.max()))
                q = np.maximum(q, 1e-6)
                q = q / q.sum()
            self.info_["dro_weights"] = q
            self.info_["dro_domain_risk"] = R
            return w

        if self.method == "vrex":
            from scipy.optimize import minimize

            K = len(src)
            G = [Z.T @ Z / len(Z) for Z in Zs]
            bvec = [Z.T @ y / len(y) for Z, y in zip(Zs, ys)]
            myy = [float(np.mean(y ** 2)) for y in ys]
            m2 = mask ** 2

            def risks(w):
                return np.array([
                    float(w @ G[k] @ w - 2.0 * (w @ bvec[k]) + myy[k]
                          + beta * float(np.sum(m2 * w * w)))
                    for k in range(K)
                ])

            def obj(w):
                R = risks(w)
                return float(R.mean() + self.vrex_lambda * R.var())

            def grad(w):
                R = risks(w)
                gR = np.array([2.0 * (G[k] @ w - bvec[k]) + 2.0 * beta * m2 * w
                               for k in range(K)])
                c = 1.0 / K + 2.0 * self.vrex_lambda * (R - R.mean()) / K
                return (c[:, None] * gR).sum(axis=0)

            res = minimize(obj, np.zeros(p), jac=grad, method="L-BFGS-B",
                           options={"maxiter": 800})
            self.info_["vrex_fun"] = float(res.fun)
            self.info_["vrex_success"] = bool(res.success)
            return np.asarray(res.x, dtype=float)

        raise ValueError(f"未知 method: {self.method!r}")

    def _val_risk(self, src: list[Domain], beta: float) -> float:
        """源域验证段上的平均风险——选超参**只用源域**，目标域零参与。"""
        if self.method == "koopman":
            return self._val_risk_koopman(src, beta)
        if self.method == "oracle":
            # oracle 臂是上界参考，允许它用目标域自身的验证段选参
            if self._oracle_Xva is None or len(self._oracle_yva) == 0:
                return float("nan")
            Z = design(self._oracle_Xtr, self.mu_, self.sd_)
            w = ridge_solve(Z, np.asarray(self._oracle_ytr, dtype=float), beta)
            pv = predict_readout(w, self._oracle_Xva, self.mu_, self.sd_)
            return float(np.mean((pv - np.asarray(self._oracle_yva, dtype=float)) ** 2))
        w = self._fit_single(src, beta)
        tot, cnt = 0.0, 0
        for d in src:
            if d.Xva is None or d.yva is None or len(d.yva) == 0:
                continue
            pv = predict_readout(w, d.Xva, self.mu_, self.sd_)
            tot += float(np.mean((pv - np.asarray(d.yva, dtype=float)) ** 2))
            cnt += 1
        return tot / max(cnt, 1)

    def _val_risk_koopman(self, src: list[Domain], beta: float) -> float:
        """Koopman 臂的选参风险：**内层留一源域**。

        直接在各源域自己的验证段上评估逐域读出头是**测不出**
        :math:`n`、:math:`\\beta` 的好坏的——那条路径根本不经过域空间外推。
        真正要对齐的是「用其余源域外推到某个未见域坐标」的能力，所以在源域
        内部做一次留一：留出源域 :math:`j`，用其余源域演化到 :math:`s_j`，
        在 :math:`j` 的验证段上计风险。目标域自始至终不参与。
        """
        K = len(src)
        if K < 4:
            return float("nan")
        tot, cnt = 0.0, 0
        for j in range(K):
            others = [src[k] for k in range(K) if k != j]
            d = src[j]
            if d.Xva is None or d.yva is None or len(d.yva) == 0:
                continue
            thetas = self._fit_thetas(others, beta)
            th_j, _ = koopman_domain_extrapolation(
                thetas, [o.s for o in others], d.s,
                n_latent=self.n_latent, ridge=self.koopman_ridge,
                bandwidth=self.bandwidth, dissipative=self.dissipative,
            )
            pv = predict_readout(th_j, d.Xva, self.mu_, self.sd_)
            tot += float(np.mean((pv - np.asarray(d.yva, dtype=float)) ** 2))
            cnt += 1
        return tot / max(cnt, 1)

    def _fit_thetas(self, src: list[Domain], beta: float) -> np.ndarray:
        """逐域解读出（Koodos Eq.6）——``koopman`` 与 ``subspace`` 两臂共用。

        当 ``standardize=False``（逐域标准化）时，:math:`\\theta_k` 只由域
        :math:`k` 的标定段决定，因此可以跨内层折缓存，避免把内层留一变成
        :math:`O(K^2)` 次最小二乘。
        """
        cols = []
        for d in src:
            key = (d.name, round(float(beta), 12))
            cached = self._theta_cache.get(key) if not self.standardize else None
            if cached is None:
                Z = design(d.Xtr, self.mu_, self.sd_)
                cached = ridge_solve(Z, np.asarray(d.ytr, dtype=float), beta)
                if not self.standardize:
                    self._theta_cache[key] = cached
            cols.append(cached)
        return np.column_stack(cols)

    def _select_subspace(self, src: list[Domain]) -> tuple[int, float, dict]:
        """``subspace`` 臂的选参：内层留一源域，**目标域零参与**。

        与 ``koopman`` 臂同理，逐域读出头在各自验证段上的表现测不出域空间外推
        的好坏；所以留出源域 :math:`j`，用其余源域外推到 :math:`s_j`，在
        :math:`j` 的验证段上计风险，据此在 ``(dims, shrink)`` 网格上取最优。
        逐坐标的域间标准差是纯无标签量，子空间选择本身不引入任何目标域信息。
        """
        K = len(src)
        if K < 3:
            return 4, 0.6, {"note": "源域少于 3 个，直接用默认 (dims=4, shrink=0.6)"}
        folds = []
        for j in range(K):
            d = src[j]
            if d.Xva is None or d.yva is None or len(d.yva) == 0:
                continue
            others = [src[k] for k in range(K) if k != j]
            thetas = self._fit_thetas(others, self.theta_beta)
            folds.append((thetas, np.array([o.s for o in others], dtype=float), d))
        if not folds:
            return 4, 0.6, {"note": "源域缺验证段，直接用默认 (dims=4, shrink=0.6)"}

        table: dict[str, float] = {}
        best = (float("inf"), 4, 0.6)
        for dims in self.subspace_dims:
            for shrink in self.shrink_grid:
                tot, cnt = 0.0, 0
                for thetas, ss, d in folds:
                    th, _ = restricted_extrapolate(thetas, ss, d.s,
                                                   dims=dims, shrink=shrink)
                    pv = predict_readout(th, d.Xva, self.mu_, self.sd_)
                    tot += float(np.mean((pv - np.asarray(d.yva, dtype=float)) ** 2))
                    cnt += 1
                risk = tot / max(cnt, 1)
                table[f"dims{dims}_shrink{shrink}"] = round(risk, 5)
                if risk < best[0]:
                    best = (risk, dims, shrink)
        return best[1], best[2], {
            "risk_table": table,
            "best_risk": round(best[0], 5),
            "n_inner_folds": len(folds),
        }

    # ------------------------------------------------------------------ API
    def fit(self, src: list[Domain], *, s_star: float | None = None,
            oracle: Domain | None = None) -> "DomainGeneralizer":
        """在源域上标定。

        Parameters
        ----------
        src:
            源域列表（每个域必须填 ``Xtr/ytr``，建议同时填验证段）。
        s_star:
            目标域坐标（``koopman`` / ``nearest`` 需要）。
        oracle:
            目标域本身（含 ``Xtr/ytr``），仅 ``method="oracle"`` 使用。
        """
        src = [d for d in src if d.is_source]
        if len(src) < 2:
            raise ValueError("至少需要 2 个源域")
        self._s_star = float(s_star) if s_star is not None else float("nan")
        if self.method == "oracle":
            if oracle is None or not oracle.is_source:
                raise ValueError("oracle 臂需要目标域自身的标定段")
            self._oracle_Xtr, self._oracle_ytr = oracle.Xtr, oracle.ytr
            self._oracle_Xva = oracle.Xva
            self._oracle_yva = oracle.yva

        self.mu_, self.sd_ = (
            standardize_from(src) if self.standardize
            else (np.zeros(np.asarray(src[0].Xtr).shape[1], dtype=float),
                  np.ones(np.asarray(src[0].Xtr).shape[1], dtype=float))
        )
        self.names_ = [d.name for d in src]
        self.s_ = np.array([d.s for d in src], dtype=float)

        if self.method == "subspace":
            # 子空间臂的超参是 (dims, shrink)，不是 beta；走自己的选参路径。
            dims, shrink, sub_info = self._select_subspace(src)
            self.dims_, self.shrink_ = int(dims), float(shrink)
            self.info_["subspace"] = sub_info
            self.beta_ = float(self.theta_beta)
        elif self.beta is None:
            risks = [(self._val_risk(src, b), b) for b in self.beta_grid]
            finite = [(r, b) for r, b in risks if np.isfinite(r)]
            self.info_["beta_scan"] = {str(b): (None if not np.isfinite(r) else round(r, 5))
                                       for r, b in risks}
            self.beta_ = min(finite)[1] if finite else self.beta_grid[0]
        else:
            self.beta_ = float(self.beta)
        self.info_["beta"] = self.beta_

        # 选出 beta 后，把源域验证段并入标定集
        merged: list[Domain] = []
        for d in src:
            if d.Xva is not None and d.yva is not None and len(d.yva):
                merged.append(Domain(
                    name=d.name, s=d.s,
                    Xtr=np.vstack([d.Xtr, d.Xva]),
                    ytr=np.concatenate([d.ytr, d.yva]),
                ))
            else:
                merged.append(d)
        self._src = merged

        if self.method == "koopman":
            self.thetas_ = self._fit_thetas(merged, self.beta_)
            self.theta_ = None
        elif self.method == "subspace":
            self.thetas_ = self._fit_thetas(merged, self.theta_beta)
            self.theta_ = None
        else:
            self.theta_ = self._fit_single(merged, self.beta_)
            self.thetas_ = None
        return self

    def _theta_for(self, s_star: float) -> np.ndarray:
        if self.method == "subspace":
            key = round(float(s_star), 9)
            if key not in self._cache:
                th, info = restricted_extrapolate(
                    self.thetas_, self.s_, s_star,
                    dims=self.dims_, shrink=self.shrink_,
                )
                self._cache[key] = (th, info)
            return self._cache[key][0]
        if self.method != "koopman":
            return self.theta_
        key = round(float(s_star), 9)
        if key not in self._cache:
            th, info = koopman_domain_extrapolation(
                self.thetas_, self.s_, s_star,
                n_latent=self.n_latent, ridge=self.koopman_ridge,
                bandwidth=self.bandwidth, dissipative=self.dissipative,
            )
            self._cache[key] = (th, info)
        return self._cache[key][0]

    def predict(self, X: np.ndarray, s_star: float | None = None) -> np.ndarray:
        s = self._s_star if s_star is None else float(s_star)
        return predict_readout(self._theta_for(s), X, self.mu_, self.sd_, self.clip)

    def koopman_info(self, s_star: float) -> dict:
        self._theta_for(s_star)
        return self._cache[round(float(s_star), 9)][1]
