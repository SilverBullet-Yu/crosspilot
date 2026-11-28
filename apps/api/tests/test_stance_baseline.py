"""规则立场基线单测 + GERestaurant 固定子集指标下限回归。

单测覆盖任务要求的关键行为：否定翻转、ß/ss 与 ae/oe/ue 变体折叠、
空文本 -> insufficient、大小写不敏感、从句正负相抵 -> insufficient、
负面双词组、比较级负面句式、命中可解释性、英语最小集。

指标下限回归：内嵌固定评测子集（random.Random(42).sample 于
GERestaurant 主表 3,078 条，N=100，随测试提交）。下限按 2026-11-21
实测（accuracy 0.520 / 宏 F1 0.440）取保守值 0.50 / 0.40：
- 不许定过高：留出正常演进的余量；
- 不许放水：词典或否定逻辑被改坏时（如否定翻转失效）指标会跌破下限。
"""

from __future__ import annotations

import json
from collections import Counter

from crosspilot_api.domain.evidence import Stance
from crosspilot_api.services.stance_baseline import (
    RuleHit,
    StanceResult,
    classify_claim_stance,
    classify_stance,
    fold,
    review_triage,
    stance_of,
)

SUBSET: list[tuple[str, str]] = [
    ('Das Bier zudem nur 4 statt 5dl gefüllt (auch bei den Nachbartischen).', 'oppose'),
    (
    'Neben den feinen Torten lieben wir dort auch traditionelle Gerichte, wie Ragout fin in'
    'der Königinpastete und jahreszeitliche Fleischgerichte.',
     'support'),
    ('Beides war eiskalt und geschmacksneutral, wirklich langweilig.', 'oppose'),
    ('Service sehr freundlich und mit Getränken sehr flott.', 'support'),
    ('Auch wirklich gut und habe ich auch noch nie gegessen.', 'support'),
    (
    'Die Bedienung hat das natürlich sofort gesehen und uns dafür ein Glas Wein angeboten.',
     'support'),
    ('Die kalten Sommerröllchen mit Huosin Sauce sind sehr zu empfehlen.', 'support'),
    ('Sehr gute Scampi, aber eben nur die.', 'support'),
    ('Eine Pizzabude ohne Ambitionen.', 'oppose'),
    (
    'Nette Menschen, gutes und leckeres Essen - bin über Tripadvisor drauf gekommen und werde'
    'definitiv wieder hingehen!',
     'support'),
    (
    'Location macht einen etwas angetaubten und unaufgeräumten und dennoch recht'
    'authentischen Eindruck.',
     'support'),
    ('Die Reaktion darauf leider Achselzucken.', 'oppose'),
    (
    'Preis-Leistungsverhältnis sehr gut, sehr nettes und zuvorkommendes Personal',
     'support'),
    (
    'In einem guten Restaurant wird einem das vorher gesagt, bevor sie auf den Tisch gestellt'
    'wird.',
     'oppose'),
    (
    'Wenn man das alles berücksichtigt, konnte ich mit meinem Teller sehr zufrieden sein.',
     'support'),
    ('Das Essen war mehr als ausreichend und es hat sehr gut geschmeckt.', 'support'),
    (
    'Der Fisch war sehr durch, welches vom Kellner ohne Reaktion registriert wurde!',
     'oppose'),
    ('Aber er war nicht ganz schlecht.', 'insufficient'),
    ('Beim Cheeseburger war nur eine Spur Cheese aufgelegt.', 'oppose'),
    (
    'Wie schon oben beschrieben kann man hier nett sitzen, zum essen würde ich lieber beim'
    'nächsten Besuch in LOC ein anderes Restaurant besuchen.',
     'insufficient'),
    (
    'Auf die Frage ob ich ein neues Besteck kriege - kein Selbstverständlich, sondern warum'
    'möchte sie das nicht mehr nehmen!',
     'oppose'),
    (
    'Auch wenn es heut zu Tage vielleicht Mode ist, hat das mit Respekt und Gastlichkeit'
    'wenig gemeinsam.',
     'oppose'),
    (
    'Geschätzt 10 Bedienungen haben versucht uns zu versorgen immer wieder'
    'Doppelbestellungen, weil keiner wirklich Wuste was der andere macht.',
     'oppose'),
    (
    'Das Essen passt in die Brauhausatmosphäre, ist deftig und konservativ - halt was wo man'
    'Bier und nicht Wein dazu trinken möchte - wobei die Preise weniger nach Brauhaus,'
    'sondern eher nach weissgedecktem Weinlokal anmuten.',
     'insufficient'),
    (
    'Wir sind natürlich sofort gegangen und konnten von unserer schönen Hotelterrasse gut'
    'sehen, dass der Ansturm ausblieb.',
     'support'),
    ('Der Empfang durch das Personal war sehr herzlich und angenehm.', 'support'),
    ('Von der Kartoffelsuppe waren wir enttäuscht.', 'oppose'),
    (
    'Wer "neu" in der Tapaswelt ist, wird super beraten - vom Essen bis zum passenden Wein.',
     'support'),
    ('Gute Qualität der Speisen und der Empfehlungen.', 'support'),
    ('Kann man empfehlen.', 'support'),
    (
    '"Stabile Brauhausküche" beschreibt es wohl am besten und so passt es auch nach LOC.',
     'support'),
    ('Insgesamt eher unterer Durchschnitt bei den örtlichen LOC.', 'oppose'),
    ('Urige Wirtschaft mit einem coolen Ambiente.', 'support'),
    ('Auch geschmacklich gibt es hier bessere Alternativen.', 'oppose'),
    (
    'Nach der BUGA in RESTAURANT_NAME - tolle Location, mega leckeres Essen und ganz wichtig'
    '- ein toller, freundlicher und sehr zuvorkommender Service 👍 Wir kommen wieder!',
     'support'),
    ('Wir kommen wieder.', 'support'),
    (
    'Man zahlt zwar etwas mehr, der Service, die nette Bedienung und die Atmosphäre sind es'
    'wert!',
     'insufficient'),
    (
    'Um es vorweg zu nehmen: Es ist laut hier, die Halbe Hofbräu Bier ist mit 5,40 Euro'
    'ziemlich teuer, und unser Kellner war überfordert.',
     'oppose'),
    ('Alle Gerichte waren sehr lecker, die Portionen groß.', 'support'),
    ('Salatdressing komisch gewürzt.', 'oppose'),
    ('Alles in allem ein sehr gelungener Besuch!', 'support'),
    ('Der Leberkäse hingegen sehr gut.', 'support'),
    ('Befremdet war ich über das Sesamöl in der Guacamole.', 'oppose'),
    ('Das war der letzte Besuch!', 'oppose'),
    ('Der Chef konnte nicht gefunden werden.', 'oppose'),
    (
    'das spätere essen (Pizza) war wirklich gut, aber so viel Zeit während der Woche haben'
    'wir nicht und werden deshalb auch nicht wieder kommen.',
     'support'),
    ('Ich bin sehr enttäuscht und komme nicht wieder.', 'oppose'),
    ('Essen war gut.', 'support'),
    (
    'Das Personal ist nur aufgesetzt freundlich, das Essen Durchschnitt, die Speisenauswahl'
    'wenig attraktiv.',
     'insufficient'),
    ('Der Blick von der Dachterasse ist der Wahnsinn.', 'support'),
    (
    'Der Service ist super aufmerksam und kompetent sowie nett und hilfsbereit.',
     'support'),
    (
    'Leider war der Hauptgang Rinderfilet so zäh und durchwachsen dass dies den guten'
    'Gesamteindruck nachhaltig beschädigt hat.',
     'oppose'),
    ('Diese Gaststätte hat eigentlich nicht mal einen Stern verdient.', 'oppose'),
    ('Besonders charmant war unser Kellner Bruno.', 'support'),
    ('Enttäuschend war für uns alle die Essensqualität.', 'oppose'),
    ('Ein Besuch lohnt sich auf jeden Fall.', 'support'),
    (
    'Das bestellte Essen war gut, die Beilagen hatten wenig mit typisch portugiesisch zu tun.',
     'insufficient'),
    (
    'Ich werde das Restaurant nicht mehr aufsuchen und kann es auch nicht empfehlen.',
     'oppose'),
    (
    'Hier gibts Burger und dazu überteuerten Wein, alles ist ziemlich lecker, doch die'
    'umliegenden FalaffelPlaces sind alle so viel besser.',
     'insufficient'),
    ('Ein LOC mir wirklich leckerem Essen bei schöner Aussicht.', 'support'),
    ('Der war gut.', 'support'),
    ('Die Haxe war extrem fett und der Knödel poppig und geschmacklos.', 'oppose'),
    (
    'Eine halbe Stunde nach der Bestellung des Weines (LOC) wurden wir über dessen nicht mehr'
    'Vorhandensein informiert, und es dauerte 1 weitere Stunde bis der Alternativwein'
    'serviert wurde.',
     'oppose'),
    ('Die Haxe mit Knödel war gut.', 'support'),
    ('Insgesamt wirklich gut, Currywurst mit Pommes ist auch zu empfehlen.', 'support'),
    ('Das fanden wir unwürdig.', 'oppose'),
    ('Sehr freundlicher Gastgeber mit einem tollen Team.', 'support'),
    (
    'Auch der Murrejubbel Knödel und vor allem das LOC mit Apfelreduktion war ein Highlight.',
     'support'),
    (
    'Als ich dieses reklamiert hatte, dauerte es noch ewig bis ich ein neues Glas bekommen'
    'hatte.',
     'oppose'),
    ('Ich habe schon deutlich besser gegessen und nur die Hälfte bezahlt.', 'oppose'),
    ('RESTAURANT_NAME ist eines mit konsequenter Speisekarte.', 'support'),
    ('Sie war super freundlich, zuvorkommend und kompetent :)', 'support'),
    (
    'Daraufhin hat sie mich angepamt, ich würde an einem Tisch sitzen der gesperrt sei.',
     'oppose'),
    (
    'Die traditionellen Innenräume sind gemütlich auf der einen Seite und professionell auf'
    'der anderen.',
     'support'),
    ('Das hat nichts mit positiven Erlebnis zu tun!', 'oppose'),
    (
    'Das Essen schmeckte wirklich herrvorragend und das Personal war sehr aufmerksam und'
    'freundlich.',
     'support'),
    (
    'Als sehr schmackhaft empfinde ich den Kartoffelsalat, der nicht aus dem Eimer kommt und'
    'frisch zubereitet wird.',
     'support'),
    ('Essen war lecker, preislich okay.', 'insufficient'),
    (
    'Als das Essen kam, wurden wir nicht enttäuscht: lecker, frisch und gute Portionen.',
     'support'),
    ('Der Banker würde triple A vergeben.', 'support'),
    ('Vorspeise Carpaccio war sehr gut dünn geschnitten und fein abgeschmeckt.', 'support'),
    ('Der Äppelwoi ist eine Katastrophe.', 'oppose'),
    (
    'Aber was hier aktuell kredenzt wird und vor allem das unprofessionelle Ambiente schreckt'
    'ab.',
     'oppose'),
    ('Eine Geräuschkulisse wie auf dem Bahnhof.', 'oppose'),
    ('Ein Steakhouse ohne Ofenkartoffel ist an Absurdität nicht zu überbieten!', 'oppose'),
    (
    'In Bezug auf Servicequalität kann die Leitung des Hauses nach unserer Erfahrung noch'
    'deutlich nachbessern und den Anreiz für Gäste erhöhen, dort zu speisen.',
     'oppose'),
    ('Die Möglichkeit online zu bestellen ist innovativ.', 'support'),
    (
    'Darauf angesprochen meint der „Oberkellner“ nur: „Ich habe alles bestellt, ich bin aus'
    'dem Schneider.',
     'oppose'),
    ('Das Ambiente ist auch super und für ein Bräustüberl absolut stimmig.', 'support'),
    (
    'Wir waren hier essen und mit der Qualität des Essens wirklich super zufrieden.',
     'support'),
    (
    'Wir wurden noch in keinem Cafe oder Lokal so extrem unfreundlich behandelt!!',
     'oppose'),
    ('Egal was für Extrawünsche man hat, Andrea findet eine Lösung.', 'support'),
    (
    'Authentisch überragend gute Gerichte von ausgezeichnete Qualität, man fühlt sich fast'
    'wie in LOC.',
     'support'),
    (
    'Schade dass bei so einer super Lage der Service so zu wünschen übrig lässt.',
     'insufficient'),
    (
    'Daß das nicht klappen kann am Valentinstag wenn Paate gemütlich feiern wollen ist wohl'
    'völlig klar.',
     'oppose'),
    (
    'Als Dessert ein sehr gut geschenkter Sambuca (7,50 €) und ein Linie-Aquavit (4,90 €).',
     'support'),
    (
    'Innovative Chefs mit intensivem Internet-Marketing; anfangs dachte ich, fast „zuviel des'
    'Guten“, was wird da auf mich zukommen.',
     'support'),
    (
    'Sehr authentisches portugiesisches Restaurant mit gut eingespieltem Service.',
     'support'),
    (
    'Bei bestem Service von Jaques und seinen Kollegen und hausgemachter Pasta konnten wir'
    'heute ein Stück LOC genießen.',
     'support'),
    (
    'Wir mussten ewig warten, bis sie überhaupt einmal kam, war dann nicht besonders'
    'freundlich und kam dann auch nur einmal um uns Essen und Trinken zu bringen.',
     'oppose'),
]


