# 莫高窟「窟外气象 → 窟内微环境」标定参数提取

> 提取方式：**实际抓取全文**。两篇均为 Open Access。
> - Gong et al. 2025：`https://www.nature.com/articles/s40494-025-01740-9`（HTML 正文 + PDF，14 页，全文可读）
> - Zhao et al. 2026（通风）：`https://www.nature.com/articles/s40494-026-02955-0`
>   ⚠️ 该文是 **"Article in Press"（early release 接受稿）**，其 nature.com **HTML 落地页只有摘要，没有正文**；
>   正文只在 PDF（`..._reference.pdf`，19 页）中。本报告数据全部取自 PDF 正文。
> 原文引文保留英文原样（含原文排版导致的 `ﬁ`/`ﬂ` 连字、换行断字）。凡原文没有的，一律写「未报告」。

---

## 表 1：Gong et al. 2025（npj Heritage Sci. 13:173）提取结果 —— 研究对象为**第 71 窟**

| 字段 | 数值 | 单位 | 图号/表号 | 原文英文证据句 |
|---|---|---|---|---|
| **窟内外 RH 相位差（≥24 h 尺度）** | **π/4**（=1/8 个周期） | rad（相位） | Fig. 11a,b（WTC 小波相干谱） | "These spectra reveal a significant correlation between the internal and external humidity on **scales of 24 h and above, with a phase difference of π/4**, suggesting that **external humidity leads internal humidity by ~1/8 of a cycle**." |
| 同上（结论复述） | 滞后 = 1/8 周期（**原文未折算为小时**） | cycle | 结论 (2) | "External humidity impacts the caves over **cycles of 24 h or longer, exhibiting a lag of 1/8 of a cycle**." |
| **窟内外 RH 相干性：≥24 h** | 显著相关（只有 0.05 显著性判据，**无相干系数数值**） | — | Fig. 11a,b | "a significant correlation between the internal and external humidity on scales of 24 h and above" |
| **窟内外 RH 相干性：<24 h** | 2019（开放）**显著低于** 2020（关闭）；**具体数值未报告** | — | Fig. 11a vs 11b | "For periods shorter than 24 h, the correlation between internal and external humidity in Cave 71 was **significantly lower in 2019 compared to 2020**… in 2019, the cave was open daily, and the introduction of moisture by a large influx of tourists caused fluctuations in internal humidity, diminishing the correlation with external conditions." |
| **降雨期相干性** | 高相干区 **5 月 5–8 日 / 尺度 12–48 h**；近乎**同相**（无滞后） | h | Fig. 11c,d（XWT） | "High-intensity regions in both years predominantly occurred from **May 5 to 8 on scales of 12–48 h**, coinciding with the rainfall period. In the highest-intensity areas, the relative humidity fluctuations inside and outside the cave were **nearly in phase**, indicating a strong positive correlation with **minimal lag effect**." |
| **CO₂–RH 相干性（游客代理）** | 2019：周期 **≤6 h** 显著相关，且**同相无滞后**；2020：无显著相关 | h | Fig. 12a,b | "In 2019, a significant correlation was observed between CO₂ levels and relative humidity, particularly for **periods of 6 h and below**… The synchronous changes in CO₂ concentration and relative humidity were **in phase, indicating a direct correlation without any lag**. Conversely, in 2020, **no significant correlation** was observed due to the absence of visitors." |
| **游客影响的 RH 频带** | **≤6 h** 显著，**≤2 h** 最强 | h | Fig. 10a, Fig. 12c,d | "The response of indoor relative humidity to visitor activity is most pronounced on **cycles of 6 h and shorter, with a particularly strong correlation at scales of 2 h and shorter**." |
| **窟内 RH 年均值 / 范围（2019–2021）** | 均值 **30.8**；范围 **8.7 – 80.0** | % | Results 统计节 | "The **average annual relative humidity inside the cave is 30.8%, with a range from 80.0% to 8.7%**." |
| 窟外 RH 年均值 / 范围（对照） | 均值 29.1；范围 0.5 – 99.3 | % | Results 统计节 | "The average annual relative humidity is 29.1%, with fluctuations between 99.3% and 0.5% over the three years." |
| **窟内月均 RH 峰值** | **48.6**（2019 年 7 月；当月降雨 37.8 mm，三年最高） | % | Fig. 5a | "In **July 2019**, the Mogao Caves recorded 37.8 mm of rainfall, the highest in three years, corresponding with the **peak monthly average relative humidity inside the cave at 48.6%**." |
| **窟内月均 RH（2020-07 vs 2021-07）** | **38.3 → 44.0**（+5.7） | % | Fig. 5b,c | "in July 2020, when the number of visitors to the Mogao Caves reached **145,200**, the average relative humidity inside Cave 71 stood at **38.3%**. In 2021, the visitor count increased to **534,100**, and the average relative humidity rose to **44.0%, an increase of 5.7%**." |
| 同期窟外 RH（对照） | 25.2 → 27.5（仅差 2.3） | % | Fig. 5b,c | "By contrast, the outdoor relative humidity during these periods only differed by 2.3%: **25.2% in 2020 and 27.5% in 2021**." |
| **窟内月均 RH（2020-08 vs 2021-08）** | **36.1 → 33.6**（−2.5） | % | Fig. 5b,c | "In August 2020, with **250,200** visitors, the average indoor relative humidity was **36.1%**. In the following year, with a reduced count of **127,300** visitors, the indoor relative humidity **decreased by 2.5% to 33.6%**." |
| **窟内 RH 月际跃升（2020-04→05，降雨 9.2 mm）** | 窟内 **+10%**（相对增幅 45.33%）；窟外 +11.37%（相对增幅 ≈90%） | % | Results 统计节 | "In May, with 9.2 mm of rainfall, both indoor and outdoor relative humidity increased. Compared to April, the outdoor relative humidity rose by 11.37%, nearly a 90% increase, while the **indoor relative humidity increased by 10%, representing a 45.33% rise**." |
| **季节规律（定性，无逐月数值）** | 春夏窟内 T 低于窟外、RH 高于窟外并延续至 9 月；10 月–2 月窟内 T 高于窟外、RH 低于窟外 | — | Fig. 4d–f, Fig. 5 | "During the warmer months of spring and summer, the internal temperature of the cave remains lower than outside, while the **relative humidity inside is higher, continuing into September**… **From October to February, the cave's temperature is notably higher than outside, while the humidity is lower**."（逐月箱线图数值仅在 Fig. 4 图中，正文未列表） |
| **游客对窟内 T 的影响** | 日最高温 **+1.4 °C**；日较差 **+1.4 °C** | °C | Fig. 9（DWT 8 级分解） | "we calculated the **highest temperature of the day to be 16.6 °C, with a daily range of 2.8 °C**. In contrast, the **actual highest temperature recorded inside the cave that day was 18 °C, with a daily range of 4.2 °C**, suggesting that **visitor presence increased the maximum temperature by 1.4 °C and also heightened the temperature amplitude by 1.4 °C**." |
| 游客影响的 T 频带 | **≤8 h**，集中于 **8 A.M.–9 P.M.** | h | Fig. 8, Fig. 9d–k | "in addition to significant daily periodic fluctuations, the year 2019 showcased a distinct high-energy region at **higher frequency scales (periods of 8 h and below)** predominantly during the **daytime hours of 8 A.M. to 9 P.M.**" |
| **游客对窟内 RH 的影响（常态日，2019-05-01）** | 峰值 **+11.4%**（34.6 → 46.0）；日较差 **+12.4%**（7.6 → 20.0） | %（RH 百分点） | Fig. 13（DWT） | "The **calculated highest relative humidity on this day was 34.6%, with a daily range of 7.6%**. In contrast, the **actual highest relative humidity recorded inside the cave was 46%, with a daily range of 20%**. This discrepancy indicates that the opening of the cave and visitor presence contributed to an **11.4% increase in relative humidity and a 12.4% increase in humidity amplitude**." |
| 归属频带（常态日） | Fig. 13**e–k** 段（4–2 h → 4–2 min）为游客/开门贡献；Fig. 13c,d 为基线 | — | Fig. 13 | "On May 1, the relative humidity signal influenced by the opening of the cave and visitor activity is primarily represented by the components in **Fig. 13e–k**. Thus, the signals in Fig. (c, d) serve as the baseline unaffected by external interference." |
| **游客对窟内 RH 的影响（降雨日，2019-05-06）** | 峰值 **+5.9%**（68.1 → 74.0）；日较差 **+6.4%**（29.6 → 36.0） | % | Fig. 13 | "The **highest relative humidity on this day was calculated at 68.1%, with a daily range of 29.6%**. Meanwhile, the **actual highest relative humidity observed was 74%, with a daily range of 36%**. This data suggests that visitor presence elevated the relative humidity inside the cave **by 5.9% and the humidity amplitude by 6.4%**." |
| **降雨 vs 游客：降雨更强** | 降雨使 RH 平均 **+23.9%**；剔除游客后降雨单独造成峰值 **+33.5%**、振幅 **+22%** | % | Results / 结论 (3) | "Comparing conditions on May 6 (a rainy day) to May 1, it is evident that **rainfall contributed to an average relative humidity increase of 23.9%**. **Excluding the impact of visitor presence, rainfall alone led to a 33.5% increase in the peak relative humidity and a 22% increase in the humidity amplitude**." |
| 同上下载结论句 | 降雨 > 游客 | — | 结论 (3) | "During rainfall, the **amplitude of relative humidity inside the cave escalates by over 20%, surpassing the impact from visitors alone**." |
| 同上（贡献声明） | 降雨影响更显著 | — | 引言贡献 (1) | "demonstrating that both rainfall events and visitor activities influence the cave's relative humidity, **with rainfall exerting a more significant effect**." |
| **关门对湿气侵入的抑制** | 关门使窟内峰值 RH 比开门时**低约 20%** | % | Discussion | "When the cave door is closed, although internal relative humidity continues to rise, the door substantially impedes moisture ingress, **reducing peak relative humidity inside the cave by about 20% compared to when the door is open**." |
| 关闭年降雨日对照（2020-05-06，封窟） | 日均 44.2%，比 5/1 高 26%，振幅仅 +1%；相对 2019-05-06 日均 −9.2%、振幅 −29%、峰值仍低 20% | % | Results | "the **average daily relative humidity inside the cave on May 6, 2020, was 44.2%, 26% higher than on May 1, but the humidity amplitude increased by only 1%**. Relative to the actual conditions on May 6, 2019, the **average daily value decreased by 9.2%, and the amplitude decreased by 29%**. Even after accounting for the impact of visitor presence, **the peak relative humidity was still 20% lower**." |
| **游客呼吸排汗贡献的湿量占比** | **约 5%** —— ⚠️ **本文为转引 Demas et al.（ref 30），非本文实测** | % | Introduction（引文段） | "**They** discovered that high humidity levels in the caves primarily resulted from the intrusion of humid or rainy outside air during visitor entry. In the studied caves, **visitors contribute only about 5% of moisture through breath and perspiration**."（"They" = Demas et al.³⁰） |
| **第 71 窟几何** | 窟+龛合计面积 **~18 m²**；体积 **~67 m³**；壁画 **~51 m²**；塑像 **5 尊**；铝合金门 **3.78 m²**（东壁，唯一开口，无机械通风） | m², m³ | Methods / 图 2 | "The **combined area of the cave and the niche is ~18 m², and the volume is around 67 m³**. The cave houses **~51 m² of murals and five statues**. An **aluminum door, measuring 3.78 m²**, is installed on the east wall and serves as the **sole entry for visitors and the primary means of natural ventilation**, given the absence of mechanical ventilation systems." |
| 监测配置 | 窟内 3 个温湿度记录仪（佛龛前 / 东南角 / 西北角），**1 min** 间隔；CO₂ 记录仪（佛龛前）1 min；窟外自动气象站 **<3 m**，**10 min** 间隔 | — | Fig. 3, Methods | "wireless temperature and relative humidity data loggers were strategically positioned at three locations: **in front of the Buddha niche, in the southeast corner, and in the northwest corner**… the data loggers were programmed to **sample every minute**… An automatic weather station situated **just outside the cave** gathers external data… **at 10-min intervals**." |
| 仪器精度 | T ±0.3 °C（−30…+75 °C）；RH ±2%（20–90%）；CO₂ ±3%（0–5000 ppm） | — | Methods | "temperature and humidity sensors (model WEMS400-HT) with an accuracy of **±0.3 °C**… and **±2% (from 20% to 90%)** for relative humidity. The CO₂ data logger (model WEMS400-CO₂) has an accuracy of **±3% (from 0 ppm to 5000 ppm)**." |
| 数据年份 | 2019 – 2021；封窟期 **2020-01-24 → 2020-05-10** | — | Methods | "The closure of the Mogao Caves due to the COVID-19 pandemic **from January 24, 2020, to May 10, 2020**… This study utilizes observational data collected **from 2019 to 2021**." |
| 单日窟内外 RH 差（2019-10-21，洞内外差最小） | 关门时段均值差 **2.62%**；开门 09:00–18:00 均值差 **7.20%** | % | Fig. 7a | "on October 21, 2019, during the closed periods from 00:00 to 09:00 and 18:00 to 24:00, the **average humidity difference between the inside and outside of the cave was only 2.62%**. However, when the cave door was open for visitors from 09:00 to 18:00, **this difference increased to an average of 7.20%**." |
| 单日窟内外 RH 差（2019-10-16，窟外高湿 + 小雨 0.2 mm） | 开门前均值差 **10.66%**；0.2 mm 小雨使窟外 RH 40%→70%，窟内 **+15%** 至 >50%；18:00 后窟内外最大差 **29.10%**，**关门**状态下窟内仍 **+10%** | % | Fig. 7b | "the external relative humidity surged from approximately **40% before the rain to 70%**… This resulted in a **rapid 15% increase in the cave's relative humidity, pushing it above 50%**… the **difference in relative humidity between the outdoors and inside the cave reached a maximum of 29.10%**. **Although the cave door was closed**, this substantial humidity gradient still caused an **approximately 10% increase in internal humidity**." |
| 单日窟内外 RH 差（2019-07-15，窟内高于窟外） | 00:00–09:00 均值差 **12.74%**；白天最大差 **25%**；窟内 44%→36%（开门前→关门）；11:30 CO₂ 峰值时窟内 RH 达当日最高、比开门前 **+14%**；全天平均差 **7.37%** | % | Fig. 7c | "the relative humidity was at its daily peak but still lower than the cave's, with an **average difference of 12.74%**… creating a **humidity difference of up to 25%**. Correspondingly, the cave's relative humidity gradually **dropped from 44% before opening to 36% by the time the door was closed**… At around 11:30, CO₂ levels peaked for the day… the cave's **relative humidity also reached its highest point of the day, rising by ~14% compared to pre-opening levels**… The **average relative humidity difference between the inside and outside of the cave reached 7.37%**." |
| 第 71 窟 5/1 温度统计表 | 2019-05-01：窟外 Max 27.3 / Min 12.09 / Avg 19.89 / SD 5.13；窟内 Max **18.0** / Min 13.8 / Avg 14.95 / SD **1.07**。2020-05-01：窟外 Max 33.67 / Min 15.13 / Avg 24.15 / SD 5.82；窟内 Max **14.0** / Min 13.2 / Avg 13.62 / SD **0.30** | °C | **Table 1** | "Table 1 \| Statistical analysis of temperature data outside and inside Cave 71 on May 1, 2019, and May 1, 2020"（表中仅温度，**无 RH 统计表**） |
| **换气次数 ACH** | **未报告**（Gong et al. 2025 全文不含 ACH / 通风量） | — | — | 全文检索无 "air change" / "ventilation rate" 实测值 |

