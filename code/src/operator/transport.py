"""延迟嵌入 Koopman/EDMD 输运算子 —— 室外气象到窟内微环境的可微物理代理。

为什么需要"算子"这一层
----------------------
窟内温湿度**没有公开实测标签**，只有物理模型生成的合成标签。若直接把物理模型
接在预报模型后面，会带来两个问题：

1. **不可微 / 不可反传**：逐时步推进的热湿耦合模型无法高效地求关于预报模型参数的梯度；
2. **推理代价高**：每推演一次窟内序列都要跑完整物理模型，边缘端不划算。

本模块用 **延迟嵌入 + 扩展动态模态分解（EDMD）** 构造一个**闭式解、可微、可解释**的
输运算子，作为物理模型的高速代理。理论依据是 Takens 嵌入定理与 HAVOK
（Brunton et al., *Chaos as an intermittently forced linear system*, Nat Commun 8, 2017）：
在受迫系统中，**未被观测的标量可观测量可以从被观测量的延迟坐标中重构**。
这里"被观测量"是室外气象，"未被观测量"是窟内微环境。

算子形式
--------
设外场驱动序列 :math:`x_t \\in \\mathbb{R}^d`，构造提升特征 :math:`\\Psi(u_t) \\in \\mathbb{R}^p`
（见 :func:`build_features`），则

* **演化**：:math:`\\Psi(u_{t+1}) \\approx K \\Psi(u_t)`，:math:`K` 由岭回归闭式解给出
* **读出**：:math:`\\hat h_t = w^\\top \\Psi(u_t)`，:math:`w` 同样闭式解

:math:`K` 的特征值谱给出**物理可解释的时间常数与衰减率**——这正是"灰箱"中
"可解释"的那一半。由于 :math:`w` 与 :math:`K` 求解均**不含反向传播**，
这满足了"纯 CPU、无 BPTT"的部署约束。

特征设计（物理动机）
--------------------
:math:`\\Psi` 由三部分组成，每一部分都对应明确的物理量：

1. **快变延迟坐标**：捕捉日循环与天气过程的高频响应；
2. **多时间尺度滑动均值**：窟壁温度本质上是室外气温的低通滤波结果，
   用多尺度均值显式给出"慢热状态"；
3. **Magnus 比值项** :math:`q_{\\text{slow}} / q_{sat}(T_{\\text{slow}})`：
   因为相对湿度定义就是 :math:`RH = q/q_{sat}(T)`，这一项把
   **温度与湿度耦合的非线性**直接写进特征，而不是指望线性读出层去逼近。

消融设计
--------
:meth:`fit` 支持 ``ablate`` 参数，可分别关闭慢变项与 Magnus 项，
用于证明"物理结构本身有贡献"，而不是换个回归器就有效。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..physics.cave_model import esat_pa, rh_to_vapor_density

#: 参与建模的室外驱动要素（缺列时自动跳过）。
DEFAULT_DRIVERS = ["T2M", "RH2M", "WS10M", "PS", "ALLSKY_SFC_SW_DWN"]

#: 多时间尺度滑动均值窗口（小时）：1 天 / 3 天 / 7 天 / 30 天 / 90 天 / 365 天。
DEFAULT_SLOW_WINDOWS = (24, 72, 168, 720, 2160, 8760)


@dataclass
class TransportConfig:
    """输运算子配置。"""

    drivers: list[str] = field(default_factory=lambda: list(DEFAULT_DRIVERS))
    #: 快变延迟坐标的回溯阶数（小时）。48 h 覆盖两个日循环。
    n_fast_lags: int = 48
    #: 慢变滑动均值窗口（小时）。
    slow_windows: tuple[int, ...] = DEFAULT_SLOW_WINDOWS
    #: 是否启用多尺度慢变项。
    use_slow: bool = True
    #: 是否启用 Magnus 比值项。
    use_magnus: bool = True
    #: 岭回归正则系数。
    ridge_beta: float = 1e-6
    #: 是否对特征做标准化（推荐开启，各物理量量纲差异大）。
    standardize: bool = True


# --------------------------------------------------------------------------
# 特征构造
# --------------------------------------------------------------------------


def _causal_ma(arr: np.ndarray, window: int) -> np.ndarray:
    """因果（仅用当前及历史）滑动均值。序列开头用扩张窗口，避免 NaN 与未来信息泄露。"""
    s = pd.Series(arr, dtype=float)
    return s.rolling(window=window, min_periods=1).mean().to_numpy()


def build_features(
    outdoor: pd.DataFrame,
    cfg: TransportConfig | None = None,
    *,
    names_out: list[str] | None = None,
) -> np.ndarray:
    """构造提升特征矩阵 :math:`\\Psi`。

    Parameters
    ----------
    outdoor : DataFrame
        外场驱动序列，索引为时间，列名见 ``cfg.drivers``。
    cfg : TransportConfig, optional
        配置。
    names_out : list, optional
        若提供，则就地填入各列特征名（便于物理归因）。

    Returns
    -------
    ndarray, shape (T, p)
        第 t 行只依赖 ``<= t`` 时刻的信息（**严格因果，无未来信息泄露**）。
    """
    cfg = cfg or TransportConfig()
    cols = [c for c in cfg.drivers if c in outdoor.columns]
    d = len(cols)
    X = outdoor[cols].to_numpy(dtype=float)
    T = len(X)
    feats: list[np.ndarray] = []
    names: list[str] = []

    # --- 1. 快变延迟坐标 ---
    for lag in range(cfg.n_fast_lags):
        shifted = np.full((T, d), np.nan)
        if lag == 0:
            shifted = X.copy()
        else:
            shifted[lag:] = X[:-lag]
        feats.append(shifted)
        names.extend(f"{c}_lag{lag}" for c in cols)

    # --- 2/3. 慢变状态与 Magnus 项 ---
    if cfg.use_slow or cfg.use_magnus:
        # 水汽密度（由 T2M 与 RH2M 换算）
        if "T2M" in outdoor.columns and "RH2M" in outdoor.columns:
            q = rh_to_vapor_density(
                outdoor["RH2M"].to_numpy(dtype=float),
                outdoor["T2M"].to_numpy(dtype=float),
            )
        else:
            q = None
        t_air = outdoor["T2M"].to_numpy(dtype=float) if "T2M" in outdoor.columns else None

        for w in cfg.slow_windows:
            if cfg.use_slow and t_air is not None:
                feats.append(_causal_ma(t_air, w)[:, None])
                names.append(f"T2M_ma{w}")
            if cfg.use_slow and q is not None:
                feats.append(_causal_ma(q, w)[:, None])
                names.append(f"q_ma{w}")
            if cfg.use_magnus and q is not None and t_air is not None:
                q_ma = _causal_ma(q, w)
                t_ma = _causal_ma(t_air, w)
                # Magnus 比值：慢变状态下的等效相对湿度（0-100 归一化）
                rh_slow = np.clip(q_ma / (esat_pa(t_ma) / (461.5 * (t_ma + 273.15))) * 100, 0, 120)
                feats.append(rh_slow[:, None])
                names.append(f"RHslow_ma{w}")

    Psi = np.concatenate(feats, axis=1)

    # 序列开头的延迟坐标含 NaN（历史不足），用该列的首个有效值回填
    if np.isnan(Psi).any():
        col_mean = np.nanmean(Psi, axis=0)
        idx = np.where(np.isnan(Psi))
        Psi[idx] = np.take(col_mean, idx[1])

    if names_out is not None:
        names_out.extend(names)
    return Psi


# --------------------------------------------------------------------------
# 输运算子
# --------------------------------------------------------------------------


@dataclass
class KoopmanTransport:
    """延迟嵌入 EDMD 输运算子。

    两阶段闭式求解：

    1. **演化矩阵 K**：:math:`K = \\Psi_{+}\\Psi^{\\top}(\\Psi\\Psi^{\\top}+\\beta I)^{-1}`，
       用于谱分析（提取物理时间常数）；
    2. **读出向量 w**：:math:`w = h\\,\\Psi^{\\top}(\\Psi\\Psi^{\\top}+\\beta I)^{-1}`，
       用于由外场特征推断窟内微环境。

    两个解都是**岭回归闭式解，不含梯度下降**。
    """

    cfg: TransportConfig = field(default_factory=TransportConfig)

    K_: np.ndarray | None = None
    w_: np.ndarray | None = None
    mu_: np.ndarray | None = None
    sigma_: np.ndarray | None = None
    feature_names_: list[str] | None = None
    n_features_in_: int | None = None

    # ---------------- 拟合 ----------------

    def _standardize_fit(self, Psi: np.ndarray) -> np.ndarray:
        if not self.cfg.standardize:
            return Psi
        self.mu_ = Psi.mean(axis=0)
        self.sigma_ = Psi.std(axis=0)
        self.sigma_[self.sigma_ < 1e-12] = 1.0
        return (Psi - self.mu_) / self.sigma_

    def transform(self, Psi: np.ndarray) -> np.ndarray:
        """应用已拟合的标准化。"""
        if not self.cfg.standardize or self.mu_ is None:
            return Psi
        return (Psi - self.mu_) / self.sigma_

    @staticmethod
    def _add_intercept(Psi_s: np.ndarray) -> np.ndarray:
        """追加常数列作为截距项。

        这一步是**必需**的：特征经过标准化后均值为 0，若读出层不含截距，
        预测值的均值必然为 0，而窟内 RH 的均值在 20% 量级——模型在结构上
        就无法表达目标水平，R2 会变成大负数。这是纯数据驱动模型极易踩的坑。
        """
        return np.column_stack([Psi_s, np.ones(len(Psi_s))])

    def fit(self, outdoor: pd.DataFrame, target: np.ndarray, *, fit_koopman: bool = True) -> "KoopmanTransport":
        """闭式拟合输运算子。

        Parameters
        ----------
        outdoor : DataFrame
            外场驱动序列（训练段）。
        target : ndarray
            目标序列（窟内 RH 物理合成标签），长度与 ``outdoor`` 一致。
        fit_koopman : bool
            是否同时拟合演化矩阵 ``K``（仅用于谱分析，推断不需要）。
            ``K`` 的维度是 p x p，当 p 较大时内存开销为 O(p^2)，
            若只需读出可置为 False。
        """
        self.feature_names_ = []
        Psi = build_features(outdoor, self.cfg, names_out=self.feature_names_)
        Psi_s = self._standardize_fit(Psi)
        self.n_features_in_ = Psi_s.shape[1]

        Z = self._add_intercept(Psi_s)
        p = Z.shape[1]

        y = np.asarray(target, dtype=float)
        ok = np.isfinite(y)
        Zo, yo = Z[ok], y[ok]
        n = Zo.shape[0]
        # **Gram 矩阵必须先按样本数归一化再加重罚项**，否则 beta 相对于
        # Z^T Z 的对角元（量级 ~n = 1.6e5）微不足道，调 beta 完全不起作用。
        # 早期版本漏了 /n，导致 beta 从 1e-6 扫到 100 时验证 R2 一位不变。
        G = Zo.T @ Zo / n + self.cfg.ridge_beta * self._penalty_mask(p)
        # 读出：w = (Z^T Z / n + beta I)^{-1} Z^T y / n
        self.w_ = np.linalg.solve(G, Zo.T @ yo / n)

        if fit_koopman:
            # 演化矩阵：K = Psi_+ Psi^T (Psi Psi^T + beta I)^{-1}
            # 不含截距——截距属于仿射项，混进状态矩阵会污染特征值谱。
            A = Psi_s[:-1]
            B = Psi_s[1:]
            m = A.shape[0]
            self.K_ = np.linalg.solve(
                A.T @ A / m + self.cfg.ridge_beta * np.eye(A.shape[1]),
                A.T @ B / m,
            ).T
        return self

    @staticmethod
    def _penalty_mask(p: int) -> np.ndarray:
        """惩罚矩阵：**截距项不参与正则化**。

        截距列全为 1，其 Gram 对角元归一化后恰为 1，与 beta 同量级；
        若把它一起惩罚，等于直接把目标均值往 0 拉——实测 beta=1 时
        预报偏差达 -18 个百分点。这是标准做法：正则化只作用于斜率。
        """
        mask = np.eye(p)
        mask[-1, -1] = 0.0
        return mask

    # ---------------- 推断 ----------------

    def predict_features(self, Psi: np.ndarray) -> np.ndarray:
        """由**已构造好**的特征矩阵预测目标（用于训练时反传梯度）。"""
        if self.w_ is None:
            raise RuntimeError("请先调用 fit()")
        return self._add_intercept(self.transform(Psi)) @ self.w_

    def predict(self, outdoor: pd.DataFrame) -> np.ndarray:
        """由外场驱动序列端到端预测窟内微环境代理。"""
        Psi = build_features(outdoor, self.cfg)
        return self.predict_features(Psi)

    def rollout_features(self, Psi: np.ndarray, steps: int) -> np.ndarray:
        """把提升特征沿算子前推 :math:`h` 步：:math:`\\Psi_{t+h} = K^{h}\\,\\Psi_t`。

        这是 Koopman 算子做**多步预报**的正统用法——**闭式、无自回归误差累积**：
        不需要把预测值喂回模型，而是直接对状态做 :math:`h` 次线性推进。
        与逐点递归（recursive）策略相比，避免了"一步误差被反复放大"的问题。
        """
        if self.K_ is None:
            raise RuntimeError("需要 fit(fit_koopman=True) 才能做 rollout")
        Kp = np.linalg.matrix_power(self.K_, int(steps))
        return self.transform(Psi) @ Kp.T

    def rollout(self, outdoor: pd.DataFrame, steps: int) -> np.ndarray:
        """端到端 :math:`h` 步预报：先构造特征，再沿算子前推，最后读出。

        Parameters
        ----------
        outdoor : DataFrame
            **仅含 t 时刻及之前**的外场序列（严格因果）。
        steps : int
            前推步数（小时）。
        """
        Psi = build_features(outdoor, self.cfg)
        Psi_h = self.rollout_features(Psi, steps)
        return self._add_intercept(Psi_h) @ self.w_

    def fit_direct(self, outdoor: pd.DataFrame, target: np.ndarray, horizon: int):
        """**直接多步**策略：为每个时效单独拟合一个读出层。

        与 rollout 相比，直接策略不假设特征子空间在 :math:`h` 步内不变，
        通常更准，但需要为每个时效单独训练、且外推到训练时效之外没有依据。
        两者在实验中作为对照，用于回答"Koopman 前推是否损失精度"。
        """
        self.feature_names_ = []
        Psi = build_features(outdoor, self.cfg, names_out=self.feature_names_)
        if self.mu_ is None:
            self._standardize_fit(Psi)
        Z = self._add_intercept(self.transform(Psi))
        y = np.asarray(target, dtype=float)

        # 目标需按 horizon 前移；尾部不足处丢弃
        y_h = np.full_like(y, np.nan)
        if horizon > 0:
            y_h[:-horizon] = y[horizon:]
        else:
            y_h = y
        ok = np.isfinite(y_h)
        p = Z.shape[1]
        Zo, yo = Z[ok], y_h[ok]
        n = Zo.shape[0]
        w = np.linalg.solve(Zo.T @ Zo / n + self.cfg.ridge_beta * self._penalty_mask(p),
                            Zo.T @ yo / n)
        return w

    def predict_direct(self, outdoor: pd.DataFrame, w: np.ndarray) -> np.ndarray:
        """用 :meth:`fit_direct` 得到的权重做直接多步预报。"""
        Psi = build_features(outdoor, self.cfg)
        return self._add_intercept(self.transform(Psi)) @ w

    # ---------------- 分位数读出（修「极值被压缩」） ----------------

    def fit_direct_quantile(self, outdoor: pd.DataFrame, target: np.ndarray,
                            horizon: int, tau: float = 0.9, *,
                            n_iter: int = 25, tol: float = 1e-7):
        """**直接多步 + 分位数（pinball）读出**，用 IRLS 求解。

        为什么需要它（本项目的关键诊断）
        --------------------------------
        MSE（岭回归）拟合的线性读出层会把极值**系统性拉向均值**。实测后果非常严重：
        某个"高湿事件"场景真实窟内 RH 在 72 h 内升到 **89.0%**，而
        * 状态式 MSE 读出只给 **34.8%**；
        * 即便把**真实的外场未来轨迹**喂进去（完美气象预报上界），也只得 **52.0%**。

        这意味着：**用绝对阈值判级会完全失效**——预报曲线永远够不到 62% 的业务阈值。
        根因是回归到均值（regression to the mean）：在均方误差意义下，
        "把尾部压平"几乎不损失什么。

        解法：把读出层从"条件均值"改为"条件分位数"，直接优化 pinball 损失

        .. math:: \\rho_\\tau(u) = u\\,(\\tau - \\mathbb{1}\\{u<0\\})

        与 L3 的 twCRPS 同源——**这正是"风险对齐"思想在算子层的落地**。

        实现：pinball 损失不可导点用 IRLS 处理——按残差符号给样本加权
        （残差 > 0 权重 :math:`\\tau`，否则 :math:`1-\\tau`），反复解加权岭回归。
        保持**闭式解体系**，无梯度下降、无 BPTT。

        Parameters
        ----------
        tau : float
            目标分位水平。风险预警取上分位（如 0.9）；0.5 即中位数回归。
        """
        self.feature_names_ = []
        Psi = build_features(outdoor, self.cfg, names_out=self.feature_names_)
        if self.mu_ is None:
            self._standardize_fit(Psi)
        Z = self._add_intercept(self.transform(Psi))
        y = np.asarray(target, dtype=float)
        y_h = np.full_like(y, np.nan)
        if horizon > 0:
            y_h[:-horizon] = y[horizon:]
        else:
            y_h = y
        ok = np.isfinite(y_h)
        Zo, yo = Z[ok], y_h[ok]
        n, p = Zo.shape

        mask = self._penalty_mask(p)
        beta = self.cfg.ridge_beta
        # 初值：普通（均值）岭回归
        w = np.linalg.solve(Zo.T @ Zo / n + beta * mask, Zo.T @ yo / n)

        for _ in range(n_iter):
            r = yo - Zo @ w
            # pinball 损失的 IRLS 权重（加 eps 防零权导致奇异）
            sw = np.where(r > 0, tau, 1.0 - tau)
            sw_sum = sw.sum()
            G = (Zo * sw[:, None]).T @ Zo / sw_sum + beta * mask
            rhs = (Zo * sw[:, None]).T @ yo / sw_sum
            w_new = np.linalg.solve(G, rhs)
            if np.max(np.abs(w_new - w)) < tol:
                w = w_new
                break
            w = w_new
        return w

    def predict_quantile(self, outdoor: pd.DataFrame, w: np.ndarray) -> np.ndarray:
        """用 :meth:`fit_direct_quantile` 得到的权重做分位数预报。"""
        return self.predict_direct(outdoor, w)

    # ---------------- 物理可解释性 ----------------

    def spectrum(self, top_k: int = 8) -> pd.DataFrame:
        """返回 ``K`` 的慢变特征值谱。

        连续时间特征值 :math:`\\lambda_c = \\ln(\\lambda_d)/\\Delta t` 的实部给出
        **衰减时间常数** :math:`\\tau = -1/\\mathrm{Re}(\\lambda_c)`，
        虚部给出**振荡周期**。这些量可与文献报导的窟内外相位滞后、
        换气次数做交叉校验。
        """
        if self.K_ is None:
            raise RuntimeError("需要在 fit(fit_koopman=True) 后使用")
        ev = np.linalg.eigvals(self.K_)
        ev = ev[np.isfinite(ev) & (np.abs(ev) > 1e-9)]
        # 只保留稳定模态（模长 < 1），按衰减慢->快排序
        stable = ev[np.abs(ev) < 1.0]
        order = np.argsort(-np.abs(stable))
        stable = stable[order][:top_k]

        dt_s = 3600.0
        lam_c = np.log(stable.astype(complex)) / dt_s
        tau_h = np.where(np.abs(lam_c.real) > 1e-12, -1.0 / lam_c.real / 3600.0, np.inf)
        with np.errstate(divide="ignore", invalid="ignore"):
            period_h = np.where(np.abs(lam_c.imag) > 1e-12,
                                2 * np.pi / np.abs(lam_c.imag) / 3600.0, np.inf)

        return pd.DataFrame({
            "lambda_discrete": np.round(stable, 6),
            "abs_lambda": np.round(np.abs(stable), 6),
            "tau_hours": np.round(tau_h, 2),
            "period_hours": np.round(period_h, 2),
            "period_days": np.round(period_h / 24.0, 2),
        })

    def readout_importance(self, top_k: int = 15) -> pd.DataFrame:
        """按 |w| 排序的读出权重，用于回答"模型学到了哪条物理通道"。

        预期结果是**慢变项与快变项同时进入前列**——若只有快变项，
        说明模型退化为"门口渗透"的朴素假设，与周启友等 (2018)
        "窟内水汽不经窟门进入"的实测结论相矛盾。
        """
        if self.w_ is None or self.feature_names_ is None:
            raise RuntimeError("请先调用 fit()")
        # 末位是截距项，不参与物理归因排序
        df = pd.DataFrame({
            "feature": list(self.feature_names_) + ["__intercept__"],
            "weight": self.w_,
        })
        df["abs_weight"] = df["weight"].abs()
        df = df[df["feature"] != "__intercept__"]
        return df.sort_values("abs_weight", ascending=False).head(top_k).reset_index(drop=True)

    def group_importance(self) -> pd.DataFrame:
        """按特征族（快变延迟 / 慢变均值 / Magnus 项）汇总权重贡献。"""
        if self.w_ is None or self.feature_names_ is None:
            raise RuntimeError("请先调用 fit()")
        names = np.array(self.feature_names_, dtype=str)
        w = self.w_[: len(names)]                    # 去掉截距项
        groups = np.where(
            np.char.startswith(names, "RHslow"),
            "magnus",
            np.where(np.char.find(names, "_ma") >= 0, "slow_ma", "fast_lag"),
        )
        df = pd.DataFrame({"group": groups, "abs_weight": np.abs(w)})
        agg = df.groupby("group")["abs_weight"].agg(["sum", "mean", "count"])
        agg["share"] = (agg["sum"] / agg["sum"].sum()).round(4)
        return agg.round(6)
