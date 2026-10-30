import time
from pathlib import Path

import requests

from scrape.supporting import create_session,save_csv


def run():

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    session = create_session()

    months = get_all_months(session)

    results = []
    for month in months:
        print(f"\n=== 开始处理 {month['name']}，共 {len(month['appids'])} 个游戏 ===")
        appids = month["appids"]
        for appid in appids:

            details=fetch_game_details(appid, headers,session)
            time.sleep(1.5)
            reviews=fetch_game_reviews(appid, headers,session)
            time.sleep(1.5)

            result = {
                "month":month["name"],
                "appid": appid,
                "name": details.get("name", ""),
                "genres": "|".join(details.get("genres", [])),
                "release": details.get("release", ""),
                "recommendations": details.get("recommendations", 0),
                "review_desc": reviews.get("review_desc", ""),
                "total_reviews": reviews.get("total_reviews", 0),
                "positive": reviews.get("positive", 0),
                "negative": reviews.get("negative", 0),
                "voted": reviews.get("voted", 0),
                "good_rated": reviews.get("good_rated", 0),
            }
            results.append(result)
            print(f" --处理完成{len(results)}-- {result['name']} | 类型: {result['genres']} | 好评率: {result['good_rated']}%")
    file = Path(__file__).stem
    save_csv(results,file)
    print(f"\n全部完成，共 {len(results)} 条记录")


def fetch_game_details(appid, headers,session):
    # 获取游戏详情数据：name,genres,release,recommendations
    url=f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=cn&l=schinese"

    res={"name":None,"genres":[],"release":"", "recommendations": 0}
    try:
        response = session.get(url, headers=headers, timeout=30)
        if response.status_code == 200:

            raw_text=response.text
            raw_data=response.json()
            data = raw_data.get(str(appid), {}).get("data", {})
            if data:
                res["name"] = data.get("name", "")
                res["genres"] = [g["description"] for g in data.get("genres", [])]
                res["release"] = data.get("release_date", {}).get("date", "")
                res["recommendations"] = data.get("recommendations", {}).get("total", 0)
            else:
                print(f"{appid}:无数据")  #业务层：成功但数据为空
        else:
            print(f"{appid}失败：{response.status_code}")  # HTTP层：被拒
    except requests.exceptions.RequestException as e:
        print(f"  [appdetails] {appid} 网络连接失败: {e}")  #网络层：未完成
    except ValueError as e:  # JSON 解析失败
        print(f"  [reviews] {appid} 返回非 JSON: {e}")
    return res


def fetch_game_reviews(appid, headers,session):
    # 获取游戏评论数据：review_desc,total_reviews,positive,negative,voted，计算good_rate
    res={"review_desc":"","total_reviews":0,"positive":0,"negative":0,"voted":0,"good_rated":0}

    url = f"https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/?appid={appid}&json=1&num_per_page=1"
    try:
        response = session.get(url, headers=headers,timeout=30)
        if response.status_code == 200:
            raw_text=response.text
            raw_data = response.json()
            summary=raw_data.get("response",{}).get("query_summary",{})

            if summary and summary.get("total_reviews", 0) > 0:
                res["review_desc"]=summary.get("review_score_desc","")  #特别好评 等
                res["total_reviews"] = summary.get("total_reviews", 0)
                pos=res["positive"]=summary.get("total_positive",0)
                neg=res["negative"]=summary.get("total_negative",0)

                voted=res["voted"]=res["positive"]+res["negative"]
                res["good_rated"]=round((pos/voted)*100,1) if voted>0 else 0
            else:
                print(f"{appid}:无数据")
        else:
            print(f"{appid}失败：{response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f" [reviews] {appid} 网络连接失败：{e}")
    except ValueError as e:  # JSON 解析失败
        print(f"  [reviews] {appid} 返回非 JSON: {e}")
    return res


def get_all_months(session):
    url = "https://api.steampowered.com/ISteamChartsService/GetTopReleasesPages/v1/"
    response = session.get(url, timeout=15)
    pages = response.json()["response"]["pages"]
    print(f"接口返回了 {len(pages)} 个月份")

    months = []
    for page in pages:
        months.append({
            "name": page["name"],
            "start_of_month": page["start_of_month"],
            "appids": [item["appid"] for item in page["item_ids"]]
        })
    return months