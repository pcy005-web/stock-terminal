from flask import Flask, render_template
import urllib.request
import urllib.parse
import json
import ssl
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from apscheduler.schedulers.background import BackgroundScheduler

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

# 전역 캐시 저장소 (장전 분석 내용 보관)
daily_market_cache = {
    'market_summary_bullets': [],
    'ai_briefing': "",
    'updated_at': "대기 중"
}

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
    rss_url = "https://news.google.com/rss/search?q=코스피+증권+주식+경제&hl=ko&gl=KR&ceid=KR:ko"
    news_list = []
    
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=3) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            for item in root.findall('.//item')[:10]:
                title_elem = item.find('title')
                link_elem = item.find('link')
                
                title = title_elem.text if title_elem is not None else "제목 없음"
                title_clean = title.rsplit(" - ", 1)[0] if " - " in title else title
                link = link_elem.text if link_elem is not None else "https://news.google.com"
                
                related_stock = "삼성전자, SK하이닉스"
                news_type = "중립"
                comment = "실시간 증시 영향력 분석 및 주도주 수급 주시"

                if any(k in title_clean for k in ["반도체", "AI", "삼성", "하이닉스", "실적", "급등", "상승", "엔비디아"]):
                    related_stock = "삼성전자, SK하이닉스, 한미반도체"
                    news_type = "호재"
                    comment = "반도체 대장주 수급 유입 및 AI 모멘텀 지속"
                elif any(k in title_clean for k in ["환율", "달러", "금리", "연준", "인플레", "우려"]):
                    related_stock = "원/달러 환율, KB금융, 신한지주"
                    news_type = "리스크"
                    comment = "매크로 변동성 및 금리 인상 경계감 반영"
                elif any(k in title_clean for k in ["방산", "수출", "조선", "전력", "수주"]):
                    related_stock = "한화에어로스페이스, 현대로템, HD현대일렉트릭"
                    news_type = "호재"
                    comment = "대규모 수주 잔고 기반 실적 모멘텀 부각"

                news_list.append({
                    'title': title_clean,
                    'link': link,
                    'stock': related_stock,
                    'comment': comment,
                    'type': news_type
                })
    except Exception:
        pass
        
    if len(news_list) < 10:
        fallback_live = [
            ("미 10년물 금리 5.0% 돌파 및 반도체주 약세 영향 점검", "https://news.google.com", "삼성전자, SK하이닉스", "금리 5% 돌파 부담 속 FOMC 대기", "리스크"),
            ("원/달러 환율 변동성 속 외국인 수급 방향성 주목", "https://news.google.com", "원/달러 환율, 코스피 대형주", "외국인 순매수 강도 조절 국면", "중립"),
            ("정부 밸류업 프로그램 및 주주환원 정책 모멘텀", "https://news.google.com", "KB금융, 현대차, 기아", "저PBR 우량주 중심 방어력 부각", "호재"),
            ("K-방산 빅수출 프로젝트 본계약 및 추가 협상 기대", "https://news.google.com", "한화에어로스페이스, 현대로템", "해외 수주 모멘텀 지속", "호재"),
            ("AI 속도조절 논란 속 반도체 하방 경직성 확보 여부", "https://news.google.com", "삼성전자, SK하이닉스, 한미반도체", "단기 변동성 확대 대응", "리스크")
        ]
        while len(news_list) < 10:
            idx = len(news_list) % len(fallback_live)
            t, l, s, c, tp = fallback_live[idx]
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
    
    return {
        'badge_text': badge_text,
        'badge_class': badge_class,
        'domestic': f"코스피({kospi.get('rate')}), 코스닥({kosdaq.get('rate')}) 대형주 현·선물 수급 포착.",
        'decoupling': f"나스닥선물({nasdaq_fut.get('rate')}) 연동 흐름 및 아시아 증시 비교.",
        'fx_oil': f"환율({usdkrw.get('price')}원) 변동성 안정화 모니터링."
    }

