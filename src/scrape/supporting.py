import re
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import markdown
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import pandas as pd


def create_session():
    session = requests.Session()
    retry=Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429,500,503,504],
        allowed_methods=["GET"],
    )
    adapter=HTTPAdapter(max_retries=retry)
    session.mount("http://",adapter)
    session.mount("https://",adapter)
    return session

def clean_url(raw_url):
    p = urlparse(raw_url)
    base = f"{p.scheme}://{p.netloc}{p.path}"  # 保留 协议 + 域名 + 路径（丢掉 ?查询 和 #锚点）
    params = {k: v[0] for k, v in parse_qs(p.query).items()}  # 只把查询参数转成字典
    return base,params


def convert_time(timestamp):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

def save_csv(rows, filename=None):
    df = pd.DataFrame(rows)

    out_dir = Path(filename)
    out_dir.mkdir(parents=True, exist_ok=True)
    path=out_dir/f"{filename}.csv"

    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"已保存到 {path}")


def html_to_md(html):

    if not html:
        return ""
    return markdownify(html).strip()


def md_to_html(md):
    if not md:
        return ""
    return markdown.markdown(md)


def md_to_txt(md):
    if not md:
        return ""
    text = md
    # 去掉加粗/斜体标记
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    # 去掉列表符号
    text = re.sub(r"^[-*+] ", "", text, flags=re.M)
    # 去掉链接，保留文字
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # 去掉多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def html_to_txt(raw_html):
    return md_to_txt(html_to_md(raw_html))
