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
import sys
import json
import html
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
FLYER = os.path.join(ROOT, 'flyer')
# 默认直接输出到仓库根目录：这样 Vercel（CLI / GitHub 导入）拿到的就是可直接托管的静态站
DIST = ROOT
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
    s = re.sub(r'`?\s*\[(ASIA|TK)\]\s*`?', '', s or '').strip(' `')
    # 去掉转录时留下的备注（如「Marke 看不清」「Schriftzug unleserlich」），别混进货名
    s = re.sub(r'\(\s*(?:Marke\s*)?[^)]*(?:unleserlich|看不清|nicht lesbar)[^)]*\)', '', s)
    s = re.sub(r'\bMarke\s+看不清\b', '', s)
    s = re.sub(r'\s{2,}', ' ', s).strip(' ,-–—|')
    return s


# ---------------------------------------------------------------- 德语 → 中文/英文 对照
GLOSSARY = load_json('glossary.json', {})
G_KEYS = sorted([k for k in GLOSSARY if not k.startswith('_')], key=len, reverse=True)
G_SINGLE = {k.lower() for k in G_KEYS if ' ' not in k}
G_PHRASE = [k.lower() for k in G_KEYS if ' ' in k]
WORD_RE = re.compile(r'[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-\.]*')
_pat_cache = {}


def _pat(key):
    if key not in _pat_cache:
        _pat_cache[key] = re.compile(
            r'(?<![A-Za-zÄÖÜäöüß])' + re.escape(key) + r'(?![A-Za-zÄÖÜäöüß])', re.IGNORECASE)
    return _pat_cache[key]


def coverage(text):
    """原文有多少词能在词典里找到（0~1），用于判断译文是否可信"""
    words = WORD_RE.findall(text or '')
    if not words:
        return 1.0
    hits = 0
    for w in words:
        wl = w.lower()
        if wl in G_SINGLE or any(wl in p for p in G_PHRASE):
            hits += 1
    return hits / len(words)


def _tidy(out):
    """收拾译文里残留的德语连接词、连字符和孤立字母"""
    out = re.sub(r'(?<=[\u4e00-\u9fff])[\s\-]*\bund\b[\s\-]*(?=[\u4e00-\u9fff])', '', out)
    out = re.sub(r'(?<=[\u4e00-\u9fff])[\s\-]*&[\s\-]*(?=[\u4e00-\u9fff])', '和', out)
    out = re.sub(r'(?<=[\u4e00-\u9fff])[\s]*-[\s]*(?=[\u4e00-\u9fff])', '', out)
    out = re.sub(r'(?<=[\u4e00-\u9fff])-(?=[\u4e00-\u9fff])', '', out)
    out = re.sub(r'\b[A-Za-zÄÖÜäöüß]{1,2}[\'’](?=[\u4e00-\u9fff])', '', out)
    out = re.sub(r'\s{2,}', ' ', out)
    return out.strip(' ,·/-–—„“”"\'')


def tr(text, lang, min_cov=0.45):
    """译成 zh/en。返回 (译文, 是否可信)；词典里没有的品牌名原样保留。"""
    if not text or lang == 'de':
        return text, False
    cov = coverage(text)
    out = text
    for k in G_KEYS:
        m = _pat(k)
        if m.search(out):
            out = m.sub(GLOSSARY[k][0 if lang == 'zh' else 1], out)
    return _tidy(out), cov >= min_cov


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


def collect_items(week_dir=None):
    src = week_dir or FLYER
    items = []
    if os.path.isdir(src):
        for fn in sorted(os.listdir(src)):
            if fn.lower().endswith('.md'):
                items.extend(parse_md(os.path.join(src, fn)))
    # 额外条目（例如 Lieferservice 传单，以 JSON 形式提供）
    extra = os.path.join(src, 'extra_items.json')
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
:root{--bg:#f4f5f7;--card:#fff;--line:#ebedf0;--line2:#e3e6eb;--fg:#1f2329;--dim:#8a9099;
--red:#e1251b;--red-dark:#c81623;--orange:#ff6a00;--ok:#00a862;--tag-bg:#fff1f0;--chip:#f5f6f8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",Roboto,sans-serif;
-webkit-text-size-adjust:100%}
a{color:var(--red);text-decoration:none}
a:hover{text-decoration:underline}
img{max-width:100%}
.wrap{max-width:1140px;margin:0 auto;padding:0 16px}

