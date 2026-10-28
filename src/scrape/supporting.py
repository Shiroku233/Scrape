from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import pandas as pd


def create_session():
    session = requests.Session()
    retry=Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429,500,503,504],
        allowed_methods=["GET"],
    )
    adapter=HTTPAdapter(max_retries=retry)
    session.mount("http://",adapter)
    session.mount("https://",adapter)
    return session




def save_csv(rows, filename=None):
    df = pd.DataFrame(rows)

    out_dir = Path(filename)
    out_dir.mkdir(parents=True, exist_ok=True)
    path=f"{out_dir} / {filename}.csv"

    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"已保存到 {path}")