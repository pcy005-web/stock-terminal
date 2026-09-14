from flask import Flask, render_template
import urllib.request
import json
import csv
import io
import ssl

app = Flask(__name__)

MARKET_CATEGORIES = [
    {
        'title': '🇰🇷 국내 증시 (네이버 API)',
        'stocks': [
            {'code': 'kospi', 'name': '코스피', 'type': 'naver', 'ticker': 'KOSPI'},
            {'code': 'kosdaq', 'name': '코스닥', 'type': 'naver', 'ticker': 'KOSDAQ'},
            {'code': 'kospi200', 'name': '코스피 200 선물', 'type': 'stooq', 'ticker': '^ks200'}
        ]
    },
    {
        'title': '🌍 해외 증시 및 변동성 (Stooq)',
        'stocks': [
            {'code': 'dow', 'name': '다우존스', 'type': 'stooq', 'ticker': '^dji'},
            {'code': 'nasdaq', 'name': '나스닥', 'type': 'stooq', 'ticker': '^comp'},
            {'code': 'sp500', 'name': 'S&P 500', 'type': 'stooq', 'ticker': '^spx'},
            {'code': 'phlx', 'name': '필라델피아 반도체', 'type': 'stooq', 'ticker': '^sox'},
            {'code': 'vix', 'name': 'S&P 500 VIX', 'type': 'stooq', 'ticker': '^vix'}
        ]
    },
    {
        'title': '🛢️ 원자재 및 환율',
        'stocks': [
            {'code': 'wti', 'name': 'WTI원유', 'type': 'stooq', 'ticker': 'cl.f'},
            {'code': 'gold', 'name': '금현물', 'type': 'stooq', 'ticker': 'gc.f'},
            {'code': 'usdkrw', 'name': '원/달러 환율', 'type': 'naver_ex', 'ticker': 'FX_USDKRW'}
        ]
    }
]

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def get_naver_market(target):
    try:
        url = f"https://m.stock.naver.com/api/index/{target}/basic"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            cur = float(data.get('closeNow', '0').replace(',', ''))
            rate = float(data.get('fluctuationsRatio', '0'))
            sign = data.get('sign', {}).get('code', '2')
            return {
                'price': f"{cur:,.2f}",
                'rate': f"{rate:+.2f}%",
                'is_up': sign in ['1', '2']
            }
    except Exception:
        pass
    return None

def get_naver_exchange():
    try:
        url = "https://m.stock.naver.com/api/marketIndex/front"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=3) as resp:
            items = json.loads(resp.read().decode('utf-8'))
            for item in items:
                if item.get('marketIndexItemCode') == 'FX_USDKRW':
                    cur = float(item.get('closePrice', '0').replace(',', ''))
                    rate = float(item.get('fluctuationsRatio', '0'))
                    sign = item.get('sign', {}).get('code', '2')
                    return {
                        'price': f"{cur:,.2f}",
                        'rate': f"{rate:+.2f}%",
                        'is_up': sign in ['1', '2']
                    }
    except Exception:
        pass
    return None

def get_stooq_data(ticker):
    try:
        url = f"https://stooq.com/q/d/l/?s={ticker}&i=d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=3) as resp:
            lines = resp.read().decode('utf-8').strip().split('\n')
            if len(lines) >= 3:
                reader = csv.DictReader(lines)
                rows = list(reader)
                if len(rows) >= 2:
                    cur = float(rows[-1]['Close'])
                    prev = float(rows[-2]['Close'])
                    diff = cur - prev
                    rate = (diff / prev) * 100 if prev else 0.0
                    return {
                        'price': f"{cur:,.2f}",
                        'rate': f"{rate:+.2f}%",
                        'is_up': diff >= 0
                    }
    except Exception:
        pass
    return None

@app.route('/')
def index():
    price_map = {}
    for cat in MARKET_CATEGORIES:
        for stock in cat['stocks']:
            stype = stock['type']
            ticker = stock['ticker']
            code = stock['code']
            
            res = None
            if stype == 'naver':
                res = get_naver_market(ticker)
            elif stype == 'naver_ex':
                res = get_naver_exchange()
            elif stype == 'stooq':
                res = get_stooq_data(ticker)
                
            price_map[code] = res or {'price': '데이터 확인중', 'rate': '+0.00%', 'is_up': True}
            
    return render_template('index.html', categories=MARKET_CATEGORIES, quotes=price_map)

if __name__ == '__main__':
    app.run(debug=True)