def test_empty_and_blank_text_insufficient() -> None:
    """空文本/纯空白必须 insufficient，且无可解释命中。"""
    assert stance_of("") is Stance.INSUFFICIENT
    assert stance_of("   \t\n ") is Stance.INSUFFICIENT
    result = classify_stance("   ")
    assert result.score == 0
    assert result.hits == []
    assert result.n_clauses == 0


def test_positive_and_negative_basic() -> None:
    assert stance_of("Die Speisen waren sehr gut.") is Stance.SUPPORT
    assert stance_of("Das Essen war eine Katastrophe.") is Stance.OPPOSE
    assert stance_of("Super Service und leckeres Essen.") is Stance.SUPPORT
    assert stance_of("Unfreundliche Bedienung und kaltes Essen.") is Stance.OPPOSE


def test_negation_flip() -> None:
    """否定窗口：正面词被否定 -> oppose；否定负面词（litotes）-> support。"""
    assert stance_of("Die Speisen waren nicht gut.") is Stance.OPPOSE
    assert stance_of("Der Service war nicht schlecht.") is Stance.SUPPORT
    assert stance_of("Kein freundliches Personal.") is Stance.OPPOSE
    assert stance_of("Nie wieder!") is Stance.OPPOSE
    # 翻转命中必须可解释：rule=negation_flip，negator 记录否定词
    result = classify_stance("Die Speisen waren nicht gut.")
    flips = [h for h in result.hits if h.rule == "negation_flip"]
    assert len(flips) == 1
    assert flips[0].negator == "nicht"
    assert flips[0].negated is True
    assert flips[0].word == "gut"


