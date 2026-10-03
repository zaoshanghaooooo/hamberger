# -*- coding: utf-8 -*-
"""Hamberger 拼单情报站 — 静态站点构建器（无交互，纯展示）

用法：
    python scripts/build.py

数据源：
    flyer/*.md          促销单逐页转录表（每周替换/新增）
    data/week.json      当期档期信息 + 重点货号
    data/buylist.json   可购清单（人工筛选，含规格与最低购买量）
    data/i18n.json      三语界面文案 + 分类名
输出：
    dist/index.html     语言自动跳转
    dist/{zh,en,de}/index.html
    dist/style.css
"""

import os
import re
import json
import html
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
FLYER = os.path.join(ROOT, 'flyer')
DIST = os.path.join(ROOT, 'dist')
LANGS = ['zh', 'en', 'de']

# 分类判定（按顺序匹配，先专后泛）
CATS = [
    ('asia',      r'(?i)asia|gyma|heuschen'),
    ('wild',      r'(?i)wild'),
    ('fisch',     r'(?i)fisch|meeresfr'),
    ('fleisch',   r'(?i)fleisch|wurst|berg bauer'),
    ('tk',        r'(?i)tiefk|gefroren|\[TK\]'),
    ('kaese',     r'(?i)käse|kaese'),
    ('milch',     r'(?i)milch|mopro|sennerei|joghurt'),
    ('feinkost',  r'(?i)feinkost|gourmet|traiteur'),
    ('obst',      r'(?i)obst|gemüse|gemuese'),
    ('getraenke', r'(?i)getränke|getraenke|wein|sekt|champagner|monin|rauch|illy|chai|bier|wasser|saft'),
    ('nonfood',   r'(?i)non-food|duni|verpackung|serviette|küchenhelfer|kuechenhelfer|karlowsky|rommelsbacher|profagus|weiß|weiss|reinigung|hygiene|geschirr|besteck|handschuh|müllsack'),
    ('trocken',   r'(?i)trocken|konserve|mutti|ponti|caputo|frießinger|friessinger|vegan|pasta|reis|mehl|gewürz|sauce|öl|oel|essig'),
]
VAT19 = {'getraenke', 'nonfood'}   # 饮料与非食品按 19% 估算，其余食品按 7%


def esc(s):
    return html.escape(str(s if s is not None else ''), quote=True)


def load_json(name, default=None):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default if default is not None else {}
    with open(p, encoding='utf-8') as fh:
        return json.load(fh)


def clean(s):
    return re.sub(r'`?\s*\[(ASIA|TK)\]\s*`?', '', s or '').strip(' `')


def classify(text):
    for key, pat in CATS:
        if re.search(pat, text or ''):
            return key
    return 'sonstiges'


def parse_md(path):
    items = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith('|'):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) < 5:
                continue
            joined = ' '.join(cells)
            if '商品名' in joined or set(joined) <= set('-: '):
                continue
            page_raw = cells[0]
            rubrik, name, desc = clean(cells[1]), clean(cells[2]), clean(cells[3])
            spec = clean(cells[4])
            price = clean(cells[5]) if len(cells) > 5 else ''
            art = clean(' | '.join(cells[6:])) if len(cells) > 6 else ''
            m = re.search(r'(\d+)', page_raw)
            page = int(m.group(1)) if m else 0
            num = re.search(r'(\d+[.,]\d{2})', price.replace(',', '.'))
            net = float(num.group(1)) if num else None
            tags = []
            if '[ASIA]' in joined:
                tags.append('asia')
            if '[TK]' in joined:
                tags.append('tk')
            blob = ' '.join([rubrik, name, desc, spec])
            items.append({
                'page': page, 'rubrik': rubrik, 'name': name, 'desc': desc,
                'spec': spec, 'price': price, 'net': net, 'art': art,
                'tags': tags, 'cat': classify(blob),
                'src': os.path.basename(path),
            })
    return items


def collect_items():
    items = []
    if os.path.isdir(FLYER):
        for fn in sorted(os.listdir(FLYER)):
            if fn.lower().endswith('.md'):
                items.extend(parse_md(os.path.join(FLYER, fn)))
    # 额外条目（例如 Lieferservice 传单，以 JSON 形式提供）
    extra = os.path.join(FLYER, 'extra_items.json')
    if os.path.exists(extra):
        with open(extra, encoding='utf-8') as fh:
            for it in json.load(fh):
                blob = ' '.join([it.get('rubrik', ''), it.get('name', ''), it.get('spec', '')])
                it.setdefault('cat', classify(blob))
                it.setdefault('tags', [])
                items.append(it)
    # 去重（同名+同规格+同价）
    seen, out = set(), []
    for it in items:
        k = (it['name'], it['spec'], it['price'])
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    for it in out:
        it['gross'] = round(it['net'] * (1.19 if it['cat'] in VAT19 else 1.07), 2) if it.get('net') else None
    out.sort(key=lambda x: (x.get('page') or 0, x['name']))
    return out