/* 顶部红色导航条（Joybuy 风） */
.topbar{background:linear-gradient(90deg,var(--red),var(--red-dark));color:#fff;position:sticky;top:0;z-index:20;
box-shadow:0 1px 4px rgba(0,0,0,.12)}
.topbar .wrap{display:flex;align-items:center;gap:16px;min-height:56px;flex-wrap:wrap}
.brand{color:#fff;font-weight:800;font-size:17px;letter-spacing:-.2px;white-space:nowrap}
.brand:hover{text-decoration:none;opacity:.92}
.brand em{font-style:normal;font-weight:500;font-size:12.5px;opacity:.86;margin-left:8px}
.topnav{display:flex;gap:16px;margin-left:auto;overflow-x:auto;scrollbar-width:none}
.topnav::-webkit-scrollbar{display:none}
.topnav a{color:#fff;font-size:14px;opacity:.94;white-space:nowrap;padding:2px 0}
.topnav a:hover{opacity:1;text-decoration:none;box-shadow:inset 0 -2px 0 #fff}
.langbar{display:flex;gap:6px;align-items:center}
.langbar a{padding:2px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.5);color:#fff;font-size:12.5px}
.langbar a.on{background:#fff;color:var(--red);font-weight:700;border-color:#fff}
.langbar a:hover{text-decoration:none;background:rgba(255,255,255,.16)}
.langbar a.on:hover{background:#fff}

/* 头部信息区 */
.hero{background:#fff;border-bottom:1px solid var(--line);padding:18px 0 16px}
h1{font-size:22px;margin:4px 0 4px;letter-spacing:-.2px}
h1 .sub{display:block;font-size:13.5px;color:var(--dim);font-weight:400;margin-top:5px}
.meta{color:var(--dim);font-size:13px;margin:4px 0 0}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 0;font-size:12.5px}
.badge{border:1px solid var(--line2);border-radius:4px;padding:3px 10px;color:var(--dim);background:var(--chip)}
.weeks{display:flex;flex-wrap:wrap;gap:6px;margin:13px 0 0}
.wk{font-size:13px;padding:4px 13px;border:1px solid var(--line2);border-radius:999px;color:var(--dim);background:var(--chip);white-space:nowrap}
.wk.on{color:#fff;background:var(--red);border-color:var(--red);font-weight:600}
.wk:hover{text-decoration:none;border-color:var(--red);color:var(--red)}
.wk.on:hover{color:#fff}
.wklist{margin:6px 0 0;padding-left:18px}
.wklist li{margin:8px 0}

.notice{margin:14px 0;padding:12px 15px;border:1px solid #ffe1b3;border-radius:8px;
background:#fffaf0;color:#7a5200;font-size:13.5px}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:18px 18px 8px;margin:14px 0}
h2{font-size:18.5px;margin:0 0 6px;padding-left:11px;position:relative}
h2:before{content:"";position:absolute;left:0;top:3px;bottom:3px;width:4px;border-radius:2px;background:var(--red)}
h3{font-size:15.5px;margin:20px 0 10px;color:var(--fg);border-left:3px solid var(--orange);padding-left:9px}
.lead{color:var(--dim);font-size:13.5px;margin:0 0 12px}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 0 8px}
table{width:100%;border-collapse:collapse;font-size:14px;min-width:560px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:600;background:var(--chip);border-bottom:1px solid var(--line2);position:sticky;top:56px;z-index:2}
tbody tr:hover{background:#fcfcfd}
td.num{white-space:nowrap;text-align:right;color:var(--red);font-weight:600}
td.art{color:#b0b4bb;white-space:nowrap;font-variant-numeric:tabular-nums}
.gross{color:var(--ok);white-space:nowrap;font-size:12.5px;font-weight:500}
.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:3px;margin-left:6px;vertical-align:1px}
.tag.tk{background:#eef5ff;color:#2b6cd4}
.tag.asia{background:var(--tag-bg);color:var(--red)}
.small{color:var(--dim);font-size:13px}
.orig{color:#b0b4bb;font-size:12px;margin-top:2px}
details{margin:0 0 6px}

/* 可购清单：商品卡片网格 */
.cardgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(292px,1fr));gap:14px;margin:6px 0 16px}
.pcard{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;display:flex;flex-direction:column;
transition:box-shadow .15s,border-color .15s}
.pcard:hover{box-shadow:0 6px 18px rgba(0,0,0,.07);border-color:#e2e5ea}
.pimg{height:96px;background:linear-gradient(135deg,#f8f9fb,#eef0f4);border-bottom:1px solid var(--line);
display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;color:#9aa1ab}
.pimg b{font-size:13px;font-weight:600;color:#7c8592;letter-spacing:.02em}
.pimg i{font-style:normal;font-size:11.5px;color:#a8aeb8;font-variant-numeric:tabular-nums}
.pbody{padding:12px 13px 14px;display:flex;flex-direction:column;gap:6px;flex:1}
.pname{font-weight:700;font-size:15px;line-height:1.45}
.pde{color:#b0b4bb;font-size:12px;line-height:1.4}
.prow{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.pprice{color:var(--red);font-weight:800;font-size:17px;letter-spacing:-.2px}
.pprice small{color:var(--dim);font-weight:400;font-size:12px;margin-left:5px}
.pmin{display:inline-block;background:var(--chip);border:1px solid var(--line2);border-radius:4px;
padding:2px 8px;font-size:12px;color:#5a6169}
.pmeta{font-size:12.5px;color:#6b7280;line-height:1.55}
.pmeta b{color:#4b5563;font-weight:600}
.part{margin-top:auto;color:#b0b4bb;font-size:11.5px;font-variant-numeric:tabular-nums}
.pnote{background:var(--chip);border:1px dashed var(--line2);border-radius:8px;padding:10px 12px;
font-size:13px;color:#5a6169;margin:6px 0 14px}
footer{padding:22px 0 48px;color:var(--dim);font-size:13px}

/* 移动端适配 */
@media(max-width:860px){
  .wrap{padding:0 12px}
  .topbar .wrap{min-height:0;padding:9px 12px;gap:10px}
  .brand{font-size:15.5px}
  .brand em{display:none}
  .topnav{order:3;width:100%;margin-left:0;gap:14px;font-size:13px;padding-bottom:2px}
  .langbar{margin-left:auto}
  .hero{padding:14px 0 12px}
  h1{font-size:19px}
  section{padding:14px 13px 6px;margin:10px 0;border-radius:8px}
  h2{font-size:17px}
  .cardgrid{grid-template-columns:1fr;gap:10px}
  .pimg{height:72px}
  th{position:static}
  th,td{padding:8px 9px;font-size:13.5px}
  table{min-width:520px}
}
@media(max-width:520px){
  h1{font-size:17.5px}
  h1 .sub{font-size:12.5px}
  .tag{display:none}
  .badge{font-size:11.5px;padding:2px 8px}
  .wk{font-size:12px;padding:3px 10px}
  .pprice{font-size:16px}
  .notice{font-size:12.5px;padding:10px 12px}
}
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
        # 名称：中文/英文页做对照，德语页保持原文
        name_de = it['name']
        name_tr, ok = tr(name_de, lang)
        if lang == 'de' or not ok:
            head = esc(name_de)
            orig = f'<div class="orig">{esc(name_tr)}</div>' if (lang != 'de' and ok is False and name_tr != name_de) else ''
        else:
            head = esc(name_tr)
            orig = f'<div class="orig">{esc(name_de)}</div>'
        desc_tr, _ = tr(it.get('desc', ''), lang)
        desc = f'<div class="small">{esc(desc_tr)}</div>' if it.get('desc') else ''
        spec_tr, _ = tr(it.get('spec', ''), lang)
        rows.append(
            '<tr>'
            f'<td>{head}{tags}{desc}{orig}</td>'
            f'<td class="small">{esc(spec_tr)}</td>'
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
        out.append('<div class="tw"><table><thead><tr>'
                   f'<th>{esc(t["ui"]["col_item"][lang])}</th>'
                   f'<th>{esc(t["ui"]["col_spec"][lang])}</th>'
                   f'<th>{esc(t["ui"]["col_art"][lang])}</th>'
                   f'<th>{esc(t["ui"]["col_net"][lang])}</th>'
                   f'<th>{esc(t["ui"]["col_gross"][lang])}</th>'
                   '</tr></thead><tbody>')
        out.append(render_item_rows(group, t, lang))
        out.append('</tbody></table></div></details>')
    return '\n'.join(out)


def render_highlights(items, week, t, lang):
    wanted = {str(a) for a in week.get('highlights', [])}
    picked = [it for it in items if any(str(a) in str(it.get('art', '')) for a in wanted)]
    if not picked:
        return ''
    return '<div class="tw"><table><thead><tr>' + ''.join(
        f'<th>{esc(t["ui"][k][lang])}</th>' for k in ['col_item', 'col_spec', 'col_art', 'col_net', 'col_gross']
    ) + '</tr></thead><tbody>' + render_item_rows(picked, t, lang) + '</tbody></table></div>'


def render_buylist(buylist, t, lang):
    """可购清单：商品卡片网格"""
    groups = buylist.get('groups', [])
    if not groups:
        return '<p class="small">—</p>'
    out = []
    for g in groups:
        gname = g['name'].get(lang) or g['name'].get('zh') or ''
        gshort = re.sub(r'[（(].*?[)）]', '', gname).strip() or gname[:8]
        out.append(f'<h3>{esc(gname)}</h3>')
        note = (g.get('note') or {})
        if note.get(lang) or note.get('zh'):
            out.append(f'<p class="pnote">{esc(note.get(lang) or note["zh"])}</p>')
        out.append('<div class="cardgrid">')
        for it in g.get('items', []):
            def L(field, _it=it):
                v = _it.get(field)
                if isinstance(v, dict):
                    return v.get(lang) or v.get('zh') or ''
                return v or ''
            name = L('name')
            de = (it.get('name') or {}).get('de', '')
            art = L('art')
            price = L('price')
            spec = L('spec')
            mn = L('min')
            cmp_ = L('compare')
            why = L('why')
            rows = []
            if spec and spec != '—':
                rows.append(f'<div class="pmeta"><b>{esc(t["ui"]["col_spec"][lang])}：</b>{esc(spec)}</div>')
            if mn and mn != '—':
                rows.append(f'<div class="pmin">{esc(mn)}</div>')
            if cmp_ and cmp_ != '—':
                rows.append(f'<div class="pmeta"><b>{esc(t["ui"]["col_compare"][lang])}：</b>{esc(cmp_)}</div>')
            if why:
                rows.append(f'<div class="pmeta"><b>{esc(t["ui"]["col_why"][lang])}：</b>{esc(why)}</div>')
            de_line = f'<div class="pde">{esc(de)}</div>' if (de and lang != 'de' and de != name) else ''
            art_line = f'<div class="part">Art. {esc(art)}</div>' if art and art != '—' else ''
            out.append(
                '<div class="pcard">'
                f'<div class="pimg"><b>{esc(gshort)}</b><i>{"Art. " + esc(art) if art and art != "—" else "—"}</i></div>'
                '<div class="pbody">'
                f'<div class="pname">{esc(name)}</div>{de_line}'
                f'<div class="prow"><span class="pprice">{esc(price)}</span></div>'
                + ''.join(rows) + art_line +
                '</div></div>'
            )
        out.append('</div>')
    return '\n'.join(out)


def week_nav(lang, meta, weeks, depth=0):
    """期号切换：本周 + 历史期号 + 归档页（全部用站点绝对路径，避免层级算错）"""
    out = []
    for w in weeks:
        cur = (w['id'] == meta['id'])
        href = f'/{lang}/' if cur else f'/{lang}/w/{w["id"]}/'
        label = w.get('short_' + lang) or w['id']
        out.append(f'<a class="wk{" on" if cur else ""}" href="{href}">{esc(label)}</a>')
    if len(weeks) > 1:
        out.append(f'<a class="wk" href="/{lang}/archive/">{esc({"zh": "全部期号", "de": "Alle Ausgaben", "en": "All issues"}[lang])}</a>')
    return '<div class="weeks">' + ''.join(out) + '</div>'


def page(lang, week, meta, items, buylist, t, how_lines, depth=0, weeks=None):
    u = t['ui']
    L = lambda k: esc(u[k][lang])
    w = meta
    hl = render_highlights(items, meta, t, lang)
    hl_block = ''
    if hl:
        hl_block = (f'<section id="highlight"><h2>{L("sec_highlight_title")}</h2>'
                    f'<p class="lead">{L("sec_highlight_intro")}</p>{hl}</section>')
    how = '\n'.join(f'<li>{esc(x[lang] if isinstance(x, dict) else x)}</li>' for x in how_lines)
    wk_nav = week_nav(lang, meta, weeks or [meta], depth)
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{L('site_title')} · {esc(w.get('short_' + lang, ''))}</title>
<meta name="description" content="{L('tagline')}">
<link rel="stylesheet" href="/style.css">
<link rel="alternate" hreflang="zh" href="/zh/">
<link rel="alternate" hreflang="en" href="/en/">
<link rel="alternate" hreflang="de" href="/de/">
</head>
<body>
<div class="topbar"><div class="wrap">
  <a class="brand" href="/{lang}/">{L('site_title')}<em>{L('market_line')}</em></a>
  <div class="topnav">
    <a href="#discounts">{L('nav_discounts')}</a>
    <a href="#highlight">{L('nav_highlight')}</a>
    <a href="#buylist">{L('nav_buylist')}</a>
    <a href="#how">{L('nav_how')}</a>
  </div>
  <div class="langbar"><a href="/zh/" class="{'on' if lang=='zh' else ''}">中文</a><a href="/en/" class="{'on' if lang=='en' else ''}">EN</a><a href="/de/" class="{'on' if lang=='de' else ''}">DE</a></div>
</div></div>
<header class="hero"><div class="wrap">
  <h1>{L('site_title')}<span class="sub">{L('tagline')}</span></h1>
  <p class="meta">{L('market_line')}</p>
  {wk_nav}
  <div class="badges">
    <span class="badge">{L('week_label')}：{esc(w.get('label_' + lang) or w.get('label_zh',''))}</span>
    <span class="badge">{L('updated_label')}：{esc(week.get('updated',''))}</span>
    <span class="badge">{esc(t['ui']['count_items'][lang].format(n=len(items)))}</span>
  </div>
</div></header>
<div class="wrap">
  <div class="notice">{L('notice_net')}<br>{L('notice_access')}</div>
</div>
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
    <p class="small">{L('lang_label')}：<a href="/zh/">中文</a> · <a href="/en/">English</a> · <a href="/de/">Deutsch</a></p>
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
<style>body{background:#f4f5f7;color:#1f2329;font:16px/1.6 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;padding:48px}
a{color:#e1251b}</style>
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


def archive_page(lang, weeks, t):
    """全部期号列表页 /<lang>/archive/"""
    u = t['ui']
    L = lambda k: esc(u[k][lang])
    lis = []
    for i, w in enumerate(weeks):
        href = f'/{lang}/' if i == 0 else f'/{lang}/w/{w["id"]}/'
        cur = f' <span class="small">（{esc({"zh": "当前", "de": "aktuell", "en": "current"}[lang])}）</span>' if i == 0 else ''
        lis.append(f'<li><a href="{href}">{esc(w.get("label_" + lang, w["id"]))}</a>{cur}</li>')
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{L('site_title')} · {esc({"zh": "全部期号", "de": "Alle Ausgaben", "en": "All issues"}[lang])}</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>
<div class="topbar"><div class="wrap">
  <a class="brand" href="/{lang}/">{L('site_title')}</a>
  <div class="topnav"><a href="/{lang}/">{esc({"zh": "最新一期", "de": "Aktuelle Ausgabe", "en": "Latest issue"}[lang])}</a></div>
  <div class="langbar"><a href="/zh/archive/" class="{'on' if lang=='zh' else ''}">中文</a><a href="/en/archive/" class="{'on' if lang=='en' else ''}">EN</a><a href="/de/archive/" class="{'on' if lang=='de' else ''}">DE</a></div>
</div></div>
<header class="hero"><div class="wrap">
  <h1>{L('site_title')}<span class="sub">{esc({"zh": "全部期号", "de": "Alle Ausgaben", "en": "All issues"}[lang])}</span></h1>
</div></header>
<div class="wrap">
  <section><ul class="wklist">{''.join(lis)}</ul>
  <p class="small"><a href="/{lang}/">← {esc({"zh": "回到最新一期", "de": "Zur aktuellen Ausgabe", "en": "Back to the latest issue"}[lang])}</a></p>
  </section>
  <footer><p class="small">{L('footer_disclaimer')}</p></footer>
</div>
</body></html>"""


def main():
    global DIST
    if '--out' in sys.argv:
        DIST = os.path.abspath(sys.argv[sys.argv.index('--out') + 1])
    t = load_json('i18n.json')
    week = load_json('week.json')
    buylist = load_json('buylist.json', {'groups': []})
    weeks = week.get('weeks', [])

    # 只有输出目录不是仓库根时才清空（避免误删源码）
    if os.path.abspath(DIST) != os.path.abspath(ROOT):
        if os.path.isdir(DIST):
            shutil.rmtree(DIST)
        os.makedirs(DIST, exist_ok=True)
    else:
        os.makedirs(DIST, exist_ok=True)
    with open(os.path.join(DIST, 'style.css'), 'w', encoding='utf-8') as fh:
        fh.write(CSS)
    with open(os.path.join(DIST, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(ROOT_HTML)

    stats = []
    for lang in LANGS:
        for i, w in enumerate(weeks):
            wdir = os.path.join(FLYER, w.get('dir') or w['id'])
            items = collect_items(wdir)
            if i == 0:
                out = os.path.join(DIST, lang, 'index.html')
                depth = 0
            else:
                out = os.path.join(DIST, lang, 'w', w['id'], 'index.html')
                depth = 2
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, 'w', encoding='utf-8') as fh:
                fh.write(page(lang, week, w, items, buylist, t, HOW_LINES, depth, weeks))
            if lang == 'zh':
                stats.append((w['id'], len(items), len(items) and sum(1 for it in items if tr(it['name'], 'zh')[1])))
        ap = os.path.join(DIST, lang, 'archive', 'index.html')
        os.makedirs(os.path.dirname(ap), exist_ok=True)
        with open(ap, 'w', encoding='utf-8') as fh:
            fh.write(archive_page(lang, weeks, t))

    print(f'built -> {DIST}')
    for wid, n, nt in stats:
        print(f'  {wid}: {n} 条（其中 {nt} 条有中文名）')
    print(f'buy list groups: {len(buylist.get("groups", []))}')


if __name__ == '__main__':
    main()
