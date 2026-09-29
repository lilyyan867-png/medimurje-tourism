import json
from pathlib import Path
from bs4 import BeautifulSoup

TEMPLATE_DIR = Path("mirror/templates")
GLOBAL_CONFIG = Path("site_config.json")
PAGES_DIR = Path("pages")

# 只保留导航点击跳转 + 外链拦截，不做隐藏
JS_CODE = r"""
(function(){
  document.addEventListener('click', function(e){
    var a = e.target.closest('a');
    if (a && a.href && a.href.indexOf('visitmedimurje.com') !== -1){
      e.preventDefault();
    }
  }, true);
  document.querySelectorAll('.brx-submenu-toggle > span[data-nav-href]').forEach(function(el){
    el.style.cursor = 'pointer';
    el.addEventListener('click', function(e){
      e.preventDefault();
      e.stopPropagation();
      window.location.href = el.getAttribute('data-nav-href');
    });
  });
})();
"""

# CSS 精确打击：只藏明确目标
CONTENT_CSS = """
/* ===== 1. 隐藏导航栏下拉（避免展开后看到英文） ===== */
.brx-dropdown-content { display: none !important; }
.brx-submenu-toggle > button { display: none !important; }

/* ===== 2. 隐藏首屏多语言小字 ===== */
.brxe-text-basic[class*="language"],
[class*="multilang"], [class*="multi-lang"] { display: none !important; }

/* ===== 3. 隐藏原站页脚 / 底部 logo ===== */
footer,
[class*="footer"],
[class*="logo-footer"],
[class*="bottom-bar"] { display: none !important; }

/* ===== 4. 隐藏无障碍、搜索 ===== */
.ti-wheelchair, .accessibility, [class*="userway"],
.ti-search { display: none !important; }

/* ===== 5. 隐藏原站 Hero 之后的主体内容 ===== */
/* 原站主体 section 有 brxe-section class，第一个是 hero，剩下的藏掉 */
section.brxe-section:not(:first-of-type) { display: none !important; }

/* ===== 6. 隐藏原站 hero 内部的多语言块（doživi zeleno 等） ===== */
#brxe-xvzhle ~ div:not(#my-content):not(#my-hero-subtitle),
#brxe-xvzhle ~ p:not(#my-hero-subtitle) { display: none !important; }

/* ===== 7. 隐藏原站 hero 里的 svg / 图标 ===== */
.brxe-svg:not(.logo-header), .brxe-icon { display: none !important; }

/* ===== 8. 我们的内容样式 ===== */
#my-content { max-width: 1200px; margin: 0 auto; padding: 60px 20px; position: relative; z-index: 100; background: #f4f7f4; }
.my-section { margin-bottom: 80px; }
.my-section-title {
  font-size: 32px; font-weight: 600; color: #1a3d24;
  border-left: 5px solid #2e7d32; padding-left: 16px;
  margin-bottom: 12px; font-family: 'PingFang SC','Microsoft YaHei',sans-serif;
}
.my-section-subtitle {
  color: #666; font-size: 16px; margin-bottom: 36px;
  padding-left: 21px; font-family: 'PingFang SC','Microsoft YaHei',sans-serif;
}
.my-card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px; }
.my-card {
  background: #fff; border-radius: 14px; padding: 28px;
  box-shadow: 0 6px 24px rgba(0,0,0,0.06); transition: transform .25s, box-shadow .25s;
  border-top: 3px solid #2e7d32;
}
.my-card:hover { transform: translateY(-4px); box-shadow: 0 12px 32px rgba(0,0,0,0.1); }
.my-card-tag {
  display: inline-block; background: #e8f5e9; color: #2e7d32;
  font-size: 12px; padding: 4px 10px; border-radius: 12px; margin-bottom: 14px;
}
.my-card-title { font-size: 20px; font-weight: 600; color: #1a3d24; margin-bottom: 14px; }
.my-card-highlight { color: #444; font-size: 15px; line-height: 1.85; margin-bottom: 14px; }
.my-card-experience {
  color: #2e7d32; font-size: 13px; line-height: 1.7; padding-top: 14px;
  border-top: 1px dashed #c8e6c9;
}
.my-logo-text {
  color: #fff; font-size: 24px; letter-spacing: 4px;
  font-family: 'STKaiti','KaiTi','PingFang SC',serif;
  font-weight: 500; text-shadow: 0 2px 8px rgba(0,0,0,.5);
  margin-right: 20px; vertical-align: middle;
}
.logo-header { display: none !important; }
/* 子页面隐藏 hero 大图 */
body[data-hero-style="none"] section:has(#brxe-xvzhle) {
  display: none !important;
}
body[data-hero-style="none"] #my-content {
  padding-top: 100px;
}
@media (max-width: 640px) {
  .my-section-title { font-size: 22px; }
  .my-card { padding: 20px; }
  #my-content { padding: 40px 16px; }
}
"""