def test_eszett_and_umlaut_variants() -> None:
    """ß/ss 与 ä/ö/ü <-> ae/oe/ue 双向匹配（JS ß 折叠坑的 Python 侧对策）。"""
    assert stance_of("Das Essen war großartig.") is Stance.SUPPORT
    assert stance_of("Das Essen war grossartig.") is Stance.SUPPORT
    assert stance_of("GROSSARTIG!") is Stance.SUPPORT  # 大小写不敏感
    assert fold("GROSSARTIG") == fold("großartig") == "grossartig"
    # 用户生成文本常见转写：Luegner / Lügner 同判
    assert stance_of("Er wurde als Luegner dargestellt.") is Stance.OPPOSE
    assert stance_of("Er wurde als Lügner dargestellt.") is Stance.OPPOSE


def test_case_insensitive() -> None:
    assert stance_of("SCHLECHTER SERVICE!") is Stance.OPPOSE
    assert stance_of("Das Essen war LECKER.") is Stance.SUPPORT


def test_mixed_clauses_insufficient() -> None:
    """从句切分后正负相抵 -> insufficient（证据冲突保持可见）。"""
    assert stance_of("Essen lecker, jedoch überteuert.") is Stance.INSUFFICIENT
    result = classify_stance("Essen top, Service schlecht.")
    assert result.n_clauses == 2
    assert result.stance is Stance.INSUFFICIENT


