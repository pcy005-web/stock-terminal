from flask import Flask, render_template
import urllib.request
import json

app = Flask(__name__)

ASSETS = [
    {'id': 'kospi', 'name': '코스피', 'symbol': '%5EKS11', 'type': 'chart'},
    {'id': 'kosdaq', 'name': '코스닥', 'symbol': '%5EKQ11', 'type': 'chart'},
    {'id': 'dow', 'name': '다우존스', 'symbol': '%5EDJI', 'type': 'chart'},
    {'id': 'nasdaq', 'name': '나스닥', 'symbol': '%5EIXIC', 'type': 'chart'},
    {'id': 'sp500', 'name': 'S&P 500', 'symbol': '%5EGSPC', 'type': 'chart'},
    {'id': 'phlx', 'name': '필라델피아 반도체', 'symbol': '%5ESOX', 'type': 'chart'},
    {'id': 'kospi200', 'name': '코스피 200 선물', 'symbol': '%5EKS200', 'type': 'quote'},
    {'id': 'vix', 'name': 'S&P 500 VIX', 'symbol': '%5EVIX', 'type': 'quote'},
    {'id': 'wti', 'name': 'WTI원유', 'symbol': 'CL=F', 'type': 'quote'},
    {'id': 'gold', 'name': '금현물', 'symbol': 'GC=F', 'type': 'quote'},
    {'id': 'usdkrw', 'name': '원/달러 환율', 'symbol': 'USDKRW=X', 'type': 'quote'}
]

def get_yahoo_data(symbol, data_type):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    try:
        if data_type == 'chart':
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                quotes = res_data['chart']['result'][0]['indicators']['quote'][0]['close']
                valid = [q for q in quotes if q is not None]
                if len(valid) >= 2:
                    cur, prev = valid[-1], valid[-2]
                else:
                    cur = prev = valid[-1] if valid else 0
        else:
            url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                q = res_data['quoteResponse']['result'][0]
                cur = q.get('regularMarketPrice', 0)
                prev = q.get('regularMarketPreviousClose', q.get('previousClose', cur))

        if not cur or not prev:
            raise ValueError("Invalid price data")

        change = cur - prev
        rate = (change / prev) * 100 if prev else 0.0
        return {
            'price': f"{cur:,.2f}",
            'rate': f"{rate:+.2f}%",
            'is_up': change >= 0
        }
    except Exception as e:
        # 오류 발생 시 폴백(차트 API로 한 번 더 재시도)
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                quotes = res_data['chart']['result'][0]['indicators']['quote'][0]['close']
                valid = [q for q in quotes if q is not None]
                cur = valid[-1] if valid else 0
                prev = valid[-2] if len(valid) >= 2 else cur
                change = cur - prev
                rate = (change / prev) * 100 if prev else 0.0
                return {
                    'price': f"{cur:,.2f}",
                    'rate': f"{rate:+.2f}%",
                    'is_up': change >= 0
                }
        except Exception:
            return {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}

@app.route('/')
def index():
    data = {}
    for asset in ASSETS:
        data[asset['id']] = get_yahoo_data(asset['symbol'], asset['type'])
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
