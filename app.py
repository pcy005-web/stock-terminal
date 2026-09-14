from flask import Flask, render_template
import urllib.request
import json

app = Flask(__name__)

# 1. 기존에 잘 맞던 6개 지수 심볼 (차트 API 유지)
CHART_ASSETS = [
    {'id': 'kospi', 'name': '코스피', 'symbol': '%5EKS11'},
    {'id': 'kosdaq', 'name': '코스닥', 'symbol': '%5EKQ11'},
    {'id': 'dow', 'name': '다우존스', 'symbol': '%5EDJI'},
    {'id': 'nasdaq', 'name': '나스닥', 'symbol': '%5EIXIC'},
    {'id': 'sp500', 'name': 'S&P 500', 'symbol': '%5EGSPC'},
    {'id': 'phlx', 'name': '필라델피아 반도체', 'symbol': '%5ESOX'}
]

# 2. 이번에 보정할 5개 지표 심볼 (Quote API로 정확한 시세/등락률 매칭)
QUOTE_ASSETS = [
    {'id': 'kospi200', 'symbol': '%5EKS200'},
    {'id': 'vix', 'symbol': '%5EVIX'},
    {'id': 'wti', 'symbol': 'CL=F'},
    {'id': 'gold', 'symbol': 'GC=F'},
    {'id': 'usdkrw', 'symbol': 'USDKRW=X'}
]

def fetch_chart_data(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=4) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            quotes = res_data['chart']['result'][0]['indicators']['quote'][0]['close']
            valid = [q for q in quotes if q is not None]
            
            if len(valid) >= 2:
                cur, prev = valid[-1], valid[-2]
            else:
                cur = prev = valid[-1] if valid else 0
                
            change = cur - prev
            rate = (change / prev) * 100 if prev else 0.0
            return {'price': f"{cur:,.2f}", 'rate': f"{rate:+.2f}%", 'is_up': change >= 0}
    except Exception:
        return {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}

def fetch_quote_data(symbol):
    try:
        # VIX, 원유, 환율 등의 정밀한 시세를 위해 quote API 활용
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=4) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            q = res_data['quoteResponse']['result'][0]
            
            cur = q.get('regularMarketPrice', 0)
            prev = q.get('regularMarketPreviousClose', q.get('previousClose', cur))
            
            change = cur - prev
            rate = (change / prev) * 100 if prev else 0.0
            return {'price': f"{cur:,.2f}", 'rate': f"{rate:+.2f}%", 'is_up': change >= 0}
    except Exception:
        return {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}

@app.route('/')
def index():
    data = {}
    # 기존 검증된 6개 지표 데이터 수집
    for asset in CHART_ASSETS:
        data[asset['id']] = fetch_chart_data(asset['symbol'])
        
    # 보정된 5개 지표 데이터 수집
    for asset in QUOTE_ASSETS:
        data[asset['id']] = fetch_quote_data(asset['symbol'])
        
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