def test_no_hits_insufficient() -> None:
    assert stance_of("Das Restaurant hat 42 Sitzplätze.") is Stance.INSUFFICIENT


def test_negative_bigrams() -> None:
    assert stance_of("Finger weg von diesem Laden!") is Stance.OPPOSE
    assert stance_of("Ein absolutes NO-GO!") is Stance.OPPOSE


def test_comparative_negative() -> None:
    """"könnte/mal + besser" 是差评句式，besser 计负。"""
    assert stance_of("Der Service könnte besser sein.") is Stance.OPPOSE
    assert stance_of("Es war schon mal besser.") is Stance.OPPOSE
    # 无比较级标记时 besser 保持正面词典极性
    assert stance_of("Das neue Konzept ist deutlich besser.") is Stance.SUPPORT


def test_hits_explainable() -> None:
    """每个判定必须带命中的规则名、词形与从句片段，可逐条核对。"""
    result = classify_stance(
        "Ein gemütlicher Bierkeller mit freundlicher und flotter Bedienung.")
    assert result.stance is Stance.SUPPORT
    assert result.score > 0
    assert {h.word for h in result.hits} >= {"gemuetlich", "freundlich", "flott"}
    assert all(h.clause_snippet for h in result.hits)
    assert all(h.rule in ("lexicon_hit", "negation_flip", "negative_bigram",
                          "comparative_negative") for h in result.hits)
    assert all(isinstance(h, RuleHit) for h in result.hits)


