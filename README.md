# 芯链哨兵：第三方半导体供应链风险观察

这是“脱钩之后，风险去了哪里？”项目的公开展示仓库。网页用2017年与2022年的12个经济体核心面板，观察中国投入、美国市场、政治位置和供应来源集中度如何在第三方节点重新组合。

## 在线查看

- [打开在线总览页](https://raw.githack.com/lesile1312/semiconductor-project/main/portable/index.html)：使用仓库中的自包含页面，可直接在浏览器打开。
- 总览页地图下方新增 12 国横向卡片区，按 2022 年 N4 排列；选择国家可联动地图与画像，并生成带国家/年份参数的分享链接。
- 总览页只展示实际用于核心指标的来源覆盖，并随国家与年份联动显示P2判定依据；未接入候选或不计分辅助材料不再作为网页功能陈列。
- BIS选定规则核对与IMF CDIS工作簿保留在报告、方法说明和来源登记中，作为不计分的补充证据；GDELT、GTA、CSL等本轮未接入来源仅保留筛选/排除记录，不生成预警或企业匹配结果。
- 来源粒度、连接键、文件哈希和筛选原因见 [`data/数据来源登记表.csv`](data/数据来源登记表.csv)、[`docs/多源数据整合与连接审计.md`](docs/多源数据整合与连接审计.md) 与 [`docs/外部数据源筛选与背景说明.md`](docs/外部数据源筛选与背景说明.md)。
- 字段级连接规则见 [`data/字段级来源血缘.csv`](data/字段级来源血缘.csv)，年度覆盖明细见 [`data/各年份数据源覆盖.csv`](data/各年份数据源覆盖.csv)。
- 从总览页可继续进入“风险迁移透镜”和“企业级扫描”；也可以下载 `portable/` 中的三个单文件页面离线打开。
- 完整网页源代码仍在仓库根目录；如在本地运行，可通过下方命令启动，三页会共用同一套地图与面板数据。

如果直接双击文件遇到浏览器的本地脚本限制，可在仓库根目录运行 `python -m http.server 8123`，再打开 `http://127.0.0.1:8123/index.html`。

## 目录说明

- `index.html`：风险总览与试点指数排名。
- `risk-migration-lens.html`：单个经济体的2017—2022风险迁移页面。
- `enterprise-scan.html`：企业BOM、供应商、客户与已确认P3事件的本地扫描原型。
- `assets/`：共享面板数据、12个研究对象坐标与 Natural Earth 低分辨率世界轮廓地图。
- `data/`：审计后的核心面板、试点指数、P2逐国来源、P3人工核对证据、IMF CDIS工作簿、来源登记表、逐字段血缘、年度覆盖表与连接检查。
- `data/raw/`、`data/processed/`：保留的来源文件及清洗中间表；`scripts/`同时包含数据处理与审计脚本。
- `scripts/build_public_assets.py`：从审核后的CSV生成网页数据；`scripts/build_portable_site.py`：生成三个自包含离线页面。
- `docs/`：研究报告可编辑稿、数据与方法说明、来源与复现说明、AI辅助与人工判断记录及报告图表；最终PDF统一放在 `output/pdf/`。
- `output/`：核心结果、验证与审计数据；`output/pdf/` 保存最终参赛报告PDF。

## 数据边界

项目使用三项主办方基础数据：UNGA Voting Ideal Points、ATOP v5.1、OECD TiVA 2025；补充UN Comtrade、美国国务院/NATO、OAS、BIS与IMF CDIS。UNGA与TiVA指标进入GTRI-v1主分，ATOP与目标年正式防务安排记录作为P2背景变量；因两年来源和编码方式存在断点，P2不计入主分。墨西哥2017保留ATOP原值并附OAS条约状态核验。P3的10条所选候选规则已人工做范围核对，但复核集合非穷尽，不构成BIS全量法律审查，只作非计分证据。IMF CDIS只作资本联系背景，2022对应2021年末、滞后一年，且不具半导体行业粒度。17项数据与公式检查、15项来源连接/字段血缘检查分开报告，均不等于预测准确率或因果效度。主模型采用P1、N1、N4和供应脆弱性四个等权维度；N2/N3用于解释N4，不重复计分。名次敏感性结果随报告附录公开。

## 离线复现多源面板与审计

Python 3.11或更新版本，在项目根目录运行：

```powershell
python -m pip install -r requirements.txt
python scripts/06_build_master_panel.py
python scripts/13_descriptive_and_validation.py
python scripts/27_calc_pilot_gtri_index.py
python scripts/32_build_multisource_integration_audit.py
python scripts/build_public_assets.py
python scripts/build_portable_site.py
python scripts/render_report_pdf.py
python scripts/render_submission_appendix.py
```

上述复现使用仓库内已归档的清洗中间表与原始证据，生成24行面板、GTRI-v1指数和敏感性表、来源登记表、逐字段血缘、按年覆盖表、15项来源连接检查及网页数据。全量重新抓取/清洗各原始来源的步骤和边界见 [`docs/多源整合复现说明.md`](docs/多源整合复现说明.md)；审核检查通过不代表指数准确率、因果效度或预测能力。

网页中的地图使用 Natural Earth 1:110m Admin 0 Countries 的低分辨率轮廓，并在其上叠加12个研究对象；2022年N4较高的节点使用暖色轮廓，其余节点使用青色轮廓。青色虚线表示“中国投入 → 第三方节点”，琥珀色虚线表示“第三方节点 → 美国市场”，线宽和透明度随N2/N3变化；这些线是指标结构示意，不是实际运输路线。新加坡因底图尺度过小使用菱形微型标记。地图只用于位置和风险节点展示，不作为法律边界依据，支持鼠标悬停、Tab 聚焦、指针跟随的轻微3D倾斜、径向流光、边缘光和低密度空间粒子；页面隐藏或开启减少动态效果时会暂停高频动效。页面和数据仅用于研究展示，不构成法律、投资或合规意见。

正式参赛材料以项目提交包中的研究报告、数据和方法说明为准；本仓库用于在线演示网页。在线预览以 `portable/` 中的自包含页面为入口，根目录页面保留共享资源结构，便于本地开发与维护。

`output/芯链哨兵_最终提交包.zip`为5项精简提交附件（两份PDF与三页自包含网页）；`output/芯链哨兵_完整参赛提交包.zip`保留全部数据、来源、代码与网页，便于评审复核；`output/芯链哨兵_非网页参赛提交包.zip`则是不含网页的可复现材料包。
