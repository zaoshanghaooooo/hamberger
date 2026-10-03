# Hamberger 拼单情报站（慕尼黑 · 三语静态站）

纯展示页面：**无表单、无购物车、无登录、无任何交互**。三语自适应（中文 / English / Deutsch），货币统一欧元。
线上仓库：<https://github.com/zaoshanghaooooo/hamberger>

## 站点结构（**仓库根目录就是站点根目录**，Vercel 零配置即可托管）

```
index.html        语言自动跳转页（按浏览器语言 → /zh/ 或 /en/ 或 /de/）
zh/ en/ de/       三种语言的主页（内容相同，文案与分类名不同）
style.css         全站样式
data/             站点数据源（i18n 文案 / 档期 / 可购清单）
flyer/            每周促销册的逐页转录表（构建输入）
scripts/          build.py（构建）/ update_week.py（周更助手）/ deploy.ps1（一键发布）
vercel.json       仅保留缓存头等静态配置
```

> 站点 HTML 由 `scripts/build.py` 预生成并直接提交到仓库，**Vercel 不需要构建步骤**，因此部署零依赖、不会因构建环境失败。

## 本地预览 / 构建

```powershell
cd hamberger-site
python scripts/build.py                 # 重新生成 index.html / zh / en / de / style.css
python -m http.server 8000              # 打开 http://localhost:8000（自动跳语言）
```

`build.py` 可选 `--out <目录>` 输出到别处（默认输出到仓库根目录，切勿指向源码目录以外的地方）。

## 部署到 Vercel

**方式一：GitHub 导入（推荐，push 即自动更新）**
1. Vercel → **Add New → Project** → 选 `zaoshanghaooooo/hamberger`
2. **Framework Preset 选 `Other`**
3. **Build Command 留空**（站点已预构建）· **Output Directory 留默认（`.`)**
4. Deploy
5. 之后流程：改数据 → `python scripts/build.py` → `git push` → Vercel 自动重新部署

**方式二：Vercel CLI**
```powershell
npm i -g vercel
vercel --prod          # 已登录时；未登录可先用 vercel login
```

**临时链接（免登录，60 分钟过期）**
```powershell
vercel deploy --temporary --yes
```
会输出一个 `https://temporary-xxx.vercel.app` 与一个认领链接，认领后可保留为正式站点。

> ⚠️ 部署前若曾用 CLI 部署过旧结构，先删除 `.vercel/` 缓存目录，否则会沿用旧配置导致 404。

## 每周更新流程（打折区）

1. 你把当周 Hamberger 折扣册链接（Yumpu）发我。
2. 我逐页转录成 `flyer/<yyyy-Www>.md`（列：页码/货架区/商品名/规格/价格/货号）。
3. 更新 `data/week.json`：档期标签、有效期、`highlights`（当周重点货号）。
4. `python scripts/build.py` → `git push` → 自动上线。

辅助脚本 `scripts/update_week.py` 可半自动完成第 2 步的**取图**与档期登记：
```powershell
python scripts/update_week.py --week-id 2026-W43-44 --doc-id 71293185 `
  --slug aktion-001-kw-43-44 --pages 52 `
  --valid-from 2026-10-19 --valid-to 2026-10-30 `
  --title-zh "第 43/44 周" --title-en "Week 43/44" --title-de "KW 43/44"
```

## 可购清单怎么维护

`data/buylist.json` 里每个分组的 `items` 字段都是三语对象：

```json
{
  "name":   {"zh": "猪肘", "de": "Schweinshaxe", "en": "Pork knuckle"},
  "spec":   {"zh": "约 1,3 kg/只", "de": "ca. 1,3 kg/Stück", "en": "approx. 1.3 kg each"},
  "min":    {"zh": "1 只（可整只拼）", "de": "1 Stück", "en": "1 piece"},
  "price":  {"zh": "2,75 €/kg（净）≈ 2,94 €/kg 含 7% 税", "de": "2,75 €/kg netto", "en": "€2.75/kg net"},
  "compare":{"zh": "德国超市无此部位；亚超猪骨 4,90 €/kg", "de": "…", "en": "…"},
  "why":    {"zh": "整只拼单最划算，中餐刚需", "de": "…", "en": "…"}
}
```

选品依据见 `research/de_supermarkt_调料全品类对照.md` 与 `research/de_supermarkt_对比结论.md`。

## 价格口径（重要）

- Hamberger 是批发市场，**标价是净价**（不含增值税）。
- 站点按 **食品 7% / 饮料与非食品 19%** 估算含税价（`scripts/build.py` 中的 `VAT19`），并写明"以结账小票为准"。
- 拼单结算按当日小票 AA，不加价。

## 免责与合规

站内已注明：批发市场仅对持 Gewerbeschein 的商用客户开放；本站为私人拼单信息分享，与 Hamberger Großmarkt GmbH 无隶属或合作关系；价格与库存以门店当日为准。Hamberger 的 AGB 禁止未经书面同意转发其价格单，公开传播请保持"个人拼单信息分享"定位。