---

## 表 2：npj HS 2026 通风论文（Zhao et al.）提取结果

### 表 2a：**Table 4** —— 12 个洞窟，**开门状态、1 月（冬季）**，由「门口法向风速 × 有效开口面积」积分换算（**非** CO₂ 示踪）

| 洞窟编号 | **ACH 开门 (/h)** | **ACH 关门 (/h)** | 通风量 (m³/s) | Ar | 入口风速 (m/s) | 窟内 T (°C) | 窟内 RH (%) | 窟外 T (°C) | 窟外 RH (%) |
|---|---|---|---|---|---|---|---|---|---|
| 100 | **2.16** | 未报告 | 0.79 | 0.35 | 0.65 | −3.5 | 40.7 | −6.3 | 55.3 |
| 217 | **9.68** | 未报告 | 0.63 | 0.64 | 0.50 | −1.6 | 37.9 | −4.5 | 50.5 |
| 219 | **43.85** | 未报告 | 0.27 | 0.70 | 0.35 | −2.2 | 40.3 | −4.3 | 50.8 |
| 148 | **2.03** | 未报告 | 1.16 | 0.96 | 0.55 | −4.7 | 40.4 | −8.6 | 49.2 |
| 138 | **0.59** | 未报告 | 0.47 | 1.29 | 0.35 | −2.1 | 38.7 | −5.1 | 49.9 |
| 150 | **5.89** | 未报告 | 0.68 | 1.10 | 0.50 | 1.4 | 33.8 | −3.4 | 45.0 |
| 285 | **8.08** | 未报告 | 0.69 | 0.99 | 0.55 | −4.0 | 46.7 | −9.4 | 47.7 |
| 445 | **9.82** | 未报告 | 0.41 | 1.41 | 0.38 | 1.5 | 36.6 | −3.1 | 41.8 |
| 45 | **12.42** | 未报告 | 0.57 | 1.73 | 0.45 | −3.5 | 31.4 | −9.8 | 49.8 |
| 46 | **13.11** | 未报告 | 0.51 | 0.10 | 0.35 | −2.3 | 37.8 | −2.5 | 33.8 |
| 209 | **5.77** | 未报告 | 0.49 | 1.17 | 0.42 | 0.1 | 34.8 | −3.9 | 49.9 |
| 206 | **8.30** | 未报告 | 0.41 | 0.24 | 0.45 | 0.2 | 36.8 | −0.9 | 38.6 |

