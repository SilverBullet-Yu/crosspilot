# L1 分层采样清单（ADR-0005 A5 · 美国市场试点）

> 生成：scripts/build_l1_sample_frame.py --n 30 ｜ 采样框：星级×时间分层，
> 星级配额 neg/neu/pos = (10, 5, 15)（负向 ≥33%），
> 时间层 2021/2022/2023H1（试点数据止于 2023-08），层内系统抽样（确定性、无种子）。

**硬约束边界（manifest tier_caveat 同源）**：本清单来自 Amazon.com 美国市场，仅作 L1 判定链方法演练（去重→抽取→门禁→区间），**不得写入德国市场偏好结论**。

## 采样框（层级池大小 → 实采）

| 星级层 | 2021 | 2022 | 2023H1 | 层合计 |
|---|---|---|---|---|
| neg(1-2星) | 1034 | 544 | 124 | 12 实采 |
| neu(3星) | 417 | 226 | 42 | 6 实采 |
| pos(4-5星) | 2223 | 1296 | 301 | 12 实采 |

## 样本清单（逐条可溯源：shard/asin/日期/星级）

| # | review_date | rating | asin | shard | verified | 摘要（前 80 字符） |
|---|---|---|---|---|---|---|
| 1 | 2021-01-01 | 1.0 | B0742LVLMJ | raw_review_Subscription_Boxes | True | Not worth it Real let down. Had 3 products in it. |
| 2 | 2021-01-01 | 3.0 | B07G584SHG | raw_review_Subscription_Boxes | True | My cats just weren't Interested... ...in anything other than the feathers of the |
| 3 | 2021-01-01 | 5.0 | B07FT4FMWX | raw_review_Subscription_Boxes | True | Beginners app coding The kid is in love with learning to code. She is doing a gr |
| 4 | 2021-03-05 | 1.0 | B07KTB8PHS | raw_review_Subscription_Boxes | True | A box of random stationary at retail price. Not worth it! A few random pens and  |
| 5 | 2021-03-11 | 4.0 | B07GS3H343 | raw_review_Subscription_Boxes | True | Good Stuff! The only reason I took a star off was for the price point. The bouqu |
| 6 | 2021-05-18 | 2.0 | B07QXSYDGF | raw_review_Subscription_Boxes | True | Cute packaging. Low quality products. This had some cute stuff in it but it’s de |
| 7 | 2021-05-22 | 3.0 | B07XKF8CB3 | raw_review_Subscription_Boxes | True | Not consistent Not consistent with amounts of treats. Sometimes get bags and som |
| 8 | 2021-05-24 | 4.0 | B07KC11QFV | raw_review_Subscription_Boxes | True | Wide variety of outdoor products. Something for everyone. I found the mix of pro |
| 9 | 2021-08-01 | 1.0 | B088YB3PRB | raw_review_Subscription_Boxes | True | Repetitive Cant get ankle socks. When I do they’re the dame three pairs. |
| 10 | 2021-08-13 | 5.0 | B07NBPQL3C | raw_review_Subscription_Boxes | True | dont believe the naysayers, its worth it this is a great quarterly shipment. wel |
| 11 | 2022-01-01 | 1.0 | B07G584SHG | raw_review_Subscription_Boxes | True | What a mistake on my part Have been trying to CANCEL since first box....no savin |
| 12 | 2022-01-01 | 5.0 | B08R5JJGB3 | raw_review_Subscription_Boxes | True | Excellent Quality and Price Each month I look forward to my Disney Tee! The qual |
| 13 | 2022-01-03 | 3.0 | B08KWJ5DXV | raw_review_Subscription_Boxes | False | This was a bad kit I did the crochet subscription for a year and loved it!! The  |
| 14 | 2022-03-07 | 1.0 | B08GYDJQ9D | raw_review_Subscription_Boxes | True | You can make them yourself much less expensive Two costly |
| 15 | 2022-03-12 | 5.0 | B097B2N157 | raw_review_Subscription_Boxes | True | Great shirt The image of Q does not look like Q. But other than that the shirt i |
| 16 | 2022-05-24 | 2.0 | B08F814PSW | raw_review_Subscription_Boxes | True | Not bad but not amazing I made one of the recipes and it looked worse than it ta |
| 17 | 2022-06-06 | 3.0 | B07HP1T567 | raw_review_Subscription_Boxes | True | The box was fun and engaging! I enjoyed the experience until I tried to access t |
| 18 | 2022-06-07 | 5.0 | B09293LP97 | raw_review_Subscription_Boxes | True | Junk journal dream box! There's so many different items in this box including st |
| 19 | 2022-08-18 | 2.0 | B09LWFPZPR | raw_review_Subscription_Boxes | True | The box is months behind schedule of release Great box when you finally get it.  |
| 20 | 2022-09-03 | 5.0 | B09R2PCK8N | raw_review_Subscription_Boxes | True | Great addition to my collection Graet box and contents. |
| 21 | 2023-01-01 | 1.0 | B07S63NKNB | raw_review_Subscription_Boxes | False | Expensive and too intricate to enjoy. Gifted this to my wife for Christmas 2020. |
| 22 | 2023-01-01 | 5.0 | B087YPRGKB | raw_review_Subscription_Boxes | True | Dog loves it |
| 23 | 2023-01-04 | 3.0 | B09T5SKDPM | raw_review_Subscription_Boxes | True | Great Product, but.... I agree with the gentleman that commented about full size |
| 24 | 2023-02-03 | 1.0 | B08M9X9KTN | raw_review_Subscription_Boxes | False | Vegan junk food A friend sent this to me as a gift. Most of this is not even org |
| 25 | 2023-02-09 | 5.0 | B07DNML26P | raw_review_Subscription_Boxes | True | awesome surprise box included really great funkos and shirt my son loved it. gre |
| 26 | 2023-03-10 | 1.0 | B0742LVLMJ | raw_review_Subscription_Boxes | True | 2nd box I've received worst box [[VIDEOID:f2700644a138dd0965eeb55476e95c7e]] So  |
| 27 | 2023-03-10 | 5.0 | B09LWP4TWW | raw_review_Subscription_Boxes | True | Love dr strange and this box was my favorite this year Always love my marvel col |
| 28 | 2023-03-20 | 3.0 | B07QXSYDGF | raw_review_Subscription_Boxes | True | Not usually my colors, but good for gifting. I'm an autumn and a lot of the colo |
| 29 | 2023-04-10 | 5.0 | B096MS17VY | raw_review_Subscription_Boxes | True | Not everyone like nude lipstics I only using brushes I prefer reds and pick colo |
| 30 | 2023-04-12 | 1.0 | B09RQRTCCK | raw_review_Subscription_Boxes | True | Not worth it Not what I expected , tasteless |

## 下一步（判定链接线）

1. 抽取层：对 30 条摘要跑规则立场基线（eval_stance_baseline.py 口径）或凭据到位后的 LLM 档；2. 判定层：domain.decide 端到端（去重 → 计数 → 门禁 → Wilson 区间 → 四状态）；3. 溯源：每条样本含 shard/asin/review_date，逐条可回原始 CSV 验证。
