import json
import time
from pathlib import Path

from DrissionPage import ChromiumPage
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

    cp=ChromiumPage()  #打开浏览器

    cp.listen.start(f"/api/v4/questions/{config.question_id}/feeds")  # 开启数据包监听

    cp.get(f"https://www.zhihu.com/question/{config.question_id}")  #打开网页



    all_answers = []

    while True:
        # 滚动到屏幕最底端
        cp.scroll.to_bottom()
        # 直接滚动到底部容易出现懒加载超时问题，到底后小幅上翻再下翻，补充触发懒加载
        cp.run_js("window.scrollBy(0, -300)")
        time.sleep(0.4)
        cp.run_js("window.scrollBy(0, 800)")
        time.sleep(0.5)

        # 等待数据包加载完毕
        response = cp.listen.wait(timeout=15)
        if not response:
            print("等待超时，停止")
            break

        raw = response.response.body

        data = raw.get("data",{})
        paging = raw.get("paging") or {}

        #尾页停止
        if paging.get("is_end",True):
            break

        page=paging.get("page","?")
        page_answers = []

        for answer in data:
            page_answers.append(parse_single_answer(answer,config))
        if not page_answers:
            print("本页无数据，停止")
            break

        all_answers += page_answers
        print(f"第{page}页完成，本页{len(page_answers)}条，共{len(all_answers)}条")



    save_path=Path(__file__).parent/"zhihu_answers.csv"
    r = Recorder(save_path)
    r.add_data(all_answers)
    r.record()

    cp.quit()



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