CSS = """
:root{--bg:#0f1115;--card:#171a21;--line:#262b35;--fg:#e8ecf3;--dim:#9aa4b2;
--accent:#4da3ff;--accent2:#ffd24d;--ok:#57d38c;--warn:#ff8a5c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",Roboto,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
.hero{padding:28px 0 18px;border-bottom:1px solid var(--line);
background:linear-gradient(180deg,#171b24,#0f1115)}
.langbar{display:flex;gap:8px;justify-content:flex-end;font-size:14px}
.langbar a{padding:3px 10px;border:1px solid var(--line);border-radius:999px;color:var(--dim)}
.langbar a.on{color:#0f1115;background:var(--accent2);border-color:var(--accent2);font-weight:700}
h1{font-size:26px;margin:10px 0 6px}
h1 .sub{display:block;font-size:15px;color:var(--dim);font-weight:400;margin-top:6px}
.meta{color:var(--dim);font-size:14px;margin:6px 0 0}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 0;font-size:13px}
.badge{border:1px solid var(--line);border-radius:999px;padding:3px 10px;color:var(--dim);background:var(--card)}
.notice{margin:16px 0;padding:12px 14px;border-left:3px solid var(--warn);background:#1a1712;color:#f0dcc9;font-size:14px}
nav.sticky{position:sticky;top:0;z-index:5;background:rgba(15,17,21,.95);border-bottom:1px solid var(--line);
backdrop-filter:blur(6px)}
nav.sticky .wrap{display:flex;gap:14px;flex-wrap:wrap;padding:10px 16px;font-size:14px}
section{padding:26px 0 6px;border-bottom:1px solid var(--line)}
h2{font-size:20px;margin:0 0 6px}
h3{font-size:16px;margin:22px 0 8px;color:var(--accent2)}
.lead{color:var(--dim);font-size:14px;margin:0 0 14px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:600;background:#141821;position:sticky;top:44px}
td.num{white-space:nowrap;text-align:right}
td.art{color:var(--dim);white-space:nowrap;font-variant-numeric:tabular-nums}
.gross{color:var(--ok);white-space:nowrap;font-size:13px}
.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:4px;margin-left:6px;vertical-align:1px}
.tag.tk{background:#14324a;color:#8fd0ff}
.tag.asia{background:#3a2a12;color:var(--accent2)}
.small{color:var(--dim);font-size:13px}
details{margin:0 0 6px}
summary{cursor:pointer;padding:10px 0;font-weight:600;color:var(--fg)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}
.card h3{margin-top:0}
footer{padding:28px 0 60px;color:var(--dim);font-size:13px}
.heroimg{width:100%;max-height:190px;object-fit:cover;border-radius:10px;opacity:.85}
@media(max-width:720px){th:nth-child(3),td:nth-child(3){display:none}h1{font-size:21px}}
"""


def fmt_eur(v):
    if v is None:
        return '—'
    s = f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return s + ' €'


def render_item_rows(items, t, lang):
    rows = []
    for it in items:
        tags = ''
        if 'tk' in it['tags']:
            tags += f'<span class="tag tk">{esc(t["ui"]["tag_tk"][lang])}</span>'
        if 'asia' in it['tags'] or it['cat'] == 'asia':
            tags += f'<span class="tag asia">{esc(t["ui"]["tag_asia"][lang])}</span>'
        gross = f'<span class="gross">≈ {fmt_eur(it["gross"])}</span>' if it.get('gross') else '—'
        desc = f'<div class="small">{esc(it["desc"])}</div>' if it.get('desc') else ''
        rows.append(
            '<tr>'
            f'<td>{esc(it["name"])}{tags}{desc}</td>'
            f'<td class="small">{esc(it["spec"])}</td>'
            f'<td class="art">{esc(it["art"])}</td>'
            f'<td class="num">{esc(it["price"])}</td>'
            f'<td class="num">{gross}</td>'
            '</tr>'
        )
    return '\n'.join(rows)


def render_discounts(items, t, lang):
    by_cat = {}
    for it in items:
        by_cat.setdefault(it['cat'], []).append(it)
    order = [k for k, _ in CATS] + ['sonstiges']
    out = []
    for key in order:
        group = by_cat.get(key)
        if not group:
            continue
        cname = t['categories'].get(key, {}).get(lang, key)
        cnt = t['ui']['count_items'][lang].format(n=len(group))
        out.append(f'<details open id="cat-{key}"><summary>{esc(cname)} <span class="small">· {esc(cnt)}</span></summary>')
        out.append('<table><thead><tr>'
                   f'<th>{esc(t["ui"]["col_item"][lang])}</th>'
                   f'<th>{esc(t["ui"]["col_spec"][lang])}</th>'
                   f'<th>{esc(t["ui"]["col_art"][lang])}</th>'
                   f'<th>{esc(t["ui"]["col_net"][lang])}</th>'
                   f'<th>{esc(t["ui"]["col_gross"][lang])}</th>'
                   '</tr></thead><tbody>')
        out.append(render_item_rows(group, t, lang))
        out.append('</tbody></table></details>')
    return '\n'.join(out)


