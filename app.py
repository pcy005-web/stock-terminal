from flask import Flask, render_template
import urllib.request
import json
import ssl

app = Flask(__name__)

# 전역 충돌을 방지하기 위해 변수명을 market_categories로 명명
MARKET_CATEGORIES = [
    {
        'title': '🇰🇷 국내 증시',
        'stocks': [
            {'code': 'kospi', 'name': '코스피', 'ticker': '^KS11'},
            {'code': 'kosdaq', 'name': '코스닥', 'ticker': '^KQ11'},
            {'code': 'kospi200', 'name': '코스피 200 선물', 'ticker': '^KS200'}
        ]
    },
    {
        'title': '🌍 해외 증시 및 변동성',
        'stocks': [
            {'code': 'dow', 'name': '다우존스', 'ticker': '^DJI'},
            {'code': 'nasdaq', 'name': '나스닥', 'ticker': '^IXIC'},
            {'code': 'sp500', 'name': 'S&P 500', 'ticker': '^GSPC'},
            {'code': 'phlx', 'name': '필라델피아 반도체', 'ticker': '^SOX'},
            {'code': 'vix', 'name': 'S&P 500 VIX', 'ticker': '^VIX'}
        ]
    },
    {
        'title': '🛢️ 원자재 및 환율',
        'stocks': [
            {'code': 'wti', 'name': 'WTI원유', 'ticker': 'CL=F'},
            {'code': 'gold', 'name': '금현물', 'ticker': 'GC=F'},
            {'code': 'usdkrw', 'name': '원/달러 환율', 'ticker': 'USDKRW=X'}
        ]
    }
]

def get_market_price(ticker):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    encoded_ticker = ticker.replace('^', '%5E')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_ticker}?interval=1d&range=2d"
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=3) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            
            result_arr = res_json.get('chart', {}).get('result')
            if not result_arr:
                return {'price': '데이터 확인중', 'rate': '+0.00%', 'is_up': True}
                
            meta = result_arr[0].get('meta', {})
            cur = meta.get('regularMarketPrice')
            prev = meta.get('chartPreviousClose', meta.get('previousClose'))
            
            if cur is None or prev is None:
                closes = result_arr[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
                valid_closes = [c for c in closes if c is not None]
                if len(valid_closes) >= 2:
                    cur, prev = valid_closes[-1], valid_closes[-2]
                elif len(valid_closes) == 1:
                    cur = prev = valid_closes[-1]
                else:
                    return {'price': '데이터 확인중', 'rate': '+0.00%', 'is_up': True}

            diff = cur - prev
            pct = (diff / prev) * 100 if prev else 0.0
            
            return {
                'price': f"{cur:,.2f}",
                'rate': f"{pct:+.2f}%",
                'is_up': diff >= 0
            }
    except Exception:
        return {'price': '데이터 확인중', 'rate': '+0.00%', 'is_up': True}

@app.route('/')
def index():
    price_map = {}
    for cat in MARKET_CATEGORIES:
        for stock in cat['stocks']:
            price_map[stock['code']] = get_market_price(stock['ticker'])
            
    # 템플릿 변수명을 categories와 quotes로 명확하게 전달
    return render_template('index.html', categories=MARKET_CATEGORIES, quotes=price_map)

if __name__ == '__main__':
    app.run(debug=True)