原文句（表头与位置）：
> "**Table 4 | Summary of experimental results in the vertical direction of cave doors**"
> 列名（按 PDF 坐标核实）：`Cave No.` | `Outside temperature °C` | `Outside humidity %` | `Entrance velocity m/s` | `Inside temperature °C` | `Inside humidity %` | `Ar number` | `Ventilation rate m3/s` | `Air change rate`
> "The measured wind velocity at measuring point 1 in the vertical section of the cave door, the calculated Archimedes numbers, ventilation rates, and **air change rates for the twelve caves are summarized in Table 4**."
> 换算方法（Fig. 19 图注）："The **ventilation rate was calculated from measured normal air velocities integrated over the effective doorway area**, and the temperature difference represents the absolute value of the indoor minus outdoor air temperature recorded during each experimental condition."

> ⚠️ **12 个洞窟的 ACH 不是 CO₂ 示踪结果**。CO₂ 示踪只做了 **第 45、46 窟**（见下表 2c）。

### 表 2b：**Table 5** —— 开门角度/宽度控制实验（**1 月**，一维风速积分法）

| 洞窟 | 工况 | 开口 | 通风量 (m³/s) | **ACH (/h)** |
|---|---|---|---|---|
| 46（双扇铝合金门） | C46-1 | 1.0 m | 0.13 | **6.71** |
| 46 | C46-2 | 0.8 m | 0.07 | **3.65** |
| 46 | C46-3 | 0.6 m | 0.05 | **2.25** |
| 46 | C46-4 | 0.4 m | 0.02 | **0.86** |
| 46 | C46-5 | 0.2 m | 0.005 | **0.16** |
| 46 | C46-6 | 0 m（全关） | 0 | **0** |
| 445（单扇铝合金门） | C445-1 | 90° | 0.18 | **3.38** |
| 445 | C445-2 | 60° | 0.07 | **1.90** |
| 445 | C445-3 | 45° | 0.03 | **0.73** |
| 445 | C445-4 | 30° | 0.005 | **0.20** |
| 445 | C445-5 | 0°（全关） | 0 | **0** |

