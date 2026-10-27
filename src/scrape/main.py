import requests
import time

url="https://httpbin.org/get"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

for i in range(3):
    response=requests.get(url,headers=headers)
    print(f"第 {i + 1} 次请求，状态码：{response.status_code}")
    time.sleep(1)

data = response.json()
print(data["url"])
print(data["headers"])