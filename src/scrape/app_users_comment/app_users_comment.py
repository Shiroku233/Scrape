import hashlib
import json
import random
import re
import time
import urllib
from functools import reduce
from pathlib import Path

from scrape.supporting import create_session, save_csv

class Config:
    def __init__(self):
        dir = Path(__file__).resolve().parent
        config_path = dir / "config.json"
        with open(config_path, 'r') as f:
            config = json.load(f)
        self.bv = config["bv"]
        self.cookie = config["cookie"]



    def get_headers(self):
        """根据指定cookie获取请求头"""
        headers = {
            "Cookie": self.cookie,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36 Edg/146.0.0.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        return headers

def run():
    session = create_session()

    # 获取配置
    config = Config()

    # 获取一次密钥，整个运行期复用
    img_key, sub_key = get_wbi_key(session,config)
    mixin_key = get_mixin_key(img_key, sub_key)
    print(f"mixin_key: {mixin_key}")

    oid = get_oid(config, session)

    #获取数据
    results=fetch_all_replies(mixin_key,oid,session,config)

    file = Path(__file__).stem
    save_csv(results, file)



def fetch_all_replies(mixin_key,oid,session,config):

    url = "https://api.bilibili.com/x/v2/reply/wbi/main"
    headers = config.get_headers()

    next_offset=""
    page=0

    # 风控：每爬10~15页评论停20~30秒
    stop=0
    stop_page=random.randint(10,15)

    all_replies=[]
    while True:
        page+=1

        params = {
            "oid": oid,  #
            "type": 1,
            "mode": 3,
            "pagination_str": '{"offset":"%s"}'%next_offset,
            "plat": 1,
            "web_location": 1315875,
        }

        if next_offset=="":  #首页：next_offset为空
            params["seek_rpid"] = ""  #增加seek_rpid参数

        #签名
        signed=enc_wbi(params,mixin_key)

        #解析
        response = session.get(url, params=signed, headers=headers, timeout=10)
        data = response.json()
        if data.get("code")!=0:
            print(f"第{page}页失败： {data.get('code')} {data.get('message')}")
            break

        #获取并合并单页数据
        page_replies = resolve_page_replies(data)
        all_replies=all_replies+page_replies
        print(f"第{page}页成功，本页{len(page_replies)} 条，累计 {len(all_replies)} 条")

        #风控
        stop += 1
        if stop >= stop_page:
            pause = random.uniform(20, 30)
            print(f"已连续爬 {stop} 页，暂停 {pause:.1f} 秒...")
            time.sleep(pause)
            stop = 0
            stop_page = random.randint(10, 15)

        #翻页指针
        next_offset = (
            data["data"].get("cursor", {})
            .get("pagination_reply", {})
            .get("next_offset") or ""
        )

        #到达最后一页停止
        if not next_offset or data["data"]["cursor"].get("is_end"):
            break

        #随机休眠
        time.sleep(random.uniform(1, 3))
    return all_replies




def get_oid(config,session):
    """通过 BV 号获取视频的 aid(oid)"""
    bv=config.bv
    url = f"https://www.bilibili.com/video/{bv}"
    response = session.get(url, headers=config.get_headers(), timeout=10)
    response.encoding = "utf-8"
    res = re.search(r'"aid":(\d+),"bvid":"' + re.escape(bv) + '"', response.text)
    if res:
        return int(res.group(1))

    # 兜底：有些页面格式略有不同，直接找 aid
    res = re.search(r'"aid":(\d+)', response.text)
    if res:
        return int(res.group(1))

    raise ValueError(f"无法从 {bv} 解析出 oid，请检查 BV 号是否正确")

def resolve_page_replies(data):
    """解析单页数据"""
    page_replies = []

    is_first_page = data["data"]["cursor"].get("is_begin")
    replies = list(data["data"].get("replies") or [])

    #检查补充置顶/管理员评论
    if is_first_page:
        top = data["data"].get("top") or {}
        for key in ("upper", "admin"):
            top_reply=top.get(key)
            if top_reply and isinstance(top_reply, dict) and top_reply.get("rpid"):
                replies.insert(0, top_reply)  # 置顶放最前


    for reply in replies:
        pictures=reply.get("content",{}).get("pictures") or []
        reply_data = {
            "name": reply["member"]["uname"],
            "uid": reply["member"]["mid"],
            "location": (reply.get("reply_control", {}).get("location") or "")[5:],
            "level": reply["member"]["level_info"]["current_level"],

            "reply_id": reply.get("rpid"),
            "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(reply["ctime"])),
            "message": reply["content"]["message"],
            "like": reply["like"],
            "sub_count": reply.get("rcount",0),

            "images": ",".join(p.get("img_src", "") for p in pictures if p.get("img_src")),
        }
        # print(reply_data)
        page_replies.append(reply_data)
    return page_replies



#----获取wts和w_rid算法----
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]



def get_wbi_key(session,config):
    """从 nav 接口获取当天的 img_key 和 sub_key"""
    url="https://api.bilibili.com/x/web-interface/nav"
    response=session.get(url,headers=config.get_headers(),timeout=10)
    data=response.json()["data"]["wbi_img"]

    img_url=data["img_url"]
    sub_url=data["sub_url"]
    img_key=img_url.rsplit("/",1)[-1].split(".")[0]
    sub_key=sub_url.rsplit("/",1)[-1].split(".")[0]

    return img_key,sub_key


def get_mixin_key(img_key,sub_key):
    """拼接并重排，取前32位作为签名密钥"""
    raw=img_key+sub_key
    return reduce(lambda s,i:s+raw[i],MIXIN_KEY_ENC_TAB,"")[:32]

def enc_wbi(params: dict, mixin_key: str):
    """对参数进行签名，返回带 wts 和 w_rid 的参数字典"""
    params["wts"] = int(time.time())
    # 按 key 排序后 URL 编码
    params = dict(sorted(params.items()))
    query = urllib.parse.urlencode(params)
    # 拼接 mixin_key 后算 MD5
    w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
    params["w_rid"] = w_rid
    return params