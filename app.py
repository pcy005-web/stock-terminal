from flask import Flask, render_template
import urllib.request
import urllib.parse
import json
import ssl
import xml.etree.ElementTree as ET
import re

app = Flask(__name__)

MARKET_CATEGORIES = [
    {
        'title': '🇰🇷 국내 증시',
        'stocks': [
            {'code': 'kospi', 'name': '코스피', 'ticker': 'NAVER_DOMESTIC_KOSPI'},
            {'code': 'kosdaq', 'name': '코스닥', 'ticker': 'NAVER_DOMESTIC_KOSDAQ'},
            {'code': 'kospi200', 'name': '코스피 200 선물', 'ticker': 'NAVER_DOMESTIC_FUT'}
        ]
    },
    {
        'title': '🌍 해외 증시 및 변동성',
        'stocks': [
            {'code': 'sp500', 'name': 'S&P 500', 'ticker': 'NAVER_WORLD_SPOT_SP'},
            {'code': 'dow', 'name': '다우존스', 'ticker': 'NAVER_WORLD_SPOT_DOW'},
            {'code': 'nasdaq', 'name': '나스닥', 'ticker': 'NAVER_WORLD_SPOT_NAS'},
            {'code': 'sp500_fut', 'name': 'S&P 500 선물', 'ticker': 'NAVER_WORLD_ES'},
            {'code': 'dow_fut', 'name': '다우존스 선물', 'ticker': 'NAVER_WORLD_YM'},
            {'code': 'nasdaq_fut', 'name': '나스닥 선물', 'ticker': 'NAVER_WORLD_NQ'},
            {'code': 'phlx', 'name': '필라델피아 반도체', 'ticker': 'NAVER_WORLD_SOX'},
            {'code': 'vix', 'name': 'S&P 500 VIX', 'ticker': 'NAVER_WORLD_VIX'}
        ]
    },
    {
        'title': '🛢️ 원자재 및 환율',
        'stocks': [
            {'code': 'wti', 'name': 'WTI원유', 'ticker': 'NAVER_ENERGY_WTI'},
            {'code': 'gold', 'name': '금현물', 'ticker': 'NAVER_METAL_GOLD'},
            {'code': 'usdkrw', 'name': '원/달러 환율', 'ticker': 'NAVER_EXCHANGE_USD'}
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://m.stock.naver.com/',
        'Accept': 'application/json, text/plain, */*'
    }

    try:
        api_url = None

        # 1. 국내 지수 및 선물 폴링 API
        if ticker.startswith('NAVER_DOMESTIC_'):
            target = ticker.replace('NAVER_DOMESTIC_', '')
            api_url = f"https://polling.finance.naver.com/api/realtime/domestic/index/{target}"

        # 2. 해외 증시 현물 폴링 API
        elif ticker.startswith('NAVER_WORLD_SPOT_'):
            spot_map = {'SP': '.INX', 'DOW': '.DJI', 'NAS': '.IXIC'}
            symbol = spot_map.get(ticker.replace('NAVER_WORLD_SPOT_', ''), '.IXIC')
            api_url = f"https://polling.finance.naver.com/api/realtime/worldstock/index/{symbol}"

        # 3. 해외 증시 선물 및 지표 폴링 API
        elif ticker.startswith('NAVER_WORLD_'):
            world_map = {
                'ES': 'EScv1', 
                'YM': 'YMcv1', 
                'NQ': 'NQcv1', 
                'SOX': '.SOX', 
                'VIX': '.VIX'
            }
            symbol = world_map.get(ticker.replace('NAVER_WORLD_', ''), 'NQcv1')
            if symbol.startswith('.'):
                api_url = f"https://polling.finance.naver.com/api/realtime/worldstock/index/{symbol}"
            else:
                api_url = f"https://polling.finance.naver.com/api/realtime/worldstock/futures/{symbol}"

        # 4. 원자재 및 원/달러 환율 API 설정
        elif ticker == 'NAVER_ENERGY_WTI':
            api_url = "https://api.stock.naver.com/marketindex/energy/CLcv1"
        elif ticker == 'NAVER_METAL_GOLD':
            api_url = "https://api.stock.naver.com/marketindex/metals/GCcv1"
        elif ticker == 'NAVER_EXCHANGE_USD':
            api_url = "https://stock.naver.com/api/stockSecurity/exchange-rates/v2/USD/charts/round?bankType=hana"

        if api_url:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=5) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                
                # 원/달러 환율 차트 API 응답 구조 전용 파싱
                if ticker == 'NAVER_EXCHANGE_USD':
                    # 리스트 형태의 시계열 데이터 중 가장 마지막(최신) 항목 추출
                    chart_data = []
                    if isinstance(res_json, list):
                        chart_data = res_json
                    elif isinstance(res_json, dict):
                        chart_data = res_json.get('result', []) or res_json.get('data', []) or res_json.get('chartRows', [])
                    
                    if chart_data and len(chart_data) > 0:
                        latest = chart_data[-1]  # 가장 최신 데이터
                        cur_price = latest.get('closePrice') or latest.get('price') or latest.get('dealBasRate')
                        prev_price = chart_data[-2].get('closePrice') if len(chart_data) > 1 else cur_price
                        
                        if cur_price is not None:
                            price_val = float(str(cur_price).replace(',', ''))
                            prev_val = float(str(prev_price).replace(',', '')) if prev_price else price_val
                            
                            rate_val = 0.0
                            if prev_val > 0:
                                rate_val = ((price_val - prev_val) / prev_val) * 100
                                
                            is_up = price_val >= prev_val
                            return {
                                'price': f"{price_val:,.2f}", 
                                'rate': f"{rate_val:+.2f}%", 
                                'is_up': is_up
                            }
                
                # 일반 단건 API 및 폴링 API 응답 파싱
                item = None
                if isinstance(res_json, dict):
                    if 'closePrice' in res_json or 'price' in res_json or 'nowValue' in res_json:
                        item = res_json
                    elif 'result' in res_json and isinstance(res_json['result'], dict):
                        item = res_json['result']
                    elif 'datas' in res_json and len(res_json['datas']) > 0:
                        item = res_json['datas'][0]
                
                if not item and isinstance(res_json, list) and len(res_json) > 0:
                    item = res_json[0]

                if item:
                    cur_price = item.get('closePrice') or item.get('nowValue') or item.get('price') or item.get('dealBasRate')
                    fluc_rate = item.get('fluctuationsRatio') or item.get('rate') or item.get('fluctuationRate') or 0
                    sign = str(item.get('sign', ''))
                    
                    if cur_price is not None:
                        price_val = float(str(cur_price).replace(',', ''))
                        rate_val = float(str(fluc_rate).replace('%', '').replace('+', '')) if fluc_rate else 0.0
                        is_up = not (sign in ['4', '5'] or str(fluc_rate).startswith('-'))
                        return {
                            'price': f"{price_val:,.2f}", 
                            'rate': f"{rate_val:+.2f}%", 
                            'is_up': is_up
                        }

    except Exception as e:
        print(f"통신 에러 발생 ({ticker}): {e}")
        pass
        
    return {'price': '0.00', 'rate': '+0.00%', 'is_up': True}

def fetch_naver_finance_news():
    rss_url = "https://news.naver.com/main/rss/rss1.id?mid=sec&sid1=101"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
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
    sox = quotes.get('phlx', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    direction = "상승 동조화" if sox.get('is_up', True) else "조정 압력 연동"
    return f"현재 필라델피아 반도체 지수 및 나스닥 선물({nasdaq_fut['rate']})의 실시간 변동 흐름에 따라 국내 반도체/IT 섹터가 밀접한 {direction} 국면에 진입해 있습니다."

def generate_smart_money_analysis(quotes):
    vix = quotes.get('vix', {'price': '15.00', 'rate': '+0.00%', 'is_up': True})
    usdkrw = quotes.get('usdkrw', {'price': '1,300', 'rate': '+0.00%', 'is_up': True})
    try:
        vix_val = float(vix['price'].replace(',', ''))
    except:
        vix_val = 15.0
    sentiment = "안정적 위험선호 (Risk-On)" if vix_val < 20 else "변동성 경계 (Risk-Off)"
    return f"현재 VIX 변동성 지수({vix['price']}) 및 원/달러 환율({usdkrw['price']}원) 기반 심리는 '{sentiment}' 상태입니다."

def generate_premarket_summary(quotes):
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    usdkrw = quotes.get('usdkrw', {'price': '-', 'rate': '+0.00%'})
    return f"나스닥 선물({nasdaq_fut['rate']}) 및 원/달러 환율({usdkrw['price']}원) 연동 결과, 장 초반 변동성에 대비한 모니터링이 필요합니다."

def generate_ai_comprehensive_briefing(quotes, news_list):
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '+0.00%'})
    usdkrw = quotes.get('usdkrw', {'price': '-', 'rate': '+0.00%'})
    top_news = news_list[0]['title'] if news_list else "경제 속보 모니터링 중"
    return f"[AI 종합 리포트]\n- 나스닥 선물: {nasdaq_fut['rate']}\n- 환율: {usdkrw['price']}원\n- 주요 이슈: {top_news}"

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
    ai_briefing_text = generate_ai_comprehensive_briefing(price_map, live_news)
                
    return render_template(
        'index.html', 
        categories=MARKET_CATEGORIES, 
        quotes=price_map,
        news_list=live_news,
        theme_summary=theme_text,
        smart_money_summary=smart_money_text,
        premarket_summary=premarket_text,
        ai_briefing=ai_briefing_text
    )

if __name__ == '__main__':
    app.run(debug=True)