原文句：
> "In Cave 46, reducing the **opening width from 1.0 m to 0 m** caused the ventilation rate to **decrease from 0.13 m³/s to 0** and the **air change rate to drop from 6.71/h to 0**. In Cave 445, decreasing the **door opening from 90° to 0°** reduced the ventilation rate **from 0.18 m³/s to 0** and the **air change rate from 3.38/h to 0**. The reduction was strongly **nonlinear**."
> "Notably, the **neutral plane always exists stably regardless of variations in cave door opening degree**, demonstrating that natural ventilation as regulated by door opening degree as a management variable is **consistently dominated by thermal buoyancy**."

### 表 2c：**Table 7** —— CO₂ 示踪衰减法，**开门**，1 月 vs 9 月，各重复 2 次

| 洞窟 | 主室体积 (m³) | 月份/次数 | 窟内外温差 ΔT (K) | 窟外风速 (m/s) | **ACH (/h)** | 绝对换气量 (m³/h) |
|---|---|---|---|---|---|---|
| 45 | 82.24 | Jan. 1st | 3.58 | 4.61 | **12.97** | 1066.65 |
| 45 | 82.24 | Jan. 2nd | 2.48 | 2.68 | **10.88** | 894.77 |
| 46 | 70.40 | Jan. 1st | 3.72 | 1.58 | **13.61** | 958.14 |
| 46 | 70.40 | Jan. 2nd | 3.67 | 1.75 | **13.20** | 929.28 |
| 45 | 82.24 | Sep. 1st | −1.52 | 2.46 | **9.46** | 777.99 |
| 45 | 82.24 | Sep. 2nd | −1.73 | 2.34 | **10.73** | 882.43 |
| 46 | 70.40 | Sep. 1st | −2.54 | 2.20 | **10.92** | 768.76 |
| 46 | 70.40 | Sep. 2nd | −1.65 | 1.69 | **8.90** | 626.56 |

原文句：
> "In January, the **air exchange rates were 12.97 and 10.88/h for Cave 45 and 13.61 and 13.20/h for Cave 46**. In September, the corresponding values were **9.46 and 10.73/h for Cave 45 and 10.92 and 8.90/h for Cave 46**. The fitted coefficients of determination were all high, with the **lowest R² value being 0.8768** and the others generally above 0.90."

