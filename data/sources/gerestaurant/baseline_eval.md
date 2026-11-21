# GERestaurant 规则立场基线评测结果

- 评测日期：2026-11-21
- 语料：`data/sources/gerestaurant/gerestaurant_reviews_3078.csv`（3078 条，PII 已清洗，餐厅域）
- 基线：`apps/api/src/crosspilot_api/services/stance_baseline.py`（透明规则：德语极性词典 + 否定窗口翻转 + 从句切分；零 ML 依赖）
- 金标口径：GENERAL-IMPRESSION 极性优先、冲突即 insufficient（见该目录 README）
- 结论定位：给后续 LLM 立场抽取方案提供对照基准；餐厅域结论不可外推为商品域——商品域表现见 `data/sources/marc/baseline_eval.md`（--dataset marc）

## 指标

| 类别 | precision | recall | F1 | 金标数 |
|---|---|---|---|---|
| support | 0.869 | 0.781 | 0.823 | 1508 |
| oppose | 0.921 | 0.433 | 0.589 | 1323 |
| insufficient | 0.115 | 0.514 | 0.189 | 247 |
| **宏平均** | — | — | **0.533** | 3078 |

**Accuracy：0.610（1878/3078）**

## 混淆矩阵（行=金标，列=预测）

| gold \ pred | support | oppose | insufficient |
|---|---|---|---|
| support | 1178 | 9 | 321 |
| oppose | 98 | 573 | 652 |
| insufficient | 80 | 40 | 127 |

## 错误类型小结

- 金标 insufficient 被判 support/oppose：120 条。主因：混合评价里正面词多于负面词（词典覆盖不均）、元否定（"kann ich nicht bestätigen"）不处理，基线倾向强行表态。这是 insufficient 类召回低的结构性原因。
- 金标 support/oppose 被判 insufficient：973 条。主因：评论不含任何词典词（如 "Wir werden dieses Restaurant sicher nicht noch einmal besuchen"），或正负各一命中相抵。
- support/oppose 互混：107 条（support→oppose 9，oppose→support 98）。主因：否定窗口误翻转与个别词的领域歧义。

### support→oppose 示例

> Wir haben eigentlich nie besser italienisch gegessen als hier.
> Wer’s zünftig, laut und gesellig mag, der ist hier richtig.
> Ich habe noch nie soo leckeres Essen gegessen!!
> Schade, denn am Restaurant gibt es absolut nichts auszusetzen.
> Ich könnte mir keinen besseren Ort wünschen.
> Wir haben schon lange nicht mehr sooooo gut gegessen!

### oppose→support 示例

> Dennoch erinnerte sie mehr an eine fertig Pizza als an eine Pizza, wo der Teich frisch zubereitet worden ist.
> Die Bedienung war früher sehr viel herzlicher und mit Herzblut dabei.
> Noch nie so reingelegt worden.
> Einziger Lichtblick und auch der Grund warum ich es nicht mit „mangelhaft“ bewerte, war der sehr freundliche K
> 23 abends dann doch etwas frisch auf der Terrasse.
> Sosse selbe wie bei der Ente...= -1Darum für den Preis von fast 60 Euro kann man eigentlich was besseres erwar

### insufficient→表态 示例

> Aber: bleibt weg von den Bratkartoffeln, die sind wabbelig und fad, null Kartoffelgeschmack, und trotz Versich
> Das Schnitzel war das Fleisch gut jedoch weder Fleisch noch Panade gesalzen und Gewürzt nach würzen bringt es 
> Das Kalbsschnitzel mit 19EUR nicht teuer aber absolut lieblos und dahin ger...zt.
> Dass der Service langsam und unfreundlich ist, kann ich nicht bestätigen.
> Wie immer war das Essen in der Gondel ein ausgezeichneter Start in den LOC, wenn... der Mann vom Service genug
> Das Essen passt in die Brauhausatmosphäre, ist deftig und konservativ - halt was wo man Bier und nicht Wein da

### 表态→insufficient 示例

> Eigentlich schade, es bleibt nur noch eine schöne Erinnerung (Es war einmal ein LOC…….
> Wir werden dieses Restaurant sicher nicht noch einmal besuchen.
> Der Kartoffelsalat schmeckte wie aus dem Eimer und war eiskalt.
> Carpaccio mit Trüffel geteilt und dann feine Mezzelune ( schwarz) gegessen.
> Der verbleibende Mitarbeiter, der sich dann alleine um alle besetzten Tische im Außenbereich gekümmert hat, wa
> Das Restaurant scheint im vorigen Jahrhundert stehen geblieben zu sein.

## 复现

```
.venv/Scripts/python.exe scripts/eval_stance_baseline.py
```
