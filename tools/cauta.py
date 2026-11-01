"""Research helpers for a new book (Python 3, standard library only).

  python3 tools/cauta.py ids      ro:"Îngerul albastru" en:"City Lights"   film/music/book IDs from Wikidata
  python3 tools/cauta.py imagini  ro:"Casa Capșa" en:"Tomb of Dante"       free image + credit, ready for refMeta
  python3 tools/cauta.py capitole roman.txt "Capșa" "Fantasio|cinema"       part and chapter where each term appears
                                         (remove the table of contents from roman.txt first, or its headings count too)

Wikipedia/Wikidata are polite APIs: the script waits between calls; if you get HTTP 429, wait a minute and retry.
"""
import json, re, sys, time, urllib.parse, urllib.request

UA = {'User-Agent': 'carte-sonora-template/1.0 (book club site research)'}
PROPS = {'P345': 'IMDb', 'P6127': 'Letterboxd', 'P4665': 'Cinemagia film', 'P4666': 'Cinemagia persoană', 'P1953': 'Discogs artist',
         'P839': 'IMSLP', 'P2034': 'Gutenberg', 'P8383': 'Goodreads', 'P856': 'site oficial', 'P625': 'coordonate'}


def api(host, **params):
    params.update(format='json', formatversion=2)
    for wait in (0, 10, 30):
        time.sleep(wait or 1)
        try:
            req = urllib.request.Request(f'https://{host}/w/api.php?' + urllib.parse.urlencode(params), headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            print('  …', e, file=sys.stderr)
    sys.exit('API unavailable, try again later')


def titles(args):
    """'ro:Titlu' / 'en:Title' -> (wiki host, title)."""
    for a in args:
        lang, _, t = a.partition(':')
        yield f'{lang}.wikipedia.org', t


def ids(args):
    for host, t in titles(args):
        site = host.split('.')[0] + 'wiki'
        r = api('www.wikidata.org', action='wbgetentities', sites=site, titles=t, props='claims')
        e = next(iter(r.get('entities', {}).values()), {})
        if 'missing' in e or not e:
            print(f'{t}: not found on {site}'); continue
        out = {}
        for p, name in PROPS.items():
            for c in e.get('claims', {}).get(p, []):
                v = c['mainsnak'].get('datavalue', {}).get('value')
                if v: out[name] = (v['latitude'], v['longitude']) if p == 'P625' else v
        print(f'{t} ({e["id"]}):', json.dumps(out, ensure_ascii=False))


def clean_artist(a):
    a = re.sub(r'<[^>]+>', '', a or '').strip()
    if not a or 'Unknown' in a: return 'autor necunoscut'
    a = re.sub(r'^(This [Pp]hoto was taken by|(The )?[Oo]riginal uploader was) ', '', a)
    return re.split(r'\s*[(.]|\s+https?://', a)[0][:60]


def imagini(args):
    """Free lead image of each article, as a refMeta entry (add ch:'Partea …, cap. …' yourself)."""
    for host, t in titles(args):
        r = api(host, action='query', titles=t, prop='pageimages', piprop='name', pilicense='free', redirects=1)
        f = r['query']['pages'][0].get('pageimage')
        if not f:
            print(f'{t}: no free image — the card will show a lettered tile'); continue
        r = api(host, action='query', titles='File:' + f, prop='imageinfo', iiprop='url|size|extmetadata', iiurlwidth=500)
        ii = r['query']['pages'][0]['imageinfo'][0]; m = ii.get('extmetadata', {})
        g = lambda k: re.sub(r'<[^>]+>', '', m.get(k, {}).get('value', '')).strip()
        thumb = ii['thumburl'].split('?')[0].replace('https://thumb.wikimedia.org/', 'https://upload.wikimedia.org/').split('/wikipedia/', 1)[1]
        big = thumb.replace('/500px-', '/960px-') if ii['width'] > 960 else re.sub(r'/thumb/(.*)/[^/]+$', r'/\1', thumb) if '/thumb/' in thumb else thumb
        lic = g('LicenseShortName')
        entry = {'ch': '', 't': thumb, 'b': big, 'by': clean_artist(g('Artist')), 'lic': 'domeniu public' if lic.lower() == 'public domain' else lic, 'src': ii['descriptionurl']}
        if g('LicenseUrl') and lic.lower() != 'public domain': entry['lu'] = g('LicenseUrl')
        ratio = ii['width'] / ii['height']
        if ratio > 1.45: entry['wide'] = 1
        elif ratio < .74: entry['tall'] = 1
        print(json.dumps(t, ensure_ascii=False) + ':' + json.dumps(entry, ensure_ascii=False, separators=(',', ':')) + ',')


def capitole(args, part_re=r'^\s*PARTEA\b', chap_re=r'^\s*CAPITOLUL\.?\s+(\d+)\s*$'):
    """Line-by-line scan of a plain-text novel; adjust the two patterns to how the book marks parts and chapters."""
    path, terms = args[0], args[1:]
    lines = open(path, encoding='utf-8').read().split('\n')
    part = chap = 0; where = []
    for l in lines:  # headings are matched case-sensitively, so prose like "Partea proastă…" is not a new part
        if re.match(part_re, l): part += 1; chap = 0
        m = re.match(chap_re, l)
        if m and part: chap = int(m.group(1))
        where.append((part, chap))
    for t in terms:
        hits = sorted({where[i] for i, l in enumerate(lines) if re.search(t, l, re.I)})
        print(f'{t}: ' + (', '.join(f'Partea {p}, cap. {c}' for p, c in hits) or 'not found (OCR may split or misspell the word)'))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    {'ids': ids, 'imagini': imagini, 'capitole': capitole}.get(cmd, lambda _: print(__doc__))(sys.argv[2:])
