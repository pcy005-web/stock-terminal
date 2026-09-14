from flask import Flask, render_template
import yfinance as yf

app = Flask(__name__)

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

def fetch_market_data():
    price_map = {}
    all_tickers = [stock['ticker'] for cat in MARKET_CATEGORIES for stock in cat['stocks']]
    
    try:
        # 야후 파이낸스 일괄 다운로드 (가장 안정적인 방식)
        data = yf.download(all_tickers, period="2d", progress=False, group_by='ticker', threads=True)
        
        for cat in MARKET_CATEGORIES:
            for stock in cat['stocks']:
                ticker = stock['ticker']
                code = stock['code']
                try:
                    df = data[ticker] if len(all_tickers) > 1 else data
                    if df is not None and not df.empty and 'Close' in df.columns:
                        closes = df['Close'].dropna()
                        if len(closes) >= 2:
                            cur = float(closes.iloc[-1])
                            prev = float(closes.iloc[-2])
                        elif len(closes) == 1:
                            cur = float(closes.iloc[-1])
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
                        continue
                except Exception:
                    pass
                
                # 예외 발생 시 대체 안전값
                price_map[code] = {'price': '정보 확인중', 'rate': '+0.00%', 'is_up': True}
    except Exception:
        for cat in MARKET_CATEGORIES:
            for stock in cat['stocks']:
                price_map[stock['code']] = {'price': '정보 확인중', 'rate': '+0.00%', 'is_up': True}
                
    return price_map

@app.route('/')
def index():
    quotes = fetch_market_data()
    return render_template('index.html', categories=MARKET_CATEGORIES, quotes=quotes)

if __name__ == '__main__':
    app.run(debug=True)
