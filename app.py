from flask import Flask, render_template

app = Flask(__name__)

MARKET_CATEGORIES = [
    {
        'title': '🇰🇷 국내 증시',
        'stocks': [
            {'code': 'kospi', 'name': '코스피', 'symbol': '^KS11'},
            {'code': 'kosdaq', 'name': '코스닥', 'symbol': '^KQ11'},
            {'code': 'kospi200', 'name': '코스피 200 선물', 'symbol': '^KS200'}
        ]
    },
    {
        'title': '🌍 해외 증시 및 변동성',
        'stocks': [
            {'code': 'dow', 'name': '다우존스', 'symbol': '^DJI'},
            {'code': 'nasdaq', 'name': '나스닥', 'symbol': '^IXIC'},
            {'code': 'sp500', 'name': 'S&P 500', 'symbol': '^GSPC'},
            {'code': 'phlx', 'name': '필라델피아 반도체', 'symbol': '^SOX'},
            {'code': 'vix', 'name': 'S&P 500 VIX', 'symbol': '^VIX'}
        ]
    },
    {
        'title': '🛢️ 원자재 및 환율',
        'stocks': [
            {'code': 'wti', 'name': 'WTI원유', 'symbol': 'CL=F'},
            {'code': 'gold', 'name': '금현물', 'symbol': 'GC=F'},
            {'code': 'usdkrw', 'name': '원/달러 환율', 'symbol': 'USDKRW=X'}
        ]
    }
]

@app.route('/')
def index():
    return render_template('index.html', categories=MARKET_CATEGORIES)

if __name__ == '__main__':
    app.run(debug=True)
