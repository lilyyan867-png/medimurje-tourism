from playwright.sync_api import sync_playwright
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from pathlib import Path
import hashlib
import json
import re
import os

BASE_URL = "https://visitmedimurje.com/en/"
ROOT = Path("mirror")
TEMPLATES = ROOT / "templates"
ASSETS = ROOT / "static" / "assets"
TEMPLATES.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)

# url -> 本地相对路径
downloaded = {}

print("脚本开始运行...")
def local_filename(url):
    """根据 URL 生成唯一且带扩展名的本地文件名"""
    p = urlparse(url)
    name = Path(p.path).name or "index"
    if "." not in name:
        name += ".bin"
    # 避免重名，用 url 的 md5 前缀
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{h}_{name}"


def save_asset(url, body):
    if url in downloaded:
        return downloaded[url]
    fname = local_filename(url)
    path = ASSETS / fname
    path.write_bytes(body)
    rel = f"assets/{fname}"
    downloaded[url] = rel
    return rel


def is_asset(content_type):
    return any(t in content_type for t in (
        "image/", "font/", "text/css", "javascript",
        "application/font", "application/x-font"
    ))


def crawl():
    def crawl():
        print("准备启动浏览器...")
        with sync_playwright() as p:
            print("Playwright 已启动")
            browser = p.chromium.launch(headless=True)
            print("Chromium 已打开")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"),
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()

        # 监听所有响应，把静态资源存下来
        def on_response(resp):
            try:
                ct = resp.headers.get("content-type", "")
                if not is_asset(ct):
                    return
                body = resp.body()
                if not body:
                    return
                save_asset(resp.url, body)
            except Exception:
                pass

        page.on("response", on_response)

        print("加载首页...")
        page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
        print("正在访问:", BASE_URL)
        page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
        print("首页加载完成")
        page.wait_for_timeout(3000)

        # 滚动页面触发懒加载图片/动图
        for _ in range(8):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(800)

        html = page.content()
        browser.close()

    return html


def localize_html(html):
    """把 HTML 里的远程 URL 换成本地路径"""
    # 先做一遍字符串替换（对 url 完全一致的情况最有效）
    for remote, local in downloaded.items():
        # 加引号的精确替换，避免误伤
        html = html.replace(f'"{remote}"', f'"/static/{local}"')
        html = html.replace(f"'{remote}'", f"'/static/{local}'")
        html = html.replace(f"({remote})", f"(/static/{local})")

    soup = BeautifulSoup(html, "lxml")

    # 处理 img / source 的 srcset
    for tag in soup.find_all(["img", "source"]):
        for attr in ("src", "data-src", "data-lazy-src"):
            v = tag.get(attr)
            if v and v in downloaded:
                tag[attr] = "/static/" + downloaded[v]
        srcset = tag.get("srcset")
        if srcset:
            parts = []
            for item in srcset.split(","):
                item = item.strip()
                if not item:
                    continue
                url, _, desc = item.partition(" ")
                if url in downloaded:
                    url = "/static/" + downloaded[url]
                parts.append(f"{url} {desc}".strip())
            tag["srcset"] = ", ".join(parts)

    # 移除会被远端覆盖或阻塞的资源
    for tag in soup.find_all(["script", "link"]):
        src = tag.get("src") or tag.get("href") or ""
        # 去掉外部追踪、统计脚本
        if any(d in src for d in ("google-analytics", "googletagmanager",
                                   "facebook.net", "hotjar", "doubleclick")):
            tag.decompose()

    # 保证相对路径以 / 开头
    for tag in soup.find_all(["link", "script", "img"]):
        for attr in ("href", "src"):
            v = tag.get(attr)
            if v and v.startswith("assets/"):
                tag[attr] = "/static/" + v

    return str(soup)


def fix_css_urls():
    """把 CSS 里的 url(...) 指向本地资源"""
    for css_file in ASSETS.glob("*.css"):
        text = css_file.read_text(encoding="utf-8", errors="ignore")
        changed = False
        for remote, local in downloaded.items():
            if remote in text:
                # CSS 内引用其它资源时，用相对 assets 的路径
                text = text.replace(remote, local.split("/")[-1])
                changed = True
        # 处理 url(//xxx) 形式的协议相对 URL
        def repl(m):
            inner = m.group(1).strip('\'"')
            if inner in downloaded:
                return f'url("{downloaded[inner].split("/")[-1]}")'
            return m.group(0)
        new_text = re.sub(r'url\(([^)]+)\)', repl, text)
        if new_text != text or changed:
            css_file.write_text(new_text, encoding="utf-8")


def extract_texts(html):
    """提取所有可见文字节点，生成替换用的 JSON"""
    soup = BeautifulSoup(html, "lxml")
    texts = []
    seen = set()
    for node in soup.find_all(string=True):
        t = node.strip()
        if not t:
            continue
        parent = node.parent.name
        if parent in ("script", "style", "noscript"):
            continue
        if len(t) < 2:
            continue
        if t in seen:
            continue
        seen.add(t)
        texts.append({"original": t, "replacement": ""})
    return texts


def main():
    html = crawl()
    print(f"已下载 {len(downloaded)} 个资源")

    html = localize_html(html)
    fix_css_urls()

    (TEMPLATES / "index.html").write_text(html, encoding="utf-8")
    print(f"HTML 已保存到 {TEMPLATES / 'index.html'}")

    texts = extract_texts(html)
    (ROOT / "texts.json").write_text(
        json.dumps(texts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已提取 {len(texts)} 条文字到 {ROOT / 'texts.json'}")


if __name__ == "__main__":
    main