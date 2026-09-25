# 芯链哨兵数据与测量检查报告

## 检查说明

本报告检查人工核对基准、指标公式、取值范围、样本键，以及两个年份的来源覆盖。P2按目标年份使用对应证据，但2017与2022的来源类型不同，因此只能作有边界的结构对照。报告不把内部检查解释为预测准确率。

## 自动检查

共完成16项检查，16项通过，0项未通过。

| check_group | check_id | observed | expected | tolerance | status |
| --- | --- | --- | --- | --- | --- |
| 人工核对参考值 | Malaysia_2022_n2_china_hs8542_import_share | 0.170601 | 0.1709 | 0.003 | PASS |
| 人工核对参考值 | Malaysia_2022_n3_us_hs8542_export_share | 0.0784204 | 0.0788 | 0.003 | PASS |
| 人工核对参考值 | Malaysia_2022_n4_dual_dependency | 0.0133786 | 0.0135 | 0.001 | PASS |
| 人工核对参考值 | Malaysia_2022_v1_hs8542_import_hhi | 0.148353 | 0.148 | 0.005 | PASS |
| 人工核对参考值 | Malaysia_2022_v2_effective_supplier_count | 13 | 13 | 0 | PASS |
| 人工核对参考值 | Vietnam_2022_n2_china_hs8542_import_share | 0.180242 | 0.1805 | 0.003 | PASS |
| 人工核对参考值 | Vietnam_2022_n3_us_hs8542_export_share | 0.0465893 | 0.0465 | 0.003 | PASS |
| 人工核对参考值 | Vietnam_2022_n4_dual_dependency | 0.00839736 | 0.0084 | 0.001 | PASS |
| 人工核对参考值 | Vietnam_2022_v1_hs8542_import_hhi | 0.206266 | 0.207 | 0.005 | PASS |
| 人工核对参考值 | Vietnam_2022_v2_effective_supplier_count | 9 | 9 | 0 | PASS |
| 公式一致性 | 全部样本：N4 = N2 × N3 | 9.19403e-17 | 0 | 1e-12 | PASS |
| 取值与覆盖范围 | 国家—年份主键唯一 | 0 | 0 | 0 | PASS |
| 取值与覆盖范围 | 12国 × 2年面板完整 | 24 | 24 | 0 | PASS |
| 取值与覆盖范围 | 比例与HHI位于[0,1] | 1 | 1 | 0 | PASS |
| 来源覆盖 | P2目标年份来源与数值齐全 | 24 | 24 | 0 | PASS |
| 来源冲突处理 | 墨西哥2017：ATOP原值与OAS核验值并列 | 0 | 0 | 0 | PASS |

## 2017—2022排序对照

Spearman相关比较同一指标在2017与2022年的国家排序，只用于描述结构变化；不代表信度系数，也不验证最终指数的预测能力。P2存在来源口径变化，相关性尤其应谨慎解释。

| indicator | paired_countries | spearman_2017_2022 |
| --- | --- | --- |
| P1 UNGA relative alignment | 12 | 0.958042 |
| P2 active formal defense tie (source-aware) | 12 | 1 |
| N1 electronics foreign value-added share | 12 | 0.601399 |
| N2 China HS8542 import share | 12 | 0.636364 |
| N3 US HS8542 export share | 12 | 0.524476 |
| N4 dual dependency | 12 | 0.433566 |
| V1 HS8542 import HHI | 12 | 0.573427 |
| V2 effective supplier count | 12 | 0.292196 |

## 2022年双重依赖较高的经济体

| country | n4_dual_dependency_2017 | n4_dual_dependency_2022 | n4_dual_dependency_change_2022_minus_2017 |
| --- | --- | --- | --- |
| Mexico | 0.242092 | 0.144559 | -0.0975326 |
| Malaysia | 0.00736375 | 0.0133786 | 0.00601483 |
| India | 0.0299965 | 0.0113099 | -0.0186866 |
| Indonesia | 0.0017555 | 0.0106547 | 0.00889924 |
| Thailand | 0.00661633 | 0.0103356 | 0.00371928 |

## 数据边界

- P2的2017值以ATOP为基础，墨西哥保留原始值并按OAS条约状态作单项修正；2022逐国核对美国国务院《Treaties in Force 2020》及2021—2023补编、目标年双边资料和NATO成员加入年份。不同来源带来的时间可比性限制已单列。
- BIS P3只整合所选且已人工复核的候选规则，范围并非穷尽；只作证据层，不纳入指数分数。
- IMF CDIS显示的是按直接对手方拆分的年末投资头寸；2022目标行使用2021观测（滞后一年），且不是半导体专项数据，不计分。
- 历史对照是描述性分析，不构成因果识别或未来预测。