def render_highlights(items, week, t, lang):
    wanted = {str(a) for a in week.get('highlights', [])}
    picked = [it for it in items if any(str(a) in str(it.get('art', '')) for a in wanted)]
    if not picked:
        return ''
    return '<table><thead><tr>' + ''.join(
        f'<th>{esc(t["ui"][k][lang])}</th>' for k in ['col_item', 'col_spec', 'col_art', 'col_net', 'col_gross']
    ) + '</tr></thead><tbody>' + render_item_rows(picked, t, lang) + '</tbody></table>'


def render_buylist(buylist, t, lang):
    groups = buylist.get('groups', [])
    if not groups:
        return f'<p class="small">—</p>'
    out = []
    for g in groups:
        title = g['name'].get(lang) or g['name'].get('zh')
        out.append(f'<h3>{esc(title)}</h3>')
        out.append('<table><thead><tr>' + ''.join(
            f'<th>{esc(t["ui"][k][lang])}</th>' for k in ['col_item', 'col_spec', 'col_min', 'col_hamb', 'col_compare', 'col_why']
        ) + '</tr></thead><tbody>')
        for it in g.get('items', []):
            def L(field):
                v = it.get(field)
                if isinstance(v, dict):
                    return v.get(lang) or v.get('zh') or ''
                return v or ''
            out.append(
                '<tr>'
                f'<td><strong>{esc(L("name"))}</strong></td>'
                f'<td class="small">{esc(L("spec"))}</td>'
                f'<td class="small">{esc(L("min"))}</td>'
                f'<td class="num">{esc(L("price"))}</td>'
                f'<td class="small">{esc(L("compare"))}</td>'
                f'<td class="small">{esc(L("why"))}</td>'
                '</tr>'
            )
        out.append('</tbody></table>')
    return '\n'.join(out)


def page(lang, week, meta, items, buylist, t, how_lines):
    u = t['ui']
    L = lambda k: esc(u[k][lang])
    w = meta
    hl = render_highlights(items, week, t, lang)
    hl_block = ''
    if hl:
        hl_block = (f'<section id="highlight"><h2>{L("sec_highlight_title")}</h2>'
                    f'<p class="lead">{L("sec_highlight_intro")}</p>{hl}</section>')
    how = '\n'.join(f'<li>{esc(x[lang] if isinstance(x, dict) else x)}</li>' for x in how_lines)
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{L('site_title')}</title>
<meta name="description" content="{L('tagline')}">
<link rel="stylesheet" href="../style.css">
<link rel="alternate" hreflang="zh" href="../zh/">
<link rel="alternate" hreflang="en" href="../en/">
<link rel="alternate" hreflang="de" href="../de/">
</head>
<body>
<header class="hero"><div class="wrap">
  <div class="langbar"><a href="../zh/" class="{'on' if lang=='zh' else ''}">中文</a><a href="../en/" class="{'on' if lang=='en' else ''}">EN</a><a href="../de/" class="{'on' if lang=='de' else ''}">DE</a></div>
  <h1>{L('site_title')}<span class="sub">{L('tagline')}</span></h1>
  <p class="meta">{L('market_line')}</p>
  <div class="badges">
    <span class="badge">{L('week_label')}：{esc(w.get('label_' + lang) or w.get('label_zh',''))}</span>
    <span class="badge">{L('updated_label')}：{esc(week.get('updated',''))}</span>
    <span class="badge">{esc(t['ui']['count_items'][lang].format(n=len(items)))}</span>
  </div>
</div></header>
<div class="wrap">
  <div class="notice">{L('notice_net')}<br>{L('notice_access')}</div>
</div>
<nav class="sticky"><div class="wrap">
  <a href="#discounts">{L('nav_discounts')}</a>
  <a href="#highlight">{L('nav_highlight')}</a>
  <a href="#buylist">{L('nav_buylist')}</a>
  <a href="#how">{L('nav_how')}</a>
