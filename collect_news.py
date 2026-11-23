"""Collect Korean entertainment headlines from Google News RSS."""
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

NOW = datetime.now(timezone.utc)
OUT = Path(__file__).with_name('news.json')
# Multiple narrow search queries improve recall without broad unrelated terms.
QUERIES = {
    'idol': ['(아이돌 OR 걸그룹 OR 보이그룹) (컴백 OR 신곡 OR 앨범) when:3d',
             '(K팝 OR 케이팝 OR 아이돌) (콘서트 OR 팬미팅 OR 화보) when:3d',
             '(아이돌 OR 걸그룹 OR 보이그룹) (공항패션 OR 뮤직비디오 OR 데뷔) when:3d',
             '(K-POP OR K팝 OR 아이돌) (티저 OR 음원 OR 활동 OR 팬사인회) when:3d'],
    'actor': ['(배우 OR 배우진) (캐스팅 OR 차기작 OR 출연) when:3d',
              '(배우 OR 연기자) (화보 OR 인터뷰 OR 수상) when:3d',
              '(배우 OR 연예인) (공식 발표 OR 소속사 OR 시사회) when:3d'],
    'drama': ['(드라마 OR 영화) (제작발표 OR 개봉 OR 캐스팅) when:3d',
              '(드라마 OR 영화) (시청률 OR 흥행 OR 시사회) when:3d'],
    'variety': ['(예능 OR 음악방송) (아이돌 OR 가수 OR 배우) when:3d',
                '(연예인 OR 아이돌) (예능 출연 OR 방송 출연) when:3d'],
    'issue': ['(연예계 OR 소속사 OR 연예인) (공식입장 OR 공식 발표 OR 수상) when:3d',
              '(아이돌 OR 배우) (시상식 OR 논란 OR 해명) when:3d',
              '(연예대상 OR 음악 시상식 OR 영화제) (수상 OR 발표) when:3d'],
}
items, seen, failures = [], set(), []
for category, queries in QUERIES.items():
    for query in queries:
        url = 'https://news.google.com/rss/search?' + urlencode({'q': query, 'hl': 'ko', 'gl': 'KR', 'ceid': 'KR:ko'})
        try:
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0 77MagazineNews/2.0'})
            with urlopen(req, timeout=18) as resp:
                root = ET.fromstring(resp.read(2_000_000))
            count = 0
            for item in root.findall('./channel/item'):
                title = unescape((item.findtext('title') or '').strip())
                link = (item.findtext('link') or '').strip()
                published_raw = item.findtext('pubDate') or ''
                src = item.find('source')
                source = (src.text or '').strip() if src is not None else 'Google 뉴스'
                try:
                    published = parsedate_to_datetime(published_raw).astimezone(timezone.utc)
                except Exception:
                    continue
                if not title or not link.startswith('https://') or not NOW - timedelta(hours=72) <= published <= NOW + timedelta(hours=1):
                    continue
                headline = re.sub(r'\s*[-|]\s*[^-|]+$', '', title).strip()
                key = re.sub(r'\W+', '', headline.lower())
                if key in seen:
                    continue
                seen.add(key)
                items.append({'title': headline[:220], 'url': link,
                              'category': category, 'source': source[:100],
                              'published': published.isoformat()})
                count += 1
                if count >= 45:
                    break
            print(category, count)
        except Exception as exc:
            failures.append(str(exc))
            print('feed error', category, exc)
items.sort(key=lambda x: x['published'], reverse=True)
if items:
    # Partial RSS failures must not erase previously collected stories.
    try:
        prior = json.loads(OUT.read_text(encoding='utf-8')).get('articles', []) if OUT.exists() else []
    except (OSError, json.JSONDecodeError):
        prior = []
    existing_urls = {item['url'] for item in items}
    for prev in prior:
        if not isinstance(prev, dict) or prev.get('url') in existing_urls:
            continue
        try:
            published = datetime.fromisoformat(prev.get('published','').replace('Z','+00:00'))
            if published >= NOW-timedelta(hours=72):
                items.append(prev)
                existing_urls.add(prev['url'])
        except (ValueError, TypeError, KeyError):
            continue
    items.sort(key=lambda a:a['published'],reverse=True)
    OUT.write_text(json.dumps({'updated_at': NOW.isoformat(), 'articles': items[:250]}, ensure_ascii=False, indent=2), encoding='utf-8')
elif not OUT.exists():
    OUT.write_text(json.dumps({'updated_at': NOW.isoformat(), 'articles': []}, ensure_ascii=False, indent=2), encoding='utf-8')
else:
    print('all feeds empty/failed, preserved prior news.json')
print('collected', len(items), 'errors', len(failures))
