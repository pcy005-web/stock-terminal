from flask import Flask, render_template
import urllib.request
import json

app = Flask(__name__)

def fetch_yahoo_index(symbol):
    try:
        # 야후 파이낸스 공개 API를 활용한 실시간 지수 조회 (패키지 설치 불필요)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            result = res_data['chart']['result'][0]
            meta = result['meta']
            
            current_price = meta['regularMarketPrice']
            prev_close = meta['chartPreviousClose'] if 'chartPreviousClose' in meta else meta['previousClose']
            
            change = current_price - prev_close
            change_rate = (change / prev_close) * 100
            is_up = change >= 0
            
            return {
                'price': f"{current_price:,.2f}",
                'rate': f"{change_rate:+.2f}%",
                'is_up': is_up
            }
    except Exception as e:
        return None

@app.route('/')
def index():
    # 코스피(^KS11), 코스닥(^KQ11), 나스닥 100(^NDX) 정확한 글로벌 티커 사용
    kospi = fetch_yahoo_index('^KS11') or {'price': '정보 없음', 'rate': '0.00%', 'is_up': True}
    kosdaq = fetch_yahoo_index('^KQ11') or {'price': '정보 없음', 'rate': '0.00%', 'is_up': True}
    nasdaq = fetch_yahoo_index('^NDX') or {'price': '정보 없음', 'rate': '0.00%', 'is_up': True}

    data = {
        'kospi': kospi,
        'kosdaq': kosdaq,
        'nasdaq': nasdaq,
    }
    
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
