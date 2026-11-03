import json
import time
from pathlib import Path

from DrissionPage import ChromiumPage,WebPage
from DrissionRecord import Recorder

from scrape.supporting import convert_time, html_to_txt, html_to_md

CONTENT_TYPE=["markdown","html","text"]

class Config:
    def __init__(self):
        dir = Path(__file__).resolve().parent
        config_path = dir / "config.json"
        with open(config_path, 'r') as f:
            config = json.load(f)
        self.content_type = config["content_type"]
        self.question_id = config["question_id"]


def run():

    config = Config()
    if config.content_type not in CONTENT_TYPE:
        raise ValueError(f"config.json 的 content_type 必须是 {CONTENT_TYPE} 之一，当前是 {config.content_type}")
    if not config.question_id:
        raise ValueError(f"config的question格式不支持")

    all_answers = []
    fetch_first_page(config,all_answers)
    fetch_pages_answers(config,all_answers)

    #去重
    results=deduped(all_answers)

    save_path=Path(__file__).parent/"zhihu_answers.csv"
    r = Recorder(save_path)
    r.add_data(results)
    r.record()



def fetch_pages_answers(config,all_answers):
    cp = ChromiumPage()  # 打开浏览器
    cp.listen.start(f"/api/v4/questions/{config.question_id}/feeds")  # 开启数据包监听

    url=f"https://www.zhihu.com/question/{config.question_id}"
    cp.get(url)  # 打开网页

    print("----开始获取主要页面回答----")
    while True:
        # 滚动到屏幕最底端
        cp.scroll.to_bottom()
        # 直接滚动到底部容易出现懒加载超时问题，到底后小幅上翻再下翻，补充触发懒加载
        last_height = cp.run_js("return document.body.scrollHeight")
        for _ in range(5):  # 最多补滚5次
            cp.scroll.to_bottom()
            cp.run_js("window.scrollBy(0, -300)")
            time.sleep(0.4)
            cp.run_js("window.scrollBy(0, 800)")
            time.sleep(0.6)
            new_height = cp.run_js("return document.body.scrollHeight")
            if new_height != last_height:
                break
            last_height = new_height

        # 等待数据包加载完毕
        response = cp.listen.wait(timeout=20)
        if not response:
            print("等待超时，停止")
            break

        raw = response.response.body

        data = raw.get("data", {})
        paging = raw.get("paging") or {}

        # 尾页停止
        if paging.get("is_end", True):
            break

        page = paging.get("page", "?")
        page_answers = []

        for answer in data:
            page_answers.append(parse_single_answer(answer, config))
        if not page_answers:
            print("本页无数据，停止")
            break

        all_answers.extend(page_answers)
        print(f"第{page}页完成，本页{len(page_answers)}条，共{len(all_answers)}条")
    # cp.quit()



def fetch_first_page(config,all_answers):
    """首页数据地址与常规页面不同，需要特殊处理"""

    wp = WebPage()  # 用 WebPage 打开浏览器
    wp.get(f"https://www.zhihu.com/question/{config.question_id}")
    wp.change_mode()  # 切换为请求模式，此时 wp.get 发出的请求能自动带上浏览器的 Cookie

    # 构造第一页请求（offset=0）
    url = f"https://www.zhihu.com/api/v4/questions/{config.question_id}/answers"
    params = {
        "include": "data[*].content,excerpt,author.name,created_time,voteup_count",
        "limit": 20,  # limit设大一点，减少后续请求次数
        "offset": 0,
        "platform": "desktop",
        "sort_by": "default",
    }
    ok = wp.get(url, params=params)
    if not ok:
        print("请求失败，可能被风控或未登录")
        wp.quit()
        return False

    raw = wp.json
    data = raw.get("data", {})
    wp.quit()  # 关闭这个临时页面

    print("----开始获取第一页回答----")
    # 解析第一页answers
    first_answers = []
    for answer in data:
        first_answers.append(parse_single_answer(answer, config))

    all_answers.extend(first_answers)
    print(f"第1页完成，本页{len(first_answers)}条，共{len(all_answers)}条")
    return True


def parse_single_answer(answer,config):
    #主要回答数据
    target = answer.get("target") or {}
    #答主数据
    author = target.get("author") or {}

    #根据content_type调整输出内容格式
    content = target.get("content", "")
    content_type=config.content_type
    if content_type == "markdown":content = html_to_md(content)
    elif content_type == "text":content = html_to_txt(content)
    elif content_type == "html":pass

    answer_data = {
        "answer_id": target.get("id"),

        "author_name": author.get("name", ""),
        "author_token": author.get("url_token", ""),
        "author_headline": author.get("headline", ""),

        "content": content,
        "created_time": convert_time(target.get("created_time")),

        "voteup_count": target.get("voteup_count", 0),
        "favlists_count": target.get("favlists_count", 0),
        "comment_count": target.get("comment_count", 0),
    }
    return answer_data

def deduped(all_answers):
    seen = set()
    deduped_answers = []
    print("----开始去重----")
    for answer in all_answers:
        aid = answer.get("answer_id")
        if aid is None or aid in seen:
            continue
        seen.add(aid)
        deduped_answers.append(answer)
    print(f"去重前 {len(all_answers)} 条，去重后 {len(deduped_answers)} 条，移除 {len(all_answers) - len(deduped_answers)} 条重复")
    return deduped_answers