### 表 2d：**关门（infiltration）ACH** —— 全篇仅 **1 个洞窟、1 次**实测

| 洞窟 | 状态 | ACH (/h) | 初始 CO₂ (ppm) | 回到本底所需时间 | R² | 洞口/主室风速 |
|---|---|---|---|---|---|---|
| **45** | **关门，1 月** | **1.59 ± 0.03** | 4159（混合后） | **约 230 min** | 0.9078 | 均 **<0.005 m/s** |

原文句：
> "Starting from an **initial concentration of 4159 ppm** after mixing, the cave required approximately **230 min to return to the background level**. The log-linear regression yielded an **air exchange rate of 1.59 ± 0.03/h with an R² of 0.9078**. Compared with the open-door condition, the ventilation capacity under door-closed infiltration was therefore **reduced by nearly an order of magnitude**."
> "Under this condition, air velocity at both the doorway and the main chamber was **extremely weak, generally below 0.005 m/s**, although slightly more fluctuation was observed near the doorway because of **leakage through joints, louvers, and frame gaps**."
> 摘要："Open-door air exchange rates reach **9–13/h**, whereas closed-door infiltration drops to **1.6/h**."

> ⚠️ 摘要的 "1.6/h" **只来自第 45 窟、1 月的一次实验**，不是 12 窟的普遍关门值。

### 表 2e：几何信息（**Table 1** —— 12 个实验窟）

列名（原文）：`Cave No.` | `Type` | `Main Chamber area` | `Main chamber height` | `Main chamber cross-section area (width × height)` | `Passage cross-section area` | `Passage depth` | `Depth of front chamber` | `Cave gate` | `Location`

| 洞窟 | 类型 | 主室平面 (m×m) | 主室高 (m) | 主室断面 (宽×高, m×m) | 甬道断面积 (m²) | 甬道进深 (m) | 前室进深 (m) | 窟门 | 位置 |
|---|---|---|---|---|---|---|---|---|---|
| 100 | Large | 9.30 × 9.30 | 7.60 | 9.30 × 7.60 | 12.00 | 6.80 | 0 | 铝合金门 | South 1F |
| 217 | Medium | 5.00 × 5.00 | 5.00 | 5.00 × 5.00 | 3.00 | 1.40 | 0 | 铝合金门 | South 2F |
| 219 | Small | 2.60 × 1.50 | 2.90 | 2.60 × 2.90 | 1.44 | 1.50 | 0 | 铝合金门 | South 2F |
| 138 | Large | 12.60 × 15.60 | 8.10 | 12.60 × 8.10 | 10.50 | 4.00 | 3.9 | 传统木门 | South 1F |
| 148 | Large | 16.80 × 6.90 | 6.20 | 16.80 × 6.90 | 13.70 | 3.10 | 3.0 | 铝合金门 | South 2F |
| 150 | Large | 6.50 × 6.50 | 5.50 | 6.50 × 5.50 | 5.25 | 2.50 | 0 | 铝合金门 | South 2F |
| 285 | Medium | 6.60 × 6.15 | 4.10 | 6.60 × 4.10 | 2.42 | 1.37 | 0 | 铝合金门 | North 2F |
| 445 | Medium | 5.30 × 5.30 | 4.60 | 5.30 × 4.60 | 2.09 | 2.03 | 0 | 铝合金门 | North 4F |
| 45 | Medium | 4.50 × 4.50 | 4.00 | 4.50 × 4.00 | 3.68 | 1.42 | 0 | 铝合金门 | North 1F |
| 46 | Medium | 4.20 × 4.10 | 4.00 | 4.10 × 4.00 | 3.30 | 1.15 | 0 | 铝合金门 | North 1F |
| 209 | Small | 5.80 × 6.00 | 5.30 | 5.80 × 5.30 | 2.52 | 1.00 | 0 | 传统木门 | South 3F |
| 206 | Small | 4.30 × 4.40 | 4.80 | 4.30 × 4.80 | 3.30 | 1.20 | 0 | 铝合金门 | South 3F |

> 原文句："The detailed characteristic parameters for each experimental grotto are summarized in **Table 1**."
> **开口尺寸（门的宽×高、有效开口面积）在正文中未给出数值**，仅在 **Fig. 4**（尺寸图，图中标注，文本不可提取）中；正文唯一给出的开口尺寸是第 46 窟 **"The fully open width was 1.0 m."**
> 第 138 窟特殊："Among the twelve selected caves, **Cave 138 had wooden side windows** on both sides of the entrance door, whereas the remaining caves communicated with the exterior **only through the doorway**. In Cave 138, the side windows were kept almost completely closed during the experiments."
> 洞门形式普查："**Aluminum-alloy single-leaf doors represent the dominant configuration, accounting for 55.44% (270 caves)** of the surveyed population. **Traditional wooden doors comprise a small minority, with only 22 caves** in total."（Fig. 2）

### 表 2f：测量方法与测量时段

