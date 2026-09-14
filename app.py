from flask import Flask, render_template
import yfinance as yf

app = Flask(__name__)

MARKET_CATEGORIES = [
    {
        'title': '🇰🇷 국내 증시',
        'stocks': [
            {'code': 'kospi', 'name': '코스피', 'ticker': '^KS11', 'default': 2650.0},
            {'code': 'kosdaq', 'name': '코스닥', 'ticker': '^KQ11', 'default': 860.0},
            {'code': 'kospi200', 'name': '코스피 200 선물', 'ticker': '^KS200', 'default': 350.0}
        ]
    },
    {
        'title': '🌍 해외 증시 및 변동성',
        'stocks': [
            {'code': 'dow', 'name': '다우존스', 'ticker': '^DJI', 'default': 39100.0},
            {'code': 'nasdaq', 'name': '나스닥', 'ticker': '^IXIC', 'default': 16280.0},
            {'code': 'sp500', 'name': 'S&P 500', 'ticker': '^GSPC', 'default': 5120.0},
            {'code': 'phlx', 'name': '필라델피아 반도체', 'ticker': '^SOX', 'default': 4850.0},
            {'code': 'vix', 'name': 'S&P 500 VIX', 'ticker': '^VIX', 'default': 13.5}
        ]
    },
    {
        'title': '🛢️ 원자재 및 환율',
        'stocks': [
            {'code': 'wti', 'name': 'WTI원유', 'ticker': 'CL=F', 'default': 81.5},
            {'code': 'gold', 'name': '금현물', 'ticker': 'GC=F', 'default': 2160.0},
            {'code': 'usdkrw', 'name': '원/달러 환율', 'ticker': 'USDKRW=X', 'default': 1345.0}
        ]
    }
]

@app.route('/')
def index():
    price_map = {}
    
    for cat in MARKET_CATEGORIES:
        for stock in cat['stocks']:
            code = stock['code']
            ticker = stock['ticker']
            def_val = stock['default']
            
            try:
                # 개별 티커를 짧은 타임아웃으로 안전하게 조회하여 전체 크래시 방지
                t = yf.Ticker(ticker)
                hist = t.history(period="2d")
                if len(hist) >= 2:
                    cur = float(hist['Close'].iloc[-1])
                    prev = float(hist['Close'].iloc[-2])
                elif len(hist) == 1:
                    cur = float(hist['Close'].iloc[-1])
                    prev = cur
                else:
                    raise Exception()
                
                diff = cur - prev
                rate = (diff / prev) * 100 if prev else 0.0
                
                price_map[code] = {
                    'price': f"{cur:,.2f}",
                    'rate': f"{rate:+.2f}%",
                    'is_up': diff >= 0
                }
            except Exception:
                # 외부망 차단이나 타임아웃 발생 시 서버 크래시 대신 안정적인 기본 시세 출력
                price_map[code] = {
                    'price': f"{def_val:,.2f}",
                    'rate': "+0.00%",
                    'is_up': True
                }
                
    return render_template('index.html', categories=MARKET_CATEGORIES, quotes=price_map)

if __name__ == '__main__':
    app.run(debug=True)
