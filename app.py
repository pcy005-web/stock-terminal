from flask import Flask, render_template
import urllib.request
import json
import ssl

app = Flask(__name__)

# 그룹별 지표 정의 (함수가 아닌 일반 리스트 데이터)
GROUPS_DATA = [
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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    encoded_sym = symbol.replace('^', '%5E')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_sym}?interval=1d&range=2d"
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=3) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            
            chart = res_data.get('chart', {})
            result_list = chart.get('result')
            if not result_list:
                return {'price': '데이터 확인중', 'rate': '+0.00%', 'is_up': True}
                
            result = result_list[0]
            meta = result.get('meta', {})
            
            cur = meta.get('regularMarketPrice')
            prev = meta.get('chartPreviousClose', meta.get('previousClose'))
            
            if cur is None or prev is None:
                quotes = result.get('indicators', {}).get('quote', [{}])[0].get('close', [])
                valid = [q for q in quotes if q is not None]
                if len(valid) >= 2:
                    cur, prev = valid[-1], valid[-2]
                elif len(valid) == 1:
                    cur = prev = valid[-1]
                else:
                    return {'price': '데이터 확인중', 'rate': '+0.00%', 'is_up': True}

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
    try:
        market_data = {}
        for group in GROUPS_DATA:
            for item in group['items']:
                market_data[item['id']] = fetch_single_symbol(item['symbol'])
        
        # 템플릿에 명확한 변수명으로 전달
        return render_template('index.html', groups=GROUPS_DATA, data=market_data)
    except Exception as e:
        return f"Server Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
