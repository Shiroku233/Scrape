import time

import requests


def run():
    appids = ["730", "570", "1091500", "271590"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    get_game_details(appids, headers)

def get_game_details(appids, headers):

    for appid in appids:
        url=f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=cn&l=schinese"
        response = requests.get(url, headers=headers,timeout=15)

        if response.status_code == 200:
            raw_data=response.json()
            data=raw_data.get(appid,{}).get("data",{})
            if data:
                genres=[g["description"] for g in data.get("genres",[])]
                release=data.get("release_date",{}).get("date","")
                recommendation=data.get("recommendation",{}).get("total",0)
                print(f"{data.get('name')} | 类型：{genres} | 发行：{release} | 推荐数：{recommendation}")
            else:
                print(f"{appid}:无数据")
        else:
            print(f"{appid}失败：{response.status_code}")
        time.sleep(2)

        url1 = f"https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/?appid={appid}&json=1&num_per_page=1"
        response1 = requests.get(url1, headers=headers,timeout=15)
        if response1.status_code == 200:
            summary=response1.json().get("response",{}).get("query_summary",{})
            pos=summary.get("total_positive",0)
            neg=summary.get("total_negative",0)

            total=pos + neg
            rate=round((pos/total)*100,1) if total>0 else 0
            print(f"好评率：{rate}% （{pos}好/{neg}差）")
        else:
            print(f"{appid}失败：{response.status_code}")

