import hashlib
import time
import urllib
from functools import reduce


from scrape.supporting import create_session, clean_url


def run():
    session = create_session()

    #获取一次密钥，整个运行期复用
    img_key, sub_key = get_wbi_key(session)
    mixin_key = get_mixin_key(img_key, sub_key)
    print(f"mixin_key: {mixin_key}")


    url ="https://api.bilibili.com/x/v2/reply/wbi/main"
    headers=get_headers()
    params = {
        "oid": 0,  #
        "type": 1,
        "mode": 3,
        "pagination_str": '{"offset":""}',
        "plat": 1,
        "web_location": 0,  #
        "seek_rpid": "",
    }


    # 获取一次密钥，整个运行期复用
    img_key, sub_key = get_wbi_key(session)
    mixin_key = get_mixin_key(img_key, sub_key)
    print(f"mixin_key: {mixin_key}")

    #签名
    signed = enc_wbi(params, mixin_key)

    response=session.get(url,params=signed,headers=headers,timeout=10)
    print(response.status_code)
    raw_data=response.json()
    print(raw_data)


def get_headers():
    with open('bili_cookie.txt', 'r') as f:
        cookie = f.read()
    headers = {
        "Cookie":cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36 Edg/146.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    return headers



MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]



def get_wbi_key(session):
    """从 nav 接口获取当天的 img_key 和 sub_key"""
    response=session.get("https://api.bilibili.com/x/web-interface/nav",headers=get_headers())
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