| 项目 | 内容 | 原文证据句 |
|---|---|---|
| **示踪气体** | **CO₂**（化学稳定、不可燃、不爆炸、便宜、易混合） | "**CO₂ was selected as the tracer gas** because it is chemically stable, non-flammable, non-explosive, inexpensive, and easy to mix with air under field conditions." |
| **方法** | **浓度衰减法（log-linear regression）** | "A **concentration decay method** was adopted because it is one of the most practical approaches for short-term ventilation assessment in enclosed spaces." |
| **计算式** | ln[C_excess(t)] = ln[C(0)] − λt；λ 取负斜率 | "C_excess(t) = C(t) – C_bg. The natural logarithm of the excess concentration was then regressed against elapsed time t (in hours)… **ln[Cexcess(t)] = ln[C(0)] – λt** yields the **air exchange rate λ directly from the negative slope**." |
| **换气次数定义** | λ = ACH (h⁻¹)；平均空气龄 **τ ≈ 1/λ** | "the **air exchange rate (AER, denoted λ) is expressed in air changes per hour (h⁻¹)**… Under the assumption of well-mixed conditions, the **mean air age of indoor air is approximately the reciprocal of the AER (τ ≈ 1/λ)**." |
| **仪器** | **TSI 7565** CO₂ 分析仪（±3.0% 或 ±50 ppm，0–5000 ppm，**1 min**）；**SWEMA 03+** 微风速仪（±0.03 m/s 或 ±3%，0.05–3 m/s，1 min）；Testo 175-H2 温湿度（±0.6 °C；±5% RH，15 min）；ST60XB 红外测温；WFWZY-1 全向风速仪；TBQ-2 总辐射表 | **Table 2** | "CO₂ concentration for tracer-gas decay experiments was monitored using a **TSI 7565 analyzer at 1 min intervals**." |
| **示踪剂注入/混合** | CO₂ 从主室中央释放；仅在注入混合阶段开风扇；**正式衰减测量前风扇全部关闭**；注入/混合阶段用塑料布临时封门缝 | "the release points of carbon dioxide were arranged at the **central position of the grotto main chamber**… fans were **only operated briefly during the CO₂ release and mixing stage**… **All fans were completely turned off before the formal concentration decay measurement commenced.**" / "**(2) close the door and temporarily seal the door-frame gaps with plastic sheets**" |
| **测点** | 主室几何中心、**离地 0.9 m**；另设垂向校核点 | "The main test point for CO₂ analysis was located in the **lower part of the geometric center of the main chamber, 0.9 m above the floor**." |
| **开门衰减试验对象** | **仅第 45、46 窟**；1 月与 9 月各 2 次；**无人状态（unoccupied）** | "Open-door experiments were carried out in **both January and September**, while a **closed-door infiltration experiment was additionally conducted in Cave 45 in January**." / "continuously record CO₂ concentration decay… **under unoccupied conditions**" |
| **衰减时长** | 1 月：45 窟 ~**18 min**（3851/3964 ppm→本底）；46 窟 ~**14 min**（4092/3877 ppm）；9 月：45 窟 ~**24 min**（3556/3727 ppm）；46 窟 ~**22 min**（3985/3926 ppm） | Results | "In January, CO₂ concentrations in Cave 45 decreased from approximately **3851 and 3964 ppm to background levels within about 18 min** in two repeated tests. In Cave 46, initial concentrations of **4092 and 3877 ppm decayed to background within approximately 14 min**. By contrast, in September, the decay process was slower: in Cave 45, concentrations of **3556 and 3727 ppm required about 24 min**… while in Cave 46, concentrations of **3985 and 3926 ppm required about 22 min**." |
| **测量时段** | **1 月 9–17 日** 与 **9 月 21–29 日**，两个季节campaign | "Field measurements were carried out in two phases: **9–17 January and 21–29 September**." |
| **测量年份** | ⚠️ **未报告**（全文未出现 campaign 年份） | — |
| **仪器布置点位** | 沿洞窟中轴、离地 **0.9 m**：门后 / 甬道中心 / 甬道–主室交界 / 主室中心；门口垂直线 **0.3 / 1.2 / 2.1 m** | "Four positions were selected: immediately behind the door, at the center of the corridor, at the junction between corridor and main chamber, and at the center of the main chamber." / "Three heights were selected: 0.3 m, 1.2 m, and 2.1 m above the floor." |
| **边界气象** | 窟外 T/RH/风速/风向/风压/太阳辐射（崖顶气象站，10 min）；洞口附近 T/RH（Testo 175-H2，15 min） | "Outdoor meteorological data were obtained from a weather station installed by the Dunhuang Academy on the cliff top above the grottoes… uploaded data at **10 min intervals**." |
| **大气压/密度** | 站点海拔 ~1138 m，P ≈ 89 kPa；ρ = 1.03–1.18 kg/m³；Δρ = 0.01–0.03 kg/m³ | "using the synchronously recorded temperature, atmospheric pressure (**~89 kPa at the site elevation of ~1138 m**)… **ρ ranged from 1.03 to 1.18 kg/m³, yielding Δρ values of 0.01–0.03 kg/m³**." |
| **季节气象背景** | 1 月窟外 T **−17.5 ~ 2.5 °C**；9 月 **12 ~ 33 °C**；年最高日间逼近 **36.5 °C**；年风速 0.1–5.2 m/s（多在 0.2–3.0）；盛行风 **SSE，年频率 41.7%**（洞口朝东 → 风与开口面斜交/近平行） | Fig. 8, Fig. 9 | "In January, outdoor air temperature fluctuated between approximately **−17.5 and 2.5 °C**, whereas in September it ranged from **12 to 33 °C**." / "The dominant annual wind direction was **SSE, with a frequency of occurrence of 41.7%**." |

### 表 2g：通风机制结论

