from flask import Flask, render_template
import urllib.request
import json

app = Flask(__name__)

ASSETS = [
    {'id': 'kospi', 'name': '코스피 (KOSPI)', 'symbol': '%5EKS11'},
    {'id': 'kosdaq', 'name': '코스닥 (KOSDAQ)', 'symbol': '%5EKQ11'},
    {'id': 'kospi200', 'name': '코스피 200 선물', 'symbol': '%5EKS200'},
    {'id': 'dow', 'name': '다우존스', 'symbol': '%5EDJI'},
    {'id': 'nasdaq', 'name': '나스닥', 'symbol': '%5EIXIC'},
    {'id': 'sp500', 'name': 'S&P 500', 'symbol': '%5EGSPC'},
    {'id': 'phlx', 'name': '필라델피아 반도체', 'symbol': '%5ESOX'},
    {'id': 'vix', 'name': 'S&P 500 VIX', 'symbol': '%5EVIX'},
    {'id': 'wti', 'name': 'WTI원유', 'symbol': 'CL=F'},
    {'id': 'gold', 'name': '금현물', 'symbol': 'GC=F'},
    {'id': 'usdkrw', 'name': '원/달러 환율', 'symbol': 'USDKRW=X'}
]

def fetch_market_data(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            result = res_data['chart']['result'][0]
            
            # 차트 가격 배열에서 유효한 값을 추출해 정확한 등락 계산
            quotes = result['indicators']['quote'][0]['close']
            valid_quotes = [q for q in quotes if q is not None]
            
            if len(valid_quotes) >= 2:
                current_price = valid_quotes[-1]
                prev_close = valid_quotes[-2]
            else:
                current_price = valid_quotes[-1] if valid_quotes else 0
                prev_close = current_price

            change = current_price - prev_close
            change_rate = (change / prev_close) * 100 if prev_close else 0.0
            is_up = change >= 0
            
            return {
                'price': f"{current_price:,.2f}",
                'rate': f"{change_rate:+.2f}%",
                'is_up': is_up
            }
    except Exception:
        return {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}

@app.route('/')
def index():
    data = {}
    for asset in ASSETS:
        data[asset['id']] = fetch_market_data(asset['symbol'])
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
