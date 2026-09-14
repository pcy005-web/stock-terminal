from flask import Flask, render_template
import urllib.request
import json
import ssl

app = Flask(__name__)

# 네이버 모바일 금융 API에서 실제로 실시간 조회가 가능한 주요 지표 설정
MARKET_CATEGORIES = [
    {
        'title': '🇰🇷 국내 증시 (네이버 실시간 연동)',
        'stocks': [
            {'code': 'kospi', 'name': '코스피', 'target': 'KOSPI'},
            {'code': 'kosdaq', 'name': '코스닥', 'target': 'KOSDAQ'},
            {'code': 'kospi200', 'name': '코스피 200', 'target': 'KPI200'}
        ]
    },
    {
        'title': '🌍 해외 증시 및 변동성',
        'stocks': [
            {'code': 'dow', 'name': '다우존스', 'target': 'DJI@DJI'},
            {'code': 'nasdaq', 'name': '나스닥', 'target': 'NAS@IXIC'},
            {'code': 'sp500', 'name': 'S&P 500', 'target': 'SPI@SPX'}
        ]
    },
    {
        'title': '🛢️ 원자재 및 환율',
        'stocks': [
            {'code': 'wti', 'name': 'WTI원유', 'target': 'OIL@CL'},
            {'code': 'gold', 'name': '금현물', 'target': 'NTS@GC'},
            {'code': 'usdkrw', 'name': '원/달러 환율', 'target': 'FX_USDKRW'}
        ]
    }
]

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def fetch_naver_market_data():
    price_map = {}
    
    # 1. 국내 지수 및 환율 조회 (네이버 API)
    for cat in MARKET_CATEGORIES:
        for stock in cat['stocks']:
            target = stock['target']
            code = stock['code']
            
            try:
                if target == 'FX_USDKRW':
                    url = "https://m.stock.naver.com/api/marketIndex/front"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, context=get_ssl_context(), timeout=3) as resp:
                        items = json.loads(resp.read().decode('utf-8'))
                        for item in items:
                            if item.get('marketIndexItemCode') == 'FX_USDKRW':
                                cur = float(item.get('closePrice', '0').replace(',', ''))
                                rate = float(item.get('fluctuationsRatio', '0'))
                                sign = item.get('sign', {}).get('code', '2')
                                price_map[code] = {
                                    'price': f"{cur:,.2f}",
                                    'rate': f"{rate:+.2f}%",
                                    'is_up': sign in ['1', '2']
                                }
                                break
                else:
                    url = f"https://m.stock.naver.com/api/index/{target}/basic"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, context=get_ssl_context(), timeout=3) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        cur = float(data.get('closeNow', '0').replace(',', ''))
                        rate = float(data.get('fluctuationsRatio', '0'))
                        sign = data.get('sign', {}).get('code', '2')
                        price_map[code] = {
                            'price': f"{cur:,.2f}",
                            'rate': f"{rate:+.2f}%",
                            'is_up': sign in ['1', '2']
                        }
            except Exception:
                # 데이터 수신 실패 시 대체 안전값
                price_map[code] = {'price': '정보 없음', 'rate': '+0.00%', 'is_up': True}
                
    return price_map

@app.route('/')
def index():
    quotes = fetch_naver_market_data()
    return render_template('index.html', categories=MARKET_CATEGORIES, quotes=quotes)

if __name__ == '__main__':
    app.run(debug=True)
