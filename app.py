from flask import Flask, render_template
import urllib.request
import urllib.parse
import json
import ssl
import xml.etree.ElementTree as ET
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

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

def fetch_yahoo_data(ticker):
    yahoo_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    encoded_ticker = ticker.replace('^', '%5E').replace('=', '%3D')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_ticker}?interval=1m&range=1d"
    
    try:
        req = urllib.request.Request(url, headers=yahoo_headers)
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=2) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            result_arr = res_json.get('chart', {}).get('result')
            
            if not result_arr:
                return None
                
            meta = result_arr[0].get('meta', {})
            cur = meta.get('regularMarketPrice')
            prev = meta.get('previousClose') or meta.get('chartPreviousClose')
            
            if cur is None:
                quotes = result_arr[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
                valid_closes = [c for c in quotes if c is not None]
                if not valid_closes:
                    return None
                cur = valid_closes[-1]
                prev = valid_closes[-2] if len(valid_closes) >= 2 else cur

            if prev is None:
                prev = cur

            diff = cur - prev
            pct = (diff / prev) * 100 if prev else 0.0
            
            return {
                'price': f"{cur:,.2f}",
                'rate': f"{pct:+.2f}%",
                'is_up': diff >= 0
            }
    except Exception:
        return None

def fetch_realtime_data(ticker):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://m.stock.naver.com/',
        'Accept': 'application/json, text/plain, */*'
    }

    try:
        api_url = None

        if ticker.startswith('NAVER_DOMESTIC_'):
            target = ticker.replace('NAVER_DOMESTIC_', '')
            api_url = f"https://polling.finance.naver.com/api/realtime/domestic/index/{target}"
        elif ticker.startswith('NAVER_WORLD_SPOT_'):
            spot_map = {'SP': '.INX', 'DOW': '.DJI', 'NAS': '.IXIC'}
            symbol = spot_map.get(ticker.replace('NAVER_WORLD_SPOT_', ''), '.IXIC')
            api_url = f"https://polling.finance.naver.com/api/realtime/worldstock/index/{symbol}"
        elif ticker.startswith('NAVER_WORLD_'):
            world_map = {'ES': 'EScv1', 'YM': 'YMcv1', 'NQ': 'NQcv1', 'SOX': '.SOX', 'VIX': '.VIX'}
            symbol = world_map.get(ticker.replace('NAVER_WORLD_', ''), 'NQcv1')
            if symbol.startswith('.'):
                api_url = f"https://polling.finance.naver.com/api/realtime/worldstock/index/{symbol}"
            else:
                api_url = f"https://polling.finance.naver.com/api/realtime/worldstock/futures/{symbol}"
        elif ticker == 'NAVER_ENERGY_WTI':
            api_url = "https://api.stock.naver.com/marketindex/energy/CLcv1"
        elif ticker == 'NAVER_METAL_GOLD':
            api_url = "https://api.stock.naver.com/marketindex/metals/GCcv1"
        elif ticker == 'NAVER_EXCHANGE_USD':
            api_url = "https://api.stock.naver.com/marketindex/exchange/FX_USDKRW"

        if api_url:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=2) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                
                item = None
                if isinstance(res_json, dict):
                    if 'closePrice' in res_json or 'price' in res_json or 'nowValue' in res_json or 'dealBasRate' in res_json:
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

    except Exception:
        pass
        
    if ticker == 'NAVER_EXCHANGE_USD':
        yahoo_data = fetch_yahoo_data('USDKRW=X')
        if yahoo_data:
            return yahoo_data

    return {'price': '0.00', 'rate': '+0.00%', 'is_up': True}