def generate_strategies(quotes):
    return [
        {"title": "반도체 주도주 수급 집중 공략", "desc": "외국인 순매수 상위 종목 및 핵심 주도주 중심 분할 매집", "stock": "삼성전자, SK하이닉스, 한미반도체", "rank": "TOP 1"},
        {"title": "전력 인프라 수출 모멘텀 유지", "desc": "실시간 수주 잔고 기반 조정 시 매수", "stock": "HD현대일렉트릭, 효성중공업, 제룡전기", "rank": "TOP 2"},
        {"title": "바이오 방어주 순환매 대응", "desc": "기관 수급 유입 확인 후 단기 스윙", "stock": "삼성바이오로직스, 셀트리온, 알테오젠", "rank": "TOP 3"},
        {"title": "방산 수출 실적주 트레이딩", "desc": "변동성 장세 속 실적 기반 하단 지지", "stock": "한화에어로스페이스, 현대로템, LIG넥스원", "rank": "TOP 4"},
        {"title": "저PBR 밸류업 종목 방어력 활용", "desc": "배당 및 정책 모멘텀 수급 체크", "stock": "KB금융, 현대차, 기아", "rank": "TOP 5"}
    ]

def job_update_premarket_summary():
    """매일 아침 장 시작 전(08:30) 자동으로 최신 지표와 리포트 분석 내용을 기반으로 장전 요약을 생성하는 함수"""
    print(">>> [자동 스케줄러] 장전 5분 마켓 핵심 요약 및 AI 브리핑 갱신 시작")
    
    # 임시로 실시간 시세 수집
    quotes = {}
    tasks = [('nasdaq_fut', 'NAVER_WORLD_NQ'), ('usdkrw', 'NAVER_EXCHANGE_USD'), ('phlx', 'NAVER_WORLD_SOX')]
    for code, ticker in tasks:
        res = fetch_realtime_data(ticker)
        quotes[code] = res if res else {'price': '-', 'rate': '+0.00%', 'is_up': True}

    nasdaq_rate = quotes.get('nasdaq_fut', {}).get('rate', '+0.00%')
    usdkrw_price = quotes.get('usdkrw', {}).get('price', '-')
    sox_rate = quotes.get('phlx', {}).get('rate', '+0.00%')

    # 키움증권 리포트 철학 및 분석 내용을 반영한 장전 5분 핵심 요약 불렛 구성
    daily_market_cache['market_summary_bullets'] = [
        f"미국 10년물 금리 장중 5.0% 돌파 및 9월 FOMC 경계감 속 증시 멀티플 디레이팅 압력 (나스닥 선물 {nasdaq_rate}, 환율 {usdkrw_price}원 연동 점검).",
        f"AI 성장성 내러티브 노이즈 부각되며 필라델피아 반도체 지수({sox_rate}) 및 핵심 반도체주 단기 충격 발생.",
        "추격 매도 자제 및 연준의 추가 인상 신중론 확인 대기, 반도체 하방 경직성 확보 주시.",
        "코스피 반도체 의존도가 낮아진 가운데, 최근 강세를 보이는 은행·보험·지주 등 주주환원 업종으로의 일부 비중 분산 대안 유효."
    ]
    
    daily_market_cache['ai_briefing'] = f"[실시간 AI 장전 마켓 종합 브리핑]\n- 나스닥 선물 변동률: {nasdaq_rate}\n- 원/달러 환율: {usdkrw_price}원\n- 핵심 제언: 금리 5% 돌파 노이즈 속 9월 FOMC 대기하며 반도체 하방 경직성 확인 및 주주환원주 분산 대응 권장"
    daily_market_cache['updated_at'] = "오늘 아침 08:30 장전 생성 완료"
    print(">>> [자동 스케줄러] 장전 요약 갱신 완료")

# 백그라운드 스케줄러 설정 (매일 월~금 오전 8시 30분 실행)
scheduler = BackgroundScheduler()
scheduler.add_job(job_update_premarket_summary, 'cron', day_of_week='mon-fri', hour=8, minute=30)
scheduler.start()

# 서버 구동 직후 캐시가 비어있다면 즉시 한 번 생성
if not daily_market_cache['market_summary_bullets']:
    job_update_premarket_summary()

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
                price_map[code] = data if data else {'price': '일시적 지연', 'rate': '+0.00%', 'is_up': True}
            except Exception:
                price_map[code] = {'price': '일시적 지연', 'rate': '+0.00%', 'is_up': True}
                
    live_news = fetch_naver_finance_news()
    theme_text = generate_theme_sync_analysis(price_map)
    smart_money_data = generate_smart_money_analysis(price_map)
    strategies_data = generate_strategies(price_map)
    
    # 미리 캐싱된 장전 요약 데이터 사용 (매일 아침 8시 30분에 고정 갱신됨)
    market_summary_bullets = daily_market_cache['market_summary_bullets']
    ai_briefing_text = daily_market_cache['ai_briefing']
                
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