</div></nav>
<div class="wrap">
  <section id="discounts">
    <h2>{L('sec_discounts_title')}</h2>
    <p class="lead">{L('sec_discounts_intro')}</p>
    {render_discounts(items, t, lang)}
  </section>
  {hl_block}
  <section id="buylist">
    <h2>{L('sec_buylist_title')}</h2>
    <p class="lead">{L('sec_buylist_intro')}</p>
    {render_buylist(buylist, t, lang)}
  </section>
  <section id="how">
    <h2>{L('sec_how_title')}</h2>
    <ul>{how}</ul>
  </section>
  <footer>
    <p>{L('footer_contact')}</p>
    <p class="small">{L('footer_disclaimer')}</p>
    <p class="small">{L('lang_label')}：<a href="../zh/">中文</a> · <a href="../en/">English</a> · <a href="../de/">Deutsch</a></p>
  </footer>
</div>
</body></html>"""


ROOT_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hamberger Group Buy · München</title>
<link rel="canonical" href="./en/">
<script>
(function(){
  var l=(navigator.language||navigator.userLanguage||'en').toLowerCase();
  var t=l.indexOf('zh')===0?'zh':(l.indexOf('de')===0?'de':'en');
  location.replace(t+'/');
})();
</script>
<style>body{background:#0f1115;color:#e8ecf3;font:16px/1.6 system-ui,sans-serif;padding:40px}
a{color:#4da3ff}</style>
</head>
<body>
<p>Redirecting… / 正在跳转… / Weiterleitung…</p>
<p><a href="./zh/">中文</a> · <a href="./en/">English</a> · <a href="./de/">Deutsch</a></p>
</body>
</html>"""


HOW_LINES = [
    {'zh': '进群（小红书「慕尼黑 Hamberger 拼单」，周日 20:00 截单）。',
     'de': 'Gruppe beitreten (Xiaohongshu „München Hamberger Sammelbestellung“, Bestellschluss Sonntag 20:00).',
     'en': 'Join the group (Xiaohongshu “Munich Hamberger Group Buy”, cut-off Sunday 20:00).'},
    {'zh': '下单：把「商品名 / 货号 + 数量」发到群接龙；整箱、整桶、整只类需按最低购买量拼。',
     'de': 'Bestellung: Artikel + Art.Nr + Menge in die Gruppe; bei Kisten, Eimern und ganzen Tieren gilt die Mindestabnahme.',
     'en': 'Order: post item + article no. + quantity in the group; crates, buckets and whole animals follow the minimum quantity.'},
    {'zh': '结算：按当日小票金额 AA（食品含 7% 增值税，饮料与非食品含 19%），不收商品加价。',
     'de': 'Abrechnung: 1:1 nach Kassenbon (7 % MwSt. auf Lebensmittel, 19 % auf Getränke/Non-Food), kein Aufschlag auf die Ware.',
     'en': 'Payment: split the receipt exactly (7 % VAT on food, 19 % on drinks/non-food), no markup on goods.'},
    {'zh': '取货：周一 18:00–20:00 Ostbahnhof 附近自提免费；1 km 内配送 3 €；请自备冷藏袋。',
     'de': 'Abholung: Montag 18:00–20:00 nahe Ostbahnhof kostenlos; Lieferung im 1-km-Umkreis 3 €; Kühltasche mitbringen.',
     'en': 'Pickup: Monday 18:00–20:00 near Ostbahnhof free; delivery within 1 km 3 €; bring a cool bag.'},
    {'zh': '支付：PayPal / 现金 / 微信 / 支付宝。',
     'de': 'Zahlung: PayPal / Bar / WeChat / Alipay.',
     'en': 'Payment: PayPal / cash / WeChat / Alipay.'},
    {'zh': '提示：批发市场只对有营业执照的商用客户开放，本拼单由持卡人代为采购。',
     'de': 'Hinweis: Der Großmarkt verkauft nur an gewerbliche Kunden; die Sammelbestellung wird über eine Kundenkarte abgewickelt.',
     'en': 'Note: the wholesale market only sells to trade customers; this group buy is handled via a card holder.'},
]


def main():
    t = load_json('i18n.json')
    week = load_json('week.json')
    buylist = load_json('buylist.json', {'groups': []})
    meta = week.get('weeks', [{}])[0]
    items = collect_items()

    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    with open(os.path.join(DIST, 'style.css'), 'w', encoding='utf-8') as fh:
        fh.write(CSS)
    with open(os.path.join(DIST, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(ROOT_HTML)
    for lang in LANGS:
        d = os.path.join(DIST, lang)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as fh:
            fh.write(page(lang, week, meta, items, buylist, t, HOW_LINES))

    cats = {}
    for it in items:
        cats[it['cat']] = cats.get(it['cat'], 0) + 1
    print(f'built -> {DIST}')
    print(f'items: {len(items)}')
    for k, v in sorted(cats.items(), key=lambda x: -x[1]):
        print(f'  {k:10s} {v:4d}')
    print(f'buy list groups: {len(buylist.get("groups", []))}')


if __name__ == '__main__':
    main()
