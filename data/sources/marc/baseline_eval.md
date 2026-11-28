# MARC 德语商品评论规则立场基线评测结果

- 评测日期：2026-11-21
- 语料：`data/sources/marc/marc_reviews_de_10000.csv`（10,000 条，PII 已清洗，商品域，官方 held-out test+validation 分片）
- 基线：`apps/api/src/crosspilot_api/services/stance_baseline.py`（透明规则：德语极性词典 + 否定窗口翻转 + 从句切分；零 ML 依赖）
- 金标口径：星级映射 4-5→support、1-2→oppose、3→insufficient（星级是消费者总体满意度的一维信号，无 aspect 标注；中评正负证据并存、方向不可判定，与 GERestaurant 混合评价→insufficient 口径一致；映射理由见该目录 README）
- 结论定位：补 GERestaurant（餐厅域）缺失的商品域基准，回答「餐厅域结论是否外推到商品域」；research-only，不进证据卡（硬约束 2：商业化启动即下线）

## 指标

| 类别 | precision | recall | F1 | 金标数 |
|---|---|---|---|---|
| support | 0.677 | 0.812 | 0.738 | 4000 |
| oppose | 0.730 | 0.490 | 0.586 | 4000 |
| insufficient | 0.237 | 0.298 | 0.264 | 2000 |
| **宏平均** | — | — | **0.530** | 10000 |

**Accuracy：0.580（5804/10000）**

## 混淆矩阵（行=金标，列=预测）

| gold \ pred | support | oppose | insufficient |
|---|---|---|---|
| support | 3248 | 172 | 580 |
| oppose | 702 | 1959 | 1339 |
| insufficient | 851 | 552 | 597 |

## 错误类型小结

- 金标 insufficient（3 星中评）被判 support/oppose：1403 条。主因：中评文本常仍是温和负面抱怨（用户用 3 星表达不满），且常见"功能可用但不满意"的混合表达；正面词多于负面词时被强判 support，反之判 oppose——按口径不可判定，但基线倾向强行表态。
- 金标 support/oppose 被判 insufficient：1919 条。主因：商品评论偏短、不含任何词典词（商品域典型缺陷词 undicht/klemmt/zu klein/beschädigt/Reinfall/Fake 等不在餐厅域词表中），或正负各一命中相抵。
- support/oppose 互混：874 条（support→oppose 172，oppose→support 702）。主因：否定窗口误翻转、个别词的领域歧义（同一形容词在商品域可正可负），以及短评里单一信号被放大。

### support→oppose 示例

> Das große Finale war enttäuschend  Am Ende zu undetailliert und hastig geschrieben . Als ob der Author so schn
> 👟  Noch der Letzte seiner Sorte der länger als seine nachfolger Lebt, schade das die Qualität von AllStar chuc
> Klimaanlage  Es hilft schon, allerdings finde ich es auch recht laut.
> Anderer Schriftzug  Schöne schlichte Flasche. Leider war das Design bzw der Schriftzug anders als auf den Foto
> Zu klein  Ich musste die Klappe leider wieder zurück schicken, da der Durchgang für meinen Hund zu klein war. 
> Lenker für Bmw  Ware ist ok. leider sind die Löcher für das Aretieren vom Gasgriff nicht vorhanden.

### oppose→support 示例

> Flohmarkt ware  Siegel sowie Verpackung war beschädigt und ware war gebraucht mit Verschleiß und Fingerabdrück
> Reißverschluss klemmt  Die Träger sind schnell abgerissen
> Undicht  Haben uns diese Unterwasser Lichter für unseren Pool gekauft. für jedes Licht gab es eine Fernbedienu
> Plastikmüll  Ich kann dazu nicht Decke sagen. Das ist Plastik und hat nicht im entferntesten mit einer Decke z
> Eigentlich zu klein für A5 2017  Habe die Folie angebracht, sie ist zu klein und es bleiben einige Millimeter 
> Verarsche  Richtiger Fake! Hoffentlich funktioniert alles mit der Rückerstattung... Aufkeinenfall zu Empfehlen

