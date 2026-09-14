from flask import Flask, render_template

app = Flask(__name__)

# 프론트엔드 자바스크립트가 직접 조회할 수 있도록 심볼 매핑 정보 전달
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

@app.route('/')
def index():
    return render_template('index.html', categories=MARKET_CATEGORIES)

if __name__ == '__main__':
    app.run(debug=True)
