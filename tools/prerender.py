"""Pre-render the English text into index.html so search engines and link previews
see the content without running JavaScript. Safe to re-run after any content edit:
the page's own script still renders everything (and the Nepali switch) at load.

Usage:  python3 tools/prerender.py        (needs playwright + Chrome)
"""
import asyncio, re, html, sys, pathlib
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / 'index.html'
CONTAINERS = ['rot-words', 'research-list', 'work-list', 'skills', 'writing-list', 'species', 'quotes']
CHROME = sys.argv[1] if len(sys.argv) > 1 else '/usr/bin/google-chrome'

async def snapshot():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])
        ctx = await b.new_context(reduced_motion='reduce')
        pg = await ctx.new_page()
        await pg.add_init_script("try{localStorage.clear()}catch(e){}")
        await pg.goto(PAGE.as_uri()); await pg.wait_for_timeout(600)
        data = await pg.evaluate("""() => ({
          t: Object.fromEntries([...document.querySelectorAll('[data-t]')].map(e => [e.dataset.t, e.textContent])),
          th: Object.fromEntries([...document.querySelectorAll('[data-th]')].map(e => [e.dataset.th, e.innerHTML])),
          c: Object.fromEntries(%s.map(id => [id, document.getElementById(id).innerHTML]))
        })""" % CONTAINERS)
        await b.close()
        return data

def clean(markup):
    # drop runtime-only classes added by scroll/visibility observers
    markup = re.sub(r'class="([^"]*)"', lambda m: 'class="%s"' % ' '.join(c for c in m.group(1).split() if c not in ('in', 'offscreen', 'play', 'grown')), markup)
    return markup

def main():
    d = asyncio.run(snapshot())
    s = PAGE.read_text()
    head, sep, tail = s.partition('<script type="application/json" id="data">')
    n = 0
    for key, txt in d['t'].items():
        pat = re.compile(r'(<(\w+)\b[^>]*\sdata-t="%s"[^>]*>)([^<]*)(</\2>)' % re.escape(key))
        head, k = pat.subn(lambda m: m.group(1) + html.escape(txt, quote=False) + m.group(4), head); n += k
    for key, inner in d['th'].items():
        pat = re.compile(r'(<(\w+)\b[^>]*\sdata-th="%s"[^>]*>)(.*?)(</\2>)' % re.escape(key), re.S)
        head, k = pat.subn(lambda m: m.group(1) + inner + m.group(4), head, count=1); n += k
    for cid in CONTAINERS:
        inner = '<!--pre-->' + clean(d['c'][cid]) + '<!--/pre-->'
        pat = re.compile(r'(<(\w+)\b[^>]*\sid="%s"[^>]*>)(?:<!--pre-->.*?<!--/pre-->)?(</\2>)' % re.escape(cid), re.S)
        head, k = pat.subn(lambda m: m.group(1) + inner + m.group(3), head, count=1)
        if not k: print('container not found:', cid)
        n += k
    PAGE.write_text(head + sep + tail)
    print('pre-rendered', n, 'elements')

if __name__ == '__main__':
    main()
