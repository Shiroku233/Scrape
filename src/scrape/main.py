import requests
import time

from bs4 import BeautifulSoup


def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    url = "https://movie.douban.com/top250"

    for i in range(3):
        response = requests.get(url, headers=headers)
        response.encoding = "utf-8"
        print(f"第 {i + 1} 次请求，状态码：{response.status_code}")

        if response.status_code != 200:
            print("请求被拒绝，稍后再试或检查headers")
            print(response.text[:500])
        else:
            resolve(response)
        time.sleep(1)


def resolve(response):
    soup = BeautifulSoup(response.text, "html.parser")
    movies = soup.find_all("div", class_="item")

    print(f"找到 {len(movies)} 部电影\n")

    for movie in movies:
        title = movie.find("span", class_="title").text
        rating = movie.find("span", class_="rating_num").text
        print(f"{title}  |  评分：{rating}")

if __name__ == "__main__":
    main()