global_cfg = json.loads(GLOBAL_CONFIG.read_text(encoding="utf-8"))
hide_selectors = global_cfg.get("hide_selectors", [])
nav_map = global_cfg.get("nav_replace", {})
logo_text = global_cfg.get("logo_text", "")
logo_href = global_cfg.get("logo_href", "/")
brand_name = global_cfg.get("brand_name", "")
global_css = global_cfg.get("global_css", "").strip()

page_files = []
if (TEMPLATE_DIR / "index.html").exists():
    page_files.append(("index", TEMPLATE_DIR / "index.html"))
if PAGES_DIR.exists():
    for cfg_file in sorted(PAGES_DIR.glob("*.json")):
        name = cfg_file.stem
        if name == "index":
            continue
        html_file = TEMPLATE_DIR / f"{name}.html"
        if html_file.exists():
            page_files.append((name, html_file))

print(f"📄 共 {len(page_files)} 个页面：{[n for n, _ in page_files]}\n")


def build_content_html(blocks):
    parts = ['<div id="my-content">']
    for block in blocks:
        parts.append('<section class="my-section">')
        if block.get("title"):
            parts.append(f'<h2 class="my-section-title">{block["title"]}</h2>')
        if block.get("subtitle"):
            parts.append(f'<p class="my-section-subtitle">{block["subtitle"]}</p>')
        parts.append('<div class="my-card-grid">')
        for item in block.get("items", []):
            parts.append('<div class="my-card">')
            if item.get("tag"):
                parts.append(f'<span class="my-card-tag">{item["tag"]}</span>')
            if item.get("title"):
                parts.append(f'<h3 class="my-card-title">{item["title"]}</h3>')
            if item.get("highlight"):
                parts.append(f'<p class="my-card-highlight">{item["highlight"]}</p>')
            if item.get("experience"):
                parts.append(f'<p class="my-card-experience">{item["experience"]}</p>')
            parts.append('</div>')
        parts.append('</div></section>')
    parts.append('</div>')
    return "".join(parts)