### insufficient→表态 示例

> nicht besser als andere, springt relativ schnell  Aufkleber funktioniert gut. Allerdings ist es nicht sehr sta
> für bestimmte Zwecke bestimmt perfekt  Für meine Zwecke war der Campingstuhl einfach zu klein (niedrig) und zu
> Naja  Etwas heftig. Mir zu krass. An sich aber nett
> Note Gel: gut; Note Verpackung: mangelhaft  Das Gel ist bei Zahnfleischentzündungen sicherlich nicht schlecht.
> Bin leider nicht überzeugt!  An sich ist die Bürste ja nicht schlecht aber dadurch, dass sie vorne einen flexi
> Sehr kuschelig aber nur 40° waschbar  Die Bettwäsche ist durchaus sehr kuschelig aber anders, wie angegeben, s

### 表态→insufficient 示例

> Keine Option  Druckbild ist leider nicht akzeptabel. Die kompletten seiten werden grau eingefärbt. Verkäufer a
> Kratzbaum  🤬🤬🤬 Stoff löst sich nach kurzer Zeit
> Beim zweiten Gebrauch undicht!!!  Beim zweiten Gebrauch bereits undicht!!!
> Undicht  Die Lieferung war prompt. 2 Gläser sind bereits undicht und Wasser befindet sich in den Zwischenräume
> Panzerfolie  Bin überhaupt nicht zufrieden. Das Handy ist mir einmal kurz, aus minimalen Höhe ca 30cm, auf den
> Mogelpackung  Ich sehe mit diesem Teil immer noch gleich fett aus. Für das Geld ein echter Reinfall

## 人工复核分流（仅用于分流，不构成自动接受）

- 低复核优先级：强支持、净分≥4、长度≥20、无否定翻转、无正负混合；覆盖 593/10000（5.9%），准确率 0.924。
- 建议人工复核：9407/10000（94.1%），准确率 0.559。
- 反对、否定翻转、正负混合、短评与无明确极性一律进入人工复核；低复核优先级仍建议抽检，不把规则结果当作已验证模型输出。
- 该评测金标是评论整体星级/印象，不是 CrossPilot 的卖点级 aspect 标签；分流准确率不能替代真实授权评论上的卖点归属与立场复核。

- 低优先级预测 support：593 条，准确率 0.924。

## 与 GERestaurant（餐厅域）对照

- 对照口径：GERestaurant 3,078 条（同一基线、同一 STANCES 三类口径，离线重跑主表得出，与 data/sources/gerestaurant/baseline_eval.md 同源）
- 规则基线的词典是**手写餐厅/服务/价格域**德语词表（见 stance_baseline.py 模块 docstring），本对照回答「餐厅域 → 商品域是否退化」

### 两域指标对照表

| 指标 | GERestaurant（餐厅域） | MARC de（商品域） | 差值（商品-餐厅） |
|---|---|---|---|
| accuracy | 0.610 | 0.580 | -0.030 |
| 宏 F1 | 0.533 | 0.530 | -0.004 |
| support F1 | 0.823 | 0.738 | -0.085 |
| support recall | 0.781 | 0.812 | +0.031 |
| oppose F1 | 0.589 | 0.586 | -0.003 |
| oppose recall | 0.433 | 0.490 | +0.057 |
| insufficient F1 | 0.189 | 0.264 | +0.076 |
| insufficient recall | 0.514 | 0.298 | -0.216 |

### 结论：餐厅域 → 商品域是否退化

**是，出现退化。** accuracy 0.610→0.580（-0.030），宏 F1 0.533→0.530（-0.004）。GERestaurant 评测报告中「餐厅域结论不可外推为商品域」的判断得到证实：基线词典以餐饮体验词为主（lecker/knusprig/gemütlich 等），商品评论的典型缺陷表达（材质/功能/物流类词）覆盖不足，泛化下降是词典域偏置的直接后果。

## 复现

```
.venv/Scripts/python.exe scripts/eval_stance_baseline.py --dataset marc
```
