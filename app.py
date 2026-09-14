from flask import Flask, render_template
import urllib.request
import json
import ssl

app = Flask(__name__)

# 요청하신 그룹별 레이아웃 정의
GROUPS = [
    {
        'group_name': '🇰🇷 국내 증시',
        'items': [
            {'id': 'kospi', 'name': '코스피', 'symbol': '^KS11'},
            {'id': 'kosdaq', 'name': '코스닥', 'symbol': '^KQ11'},
            {'id': 'kospi200', 'name': '코스피 200 선물', 'symbol': '^KS200'}
        ]
    },
    {
        'group_name': '🌍 해외 증시 및 변동성',
        'items': [
            {'id': 'dow', 'name': '다우존스', 'symbol': '^DJI'},
            {'id': 'nasdaq', 'name': '나스닥', 'symbol': '^IXIC'},
            {'id': 'sp500', 'name': 'S&P 500', 'symbol': '^GSPC'},
            {'id': 'phlx', 'name': '필라델피아 반도체', 'symbol': '^SOX'},
            {'id': 'vix', 'name': 'S&P 500 VIX', 'symbol': '^VIX'}
        ]
    },
    {
        'group_name': '🛢️ 원자재 및 환율',
        'items': [
            {'id': 'wti', 'name': 'WTI원유', 'symbol': 'CL=F'},
            {'id': 'gold', 'name': '금현물', 'symbol': 'GC=F'},
            {'id': 'usdkrw', 'name': '원/달러 환율', 'symbol': 'USDKRW=X'}
        ]
    }
]

def fetch_single_symbol(symbol):
    """서버리스 환경에서 타임아웃과 크래시를 방지하기 위한 안전한 초고속 API 요청 함수"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    # 야후 파이낸스 차트 API를 활용해 가장 가볍고 빠르게 최근 2일 데이터 수집
    encoded_sym = symbol.replace('^', '%5E')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_sym}?interval=1d&range=2d"
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=2.5) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            result = res_data['chart']['result'][0]
            
            # 메타 데이터에서 최신 가격과 전일 종가 추출 (가장 정확하고 빠름)
            meta = result['meta']
            cur = meta.get('regularMarketPrice', 0)
            prev = meta.get('chartPreviousClose', meta.get('previousClose', 0))
            
            # 만약 메타에 값이 없다면 인디케이터 닫힘 가격 활용
            if not cur or not prev:
                quotes = result['indicators']['quote'][0]['close']
                valid = [q for q in quotes if q is not None]
                if len(valid) >= 2:
                    cur, prev = valid[-1], valid[-2]
                elif len(valid) == 1:
                    cur = prev = valid[-1]
            
            if not cur or not prev:
                return {'price': '데이터 없음', 'rate': '+0.00%', 'is_up': True}
                
            change = cur - prev
            rate = (change / prev) * 100 if prev else 0.0
            
            return {
                'price': f"{cur:,.2f}",
                'rate': f"{rate:+.2f}%",
                'is_up': change >= 0
            }
    except Exception:
        return {'price': '데이터 확인중', 'rate': '+0.00%', 'is_up': True}

@app.route('/')
def index():
    data = {}
    for group in GROUPS:
        for item in group['items']:
            data[item['id']] = fetch_single_symbol(item['symbol'])
            
    return render_template('index.html', groups=GROUPS, data=data)

if __name__ == '__main__':
    app.run(debug=True)