| 结论 | 数值 | 原文证据句 |
|---|---|---|
| **单侧通风空间受限** | 主室中心/入口风速比 **0.08–0.35，平均 0.17** | "The velocity ratios between the main-chamber center and the entrance **ranged from 0.08 to 0.35 across the caves, with an average of 0.17**." |
| **沿进深温度递增** | 入口→主室中心温差 **1.8 – 5.2 °C** | "Air temperature increased with cave depth, with total temperature differences between the entrance and the main-chamber center **ranging from 1.8 to 5.2 °C**." |
| **门口双向交换流 + 中性面** | 下部 0.3 m 进风、上部 2.1 m 出风、**中性面约在 1.2 m 高度** | "inflow of colder external air at the lower level (**0.3 m**), outflow of warmer cave air at the upper level (**2.1 m**), and a flow-direction reversal near mid-height (**1.2 m**) corresponding to the **neutral plane**." |
| **驱动机制** | **热压（浮力）主导 + 风压叠加，混合控制（mixed-control）**；中性面在所有开度下稳定存在 | "The calculated **Archimedes numbers indicate that most experimental conditions fell within a mixed-control regime**, meaning that wind pressure and buoyancy acted together rather than independently." / "This pattern corresponds to a classic **bidirectional exchange flow with a neutral plane** and indicates that **indoor–outdoor temperature difference is a key driver** of ventilation in these caves." |
| **ΔT 与风的作用对比** | AER 随 **|ΔT| 近似线性** 增长；与风速关系更散、**非线性，拟合更差** | "the air exchange rate **increased approximately linearly with the absolute indoor–outdoor temperature difference**, whereas its relationship with outdoor wind speed was better represented by a **quadratic trend. The fit quality was lower for wind speed** than for temperature difference." |
| **分层（stratification）** | 入口/甬道 = **动态区**；主室 = **准静态区**（岩石热惯性缓冲） | "The entrance and corridor zones represent a **dynamic region** directly influenced by external climatic forcing, whereas the **main chamber acts as a quasi-static zone** buffered by the thermal inertia of the surrounding rock mass." |
| **开度阈值效应** | 开度低于某一范围后通风量**急剧非线性衰减至近零** | "Once the opening degree falls below a certain range, however, the **ventilation rate decreases much more rapidly and approaches a near-zero state**. This behavior suggests the presence of a **ventilation threshold**." |
| **与常规穿堂风不同** | 深窟单开口无法形成贯穿流 | "This pattern differs fundamentally from the **cross-ventilation mode** commonly observed in buildings with openings on opposite sides… **ventilation operates as a localized doorway exchange process rather than a whole-space air-renewal mechanism**." |
| **管理建议（时序）** | 温和天气（T 15–25 °C，RH 40–60%）可临时开门 **15–30 min** | "when the outdoor environment is mild (**temperature 15–25 °C, relative humidity 40–60%**) without severe fluctuations, the cave door can be **temporarily opened for 15–30 min** to accelerate indoor air renewal" |
| **方法学局限（对模型标定很重要）** | AER 是**全窟体平均**值；可能**低估入口区、高估主室**的换气 | "the tracer-gas decay method assumes a **well-mixed cave volume**, which is imperfectly satisfied… The reported AER values therefore represent a **bulk, cave-averaged renewal rate**, and may **underestimate local air renewal near the entrance while overestimating it in the main chamber**." |

### 表 2h：⚠️ 原文内部数据一致性问题（我为标定做的算术核查，非原文声明）

1. **Table 5 的"Volume"列与 Table 7 冲突**：Table 5 给第 46 窟 **82.24 m³**，但 Table 7 给第 46 窟 **70.40 m³**、第 45 窟 **82.24 m³**。
   Table 5 自身也不自洽：C46-1 的 0.13 m³/s ÷ 6.71 h⁻¹ ⇒ 隐含体积 **69.8 m³**（≈70.40），而非列出的 82.24 m³；C445-1 的 0.18 m³/s ÷ 3.38 h⁻¹ ⇒ 隐含体积 **191.7 m³**，而非列出的 127.60 m³。
2. **Table 4 未给出所用体积**：用 `通风量 × 3600 ÷ ACH` 反算，隐含体积约为 Table 1 主室体积的 **1.8–2.0 倍**（如 45 窟 165 m³ vs 82.24 m³；46 窟 140 m³ vs 70.40 m³；100 窟 1317 m³ vs 657 m³）。原文未说明归一化体积口径，**直接用 Table 4 的 ACH 标定时需注意口径**。
3. **Table 4 的 ACH 与 Table 7 的 ACH 口径不同**（前者风速积分、后者示踪衰减），不可混用。第 46 窟两表分别为 13.11 /h（Table 4）与 13.61、13.20 /h（Table 7）——数量级一致；但第 219 窟 Table 4 高达 **43.85 /h**，属外推小体积洞窟。

---

## 与二手转述不符之处（逐条核对）

