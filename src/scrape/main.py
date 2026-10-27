import requests

url="https://httpbin.org/get"
response=requests.get(url)

print(response.status_code)

data = response.json()
print(data["url"])
print(data["headers"])