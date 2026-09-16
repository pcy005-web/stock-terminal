from flask import Flask, render_template
import urllib.request
import urllib.parse
import json
import ssl
import xml.etree.ElementTree as ET
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
                
                related_stock = "삼성전자 (005930), SK하이닉스 (000660)"
                news_type = "중립"
                comment = "실시간 지수 연동성 및 거래대금 상위 주도주 수급 모니터링"

                if any(k in title_clean for k in ["반도체", "AI", "삼성", "하이닉스", "실적", "급등", "상승", "엔비디아"]):
                    related_stock = "삼성전자, SK하이닉스, 한미반도체, 주성엔지니어링"
                    news_type = "호재"
                    comment = "반도체 대장주 및 소부장 핵심 주도주로 외국인·기관 수급 유입 집중"
                elif any(k in title_clean for k in ["환율", "달러", "하락", "금리", "연준", "인플레", "위기", "폭락", "우려"]):
                    related_stock = "원/달러 환율, KB금융, 신한지주, NAVER"
                    news_type = "리스크"
                    comment = "매크로 변동성 확대 및 외국인 수급 이탈 우려에 따른 방어적 대응"
                elif any(k in title_clean for k in ["방산", "수출", "조선", "원전", "전력", "수주"]):
                    related_stock = "한화에어로스페이스, 현대로템, HD현대일렉트릭, 두산에너빌리티"
                    news_type = "호재"
                    comment = "대규모 수주 잔고와 막대한 거래대금이 유입되는 시장 주도 섹터"
                elif any(k in title_clean for k in ["바이오", "제약", "임상", "신약"]):
                    related_stock = "삼성바이오로직스, 셀트리온, 알테오젠, HLB"
                    news_type = "호재"
                    comment = "기관 순매수세가 유입되는 바이오 대장주 중심 순환매 포착"

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
            ("글로벌 AI 인프라 투자 확대에 따른 반도체 소부장 수급 점검", "https://news.google.com", "삼성전자, SK하이닉스, 한미반도체", "AI 투자 가속화가 국내 반도체 주도주 수급에 직접적 영향", "호재"),
            ("원/달러 환율 변동성 지속 속 외국인 수급 방향성 주목", "https://news.google.com", "원/달러 환율, KB금융, 현대차", "환율 변동성 확대로 외국인 순매수 강도 조절 국면", "중립"),
            ("정부 밸류업 프로그램 및 주주환원 정책 모멘텀", "https://news.google.com", "KB금융, 신한지주, 현대차, 기아", "저PBR 및 고배당 우량주 중심 하방 지지력 강화", "호재"),
            ("K-방산 빅수출 프로젝트 본계약 및 추가 협상 기대", "https://news.google.com", "한화에어로스페이스, 현대로템, LIG넥스원", "해외 수주 모멘텀 지속으로 방산 섹터 트레이딩 유효", "호재"),
            ("미국 국채 금리 변동성에 따른 성장주 밸류에이션 점검", "https://news.google.com", "미국 국채금리, NAVER, 카카오", "금리 발작 우려에 따른 지수 단기 변동성 확대 리스크", "리스크"),
            ("조선업 슈퍼사이클 친환경 선박 수주 릴레이 지속", "https://news.google.com", "HD한국조선해양, HD현대중공업, 삼성중공업", "탄탄한 수주 잔고 기반 실적 턴어라운드 가시화", "호재"),
            ("바이오 CDMO 글로벌 빅파마 대규모 계약 체결", "https://news.google.com", "삼성바이오로직스, 셀트리온, 알테오젠", "실적 안정성과 성장성을 동시에 갖춘 주도주 부각", "호재"),
            ("전력기기 및 변압기 북미 수출 사상 최대 기록 경신", "https://news.google.com", "HD현대일렉트릭, 효성중공업, 제룡전기", "전력망 교체 슈퍼사이클 수혜 집중 및 주도주 급등", "호재"),
            ("국내 증시 대형주 거래대금 점진적 회복세 진입", "https://news.google.com", "코스피, 코스닥 시가총액 상위주", "시장 전체 유동성 유입 여부에 따른 순환매 대응 필요", "중립"),
            ("글로벌 원자재 공급망 차질 및 국제유가 변동성 주시", "https://news.google.com", "WTI원유, 금현물, 흥구석유", "원자재발 인플레이션 압력 재부각 가능성 대비", "리스크")
        ]
        while len(news_list) < 10:
            idx = len(news_list)
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
        {"title": "전력 인프라 수출 모멘텀 유입", "desc": "실시간 수주 잔고 기반 조정 시 매수", "stock": "HD현대일렉트릭, 효성중공업, 제룡전기", "rank": "TOP 2"},
        {"title": "바이오 방어주 순환매 대응", "desc": "기관 수급 유입 확인 후 단기 스윙", "stock": "삼성바이오로직스, 셀트리온, 알테오젠", "rank": "TOP 3"},
        {"title": "방산 수출 실적주 트레이딩", "desc": "변동성 장세 속 실적 기반 하단 지지", "stock": "한화에어로스페이스, 현대로템, LIG넥스원", "rank": "TOP 4"},
        {"title": "저PBR 밸류업 종목 방어력 활용", "desc": "배당 및 정책 모멘텀 수급 체크", "stock": "KB금융, 현대차, 기아", "rank": "TOP 5"}
    ]

