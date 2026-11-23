# 许可原件存档

各数据源许可声明的**原件或官方页面留痕**，随作品说明一并提交。
每个来源的署名文本、许可条款解读与使用约束以 `data/sources/<source>/README.md` 为准（本目录只存原件，不重复解读）。

存档日期：2026-11-23。

## 文件索引

| 文件 | 许可 | 适用来源 | 原件出处 | 形态 |
|---|---|---|---|---|
| `CC0-1.0.txt` | CC0 1.0（公共领域） | `eu_safety_gate/` | creativecommons.org/publicdomain/zero/1.0/legalcode.txt | 官方文本直存 |
| `Apache-2.0.txt` | Apache-2.0 | `amazon_reviews_2023/` | apache.org/licenses/LICENSE-2.0.txt | 官方文本直存 |
| `CC-BY-4.0.txt` | CC-BY-4.0 | `gerestaurant/` | creativecommons.org/licenses/by/4.0/legalcode.txt | 官方文本直存 |
| `ODC-By-1.0.html` | ODC-By 1.0 | `usage_bielefeld/` | opendatacommons.org/licenses/by/1-0/ | 官方页面留痕（HTML 原样） |
| `eurostat-reuse-policy.html` | Eurostat 开放数据复用政策 | `eurostat_isoc/`、`eu_comext/` | ec.europa.eu/eurostat/web/quality-and-transparency/re-use-policy | 官方页面留痕（HTML 原样） |
| `gdelt-about-page.html` | 无限制使用 + 须署名 | `gdelt/` | gdeltproject.org/about.html（官方页面留痕，HTML 原样） | 官方页面留痕 |
| `gdelt-use-policy-excerpt.txt` | 同上 | `gdelt/` | 同上「Using GDELT」节声明句逐字摘录：*"all datasets released by the GDELT Project are available for unlimited and unrestricted use for any academic, commercial, or governmental use of any kind without fee"* | 官方文本摘录 |
| `amazon-academic-research-license.txt` | Amazon 学术研究许可（research-only，硬约束 2） | `marc/`（数据本体**不随仓库分发**，本地凭 `_scripts/fetch_marc.py` 复现） | 提取自 `data/sources/marc/raw/upstream_load_script.py` 的 `_LICENSE` 常量（MARC 官方上游加载脚本逐字原文，AST 解析提取，未改动） | 官方文本提取 |

## 完整性（SHA-256，2026-11-23）

原件防篡改基线；本 README 自身不含在清单内。

```
cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30  Apache-2.0.txt
9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411  CC-BY-4.0.txt
a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499  CC0-1.0.txt
974e6ec27d1693292cdf63b08eb57baccad25ebc85dbfcdca816839b924961b8  amazon-academic-research-license.txt
5e5d016ccde1dc1b1b1ae7c972847c96755501e01acc534c3cf59accdb43d0ee  gdelt-use-policy-excerpt.txt
7d7e622bbb4b5f21b1c5cb2dd7ce8b1b747ee2c3ab9fc8309c19082e12d13b2d  ODC-By-1.0.html
1ca046dd2f523712d37619e671f25abebcc5627f71368c508e0ae537943734e7  eurostat-reuse-policy.html
384754b514042255c4542d51dc1e631da55c83c67d46a92b53b48a812d94be6b  gdelt-about-page.html
```

## 使用约束要点（详见各源 README）- **marc**：许可文本本身可随仓库分发；其管辖的**数据本体禁再发布**（`.gitignore` 已排除 `data/sources/marc/*.csv`）。商业化路径启动即下线（`services/datasets.py:REGISTRY` 闸门 `commercial_ok=False`）。
- **署名**：`eu_safety_gate` 须 "© European Union" + 提取日期；`eu_comext` 须 "Source: Eurostat (Comext), DS-045409, 提取日期"；`gdelt` 署名文本已逐行写入主表 CSV；`eurostat_isoc` 须 "Source: Eurostat" + 提取日期。
- **基准语料**（`gerestaurant` / `usage_bielefeld` / `marc`）只作立场基线评测，不进证据卡；`gerestaurant` 禁止外推商品域；`usage_bielefeld` 登记保持 `community-free` 保守口径。
