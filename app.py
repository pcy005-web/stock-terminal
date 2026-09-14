from flask import Flask, render_template_string
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def get_market_data():
    try:
        url = "https://finance.naver.com/"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            kospi_elem = soup.select_one("#KOSPI_now")
            kospi_change_elem = soup.select_one("#KOSPI_rate")

            kospi = kospi_elem.text if kospi_elem else "데이터 수신 대기"
            kospi_rate = kospi_change_elem.text if kospi_change_elem else ""

            return {"kospi": kospi, "kospi_rate": kospi_rate}
    except Exception as e:
        print(f"에러 발생: {e}")

    return {"kospi": "불러오기 실패", "kospi_rate": ""}

index_html = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AlphaFlow Terminal Pro - 실시간 연동</title>
    <style>
        body { background: #0f172a; color: #f8fafc; font-family: sans-serif; padding: 20px; max-width: 600px; margin: 0 auto; }
        .card { background: #1e293b; border: 1px solid #475569; border-radius: 8px; padding: 16px; margin-top: 15px; }
        .down { color: #f43f5e; font-weight: bold; }
        .btn { margin-top: 15px; padding: 10px 16px; background: #38bdf8; color: #0f172a; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; width: 100%; }
    </style>
</head>
<body>
    <h2>⚡ AlphaFlow 실시간 증시 연동 시스템</h2>
    <div class="card">
        <h3>코스피 (KOSPI) 실시간 시세</h3>
        <p style="font-size: 1.5rem; margin-top: 8px;">
            {{ data.kospi }} <span class="down">{{ data.kospi_rate }}</span>
        </p>
        <p style="font-size: 0.75rem; color: #94a3b8; margin-top: 8px;">
            ※ 새로고침(F5)할 때마다 서버가 네이버 금융 최신 데이터를 실시간으로 가져옵니다.
        </p>
    </div>
    <button class="btn" onclick="location.reload()">🔄 지금 바로 새로고침</button>
</body>
</html>
'''

@app.route('/')
def home():
    data = get_market_data()
    return render_template_string(index_html, data=data)

if __name__ == '__main__':
    app.run(debug=True)