def generate_premarket_summary_bullets(quotes, news_list):
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '-0.6%', 'is_up': False})
    usdkrw = quotes.get('usdkrw', {'price': '1,300', 'rate': '+0.00%', 'is_up': True})
    sox = quotes.get('phlx', {'price': '-', 'rate': '-3.4%', 'is_up': False})
    
    n_rate = nasdaq_fut.get('rate', '-0.6%')
    w_price = usdkrw.get('price', '1,300')
    s_rate = sox.get('rate', '-3.4%')
    top_news = news_list[0]['title'] if news_list else "글로벌 매크로 이슈 점검"
    
    bullet_1 = f"해외 증시 및 주요 지표: 미국 증시는 나스닥 선물({n_rate}) 및 환율({w_price}원) 흐름 속에서 매크로 변동성과 실시간 이슈('{top_news}')의 영향을 복합적으로 소화하는 모습입니다."
    bullet_2 = f"핵심 노이즈 및 시장 심리: 금리 및 정책 경계감 속에서 필라델피아 반도체 지수({s_rate}) 등 기술주 섹터가 단기 변동성 검증대에 놓였으며, 앞자리가 바뀐 지표들에 대한 심리적 경계감이 상존하고 있습니다."
    bullet_3 = "지수 하단 지지력 점검: 다만 증시가 장 초반의 낙폭을 상당 부분 만회하거나 하방 경직성을 시도한다는 점은, 시장이 극단적 우려보다는 연준의 속도 조절이나 기존 예상 범주 내의 충돌로 받아들이고 있음을 시사합니다."
    bullet_4 = "오늘의 대응 전략: 현 시점의 변동성을 추세 훼손 신호로 과도하게 해석하기보다는, 주요 지표 안정 여부를 확인하면서 무리한 추격 매도를 자제하고 은행·보험·주주환원주 및 주도주 눌림목으로 포트폴리오를 분산하는 대안이 유효합니다."
    
    return [bullet_1, bullet_2, bullet_3, bullet_4]

def generate_ai_comprehensive_briefing(quotes, news_list):
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '-0.6%'})
    usdkrw = quotes.get('usdkrw', {'price': '-', 'rate': '1,300'})
    top_news = news_list[0]['title'] if news_list else "글로벌 매크로 및 수급 모니터링"
    
    return (
        "[장전 마켓 인사이트 & AI 종합 브리핑 (매일 아침 자동 갱신)]\n"
        f"- 대외 실시간 지표: 나스닥 선물 {nasdaq_fut['rate']} | 원/달러 환율 {usdkrw['price']}원\n"
        f"- 핵심 뉴스 및 노이즈: {top_news}\n"
        "- 시황 분석 및 혜안: 글로벌 채권금리 및 기술주 노이즈로 인해 단기 변동성이 확대되고 있으나, 시장의 하방 지지력과 매물 소화 과정을 주시해야 합니다. 무리한 포지션 축소보다는 하방 경직성이 확보된 주도주 및 방어적 대안(주주환원/배당주) 중심의 유연한 포트폴리오 분산 전략을 권장합니다."
    )

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
    market_summary_bullets = generate_premarket_summary_bullets(price_map, live_news)
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

# 새로고침 없이 5초마다 실시간 지표를 갱신하기 위해 추가된 API 엔드포인트
@app.route('/api/quotes')
def api_quotes():
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
                
    return json.dumps(price_map, ensure_ascii=False)

if __name__ == '__main__':
    app.run(debug=True)