def test_result_type_contract() -> None:
    """StanceResult 契约：stance 是 domain 层 Stance，分值与命中一致。"""
    result: StanceResult = classify_stance("Das Essen war lecker.")
    assert isinstance(result.stance, Stance)
    assert result.score == sum(1 if h.polarity == "positive" else -1 for h in result.hits)


def test_english_minimal() -> None:
    """通用输入的最小英语覆盖（不是重点，只保证不崩与基本方向）。"""
    assert stance_of("The food was great, service excellent.") is Stance.SUPPORT
    assert stance_of("Rude staff and dirty tables.") is Stance.OPPOSE


# ---- 固定子集指标下限回归（GERestaurant，N=100，seed=42） ----


def _subset_metrics() -> tuple[float, float]:
    """在内嵌固定子集上计算 accuracy 与宏 F1（与评测脚本同一口径）。"""
    rows = json.loads(json.dumps(SUBSET))
    true_pos: Counter = Counter()
    gold_n: Counter = Counter()
    pred_n: Counter = Counter()
    for text, gold in rows:
        pred = classify_stance(text).stance.value
        gold_n[gold] += 1
        pred_n[pred] += 1
        if pred == gold:
            true_pos[gold] += 1
    accuracy = sum(true_pos.values()) / len(rows)
    f1s = []
    for s in ("support", "oppose", "insufficient"):
        precision = true_pos[s] / pred_n[s] if pred_n[s] else 0.0
        recall = true_pos[s] / gold_n[s] if gold_n[s] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1s.append(f1)
    return accuracy, sum(f1s) / len(f1s)