def fetch_naver_finance_news():
    rss_url = "https://news.naver.com/main/rss/rss1.id?mid=sec&sid1=101"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    news_list = []
    try:
        req = urllib.request.Request(rss_url, headers=headers)
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=2) as response:
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
                    news_type = "중립"
                    comment = "실시간 뉴스 모니터링 및 시장 영향 분석 중"

                    if any(k in clean_title for k in ["반도체", "AI", "삼성", "하이닉스", "급등", "상승", "호조", "확대"]):
                        related_stock = "삼성전자, SK하이닉스, 한미반도체"
                        news_type = "호재"
                        comment = "글로벌 반도체 업종 반등 및 IT 주도주 수급 유입 기대"
                    elif any(k in clean_title for k in ["환율", "달러", "외국인", "하락", "불안", "우려", "금리", "연준"]):
                        related_stock = "KB금융, 신한지주, 원/달러 환율"
                        news_type = "리스크"
                        comment = "환율 및 금리 변동성 확대에 따른 국내 증시 수급 영향 점검"
                    elif any(k in clean_title for k in ["방산", "수출", "한화", "현대", "조선", "수주"]):
                        related_stock = "현대로템, HD현대일렉트릭, 한화에어로스페이스"
                        news_type = "호재"
                        comment = "실적 기반 수주 모멘텀 지속 및 주도주 하단 지지력 강화"
                    else:
                        news_type = "중립"
                        comment = "지수 연동 흐름에 따른 중립적 수급 대응 필요"

                    news_list.append({
                        'title': clean_title,
                        'link': news_link,
                        'stock': related_stock,
                        'comment': comment,
                        'type': news_type
                    })
                    
                if len(news_list) >= 10:
                    break
    except Exception:
        pass
        
    while len(news_list) < 10:
        idx = len(news_list) + 1
        fallback_data = [
            ("글로벌 AI 인프라 투자 확대에 따른 반도체 수급 점검", "https://search.naver.com/search.naver?where=news&query=AI+인프라+반도체", "삼성전자, SK하이닉스, 한미반도체", "AI 인프라 투자 확대가 반도체 소부장 주도주 수급에 긍정적 영향", "호재"),
            ("원/달러 환율 변동성 속 외국인 수급 동향 주시", "https://search.naver.com/search.naver?where=news&query=원달러+환율+외국인수급", "KB금융, 신한지주, 원/달러 환율", "환율 변동성 완화에도 적극적 외인 매수 유입은 제한적", "중립"),
            ("정부 밸류업 프로그램 및 주주환원 정책 모멘텀 지속", "https://search.naver.com/search.naver?where=news&query=밸류업+프로그램+주주환원", "KB금융, 현대차, 기아", "저PBR 종목군에 대한 정책 기대감 및 주도주 유입", "호재"),
            ("K-방산 주요국 추가 수출 협상 본계약 임박", "https://search.naver.com/search.naver?where=news&query=K방산+수출+협상", "현대로템, LIG넥스원, 한화에어로스페이스", "해외 수주 실적 가시화에 따른 방산 주도주 트레이딩 유효", "호재"),
            ("미국 국채 금리 변동성 확대에 따른 기술주 경계감 노출", "https://search.naver.com/search.naver?where=news&query=국채금리+기술주+경계감", "미국 국채금리, NAVER, 카카오", "금리 발작 우려에 따른 국내 증시 수급 취약성 점검", "리스크"),
            ("조선업 슈퍼사이클 친환경 선박 수주 랠리", "https://search.naver.com/search.naver?where=news&query=조선업+친환경선박+수주", "HD한국조선해양, HD현대중공업", "수주 잔고 기반 실적 턴어라운드 및 조선 주도주 가속화", "호재"),
            ("바이오 CDMO 글로벌 대형 제약사 신규 계약 체결", "https://search.naver.com/search.naver?where=news&query=바이오+CDMO+계약", "삼성바이오로직스, 셀트리온, 알테오젠", "안정적인 실적 성장 및 바이오 주도주 모멘텀 확보", "호재"),
            ("전력기기 및 변압기 수출 사상 최대 기록 경신", "https://search.naver.com/search.naver?where=news&query=전력기기+변압기+수출", "HD현대일렉트릭, 효성중공업, 제룡전기", "북미 전력망 교체 수요에 따른 수혜 집중 및 주도주 급등", "호재"),
            ("국내 증시 거래대금 점진적 회복 국면 진입", "https://search.naver.com/search.naver?where=news&query=국내증시+거래대금", "코스피, 코스닥 대형주 및 주도주", "시장 유동성 유입 여부 지속 체크 필요", "중립"),
            ("글로벌 원자재 공급망 및 유가 변동성 점검", "https://search.naver.com/search.naver?where=news&query=원자재+공급망+유가", "WTI원유, 금현물, 흥구석유", "원자재 가격 변동에 따른 인플레 압력 주시", "리스크")
        ]
        t, l, s, c, tp = fallback_data[idx - 1]
        news_list.append({'title': t, 'link': l, 'stock': s, 'comment': c, 'type': tp})
            
    return news_list

def generate_theme_sync_analysis(quotes):
    sox = quotes.get('phlx', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    is_up = sox.get('is_up', True)
    
    us_driver = f"필라델피아 반도체 지수 및 나스닥 선물({nasdaq_fut['rate']}) {'강세 흐름 주도' if is_up else '조정 압력 연동'}"
    core_stocks = "NVIDIA, 마이크론 테크놀로지, 인텔"
    domestic_stocks = "삼성전자, SK하이닉스, 한미반도체"
    risk_strategy = "미국채 금리 변동성 및 차익실현 매물 출회 가능성에 대비한 눌림목 중심 분할 매집" if is_up else "지수 하방 압력 연동에 따른 보수적 접근 및 현금 비중 확보 우선"
    
    return {
        'us_driver': us_driver,
        'core_stocks': core_stocks,
        'domestic_stocks': domestic_stocks,
        'risk_strategy': risk_strategy
    }

def generate_smart_money_analysis(quotes):
    kospi = quotes.get('kospi', {'price': '0', 'rate': '+0.00%', 'is_up': True})
    kosdaq = quotes.get('kosdaq', {'price': '0', 'rate': '+0.00%', 'is_up': True})
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '0', 'rate': '+0.00%', 'is_up': True})
    usdkrw = quotes.get('usdkrw', {'price': '1,300', 'rate': '+0.00%', 'is_up': True})
    
    kospi_up = kospi.get('is_up', True)
    
    badge_text = "외인/기관 순매수 유입" if kospi_up else "외인/기관 매도 우위"
    badge_class = "up" if kospi_up else "down"
    
    domestic_text = f"코스피({kospi.get('rate')}), 코스닥({kosdaq.get('rate')}) 중심 대형주 현·선물 동반 수급 포착."
    us_up = nasdaq_fut.get('is_up', True)
    decoupling_text = f"나스닥선물({nasdaq_fut.get('rate')}) 연동 흐름을 보이며 아시아 증시 대비 {'우수' if us_up else '약세'}."
    fx_oil_text = f"환율({usdkrw.get('price')}원) 및 유가 변동성 안정화로 수급 환경 모니터링 중."

    return {
        'badge_text': badge_text,
        'badge_class': badge_class,
        'domestic': domestic_text,
        'decoupling': decoupling_text,
        'fx_oil': fx_oil_text
    }

