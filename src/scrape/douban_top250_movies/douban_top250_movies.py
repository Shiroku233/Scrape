import pandas as pd
import requests
import time

from bs4 import BeautifulSoup


def run():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    all_movies = []

    for start in range(0,250,25):
        url = f"https://movie.douban.com/top250?start={start}"
        response = requests.get(url, headers=headers)
        response.encoding = "utf-8"
        print(f"正在爬 start={start}，状态码：{response.status_code}")

        if response.status_code != 200:
            print("请求被拒绝，稍后再试或检查headers")
            print(response.text[:500])
        else:
            all_movies.extend(resolve(response))
        time.sleep(2)
    print(f"共爬取 {len(all_movies)} 部电影")
    save_data(all_movies)


def resolve(response):
    soup = BeautifulSoup(response.text, "html.parser")
    movies = soup.find_all("div", class_="item")

    print(f"找到 {len(movies)} 部电影\n")

    page_movies = []
    for movie in movies:
        title = movie.find("span", class_="title").text
        rating = float(movie.find("span", class_="rating_num").text)
        page_movies.append([title, rating])
    return page_movies

def save_data(movie_list):
    df=pd.DataFrame(movie_list,columns=["片名", "评分"])
    df.to_csv("douban_top250_movies.csv", index=False,encoding="utf-8-sig")