| # | 你的转述 | 判定 | 说明（以原文为准） |
|---|---|---|---|
| 1 | "**≥24 h 尺度相位差 π/4**" | ✅ **原文一致** | 原文：*"on scales of 24 h and above, with a phase difference of π/4"*（Fig. 11a,b）。尺度条件 **≥24 h** 正确。 |
| 2 | "**日尺度约 3 小时**" | ⚠️ **原文未报告（措辞不符，换算后才能得到）** | 原文从未以"小时"表述相位差，只写 *"external humidity leads internal humidity by **~1/8 of a cycle**"*、*"a lag of **1/8 of a cycle**"*。按 24 h 周期折算 1/8 = 3 h 属**我方换算**，不是原文句子。且原文限定为"**24 h 及以上**尺度"，并非单指日尺度。 |
| 3 | "**日最高温与日较差各 +1.4 °C**" | ✅ **原文一致** | 原文：*"visitor presence **increased the maximum temperature by 1.4 °C** and also **heightened the temperature amplitude by 1.4 °C**"*（2019-05-01：滤波 16.6 °C / 较差 2.8 °C vs 实测 18 °C / 较差 4.2 °C）。 |
| 4 | "**窟内平均 RH 38.3% → 44.0%**" | ⚠️ **数值一致，但限定条件必须补上** | 这是 **2020 年 7 月 vs 2021 年 7 月的窟内月平均**（Fig. 5），不是年均值——**窟内年均 RH 是 30.8%**。对应的 "145,200 / 534,100 人" 是**莫高窟全遗址的月度游客量**，不是第 71 窟洞内人数。 |
| 5 | "游客呼吸排汗贡献的湿量占比" | ⚠️ **原文报告 ~5%，但是转引而非本文实测** | 原文：*"**They** discovered… visitors contribute **only about 5% of moisture through breath and perspiration**."* 其中 **"They" = Demas et al.（ref 30）**。Gong et al. 2025 **没有自己做呼吸排汗湿量的独立测算**。 |
| 6 | "**降雨 vs 游客，哪个更强**" | ✅ **原文一致（降雨更强），且原文给出了量化值** | 降雨 → 平均 **+23.9%**，单独致峰值 **+33.5%**、振幅 **+22%**；游客 → 常态日峰值 **+11.4%**、振幅 **+12.4%**；降雨日仅 **+5.9%** / **+6.4%**。原文结论：*"the amplitude… escalates by over 20%, **surpassing the impact from visitors alone**"*。 |
| 7 | （你未提，但需纠正的常见误读）"Gong et al. 2025 有换气次数" | ❌ **原文未报告** | Gong et al. 2025 全文**不含任何 ACH / 换气量实测值**；它只给相位、相干与分解振幅。ACH 必须完全来自 npj HS 2026。 |
| 8 | （你未提，但需纠正）"npj HS 2026 有逐窟 ACH" | ⚠️ **部分成立，需分口径** | 逐窟 ACH 在 **Table 4（12 窟，1 月，开门，风速积分法）**；但**示踪法只做了 45、46 两窟**（Table 7），**关门状态只做了 45 窟一次**（1.59 ± 0.03 /h）。摘要 "9–13/h" 与 "1.6/h" 仅代表 45/46 窟。 |
| 9 | "窟内外 RH 的离散小波分解在 **Figure 11、13 附近**" | ⚠️ **图号需修正** | **Fig. 13** 才是 RH 的 8 级离散小波分解（DWT）与重构（5/1 与 5/6）；**Fig. 11 是 RH 窟内外的小波相干谱（WTC）与交叉小波谱（XWT）**，不含 DWT。另有 **Fig. 10** = RH 的小波时频图、**Fig. 12** = CO₂–RH 相干/交叉小波、**Fig. 9** = 温度的 DWT。 |

---

## 总结：这些数值如何约束"窟外气象 → 窟内微环境"物理模型（3–5 句）

1. **有效换气量（平流项）有了硬边界**：同类中型殿堂窟（45 窟 82.24 m³、46 窟 70.40 m³）实测 **开门 λ ≈ 8.9–13.6 h⁻¹、关门 λ = 1.59 h⁻¹**，相差近一个数量级；折算成第 71 窟（V ≈ 67 m³，门 3.78 m²）即 **开门 Q_eff ≈ 600–900 m³/h、关门 Q_eff ≈ 107 m³/h**，因此"开门/关门"在模型里应作为一个**离散的、量级跃变的换气开关**，而不是连续调节量。
2. **热湿耦合的时间常数被 λ 锁定**：原文明确 **τ ≈ 1/λ**（平均空气龄），故关门时窟内空气时间常数 **τ ≈ 38 min**、开门时仅 **τ ≈ 4.4–6.7 min**；这与 Gong 观测到的"≥24 h 尺度相位差 π/4（滞后 1/8 周期）"在量级上自洽——**窟内 RH 对窟外 RH 的传递函数应写成"一阶低通 + 纯滞后"形式，滞后项取 1/8 周期（日尺度 ≈3 h），时间常数取 1/λ 并随门态切换**。
3. **游客项是"小显热源 + 极小潜热源"**：常态日游客仅使日最高温 **+1.4 °C**、日较差 **+1.4 °C**、RH 峰值 **+11.4%**，而呼吸排汗湿量占比仅约 5%（转引），说明窟内 RH 的主要驱动不是人体直接散湿，而是**开门引入窟外湿空气的平流项**；模型应把人体写成**显热源主导、潜热源微弱的室内源项**，并作用于 ≤8 h（T）/≤6 h（RH）的频带。
4. **降雨是上游边界条件的强驱动通道**：降雨期窟内外 RH 在 12–48 h 尺度上**近乎同相、无滞后**，且使窟内振幅 **+22%**、峰值 **+33.5%**，远大于游客项；因此模型需要一个**降雨触发的窟外湿度阶跃输入**，且在此通道下可近似取"窟内 RH 跟随窟外 RH"，滞后与阻尼都显著减弱。
5. **必须做分层/双区处理，否则会系统性高估主室换气**：实测入口到主室中心风速比 **0.08–0.35（均值 0.17）**、温差 **1.8–5.2 °C**，且作者自述示踪 AER 是**全窟体均值、会高估主室**；因此单区集总模型应引入**有效混合因子（≈0.17 量级）**或用"门口动态区 + 主室准静态区"的双区结构，并以 |ΔT|–AER 的**近似线性关系**（而非风速关系，风速拟合更差）作为通风强度的主控参数化。

---

## 抓取到的原始文件

- `_lit/gong2025.html` / `_lit/gong2025.pdf` / `_lit/gong2025.txt`（PDF 提取全文）
- `_lit/vent2026.html`（仅摘要）/ `_lit/vent2026_ref.pdf` / `_lit/vent2026_ref.txt`（PDF 提取全文，19 页）
