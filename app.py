from flask import Flask, render_template
import yfinance as yf

app = Flask(__name__)

# 요청하신 그룹별 레이아웃 정의 (야후 파이낸스 정확한 심볼 매핑)
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

def fetch_market_data():
    data = {}
    all_symbols = [item['symbol'] for group in GROUPS for item in group['items']]
    
    try:
        # yfinance를 통해 일괄 조회
        tickers = yf.Tickers(" ".join(all_symbols))
        for group in GROUPS:
            for item in group['items']:
                sym = item['symbol']
                ast_id = item['id']
                try:
                    t = tickers.tickers[sym]
                    # 실시간 quote 정보 우선 활용 (인베스팅닷컴과 동일한 실시간 시세 반영)
                    fi = t.fast_info
                    cur = float(fi.get('last_price', 0))
                    prev = float(fi.get('previous_close', 0))
                    
                    # 만약 fast_info 값이 없을 경우 history 데이터로 보완
                    if not cur or not prev:
                        hist = t.history(period="2d")
                        if len(hist) >= 2:
                            cur = float(hist['Close'].iloc[-1])
                            prev = float(hist['Close'].iloc[-2])
                        elif len(hist) == 1:
                            cur = float(hist['Close'].iloc[-1])
                            prev = cur

                    change = cur - prev
                    rate = (change / prev) * 100 if prev else 0.0
                    
                    data[ast_id] = {
                        'price': f"{cur:,.2f}" if cur else "데이터 없음",
                        'rate': f"{rate:+.2f}%",
                        'is_up': change >= 0
                    }
                except Exception:
                    data[ast_id] = {'price': '데이터 확인중', 'rate': '+0.00%', 'is_up': True}
    except Exception:
        for group in GROUPS:
            for item in group['items']:
                data[item['id']] = {'price': '데이터 확인중', 'rate': '+0.00%', 'is_up': True}
                
    return data

@app.route('/')
def index():
    market_data = fetch_market_data()
    return render_template('index.html', groups=GROUPS, data=market_data)

if __name__ == '__main__':
    app.run(debug=True)
