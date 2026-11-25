# L1 分层采样清单（ADR-0005 A5 · 美国市场试点）

> 生成：scripts/build_l1_sample_frame.py --n 30 ｜ 采样框：星级×时间分层，
> 星级配额 neg/neu/pos = (10, 5, 15)（负向 ≥33%），
> 时间层 2021/2022/2023H1（试点数据止于 2023-08），层内系统抽样（确定性、无种子）。

**硬约束边界（manifest tier_caveat 同源）**：本清单来自 Amazon.com 美国市场，仅作 L1 判定链方法演练（去重→抽取→门禁→区间），**不得写入德国市场偏好结论**。

## 采样框（层级池大小 → 实采）

| 星级层 | 2021 | 2022 | 2023H1 | 层合计 |
|---|---|---|---|---|
| neg(1-2星) | 1028 | 535 | 122 | 12 实采 |
| neu(3星) | 412 | 224 | 42 | 6 实采 |
| pos(4-5星) | 2203 | 1286 | 294 | 12 实采 |

## 样本清单（逐条可溯源：shard/asin/日期/星级）

| # | review_date | rating | asin | shard | verified | 摘要（前 80 字符） |
|---|---|---|---|---|---|---|
| 1 | 2021-01-01 | 1.0 | B0742LVLMJ | raw_review_Subscription_Boxes | True | Not worth it Terrible value. Same skincare products/lines over and over again in |
| 2 | 2021-01-01 | 3.0 | B07G584SHG | raw_review_Subscription_Boxes | True | My cats just weren't Interested... ...in anything other than the feathers of the |
| 3 | 2021-01-01 | 5.0 | B07FT4FMWX | raw_review_Subscription_Boxes | True | Beginners app coding The kid is in love with learning to code. She is doing a gr |
| 4 | 2021-03-05 | 2.0 | B07KM6T8GV | raw_review_Subscription_Boxes | True | Why is this box called how to be a redhead? I have to agree with others that the |
| 5 | 2021-03-10 | 5.0 | B07XGNHYC2 | raw_review_Subscription_Boxes | True | Sneaky Education My son is 16 and I thought this would be something we could do  |
| 6 | 2021-05-18 | 2.0 | B07QXSYDGF | raw_review_Subscription_Boxes | True | Cute packaging. Low quality products. This had some cute stuff in it but it’s de |
| 7 | 2021-05-21 | 3.0 | B08MW8RVK9 | raw_review_Subscription_Boxes | False | Too little diversity in characters depicted I've received four of the shirts, wa |
| 8 | 2021-05-23 | 5.0 | B08R8Y2TP6 | raw_review_Subscription_Boxes | True | Great gift  Good value This is a really gifted will and valuable little Box of n |
| 9 | 2021-08-02 | 1.0 | B07QL1JRCN | raw_review_Subscription_Boxes | True | Waste of Money This is suppose to be a lip monthly subscription, I received one  |
| 10 | 2021-08-12 | 5.0 | B087GQ51ZB | raw_review_Subscription_Boxes | True | 12/10 💕 I found this subscription box last year and fell in love. All the ingred |
| 11 | 2022-01-01 | 2.0 | B07VXY755K | raw_review_Subscription_Boxes | True | Beware! Amazon sub starts with older box! Be aware, you will not receive the cur |
| 12 | 2022-01-01 | 5.0 | B09BDCTCKR | raw_review_Subscription_Boxes | True | Best Idea For Me This is worth the money for Snoopy fans! |
| 13 | 2022-01-03 | 3.0 | B08KWJ5DXV | raw_review_Subscription_Boxes | False | This was a bad kit I did the crochet subscription for a year and loved it!! The  |
| 14 | 2022-03-08 | 1.0 | B08LDV5MBB | raw_review_Subscription_Boxes | True | It should not be in subscription boxes. box with a tube of stuff. Not a gift box |
| 15 | 2022-03-12 | 4.0 | B07XGNHYC2 | raw_review_Subscription_Boxes | True | it’s worth it. i love the lil snacks that came in they were all good! |
| 16 | 2022-05-24 | 2.0 | B08F814PSW | raw_review_Subscription_Boxes | True | Not bad but not amazing I made one of the recipes and it looked worse than it ta |
| 17 | 2022-06-06 | 3.0 | B07HP1T567 | raw_review_Subscription_Boxes | True | The box was fun and engaging! I enjoyed the experience until I tried to access t |
| 18 | 2022-06-07 | 5.0 | B08N6WFYN9 | raw_review_Subscription_Boxes | True | Variety I love that you get pretty strange designs, love the dark palette (thoug |
| 19 | 2022-08-17 | 1.0 | B07G584SHG | raw_review_Subscription_Boxes | False | Cheap collection of toys that disinterest cats I really feel like they’ve put to |
| 20 | 2022-09-03 | 5.0 | B092587ST1 | raw_review_Subscription_Boxes | True | The different teas When can I cancel I dont need any more love what I got just t |
| 21 | 2023-01-01 | 5.0 | B0BRBQ87F1 | raw_review_Subscription_Boxes | False | Such a great buy for my kids! This sparked a great discussion about veterans and |
| 22 | 2023-01-04 | 1.0 | B07XGNHYC2 | raw_review_Subscription_Boxes | False | Nothing Edible...Just Gross Junk Food This was a monthly gift subscription. We g |
| 23 | 2023-01-04 | 3.0 | B09T5SKDPM | raw_review_Subscription_Boxes | True | Great Product, but.... I agree with the gentleman that commented about full size |
| 24 | 2023-02-05 | 1.0 | B0BKLKYWPY | raw_review_Subscription_Boxes | True | No real rock curation happening This is not a rock subscription regardless of wh |
| 25 | 2023-02-09 | 5.0 | B07DNM6GBC | raw_review_Subscription_Boxes | True | Great Good |
| 26 | 2023-03-09 | 5.0 | B09LVZ3T6C | raw_review_Subscription_Boxes | True | Open collector Box is a safe bet for a cool T and 2 pops Open collector Box is a |
| 27 | 2023-03-11 | 2.0 | B08L3SSNL5 | raw_review_Subscription_Boxes | True | The digital content I pay $40 a month for the kits but can do nothing with them  |
| 28 | 2023-03-20 | 3.0 | B07QXSYDGF | raw_review_Subscription_Boxes | True | Not usually my colors, but good for gifting. I'm an autumn and a lot of the colo |
| 29 | 2023-04-09 | 5.0 | B08JCKKDP5 | raw_review_Subscription_Boxes | False | This is super fun! I’ve got only one shirt so far. But I adored the design and c |
| 30 | 2023-04-12 | 1.0 | B09RQRTCCK | raw_review_Subscription_Boxes | True | Not worth it Not what I expected , tasteless |

## 下一步（判定链接线）

1. 抽取层：对 30 条摘要跑规则立场基线（eval_stance_baseline.py 口径）或凭据到位后的 LLM 档；2. 判定层：domain.decide 端到端（去重 → 计数 → 门禁 → Wilson 区间 → 四状态）；3. 溯源：每条样本含 shard/asin/review_date，逐条可回原始 CSV 验证。
