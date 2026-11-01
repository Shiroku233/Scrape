import hashlib
import json
import math
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
        self.fetch_sub=config["fetch_sub"]


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

    all_replies = []

    #获取主评论
    main_replies = fetch_main_replies(mixin_key, session, config)
    all_replies.extend(main_replies)

    #获取楼中楼
    if config.fetch_sub:
        for i in range(len(main_replies)):
            main=main_replies[i]
            #对应主评论存在楼中楼才获取
            if main.get("sub_count", 0) > 0:
                print(f"第{i+1}条主评论，存在楼中楼")
                sub_replies = fetch_sub_replies(main,session, config)
                all_replies.extend(sub_replies)

    print(f"获取完成，共{len(all_replies)}条评论")
    file = Path(__file__).stem
    save_csv(all_replies, file)



def fetch_main_replies(mixin_key,session,config):

    url = "https://api.bilibili.com/x/v2/reply/wbi/main"
    headers = config.get_headers()
    oid = get_oid(config, session)

    next_offset=""
    page=0

    # 风控：每爬10~15页评论停20~30秒
    stop=0
    stop_page=random.randint(10,15)

    main_replies=[]
    print("----开始获取主评论----")
    while True:
        page+=1

        # 获取参数并签名
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

        signed=enc_wbi(params,mixin_key)

        #请求
        response = session.get(url, params=signed, headers=headers, timeout=10)
        data = response.json()
        if data.get("code")!=0:
            print(f"[主评论] 第{page}页失败： {data.get('code')} {data.get('message')}")
            break

        # 检查补充置顶/管理员评论
        if page==1:
            top = data["data"].get("top") or {}
            for key in ("upper", "admin"):
                raw_top_reply = top.get(key)
                # 置顶评论存在才处理，且置顶放最前
                if raw_top_reply and isinstance(raw_top_reply, dict) and raw_top_reply.get("rpid"):
                    top_reply=parse_single_reply(raw_top_reply)
                    #标记top
                    top_reply["mark"]="top"
                    main_replies.append(top_reply)
                    print(f"[置顶评论] 存在 添加成功")

        #获取并合并单页评论
        page_replies = []
        raw_replies = list(data["data"].get("replies") or [])
        for reply in raw_replies:
            main = parse_single_reply(reply)
            # 标记主评论
            if not main.get("mark"):
                main["mark"] = "main"
            page_replies.append(main)
        main_replies+=page_replies
        print(f"[主评论] 第{page}页成功，本页{len(page_replies)} 条，累计 {len(main_replies)} 条")

        #风控
        stop += 1
        if stop >= stop_page:
            pause = random.uniform(20, 30)
            print(f"[风控] 已连续爬 {stop} 页，暂停 {pause:.1f} 秒...")
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
    return main_replies

def fetch_sub_replies(main,session,config):

    url = "https://api.bilibili.com/x/v2/reply/reply"
    headers=config.get_headers()
    oid = get_oid(config, session)

    page=0
    sub_pages = math.ceil(main["sub_count"] / 20)

    # 风控：每爬5~8页评论停10~15秒
    stop = 0
    stop_page = random.randint(5, 8)

    sub_replies=[]
    print("----开始获取楼中楼----")
    while page<sub_pages:
        page+=1
        params = {
            "oid": oid,  #
            "type": 1,
            "root": main.get("reply_id"),
            "ps": 20,
            "pn": page
        }

        # 请求
        response = session.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        if data.get("code") != 0:
            print(f"[楼中楼] 第{page}页失败： {data.get('code')} {data.get('message')}")
            break

        #获取并合并楼中楼单页评论
        page_replies = []
        raw_replies = list(data["data"].get("replies") or [])
        for reply in raw_replies:
            sub=parse_single_reply(reply)
            # 标记楼中楼
            if not sub.get("mark"):
                sub["mark"] = "main"
            page_replies.append(sub)
        sub_replies += page_replies
        print(f"[楼中楼] 第{page}页成功，本页{len(page_replies)} 条，累计 {len(sub_replies)} 条")
        # 风控
        stop += 1
        if stop >= stop_page:
            pause = random.uniform(10, 15)
            print(f"[风控] 已连续爬 {stop} 页，暂停 {pause:.1f} 秒...")
            time.sleep(pause)
            stop = 0
            stop_page = random.randint(5, 8)

        # 随机休眠
        time.sleep(random.uniform(1, 3))
    return sub_replies


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

def parse_single_reply(reply):
    pictures = reply.get("content", {}).get("pictures") or []
    reply_data = {
        "name": reply["member"]["uname"],
        "uid": reply["member"]["mid"],
        "location": (reply.get("reply_control", {}).get("location") or "")[5:],
        "level": reply["member"]["level_info"]["current_level"],

        "reply_id": reply.get("rpid_str") or str(reply.get("rpid")),
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(reply["ctime"])),
        "message": reply["content"]["message"],
        "like": reply["like"],

        "root": reply.get("root", 0),
        "sub_count": reply.get("rcount", 0),

        "images": ",".join(p.get("img_src", "") for p in pictures if p.get("img_src")),
    }
    # print(reply_data)
    return reply_data



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