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
    """네이버 증권 뉴스 RSS를 통해 실시간 헤드라인 10선 추출"""
    rss_url = "https://news.naver.com/main/rss/rss1.id?mid=sec&sid1=101" # 경제 뉴스 RSS
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    news_list = []
    try:
        req = urllib.request.Request(rss_url, headers=headers)
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=4) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            # RSS 아이템(기사) 파싱
            items = root.findall('.//item')
            for item in items[:10]: # 상위 10개만 추출
                title = item.find('title')
                link = item.find('link')
                if title is not None and title.text:
                    # HTML 태그 제거 및 특수문자 정리
                    clean_title = re.sub('<.*?>', '', title.text)
                    news_link = link.text if link is not None else "#"
                    news_list.append({
                        'title': clean_title,
                        'link': news_link
                    })
    except Exception:
        # 비상시 기본 대체 뉴스
        fallback_titles = [
            "글로벌 AI 인프라 투자 확대에 따른 반도체 수급 점검",
            "원/달러 환율 변동성 속 외국인 수급 동향 주시",
            "정부 밸류업 프로그램 및 주주환원 정책 모멘텀 지속",
            "K-방산 및 조선업 슈퍼사이클 수주 랠리 가시화",
            "연준 통화정책 기대감 및 국채 금리 움직임 분석"
        ]
        for t in fallback_titles:
            news_list.append({'title': t, 'link': '#'})
            
    return news_list

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
                
    # 실시간 뉴스 긁어오기
    live_news = fetch_naver_finance_news()
                
    return render_template(
        'index.html', 
        categories=MARKET_CATEGORIES, 
        quotes=price_map,
        news_list=live_news
    )

if __name__ == '__main__':
    app.run(debug=True)
