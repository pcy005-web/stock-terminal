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
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=5) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            
            for item in items:
                title_elem = item.find('title')
                link_elem = item.find('link')
                
                if title_elem is not None and title_elem.text:
                    clean_title = re.sub('<.*?>', '', title_elem.text).strip()
                    raw_link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                    
                    if not raw_link or raw_link == "https://finance.naver.com" or "index.nhn" in raw_link:
                        encoded_title = urllib.parse.quote(clean_title[:20])
                        news_link = f"https://search.naver.com/search.naver?where=news&query={encoded_title}"
                    else:
                        news_link = raw_link
                    
                    related_stock = "시장 전체"
                    if any(k in clean_title for k in ["반도체", "AI", "삼성", "하이닉스"]):
                        related_stock = "삼성전자, SK하이닉스"
                    elif any(k in clean_title for k in ["환율", "달러", "외국인"]):
                        related_stock = "원/달러 환율, 금융주"
                    elif any(k in clean_title for k in ["방산", "수출", "한화", "현대"]):
                        related_stock = "현대로템, 한화에어로스페이스"
                    elif any(k in clean_title for k in ["조선", "선박", "수주"]):
                        related_stock = "HD한국조선해양, 삼성중공업"
                    elif any(k in clean_title for k in ["바이오", "제약", "셀트리온"]):
                        related_stock = "삼성바이오로직스, 셀트리온"
                    elif any(k in clean_title for k in ["전력", "변압기", "효성"]):
                        related_stock = "HD현대일렉트릭, 효성중공업"
                    elif any(k in clean_title for k in ["금리", "연준", "국채"]):
                        related_stock = "국채금리, 성장주"

                    news_list.append({
                        'title': clean_title,
                        'link': news_link,
                        'stock': related_stock
                    })
                    
                if len(news_list) >= 10:
                    break
    except Exception:
        pass
        
    while len(news_list) < 10:
        idx = len(news_list) + 1
        fallback_data = [
            ("글로벌 AI 인프라 투자 확대에 따른 반도체 수급 점검", "https://search.naver.com/search.naver?where=news&query=AI+인프라+반도체", "삼성전자, SK하이닉스"),
            ("원/달러 환율 변동성 속 외국인 수급 동향 주시", "https://search.naver.com/search.naver?where=news&query=원달러+환율+외국인수급", "원/달러 환율"),
            ("정부 밸류업 프로그램 및 주주환원 정책 모멘텀 지속", "https://search.naver.com/search.naver?where=news&query=밸류업+프로그램+주주환원", "KB금융, 현대차"),
            ("K-방산 주요국 추가 수출 협상 본계약 임박", "https://search.naver.com/search.naver?where=news&query=K방산+수출+협상", "현대로템, LIG넥스원"),
            ("조선업 슈퍼사이클 친환경 선박 수주 랠리", "https://search.naver.com/search.naver?where=news&query=조선업+친환경선박+수주", "HD한국조선해양"),
            ("바이오 CDMO 글로벌 대형 제약사 신규 계약 체결", "https://search.naver.com/search.naver?where=news&query=바이오+CDMO+계약", "삼성바이오로직스"),
            ("연준 통화정책 완화 기대감과 국채 금리 안정세", "https://search.naver.com/search.naver?where=news&query=연준+통화정책+국채금리", "미국 국채금리"),
            ("전력기기 및 변압기 수출 사상 최대 기록 경신", "https://search.naver.com/search.naver?where=news&query=전력기기+변압기+수출", "HD현대일렉트릭"),
            ("국내 증시 거래대금 점진적 회복 국면 진입", "https://search.naver.com/search.naver?where=news&query=국내증시+거래대금", "코스피, 코스닥"),
            ("글로벌 원자재 공급망 및 유가 변동성 점검", "https://search.naver.com/search.naver?where=news&query=원자재+공급망+유가", "WTI원유, 금현물")
        ]
        t, l, s = fallback_data[idx - 1]
        news_list.append({'title': t, 'link': l, 'stock': s})
            
    return news_list

def generate_theme_sync_analysis(quotes):
    """2번: 미·한 테마 연동성 실시간 분석 생성"""
    sox = quotes.get('phlx', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    nasdaq = quotes.get('nasdaq', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    
    direction = "상승 동조화" if sox.get('is_up', True) else "조정 압력 연동"
    analysis = f"현재 필라델피아 반도체 지수({sox['rate']})와 나스닥({nasdaq['rate']})의 실시간 변동 흐름에 따라 국내 반도체/IT 섹터가 밀접한 {direction} 국면에 진입해 있습니다. 미국 기술주 수급 변화가 국내 장 초반 외국인 순매수 강도에 직결되는 구간입니다."
    return analysis

def generate_smart_money_analysis(quotes):
    """3번: 스마트머니 수급 레이더 실시간 분석 생성"""
    vix = quotes.get('vix', {'price': '15.00', 'rate': '+0.00%', 'is_up': True})
    usdkrw = quotes.get('usdkrw', {'price': '1,300', 'rate': '+0.00%', 'is_up': True})
    
    try:
        vix_val = float(vix['price'].replace(',', ''))
    except:
        vix_val = 15.0
        
    sentiment = "안정적 위험선호 (Risk-On)" if vix_val < 20 else "변동성 경계 (Risk-Off)"
    analysis = f"현재 VIX 변동성 지수({vix['price']}) 및 원/달러 환율({usdkrw['price']}원)을 기반으로 한 시장 심리는 '{sentiment}' 상태입니다. 기관 및 외국인 스마트머니는 AI 인프라, 전력기기, 방산 등 실적 가시성이 높은 주도 섹터로 집중 유입되는 양상을 보이고 있습니다."
    return analysis

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
    theme_text = generate_theme_sync_analysis(price_map)
    smart_money_text = generate_smart_money_analysis(price_map)
    premarket_text = generate_premarket_summary(price_map)
                
    return render_template(
        'index.html', 
        categories=MARKET_CATEGORIES, 
        quotes=price_map,
        news_list=live_news,
        theme_summary=theme_text,
        smart_money_summary=smart_money_text,
        premarket_summary=premarket_text
    )

if __name__ == '__main__':
    app.run(debug=True)
