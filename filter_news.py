"""77 MAGAZINE STUDIO — news.json quality filter.

Run after the existing Google News collector, before committing news.json.
This script only reads/writes news.json; it never changes the editor or workflows.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

NEWS_FILE = Path(__file__).resolve().parent / 'news.json'
# The script is normally placed at the repository root with news.json.
EXCLUDED_SOURCES = ('naver blog', 'weverse', 'tistory', '브런치스토리', '네이버 블로그')
EXCLUDED_PREFIXES = ('[시론]', '[사설]', '[칼럼]', '[기고]', '[기자수첩]', '[프리즘]')
OFF_TOPIC = ('엔비디아', '나스닥', '주식', '코스피', '코스닥', '모태펀드', '반도체', '증시', '환율', '금리', '부동산', '감귤', '지방선거')
ENTERTAINMENT = ('아이돌', '걸그룹', '보이그룹', '가수', '배우', '연예', '드라마', '영화', '예능', '공연', '음악방송', '앨범', '신곡', '데뷔', '팬미팅', '콘서트', '화보', '캐스팅', '시상식', '소속사', 'K팝', 'K-POP', '케이팝', '뮤직비디오', 'MAMA', 'OTT')


def normalized(text: str) -> str:
    text = re.sub(r'^\s*\[[^]]+\]\s*', '', text)
    text = re.sub(r'\([^)]*(?:종합|공식|인터뷰)[^)]*\)', ' ', text)
    return re.sub(r'[^가-힣a-z0-9]+', '', text.lower())


def tokens(text: str) -> set[str]:
    text = re.sub(r'\[[^]]+\]', ' ', text)
    return {x.lower() for x in re.findall(r'[가-힣a-zA-Z0-9]{2,}', text) if len(x) > 1}


def near_duplicate(a: str, b: str) -> bool:
    aa, bb = normalized(a), normalized(b)
    if aa == bb:
        return True
    # Avoid hiding separate short headlines about the same celebrity.
    if min(len(aa), len(bb)) < 22:
        return False
    ta, tb = tokens(a), tokens(b)
    overlap = len(ta & tb) / max(1, len(ta | tb))
    return overlap >= 0.70 and SequenceMatcher(None, aa, bb).ratio() >= 0.80


def relevant(article: dict) -> bool:
    title = str(article.get('title', '')).strip()
    source = str(article.get('source', '')).strip().lower()
    if not title or not article.get('url'):
        return False
    if any(x in source for x in EXCLUDED_SOURCES):
        return False
    if any(title.startswith(x) for x in EXCLUDED_PREFIXES):
        return False
    if any(x in title for x in OFF_TOPIC) and not any(x.lower() in title.lower() for x in ENTERTAINMENT):
        return False
    # Broad keywords like '컴백' can also occur in finance or politics.
    if article.get('category') == 'idol' and ('컴백' in title or 'K-POP' in title.upper()) and not any(x.lower() in title.lower() for x in ENTERTAINMENT):
        return False
    return True


def main() -> None:
    if not NEWS_FILE.exists():
        raise SystemExit('news.json을 찾을 수 없습니다. 이 파일을 저장소 맨 위에 올려주세요.')
    data = json.loads(NEWS_FILE.read_text(encoding='utf-8'))
    original = data.get('articles', [])
    retained = []
    for article in original:
        if not isinstance(article, dict) or not relevant(article):
            continue
        if any(near_duplicate(article['title'], old['title']) for old in retained):
            continue
        retained.append(article)
        if len(retained) >= 100:
            break
    # Safety: keep the source list if an aggressive rule would erase everything.
    if original and not retained:
        print('필터링 결과가 0건이라 기존 뉴스 데이터를 유지합니다.')
        return
    data['articles'] = retained
    NEWS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'필터 완료: {len(original)}건 → {len(retained)}건 (제외 {len(original)-len(retained)}건)')


if __name__ == '__main__':
    main()
