"""Optional official Meta Business Discovery collector + best-effort indexed news discovery.

Environment variables for official media:
IG_USER_ID, IG_ACCESS_TOKEN (store as GitHub Actions secrets).
Without credentials, posts are explicitly empty; never forge Instagram posts.
"""
import json
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ACCOUNTS = ['eyesmag','izitmag_','fastpapermag','hipkr_','_tripgoing','ymagazine_official','ourlogmag','ent4k_mag','ddak.mag']
OUT = Path(__file__).with_name('instagram.json')
NOW = datetime.now(timezone.utc)

def get(url):
    req=Request(url, headers={'User-Agent':'77MagazineMonitor/1.0 (+GitHub Actions)', 'Accept':'application/json, application/xml;q=0.9, */*;q=0.8'})
    with urlopen(req,timeout=18) as response:
        return response.read(2_000_000)

def fetch_graph(account, user_id, token):
    # Business Discovery only works for eligible professional accounts and approved permissions.
    fields=f'business_discovery.username({account}){{username,media.limit(12){{id,caption,permalink,timestamp,media_type}}}}'
    from urllib.parse import urlencode
    query=urlencode({'fields':fields,'access_token':token})
    result=json.loads(get(f'https://graph.facebook.com/v27.0/{user_id}?{query}'))
    return result.get('business_discovery',{}).get('media',{}).get('data',[])

def safe_pub(s):
    try:return parsedate_to_datetime(s).astimezone(timezone.utc).isoformat()
    except:return ''

def indexed_mentions(account):
    # Google News searches are NOT Instagram posts; show as separate related discoveries.
    q=quote(f'"{account}" instagram')
    url=f'https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko'
    root=ET.fromstring(get(url))
    items=[]
    for entry in root.findall('./channel/item')[:8]:
        title=unescape((entry.findtext('title') or '').strip())
        dest=(entry.findtext('link') or '').strip()
        pub=safe_pub(entry.findtext('pubDate') or '')
        if not title or not dest.startswith('https://'):continue
        items.append({'account':account,'title':title[:300],'url':dest,'published':pub,'source':'indexed_news'})
    return items

def main():
    token=os.getenv('IG_ACCESS_TOKEN','').strip();user_id=os.getenv('IG_USER_ID','').strip()
    mode='api' if token and user_id else 'not_configured'
    posts=[]; mentions=[];errors=[]
    if mode=='api':
        for account in ACCOUNTS:
            try:
                for p in fetch_graph(account,user_id,token):
                    href=p.get('permalink',''); cap=p.get('caption','') or ''
                    if href.startswith('https://www.instagram.com/'):
                        posts.append({'account':account,'title':cap.splitlines()[0][:220] if cap else '인스타그램 게시물','caption':cap[:1500],'url':href,'published':p.get('timestamp',''),'media_type':p.get('media_type','')})
                print(account,'API OK')
            except Exception as exc:
                print(account,'API FAIL',type(exc).__name__,str(exc)[:180]);errors.append(account)
    else:
        print('Official Instagram API not configured; no posts will be invented.')
    # Indexed search is discovery only and may contain articles merely ABOUT the accounts.
    for account in ACCOUNTS:
        try:
            mentions.extend(indexed_mentions(account))
            print(account,'search OK')
        except Exception as exc:
            print(account,'search FAIL',type(exc).__name__,str(exc)[:180])
    old={}
    if OUT.exists():
        try:old=json.loads(OUT.read_text(encoding='utf-8'))
        except Exception:pass
    # Preserve previously verified API results on transient API errors, but do not present old posts as new.
    if mode=='api' and errors:
        posts.extend(p for p in old.get('posts',[]) if p.get('account') in errors)
    def unique(items):
        found=set();out=[]
        for p in sorted(items,key=lambda p:p.get('published',''),reverse=True):
            if p.get('url') not in found:
                out.append(p);found.add(p.get('url'))
        return out
    output={'updated_at':NOW.isoformat(),'mode':mode,'accounts':ACCOUNTS,'posts':unique(posts)[:180],'mentions':unique(mentions)[:90],'api_failed_accounts':errors}
    OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Saved',len(output['posts']),'official posts and',len(output['mentions']),'search results')

if __name__=='__main__':main()