def test_review_triage_only_accepts_strong_support_as_low_priority() -> None:
    strong = "Sehr gut, super, toll, klasse und perfekt."
    result = classify_stance(strong)
    assert result.stance is Stance.SUPPORT
    assert review_triage(strong, result).required is False


def test_review_triage_keeps_oppose_negation_mixed_and_short_for_review() -> None:
    samples = [
        "Schlecht, mies, kaputt, schlimm und furchtbar.",
        "Nicht schlecht.",
        "Gut aber schlecht.",
        "Gut.",
    ]
    for text in samples:
        assert review_triage(text, classify_stance(text)).required is True


def test_claim_stance_isolates_cross_claim_polarity() -> None:
    text = "Der Preis ist überteuert, aber die Fächer sind sehr gut."
    features = classify_claim_stance(text, "features")
    price = classify_claim_stance(text, "price")
    assert features.stance is Stance.SUPPORT
    assert price.stance is Stance.OPPOSE
    assert features.scope == price.scope == "claim_clauses"
    assert features.n_clauses == price.n_clauses == 1
    assert features.total_clauses == price.total_clauses == 2
    assert "faecher" in features.matched_aspect_terms
    assert "preis" in price.matched_aspect_terms
    assert {hit.word for hit in features.hits} == {"gut"}
    assert {hit.word for hit in price.hits} == {"ueberteuert"}


def test_claim_stance_keeps_negation_inside_selected_clause() -> None:
    result = classify_claim_stance("Die Fächer sind nicht gut, der Preis ist fair.", "features")
    assert result.stance is Stance.OPPOSE
    assert result.hits[0].rule == "negation_flip"
    assert result.hits[0].negator == "nicht"
    assert result.n_clauses == 1
    assert result.total_clauses == 2


def test_claim_stance_fallback_requires_review_for_custom_or_missing_terms() -> None:
    for claim_id in ("features", "custom-waterproof", "unassigned"):
        text = "Dieses Produkt ist wirklich gut super toll perfekt."
        result = classify_claim_stance(text, claim_id)
        assert result.scope == "whole_text_fallback"
        triage = review_triage(text, result)
        assert triage.required is True
        assert any("回退整条评论" in reason for reason in triage.reasons)


def test_claim_scope_is_visible_even_for_strong_support() -> None:
    text = "Die Fächer sind wirklich gut super toll perfekt."
    result = classify_claim_stance(text, "features")
    triage = review_triage(text, result)
    assert result.scope == "claim_clauses"
    assert triage.required is False
    assert any("仅计 1/1 个相关从句" in reason for reason in triage.reasons)


def test_custom_claim_terms_enable_scoped_stance() -> None:
    text = "Der Preis ist überteuert, aber die wasserdichte Tasche ist sehr gut."
    result = classify_claim_stance(text, "custom-waterproof", ("wasserdicht",))
    assert result.stance is Stance.SUPPORT
    assert result.scope == "claim_clauses"
    assert result.n_clauses == 1
    assert result.total_clauses == 2
    assert result.matched_aspect_terms == ("wasserdicht",)
    assert {hit.word for hit in result.hits} == {"gut"}


def test_explicit_empty_terms_do_not_fall_back_to_builtin_dictionary() -> None:
    text = "Der Preis ist überteuert, aber die Fächer sind sehr gut."
    result = classify_claim_stance(text, "features", ())
    assert result.stance is Stance.INSUFFICIENT
    assert result.scope == "whole_text_fallback"
    assert review_triage(text, result).required is True


def test_fixed_subset_metric_floors() -> None:
    accuracy, macro_f1 = _subset_metrics()
    assert len(SUBSET) == 100
    # 2026-11-21 实测 accuracy 0.540 / 宏 F1 0.465；下限取保守值（见文件头说明）
    assert accuracy >= 0.50, f"accuracy 跌破下限：{accuracy:.3f}"
    assert macro_f1 >= 0.40, f"宏 F1 跌破下限：{macro_f1:.3f}"
