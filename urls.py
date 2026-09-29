import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
import re

# ========== 配置 ==========
BASE_URL = "https://visitmedimurje.com/en/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://visitmedimurje.com/",
}
SAVE_DIR = "visitmedimurje_data"


def fetch_page(url, retries=3):
    """发送请求并返回 HTML 文本，带重试机制"""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return resp.text
        except requests.RequestException as e:
            print(f"  [第{attempt+1}次] 请求失败: {e}")
            time.sleep(2 * (attempt + 1))
    return None


def parse_homepage(html):
    """解析首页，提取标题、导航链接、文章/景点摘要"""
    soup = BeautifulSoup(html, "lxml")
    data = {"title": "", "links": [], "articles": []}

    # 网页标题
    title_tag = soup.find("title")
    if title_tag:
        data["title"] = title_tag.get_text(strip=True)

    # 提取导航/内容链接
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        # 过滤空链接、锚点、外部链接
        if not text or href.startswith("#") or href.startswith("javascript"):
            continue
        # 补全相对路径
        if href.startswith("/"):
            href = "https://visitmedimurje.com" + href
        # 只保留站内链接
        if "visitmedimurje.com" in href and href not in seen:
            seen.add(href)
            data["links"].append({"text": text, "url": href})

    # 尝试提取文章/景点卡片（根据常见 WordPress 结构）
    for article in soup.find_all(["article", "div"], class_=re.compile(
            r"card|post|item|entry|attraction|listing", re.I)):
        title_el = article.find(["h2", "h3", "h4"])
        desc_el = article.find("p")
        link_el = article.find("a", href=True)
        if title_el:
            data["articles"].append({
                "title": title_el.get_text(strip=True),
                "description": desc_el.get_text(strip=True) if desc_el else "",
                "url": link_el["href"] if link_el else "",
            })

    return data


def crawl_detail_pages(links, max_pages=20):
    """爬取详情页内容"""
    results = []
    for i, link in enumerate(links[:max_pages]):
        print(f"[{i+1}/{min(len(links), max_pages)}] 正在爬取: {link['url']}")
        html = fetch_page(link["url"])
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")

        # 提取详情页正文（适配常见 WordPress 内容容器）
        content_el = soup.find(
            ["div", "article"],
            class_=re.compile(r"content|entry|post|main|text", re.I)
        )
        content = ""
        if content_el:
            # 清理脚本和样式
            for tag in content_el.find_all(["script", "style", "nav", "footer"]):
                tag.decompose()
            content = content_el.get_text(separator="\n", strip=True)

        # 提取详情页图片
        images = [
            img.get("src") or img.get("data-src")
            for img in soup.find_all("img")
            if img.get("src") or img.get("data-src")
        ]

        results.append({
            "url": link["url"],
            "title": link["text"],
            "content": content[:3000],  # 限制长度
            "images": images[:10],
        })
        time.sleep(1)  # 控制请求频率

    return results


def main():
    os.makedirs(SAVE_DIR, exist_ok=True)

    # 1. 抓取首页
    print("正在抓取首页...")
    html = fetch_page(BASE_URL)
    if not html:
        print("首页抓取失败，请检查网络或增加代理")
        return

    home_data = parse_homepage(html)
    print(f"首页标题: {home_data['title']}")
    print(f"发现 {len(home_data['links'])} 个站内链接")
    print(f"发现 {len(home_data['articles'])} 个内容条目")

    # 2. 保存首页数据
    pd.DataFrame(home_data["articles"]).to_csv(
        os.path.join(SAVE_DIR, "homepage_articles.csv"),
        index=False, encoding="utf-8-sig"
    )

    # 3. 爬取详情页
    if home_data["links"]:
        detail_results = crawl_detail_pages(home_data["links"], max_pages=20)
        pd.DataFrame(detail_results).to_csv(
            os.path.join(SAVE_DIR, "detail_pages.csv"),
            index=False, encoding="utf-8-sig"
        )
        print(f"\n已保存 {len(detail_results)} 条详情页数据")

    print(f"\n所有数据已保存到 '{SAVE_DIR}/' 目录")


if __name__ == "__main__":
    main()