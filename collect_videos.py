"""Fetch recent uploads from verified official YouTube channel RSS feeds, no API key."""
import json
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import urlopen, Request
import xml.etree.ElementTree as ET

CHANNELS = {
    'HYBE LABELS': 'UC3IZKseVpdzPSBaWxBxundA',
    'SMTOWN': 'UCEf_Bc-KVd7onSeifS3py9g',
    'JYP Entertainment': 'UCaO6TYtlC8U5ttz62hTrZgg',
}
ATOM = '{http://www.w3.org/2005/Atom}'
YT = '{http://www.youtube.com/xml/schemas/2015}'
OUT = Path(__file__).with_name('videos.json')
now = datetime.now(timezone.utc)
videos, errors = [], []
for channel, cid in CHANNELS.items():
    url = f'https://www.youtube.com/feeds/videos.xml?channel_id={cid}'
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 77Magazine/1.0'})
        with urlopen(req, timeout=20) as response:
            root = ET.fromstring(response.read(2_000_000))
        for entry in root.findall(f'{ATOM}entry'):
            video_id = entry.findtext(f'{YT}videoId', '')
            title = entry.findtext(f'{ATOM}title', '')
            published = entry.findtext(f'{ATOM}published', '')
            if not (len(video_id) == 11 and title and published):
                continue
            date = datetime.fromisoformat(published.replace('Z', '+00:00'))
            if date < now - timedelta(days=14):
                continue
            videos.append({'id': video_id, 'title': title, 'channel': channel,
                           'url': f'https://www.youtube.com/watch?v={video_id}',
                           'published': date.isoformat()})
        print(channel, 'OK')
    except Exception as exc:
        errors.append(str(exc))
        print(channel, 'ERROR', exc)

seen, unique = set(), []
for v in sorted(videos, key=lambda x: x['published'], reverse=True):
    if v['id'] not in seen:
        unique.append(v)
        seen.add(v['id'])
if unique:
    OUT.write_text(json.dumps({'updated_at': now.isoformat(), 'videos': unique[:120]}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('saved', len(unique), 'videos')
elif not OUT.exists():
    OUT.write_text(json.dumps({'updated_at': now.isoformat(), 'videos': []}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('no feeds available; generated empty file')
else:
    print('no valid new results; preserved previous file')
