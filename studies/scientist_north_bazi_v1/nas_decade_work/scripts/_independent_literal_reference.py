"""Standalone literal-table QA reference; no study data loaded."""
import numpy as np

def require(ok,message):
    if not bool(ok): raise AssertionError(message)

STEMS = list('甲乙丙丁戊己庚辛壬癸')

GODS = '比肩 劫财 食神 伤官 偏财 正财 七杀 正官 偏印 正印'.split()

LITERAL_ROWS = {'甲': '比肩 劫财 食神 伤官 偏财 正财 七杀 正官 偏印 正印', '乙': '劫财 比肩 伤官 食神 正财 偏财 正官 七杀 正印 偏印', '丙': '偏印 正印 比肩 劫财 食神 伤官 偏财 正财 七杀 正官', '丁': '正印 偏印 劫财 比肩 伤官 食神 正财 偏财 正官 七杀', '戊': '七杀 正官 偏印 正印 比肩 劫财 食神 伤官 偏财 正财', '己': '正官 七杀 正印 偏印 劫财 比肩 伤官 食神 正财 偏财', '庚': '偏财 正财 七杀 正官 偏印 正印 比肩 劫财 食神 伤官', '辛': '正财 偏财 正官 七杀 正印 偏印 劫财 比肩 伤官 食神', '壬': '食神 伤官 偏财 正财 七杀 正官 偏印 正印 比肩 劫财', '癸': '伤官 食神 正财 偏财 正官 七杀 正印 偏印 劫财 比肩'}

TG = {day: dict(zip(STEMS, [GODS.index(v) for v in row.split()])) for day, row in LITERAL_ROWS.items()}

HIDDEN = {'子': '癸', '丑': '己癸辛', '寅': '甲丙戊', '卯': '乙', '辰': '戊乙癸', '巳': '丙戊庚', '午': '丁己', '未': '己丁乙', '申': '庚壬戊', '酉': '辛', '戌': '戊辛丁', '亥': '壬甲'}

def encode(yp, mp, dp):
    """Literal target table and direct branch loop; no production helper import."""
    reference, visible = (dp[0], {yp[0], mp[0]})
    result = np.zeros((2, 10), dtype=np.int16)
    for m in (0, 1):
        for s in [yp[0], mp[0]]:
            result[m, TG[reference][s]] += 1
        for b in [yp[1], mp[1], dp[1]]:
            source = HIDDEN[b]
            exposed = [s for s in source if s in visible]
            s = exposed[0] if m == 1 and exposed else source[0]
            result[m, TG[reference][s]] += 1
    require(np.all(result.sum(axis=1) == 5), 'Independent five-position count sum failure')
    return result
