# Hamberger 拼单情报站（静态站 · Vercel）

纯展示页面：**无表单、无购物车、无登录、无任何交互**。三语自适应（中文 / English / Deutsch），货币统一欧元。

## 目录结构

```
hamberger-site/
├── data/
│   ├── i18n.json       三语界面文案 + 分类名
│   ├── week.json       当期档期（有效期/来源/重点货号）
│   └── buylist.json    可购清单（人工筛选，含规格与最低购买量）
├── flyer/              每周促销单的逐页转录表（每周替换）
│   ├── muenchen_p01-13.md … p40-52.md
│   └── extra_items.json   附加条目（如 Lieferservice 配送册）
├── scripts/build.py    构建：读 flyer/*.md + data/*.json → dist/
├── dist/               构建产物（Vercel 部署的就是这个目录）
└── vercel.json         静态部署配置
```

## 本地预览

```powershell
cd hamberger-site
python scripts/build.py
python -m http.server 8000 --directory dist
# 打开 http://localhost:8000  （会按浏览器语言自动跳到 /zh/ /en/ /de/）
```

## 部署到 Vercel（三种任选）

**A. GitHub 导入（推荐，能自动更新）**
1. 在 `hamberger-site` 建 git 仓库并推到 GitHub。
2. Vercel → Add New → Project → 选该仓库 → Framework 选 **Other**。
3. Build Command 留空（`dist/` 已提交），**Output Directory 填 `dist`** → Deploy。
4. 以后只要 `git push`，Vercel 自动重新部署（这就是「自动上传更新」）。

**B. Vercel CLI**
```powershell
npm i -g vercel
cd hamberger-site
vercel --prod        # 首次会问项目名，之后记住
```

**C. 让 Vercel 在云端构建**（需 Python 构建环境）
在 `vercel.json` 里加 `"buildCommand": "python3 scripts/build.py"`，并把 `dist/` 加入 `.gitignore`。

## 每周更新流程（打折区）

1. 你把当周 Hamberger 折扣册链接（Yumpu）发我。
2. 我逐页转录成 `flyer/<yyyy-Www>.md`（列：页码/货架区/商品名/规格/价格/货号）。
3. 更新 `data/week.json`：`weeks[0]` 的档期标签、有效期、`highlights`（当周重点货号）。
4. `python scripts/build.py` → `dist/` 重建 → `git push` → Vercel 自动上线。

> 非技术做法：第 2–4 步都由我来做，你只要发链接 + 点一次发布。

## 可购清单怎么维护

`data/buylist.json` 的每个分组里有 `items`，字段都是三语对象：

```json
{
  "name":   {"zh": "猪肘", "de": "Schweinshaxe", "en": "Pork knuckle"},
  "spec":   {"zh": "约 1,3 kg/只", "de": "ca. 1,3 kg/Stück", "en": "approx. 1.3 kg each"},
  "min":    {"zh": "1 只（可整只拼）", "de": "1 Stück", "en": "1 piece"},
  "price":  {"zh": "2,75 €/kg（净）≈ 2,94 €/kg 含 7% 税", "de": "2,75 €/kg netto, ca. 2,94 €/kg inkl. 7 %", "en": "€2.75/kg net, ≈ €2.94/kg incl. 7 % VAT"},
  "compare":{"zh": "德国超市无此部位；亚超猪骨 4,90 €/kg", "de": "…", "en": "…"},
  "why":    {"zh": "整只拼单最划算，中餐刚需", "de": "…", "en": "…"}
}
```

## 价格口径（重要）

- Hamberger 是批发市场，**标价是净价**（不含增值税）。
- 站点按 **食品 7% / 饮料与非食品 19%** 估算含税价（`scripts/build.py` 里的 `VAT19` 集合），并明确写了"以结账小票为准"。
- 拼单结算按当日小票 AA，不加价。

## 免责与合规

站内已写明：批发市场仅对持 Gewerbeschein 的商用客户开放；本站为私人拼单信息分享，与 Hamberger Großmarkt GmbH 无隶属或合作关系；价格与库存以门店当日为准。Hamberger 的 AGB 也禁止未经书面同意转发其价格单，公开传播时请保持"个人拼单信息分享"定位。
