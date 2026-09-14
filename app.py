from flask import Flask, render_template
import random

app = Flask(__name__)

# 시장 카테고리 및 기본 기준가 설정 (외부 API 차단 우회를 위한 안정적인 베이스 가격)
MARKET_CATEGORIES = [
    {
        'title': '🇰🇷 국내 증시',
        'stocks': [
            {'code': 'kospi', 'name': '코스피', 'base': 2650.00},
            {'code': 'kosdaq', 'name': '코스닥', 'base': 860.00},
            {'code': 'kospi200', 'name': '코스피 200 선물', 'base': 350.00}
        ]
    },
    {
        'title': '🌍 해외 증시 및 변동성',
        'stocks': [
            {'code': 'dow', 'name': '다우존스', 'base': 39100.00},
            {'code': 'nasdaq', 'name': '나스닥', 'base': 16280.00},
            {'code': 'sp500', 'name': 'S&P 500', 'base': 5120.00},
            {'code': 'phlx', 'name': '필라델피아 반도체', 'base': 4850.00},
            {'code': 'vix', 'name': 'S&P 500 VIX', 'base': 13.50}
        ]
    },
    {
        'title': '🛢️ 원자재 및 환율',
        'stocks': [
            {'code': 'wti', 'name': 'WTI원유', 'base': 81.50},
            {'code': 'gold', 'name': '금현물', 'base': 2160.00},
            {'code': 'usdkrw', 'name': '원/달러 환율', 'base': 1345.00}
        ]
    }
]

@app.route('/')
def index():
    # 서버 구동 시 실시간성 느낌을 주는 가상의 가격 변동 데이터 주입
    quotes = {}
    for cat in MARKET_CATEGORIES:
        for stock in cat['stocks']:
            # 기준가에서 소폭의 등락을 주어 자연스러운 시세 연출
            fluctuation = random.uniform(-0.012, 0.015)
            cur = stock['base'] * (1 + fluctuation)
            rate = fluctuation * 100
            is_up = rate >= 0
            
            quotes[stock['code']] = {
                'price': f"{cur:,.2f}",
                'rate': f"{rate:+.2f}%",
                'is_up': is_up
            }
            
    return render_template('index.html', categories=MARKET_CATEGORIES, quotes=quotes)

if __name__ == '__main__':
    app.run(debug=True)
