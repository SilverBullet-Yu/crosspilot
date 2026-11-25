"""规则立场基线：德语（或通用）文本 -> Stance，零 ML 依赖、零新 pip 包。

定位（2026-11-21）：正式立场抽取方案是可替换的 LLM API（不可依赖，Token 补贴
细则未确认），本模块是**不依赖 LLM 的透明规则基线**，并在 GERestaurant 基准上
实测其质量（data/sources/gerestaurant/baseline_eval.md），给后续 LLM 方案一个
对照基准。规则与词典全部内置、判定逐条可解释（返回命中词与规则名）。

立场语义（与 GERestaurant 评测口径一致）：support = 对目标的正面评价/推荐倾向，
oppose = 负面评价/不推荐，insufficient = 无极性信号或正负冲突不可判定。

三条透明规则：
1. 极性词典：手写德语核心词表（餐厅/服务/价格域）+ 少量英语核心词；变体处理 =
   全小写 + ß/ss 折叠（JS 侧 toLowerCase 不折 ß 是已知坑，Python 的 str.lower()
   同样不折，必须显式 .replace("ß", "ss")）+ 常见屈折后缀剥离（nette->nett、
   leckeren->lecker）。
2. 否定窗口：否定词（nicht/kein/ohne/nie/...）向前看 4 个 token，窗口内极性词
   极性翻转（奇偶翻转，兼容 "nicht un..." 双重否定）；"nicht schlecht" 判正、
   "keine Empfehlung" 判负即由此而来。
3. 从句切分：按标点与转折/并列标记（aber/doch/jedoch/sondern/und/oder/...）
   切分，各从句独立计分后求和，net>0 -> support，net<0 -> oppose，
   net==0 -> insufficient（无命中与正负打平均归为证据不足/冲突，与
   domain/evidence.py 判定管道的「冲突必须可见」哲学一致）。

已知局限（如实）：词典覆盖有限；"nicht nur lecker sondern auch ..." 类结构会
误翻转；"kann ich nicht bestätigen" 类元否定不处理；讽刺/反语不可识别。餐厅域
评测结论不可外推为商品域（见 baseline_eval.md）。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from crosspilot_api.domain.evidence import Stance

# ---- 词典：手写核心词（书面形式），匹配前统一做折叠归一 ----
# 德语正面（餐厅/服务/价格域）
_POSITIVE_DE = frozenset({
    "gut", "besser", "best", "super", "toll", "top", "klasse", "prima",
    "perfekt", "großartig", "hervorragend", "ausgezeichnet", "exzellent",
    "überragend", "fantastisch", "fabelhaft", "wunderbar", "zauberhaft",
    "spitze", "erstklassig", "genial", "ideal", "gelungen", "lecker",
    "köstlich", "schmackhaft", "appetitlich", "frisch", "saftig", "knusprig",
    "aromatisch", "würzig", "zart", "reichhaltig", "großzügig", "fair",
    "günstig", "preiswert", "preisgünstig", "nett", "freundlich",
    "sympathisch", "zuvorkommend", "aufmerksam", "höflich", "flott",
    "schnell", "zügig", "pünktlich", "kompetent", "professionell", "herzlich",
    "charmant", "liebevoll", "gemütlich", "stimmungsvoll", "romantisch",
    "stilvoll", "angenehm", "sauber", "ordentlich", "gepflegt", "hübsch",
    "schön", "wunderschön", "schmeckt", "schmecken", "geschmeckt",
    "empfehlenswert", "empfehlen", "empfehlung", "weiterempfehlen",
    "weiterzuempfehlen", "hausgemacht", "genuss", "bestens", "hammer",
    "wieder", "wiederkommen",
})
# 德语负面（餐厅/服务/价格域）
_NEGATIVE_DE = frozenset({
    "schlecht", "miserabel", "katastrophal", "katastrophe", "schrecklich",
    "furchtbar", "fürchterlich", "grauenhaft", "grausig", "entsetzlich",
    "schlimm", "übel", "ekelhaft", "eklig", "ungenießbar", "fade", "fad",
    "lauwarm", "kalt", "eiskalt", "trocken", "zäh", "wabbelig", "matschig",
    "pappig", "fettig", "ölig", "ranzig", "muffig", "verdorben", "versalzen",
    "verkocht", "angebrannt", "verbrannt", "dürftig", "mickrig", "winzig",
    "lieblos", "langweilig", "verspätet", "unpünktlich", "unfreundlich",
    "unhöflich", "arrogant", "genervt", "zynisch", "überfordert", "ignoriert",
    "warten", "wartet", "gewartet", "enttäuschend", "enttäuscht", "schade",
    "leider", "ärgerlich", "nervig", "nervt", "laut", "dreckig", "schmutzig",
    "schmierig", "unhygienisch", "kaputt", "mies", "überteuert", "abzocke",
    "abgezockt", "unverschämt", "inkompetent", "unorganisiert", "chaotisch",
    "falsch", "vergessen", "geschmacklos", "respektlos", "mangelhaft",
    "unappetitlich", "schimmelig", "abraten", "wenig", "aggressiv", "pech",
    "reingelegt", "verbesserungswürdig", "lügner", "unfair",
    "unprofessionell",
})
# 少量英语核心词（「通用」输入的最小覆盖，不是重点）
_POSITIVE_EN = frozenset({
    "good", "great", "excellent", "amazing", "awesome", "fantastic",
    "perfect", "superb", "wonderful", "lovely", "tasty", "delicious",
    "friendly", "recommend", "recommended", "best", "love", "loved",
})
_NEGATIVE_EN = frozenset({
    "bad", "terrible", "awful", "worst", "horrible", "disgusting", "rude",
    "dirty", "bland", "disappointing", "disappointed", "stale", "slow",
})
# 否定词（德语为主 + 英语最小集）；窗口内极性翻转
_NEGATORS = frozenset({
    "nicht", "kein", "keine", "keinen", "keiner", "keinem", "keines", "keins",
    "nie", "niemals", "nirgends", "nirgendwo", "ohne", "weder", "kaum",
    "keineswegs", "nichts", "nix", "not", "no", "never", "without", "nothing",
})
# 从句切分标记（转折/并列/因果），作为独立 token 出现时切分
_CLAUSE_MARKERS = frozenset({
    "aber", "doch", "jedoch", "allerdings", "andererseits", "stattdessen",
    "sondern", "denn", "weil", "obwohl", "und", "oder", "bzw",
    "beziehungsweise", "daher", "deshalb", "deswegen", "trotzdem", "dennoch",
})
_NEGATION_WINDOW = 4  # 否定词向后的生效 token 窗口（德语否定词先于被否定词）
# 屈折后缀剥离（德语形容词/名词常见词尾，从长到短尝试）
_INFLECTION_SUFFIXES = ("esten", "sten", "es", "er", "en", "em", "e", "n", "s")

_TOKEN_RE = re.compile(r"\w+")
_CLAUSE_SPLIT_RE = re.compile(r"[.,!?;:()\[\]\"']+")


def fold(text: str) -> str:
    """归一化：NFC -> 小写 -> 变体折叠，词典与文本双侧同口径。

    折叠两类已知变体坑：
    - ß/ẞ -> ss（JS toLowerCase 不折 ß；Python str.lower() 同样不折，须显式处理）
    - ae/oe/ue：德语用户生成文本常把 ä/ö/ü 转写为 ae/oe/ue（Luegner/kaufen/
      spaeter 实例见于本语料），两侧统一折算后才可互相匹配。
    """
    text = unicodedata.normalize("NFC", text).lower()
    text = text.replace("ß", "ss").replace("ẞ", "ss")
    return (text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
            .replace("Ä", "ae").replace("Ö", "oe").replace("Ü", "ue"))


# 负面双词组（按折叠后 token 对匹配，命中即计 -1）：
# no-go / Finger weg / (bleibt) weg 是德语差评的固定表达
_NEGATIVE_BIGRAMS = frozenset(
    (fold(a), fold(b)) for a, b in (("no", "go"), ("finger", "weg"), ("bleibt", "weg")))
# 比较级负面规则：从句同时含 besser 与下列标记（kann/könnte/mal/früher/…）
# 时，"besser" 计为负面——"war schon mal besser" / "könnte besser sein" 是
# 差评句式，单独的 besser 词典命中会误判为 support
_COMPARATIVE_NEG_MARKERS = frozenset(
    fold(w) for w in ("mal", "früher", "damals", "kann", "können", "könnte",
                      "sollte", "müsste"))
# 正面前缀：Lieblings-（Lieblingsitaliener 等复合词无法按整词穷举）
_POSITIVE_PREFIX = fold("lieblings")


_LEX_POS = frozenset(fold(w) for w in _POSITIVE_DE | _POSITIVE_EN)
_LEX_NEG = frozenset(fold(w) for w in _NEGATIVE_DE | _NEGATIVE_EN)
_NEGATORS_FOLDED = frozenset(fold(w) for w in _NEGATORS)
_CLAUSE_MARKERS_FOLDED = frozenset(fold(w) for w in _CLAUSE_MARKERS)


@dataclass(frozen=True)
class RuleHit:
    """一条可解释的规则命中。"""

    #: 命中的词典词形（折叠后）
    word: str
    #: 词典极性（翻转前）
    polarity: str  # "positive" | "negative"
    #: 是否被否定窗口翻转
    negated: bool
    #: 生效的否定词（未翻转时为 None）
    negator: str | None = None
    #: 规则名：lexicon_hit（直接命中）或 negation_flip（否定翻转）
    rule: str = "lexicon_hit"
    #: 所在从句文本片段（折叠后，截断至 60 字符，用于解释展示）
    clause_snippet: str = ""


@dataclass(frozen=True)
class StanceResult:
    """规则基线的完整判定结果，判定过程可逐条核对。"""

    stance: Stance
    #: 极性净分（正命中数 - 负命中数，翻转已计入）
    score: int
    hits: list[RuleHit] = field(default_factory=list)
    #: 从句数（切分后的非空从句）
    n_clauses: int = 0


def _lookup(token: str) -> tuple[str, str] | None:
    """词典查找：整词 -> 屈折后缀剥离 -> Lieblings- 前缀。

    返回 (词典词形, 极性) 或 None。整词优先，避免后缀剥离产生假命中。
    """
    if token in _LEX_POS:
        return token, "positive"
    if token in _LEX_NEG:
        return token, "negative"
    for suffix in _INFLECTION_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            stem = token[: -len(suffix)]
            if stem in _LEX_POS:
                return stem, "positive"
            if stem in _LEX_NEG:
                return stem, "negative"
    if token.startswith(_POSITIVE_PREFIX) and len(token) > len(_POSITIVE_PREFIX):
        return _POSITIVE_PREFIX, "positive"
    return None


def split_clauses(text: str) -> list[list[str]]:
    """简单从句切分：按标点切分，再在转折/并列标记 token 处断开。"""
    clauses: list[list[str]] = []
    current: list[str] = []
    for raw_clause in _CLAUSE_SPLIT_RE.split(text):
        for token in _TOKEN_RE.findall(fold(raw_clause)):
            if token in _CLAUSE_MARKERS_FOLDED:
                if current:
                    clauses.append(current)
                current = []
            else:
                current.append(token)
        if current:
            # 每个标点分块结束即落一段从句（逗号/句号都是从句边界）
            clauses.append(current)
            current = []
    return clauses


def classify_stance(text: str) -> StanceResult:
    """透明规则立场判定：词典命中 + 否定窗口翻转 + 从句级求和。

    空文本或无任何极性命中 -> insufficient；正负相抵（score==0）同样
    insufficient（证据冲突不可判定）。每个命中都附带规则名与词形，可解释。
    """
    if not text or not text.strip():
        return StanceResult(stance=Stance.INSUFFICIENT, score=0, hits=[], n_clauses=0)

    hits: list[RuleHit] = []
    score = 0
    clauses = split_clauses(text)
    for tokens in clauses:
        snippet = " ".join(tokens)[:60]
        # 比较级负面：从句内 "besser" + (kann/könnte/mal/früher/...) 即差评句式
        comparative_neg = ("besser" in tokens
                           and any(t in _COMPARATIVE_NEG_MARKERS for t in tokens))
        skip_next = False
        for i, token in enumerate(tokens):
            if skip_next:
                skip_next = False
                continue
            # 负面双词组优先于单词命中（如 no-go、Finger weg）
            if i + 1 < len(tokens) and (token, tokens[i + 1]) in _NEGATIVE_BIGRAMS:
                score -= 1
                hits.append(RuleHit(
                    word=f"{token} {tokens[i + 1]}",
                    polarity="negative",
                    negated=False,
                    rule="negative_bigram",
                    clause_snippet=snippet,
                ))
                skip_next = True
                continue
            looked_up = _lookup(token)
            if looked_up is None:
                continue
            word, polarity = looked_up
            if comparative_neg and word == "besser":
                # 比较级规则翻转：直接按负面计分，不经否定窗口
                score -= 1
                hits.append(RuleHit(
                    word=word,
                    polarity="positive",
                    negated=True,
                    rule="comparative_negative",
                    clause_snippet=snippet,
                ))
                continue
            # 否定窗口：向前看 _NEGATION_WINDOW 个 token，奇数个否定词即翻转
            window = tokens[max(0, i - _NEGATION_WINDOW):i]
            negators_in_window = [t for t in window if t in _NEGATORS_FOLDED]
            negated = len(negators_in_window) % 2 == 1
            if negated:
                # 否定翻转：正面词判负，负面词判正（"nicht schlecht" 判正）
                effective = "negative" if polarity == "positive" else "positive"
            else:
                effective = polarity
            delta = 1 if effective == "positive" else -1
            score += delta
            hits.append(RuleHit(
                word=word,
                polarity=polarity,
                negated=negated,
                negator=negators_in_window[-1] if negators_in_window else None,
                rule="negation_flip" if negated else "lexicon_hit",
                clause_snippet=snippet,
            ))
    if score > 0:
        stance = Stance.SUPPORT
    elif score < 0:
        stance = Stance.OPPOSE
    else:
        stance = Stance.INSUFFICIENT
    return StanceResult(stance=stance, score=score, hits=hits, n_clauses=len(clauses))


def stance_of(text: str) -> Stance:
    """只取立场的便捷入口（内部走 classify_stance，规则完全一致）。"""
    return classify_stance(text).stance