def process_page(name, html_file, page_cfg):
    backup = html_file.with_name(html_file.stem + "_backup.html")
    if not backup.exists():
        backup.write_text(html_file.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  已备份 → {backup.name}")

    html = backup.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    # CSS
    css_parts = ["<style id='site-custom-css'>"]
    for sel in hide_selectors:
        css_parts.append(f"{sel} {{ display: none !important; }}")
    css_parts.append(CONTENT_CSS)
    if global_css:
        css_parts.append(global_css)
    if page_cfg.get("custom_css", "").strip():
        css_parts.append(page_cfg["custom_css"])
    css_parts.append("</style>")
    head = soup.find("head")
    if head:
        old = soup.find(id="site-custom-css")
        if old:
            old.decompose()
        head.append(BeautifulSoup("".join(css_parts), "lxml"))
        # ---------- 删除汉堡按钮和移动端侧边菜单 ----------
        killed = 0
        # 1. 按钮本身
        for btn in soup.find_all("button"):
            cls = " ".join(btn.get("class", []))
            label = (btn.get("aria-label") or "").lower()
            if "brxe-toggle" in cls or "brx-toggle" in cls or label in ("open", "close", "menu", "toggle"):
                btn.decompose()
                killed += 1
        # 2. 它控制的侧边菜单容器
        for menu_id in ("brxe-gincmk",):
            el = soup.find(id=menu_id)
            if el:
                el.decompose()
                killed += 1
        # 3. 隐藏的 li 里那个 toggle
        for li in soup.find_all("li", style=lambda s: s and "display: none" in s):
            if li.find("button"):
                li.decompose()
                killed += 1
        if killed:
            print(f"  删除汉堡按钮/侧边菜单 {killed} 个")
    # 导航
    for toggle in soup.find_all("div", class_="brx-submenu-toggle"):
        span = toggle.find("span")
        if not span:
            continue
        txt = span.get_text(strip=True)
        if txt in nav_map:
            span.string = nav_map[txt]["text"]
            span["data-nav-href"] = nav_map[txt]["href"]

    for a in soup.find_all("a", class_="brxe-text-link"):
        t = a.get_text(strip=True)
        if t in nav_map:
            a.string = nav_map[t]["text"]
            a["href"] = nav_map[t]["href"]

    # hero 标题/副标题
    hero_style = page_cfg.get("hero_style", "full")
    title_div = soup.find(id="brxe-xvzhle")

    if title_div and page_cfg.get("hero_title"):
        title_div.clear()
        title_div.append(page_cfg["hero_title"])

    if title_div and page_cfg.get("hero_subtitle"):
        old = soup.find(id="my-hero-subtitle")
        if old:
            old.decompose()
        p = soup.new_tag("p", id="my-hero-subtitle")
        p.string = page_cfg["hero_subtitle"]
        p["style"] = (
            "color:#fff;font-size:16px;line-height:1.9;"
            "max-width:720px;margin:24px auto 0;text-align:center;"
            "text-shadow:0 2px 8px rgba(0,0,0,0.5);"
            "font-family:'PingFang SC','Microsoft YaHei',sans-serif;"
            "padding:0 20px;font-weight:300;position:relative;z-index:10;"
        )
        title_div.insert_after(p)

    # 内容块
    old_content = soup.find(id="my-content")
    if old_content:
        old_content.decompose()

    blocks = page_cfg.get("blocks", [])
    if blocks:
        content_html = build_content_html(blocks)
        content_soup = BeautifulSoup(content_html, "lxml")
        nav = soup.find("nav")
        if nav:
            nav.insert_after(content_soup)
        else:
            body = soup.find("body")
            if body:
                body.insert(0, content_soup)
        print(f"  注入 {len(blocks)} 个内容区块")

    # logo
    logo_svg = soup.find("svg", class_="logo-header")
    if logo_svg:
        parent_a = logo_svg.find_parent("a")
        if parent_a:
            parent_a["href"] = logo_href
            parent_a.attrs.pop("target", None)
            parent_a.attrs.pop("rel", None)
            if brand_name:
                old_brand = parent_a.find(id="my-brand")
                if old_brand:
                    old_brand.decompose()
                bs = soup.new_tag("span", id="my-brand")
                bs["class"] = "my-logo-text"
                bs.string = brand_name
                parent_a.insert(0, bs)
            if logo_text:
                old_back = parent_a.find(id="my-back-home")
                if old_back:
                    old_back.decompose()
                span = soup.new_tag("span", id="my-back-home")
                span.string = logo_text
                span["style"] = (
                    "color:#fff;font-size:14px;letter-spacing:3px;"
                    "margin-left:12px;vertical-align:middle;"
                    "text-shadow:0 1px 4px rgba(0,0,0,0.5);"
                    "font-family:'PingFang SC','Microsoft YaHei',sans-serif;"
                )
                parent_a.append(span)

    body = soup.find("body")
    if body:
        body["data-hero-style"] = hero_style

    # JS
    old_js = soup.find(id="my-nav-js")
    if old_js:
        old_js.decompose()
    js = soup.new_tag("script", id="my-nav-js")
    js.string = JS_CODE
    if body:
        body.append(js)

    html_file.write_text(str(soup), encoding="utf-8")


for name, html_file in page_files:
    print(f"🔧 {name}.html")
    cfg_path = PAGES_DIR / f"{name}.json"

    if cfg_path.exists():
        page_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    elif name == "index":
        page_cfg = {
            "hero_title": "梅吉穆列・两河间的绿野秘境",
            "hero_subtitle": (
                "克罗地亚最北端的隐秘沃土，静卧穆拉河与德拉瓦河的环抱之中。"
                "世代耕耘出如画田园，生活悠然松弛，藏着人与自然共生的慢时光。"
                "欢迎探索这片满目青翠的桃源之境。"
            ),
            "blocks": [],
            "hero_style": "full",
        }
    else:
        page_cfg = {}
    if name == "index":
        process_page(name, html_file, page_cfg)
    else:
        print(f"  ⏭ 跳过（子页面用独立 HTML）")

    print()

print("🎉 全部完成，Ctrl+F5 强刷浏览器")