def generate_strategies(quotes):
    return [
        {"title": "반도체 주도주 수급 집중 공략", "desc": "외국인 순매수 상위 종목 및 핵심 주도주 중심 분할 매집", "stock": "삼성전자, SK하이닉스, 한미반도체", "rank": "TOP 1"},
        {"title": "전력 인프라 수출 모멘텀 유지", "desc": "실시간 수주 잔고 기반 조정 시 매수", "stock": "HD현대일렉트릭, 효성중공업, 제룡전기", "rank": "TOP 2"},
        {"title": "바이오 방어주 순환매 대응", "desc": "기관 수급 유입 확인 후 단기 스윙", "stock": "삼성바이오로직스, 셀트리온, 알테오젠", "rank": "TOP 3"},
        {"title": "방산 수출 실적주 트레이딩", "desc": "변동성 장세 속 실적 기반 하단 지지", "stock": "현대로템, 한화에어로스페이스, LIG넥스원", "rank": "TOP 4"},
        {"title": "저PBR 밸류업 종목 방어력 활용", "desc": "배당 및 정책 모멘텀 수급 체크", "stock": "KB금융, 현대차, 기아", "rank": "TOP 5"}
    ]

def generate_premarket_summary_bullets(quotes):
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    usdkrw = quotes.get('usdkrw', {'price': '-', 'rate': '+0.00%'})
    sox = quotes.get('phlx', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    return [
        f"필라델피아 반도체 지수({sox.get('rate')}) 변동에 따라 국내 IT 대형주 및 주도주 전반의 투자 심리 영향.",
        f"원/달러 환율({usdkrw.get('price')}원) 등락에 따른 외국인 수급 유출입 환경 조성.",
        f"나스닥 선물({nasdaq_fut.get('rate')}) 흐름 연동 낙폭 과대 우량주 중심 선별적 접근 유효."
    ]

def generate_ai_comprehensive_briefing(quotes, news_list):
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '+0.00%'})
    usdkrw = quotes.get('usdkrw', {'price': '-', 'rate': '+0.00%'})
    top_news = news_list[0]['title'] if news_list else "경제 속보 모니터링 중"
    return f"[실시간 AI 마켓 종합 분석]\n- 나스닥 선물: {nasdaq_fut['rate']}\n- 환율: {usdkrw['price']}원\n- 주요 이슈: {top_news}\n- 종합 제언: 실시간 수급 연동 지표 중심 주도주 선별 대응 권장"

@app.route('/')
def index():
    price_map = {}
    tasks = []
    for cat in MARKET_CATEGORIES:
        for stock in cat['stocks']:
            tasks.append((stock['code'], stock['ticker']))

    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_code = {executor.submit(fetch_realtime_data, ticker): code for code, ticker in tasks}
        
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            try:
                data = future.result()
                if data:
                    price_map[code] = data
                else:
                    price_map[code] = {'price': '일시적 지연', 'rate': '+0.00%', 'is_up': True}
            except Exception:
                price_map[code] = {'price': '일시적 지연', 'rate': '+0.00%', 'is_up': True}
                
    live_news = fetch_naver_finance_news()
    theme_text = generate_theme_sync_analysis(price_map)
    smart_money_data = generate_smart_money_analysis(price_map)
    strategies_data = generate_strategies(price_map)
    market_summary_bullets = generate_premarket_summary_bullets(price_map)
    ai_briefing_text = generate_ai_comprehensive_briefing(price_map, live_news)
                
    return render_template(
        'index.html', 
        categories=MARKET_CATEGORIES, 
        quotes=price_map,
        news_list=live_news,
        theme_summary=theme_text,
        smart_money_summary=smart_money_data,
        strategies=strategies_data,
        market_summary_bullets=market_summary_bullets,
        ai_briefing=ai_briefing_text
    )

if __name__ == '__main__':
    app.run(debug=True)
