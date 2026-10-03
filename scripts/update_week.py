# -*- coding: utf-8 -*-
"""每周更新助手：抓取当周 Hamberger 折扣册页图 + 生成转录骨架 + 更新档期

用法示例：
    python scripts/update_week.py \
        --week-id 2026-W43-44 \
        --doc-id 71293185 \
        --slug aktion-001-kw-43-44 \
        --pages 52 \
        --valid-from 2026-10-19 --valid-to 2026-10-30 \
        --title-zh "第 43/44 周 · 2026.10.19 – 10.30" \
        --title-en "Week 43/44 · 19–30 Oct 2026" \
        --title-de "KW 43/44 · 19.10.–30.10.2026"

它会：
 1. 把 52 页图片下载到 flyer/images/<week-id>/
 2. 在 flyer/ 生成 <week-id>.md 的转录骨架（表头 + 空行，供逐页填写）
 3. 把 data/week.json 的 weeks[0] 更新为当周信息
之后：填写转录表 → python scripts/build.py → git push（Vercel 自动部署）

图片直链规律：https://img.yumpu.com/<doc-id>/<页码>/2400x3398/<slug>.jpg?quality=90
（doc-id 与 slug 见官网 hamberger-cc.de/de/aktuelles 里 Yumpu 链接）
"""

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLYER = os.path.join(ROOT, 'flyer')
DATA = os.path.join(ROOT, 'data')

HEADER = """# Hamberger {market} — {week}  ({valid})

Quelle: Yumpu doc id {doc}, Seitenbilder `https://img.yumpu.com/{doc}/{{p}}/2400x3398/{slug}.jpg?quality=90`
Legende: `[ASIA]` = Asien-Artikel, `[TK]` = Tiefkühlware. Preise = Nettopreise laut Prospekt.

| 页码 | 货架区/主题 | 商品名(原文德语) | 补充描述 | 规格/包装 | 标注价 | Art.Nr |
|---|---|---|---|---|---|---|
"""


def download_images(doc_id, slug, pages, outdir):
    os.makedirs(outdir, exist_ok=True)
    ok = 0
    for p in range(1, pages + 1):
        dst = os.path.join(outdir, f'p{p:02d}.jpg')
        if os.path.exists(dst) and os.path.getsize(dst) > 10000:
            ok += 1
            continue
        url = f'https://img.yumpu.com/{doc_id}/{p}/2400x3398/{slug}.jpg?quality=90'
        r = subprocess.run(['curl.exe', '-s', '-L', '--max-time', '90', '-o', dst, url],
                           capture_output=True)
        if os.path.exists(dst) and os.path.getsize(dst) > 10000:
            ok += 1
        else:
            print(f'  ! Seite {p} nicht geladen')
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week-id', required=True, help='z.B. 2026-W43-44')
    ap.add_argument('--doc-id', required=True, help='Yumpu document id, z.B. 71293185')
    ap.add_argument('--slug', required=True, help='Yumpu slug, z.B. aktion-001-kw-43-44')
    ap.add_argument('--pages', type=int, default=52)
    ap.add_argument('--valid-from', default='')
    ap.add_argument('--valid-to', default='')
    ap.add_argument('--market', default='München')
    ap.add_argument('--title-zh', default='')
    ap.add_argument('--title-en', default='')
    ap.add_argument('--title-de', default='')
    ap.add_argument('--skip-download', action='store_true')
    a = ap.parse_args()

    valid = f'{a.valid_from} – {a.valid_to}'.strip(' –')
    imgdir = os.path.join(FLYER, 'images', a.week_id)
    if not a.skip_download:
        n = download_images(a.doc_id, a.slug, a.pages, imgdir)
        print(f'Bilder: {n}/{a.pages} -> {imgdir}')

    md = os.path.join(FLYER, f'{a.week_id}.md')
    if not os.path.exists(md):
        with open(md, 'w', encoding='utf-8') as fh:
            fh.write(HEADER.format(market=a.market, week=a.week_id, valid=valid,
                                   doc=a.doc_id, slug=a.slug))
        print(f'Transkriptions-Vorlage erstellt: {md}')
    else:
        print(f'Vorlage existiert schon: {md}')

    wk_path = os.path.join(DATA, 'week.json')
    wk = json.load(open(wk_path, encoding='utf-8')) if os.path.exists(wk_path) else {'weeks': []}
    entry = {
        'id': a.week_id,
        'label_zh': a.title_zh or a.week_id,
        'label_en': a.title_en or a.week_id,
        'label_de': a.title_de or a.week_id,
        'valid_from': a.valid_from,
        'valid_to': a.valid_to,
        'source_de': f'Hamberger Aktion (doc {a.doc_id}), {a.market}',
        'source_zh': f'Hamberger 促销册（doc {a.doc_id}），{a.market}',
        'source_en': f'Hamberger flyer (doc {a.doc_id}), {a.market}',
        'files': [f'{a.week_id}.md'],
    }
    weeks = [w for w in wk.get('weeks', []) if w.get('id') != a.week_id]
    weeks.insert(0, entry)
    wk['weeks'] = weeks[:6]
    wk['current'] = a.week_id
    wk['updated'] = a.valid_from or ''
    json.dump(wk, open(wk_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'data/week.json aktualisiert -> {a.week_id}')
    print('Nächste Schritte: 1) Transkription füllen  2) python scripts/build.py  3) git push')


if __name__ == '__main__':
    main()
