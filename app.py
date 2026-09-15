from flask import Flask, render_template
import urllib.request
import json
import ssl
import xml.etree.ElementTree as ET
import re

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

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def fetch_realtime_data(ticker):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    encoded_ticker = ticker.replace('^', '%5E')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_ticker}?interval=1d&range=5d"
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=4) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            result_arr = res_json.get('chart', {}).get('result')
            
            if not result_arr:
                return None
                
            quotes = result_arr[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
            valid_closes = [c for c in quotes if c is not None]
            
            if not valid_closes:
                return None
            
            cur = valid_closes[-1]
            prev = valid_closes[-2] if len(valid_closes) >= 2 else cur
            
            diff = cur - prev
            pct = (diff / prev) * 100 if prev else 0.0
            
            return {
                'price': f"{cur:,.2f}",
                'rate': f"{pct:+.2f}%",
                'is_up': diff >= 0
            }
    except Exception:
        return None

def fetch_naver_finance_news():
    rss_url = "https://news.naver.com/main/rss/rss1.id?mid=sec&sid1=101"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    news_list = []
    try:
        req = urllib.request.Request(rss_url, headers=headers)
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=4) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            for item in items[:10]:
                title = item.find('title')
                link = item.find('link')
                if title is not None and title.text:
                    clean_title = re.sub('<.*?>', '', title.text)
                    # 링크 공백 제거 및 정제 (동일 페이지 이동 방지)
                    news_link = link.text.strip() if link is not None and link.text else "https://finance.naver.com"
                    news_list.append({
                        'title': clean_title,
                        'link': news_link
                    })
    except Exception:
        fallback_titles = [
            ("글로벌 AI 인프라 투자 확대에 따른 반도체 수급 점검", "https://finance.naver.com"),
            ("원/달러 환율 변동성 속 외국인 수급 동향 주시", "https://finance.naver.com"),
            ("정부 밸류업 프로그램 및 주주환원 정책 모멘텀 지속", "https://finance.naver.com")
        ]
        for t, l in fallback_titles:
            news_list.append({'title': t, 'link': l})
            
    return news_list

def generate_premarket_summary(quotes):
    nasdaq = quotes.get('nasdaq', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    sp500 = quotes.get('sp500', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    usdkrw = quotes.get('usdkrw', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    vix = quotes.get('vix', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    
    summary = f"미 증시 주요 지표 연동 결과, 나스닥({nasdaq['rate']}) 및 S&P 500({sp500['rate']})의 흐름이 국내 시초가에 직접적인 영향을 미치고 있습니다. 현재 원/달러 환율은 {usdkrw['price']}원({usdkrw['rate']})을 기록 중이며, 변동성 지수(VIX)는 {vix['price']}로 나타나 시장 경계감 속 종목별 차별화 장세가 예상됩니다."
    return summary

@app.route('/')
def index():
    price_map = {}
    for cat in MARKET_CATEGORIES:
        for stock in cat['stocks']:
            code = stock['code']
            ticker = stock['ticker']
            
            data = fetch_realtime_data(ticker)
            if data:
                price_map[code] = data
            else:
                price_map[code] = {'price': '일시적 지연', 'rate': '+0.00%', 'is_up': True}
                
    live_news = fetch_naver_finance_news()
    premarket_text = generate_premarket_summary(price_map)
                
    return render_template(
        'index.html', 
        categories=MARKET_CATEGORIES, 
        quotes=price_map,
        news_list=live_news,
        premarket_summary=premarket_text
    )

if __name__ == '__main__':
    app.run(debug=True)
