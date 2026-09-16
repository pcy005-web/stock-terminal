from flask import Flask, render_template
import urllib.request
import urllib.parse
import json
import ssl
import xml.etree.ElementTree as ET
import re
from datetime import datetime
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

def analyze_news_content(clean_title):
    """뉴스 제목 키워드를 기반으로 관련 종목, 리스크/호재 구분을 동적으로 생성합니다."""
    if any(k in clean_title for k in ["반도체", "AI", "삼성", "하이닉스", "엔비디아", "칩", "파운드리"]):
        return "삼성전자, SK하이닉스, 한미반도체", "호재", "글로벌 반도체 업종 모멘텀 및 IT 주도주 수급 유입 기대"
    elif any(k in clean_title for k in ["환율", "달러", "외국인", "하락", "불안", "우려", "금리", "연준", "급락", "경고"]):
        return "KB금융, 신한지주, 원/달러 환율", "리스크", "환율 및 금리 변동성 확대에 따른 국내 증시 수급 영향 점검"
    elif any(k in clean_title for k in ["방산", "수출", "한화", "현대", "조선", "수주", "원자력", "전력", "변압기"]):
        return "현대로템, HD현대일렉트릭, 한화에어로스페이스", "호재", "실적 기반 수주 모멘텀 지속 및 주도주 하단 지지력 강화"
    elif any(k in clean_title for k in ["바이오", "임상", "신약", "제약", "셀트리온", "FDA"]):
        return "삼성바이오로직스, 셀트리온, 알테오젠", "호재", "바이오 섹터 순환매 및 제약주 수급 개선 기대"
    elif any(k in clean_title for k in ["밸류업", "배당", "저PBR", "주주환원", "자사주"]):
        return "KB금융, 현대차, 기아", "호재", "주주환원 정책 모멘텀 및 방어주 중심 외인 수급 지지"
    else:
        return "코스피/코스닥 대형주", "중립", "지수 연동 흐름에 따른 실시간 개별 이슈 수급 대응 필요"

def fetch_naver_finance_news():
    """실시간 네이버 금융 주요 뉴스 및 한국경제 RSS를 동적으로 수집합니다."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    news_list = []
    seen_titles = set()

    # 1. 네이버 금융 메인 실시간 주요 뉴스 크롤링
    try:
        url = "https://finance.naver.com/news/mainnews.naver"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=3) as response:
            html = response.read().decode('euc-kr', errors='ignore')
            matches = re.findall(r'<d[dt] class="articleSubject">\s*<a href="([^"]+)">(.*?)</a>', html, re.DOTALL)
            
            for link, title in matches:
                clean_title = re.sub('<.*?>', '', title).strip()
                clean_title = clean_title.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                if clean_title and clean_title not in seen_titles:
                    seen_titles.add(clean_title)
                    full_link = f"https://finance.naver.com{link}" if link.startswith('/') else link
                    stock, news_type, comment = analyze_news_content(clean_title)
                    news_list.append({
                        'title': clean_title,
                        'link': full_link,
                        'stock': stock,
                        'comment': comment,
                        'type': news_type
                    })
                if len(news_list) >= 10:
                    break
    except Exception:
        pass

    # 2. 부족할 경우 한국경제 실시간 증권/경제 RSS 보충 수집
    if len(news_list) < 10:
        try:
            hk_url = "https://www.hankyung.com/feed/finance"
            req = urllib.request.Request(hk_url, headers=headers)
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=3) as response:
                xml_data = response.read().decode('utf-8', errors='ignore')
                root = ET.fromstring(xml_data)
                for item in root.findall('.//item'):
                    title_elem = item.find('title')
                    link_elem = item.find('link')
                    if title_elem is not None and title_elem.text:
                        clean_title = re.sub('<.*?>', '', title_elem.text).strip()
                        if clean_title not in seen_titles:
                            seen_titles.add(clean_title)
                            raw_link = link_elem.text.strip() if link_elem is not None and link_elem.text else f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(clean_title[:20])}"
                            stock, news_type, comment = analyze_news_content(clean_title)
                            news_list.append({
                                'title': clean_title,
                                'link': raw_link,
                                'stock': stock,
                                'comment': comment,
                                'type': news_type
                            })
                            if len(news_list) >= 10:
                                break
        except Exception:
            pass

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
    """실시간 해외/국내 지수 및 환율 동향을 반영하여 수급 기반 전략 TOP 5를 동적으로 편성합니다."""
    sox = quotes.get('phlx', {'rate': '+0.00%', 'is_up': True})
    usdkrw = quotes.get('usdkrw', {'price': '1,300', 'rate': '+0.00%', 'is_up': True})
    kospi = quotes.get('kospi', {'rate': '+0.00%', 'is_up': True})
    
    sox_up = sox.get('is_up', True)
    kospi_up = kospi.get('is_up', True)
    
    strategies = []
    
    # 1. 반도체 전략
    if sox_up:
        strategies.append({
            "title": f"필반 지수 강세({sox.get('rate')}) 연동 반도체 집중 공략",
            "desc": "외국인 순매수 유입 가능성이 높은 IT 주도주 중심 분할 매집",
            "stock": "삼성전자, SK하이닉스, 한미반도체",
            "score": 95
        })
    else:
        strategies.append({
            "title": f"반도체 섹터 단기 숨고르기({sox.get('rate')}) 대응 전략",
            "desc": "추격 매수 자제 및 눌림목 지지선 확인 후 하단 분할 대응",
            "stock": "삼성전자, SK하이닉스, 한미반도체",
            "score": 75
        })

    # 2. 전력/방산 수주주 전략
    strategies.append({
        "title": "전력 인프라 및 방산 수주 모멘텀 유지",
        "desc": "북미/유럽 수출 실적 가시화 및 수주 잔고 기반 조정 시 매수",
        "stock": "HD현대일렉트릭, 한화에어로스페이스, 현대로템",
        "score": 90 if sox_up else 92
    })

    # 3. 금융/방어주 전략
    if not kospi_up or '-' in str(usdkrw.get('rate', '')):
        strategies.append({
            "title": f"환율 변동성({usdkrw.get('price')}원) 대비 저PBR/금융주 방어",
            "desc": "지수 변동성 구간 외국인 방어적 수급 및 고배당 모멘텀 활용",
            "stock": "KB금융, 신한지주, 현대차",
            "score": 94
        })
    else:
        strategies.append({
            "title": "저PBR 밸류업 프로그램 방어력 활용",
            "desc": "배당 시즌 및 주주환원 정책 모멘텀 보유주 수급 지지",
            "stock": "KB금융, 현대차, 기아",
            "score": 82
        })

    # 4. 바이오 전략
    strategies.append({
        "title": "바이오 / CDMO 섹터 순환매 대응",
        "desc": "기관 수급 유입 및 글로벌 임상/수주 모멘텀 종목 단기 스윙",
        "stock": "삼성바이오로직스, 셀트리온, 알테오젠",
        "score": 85
    })

    # 5. 조선주 전략
    strategies.append({
        "title": "조선 및 친환경 선박 수주 랠리 가속",
        "desc": "선가 상승 및 수주 잔고 증가에 따른 실적 턴어라운드 종목 대응",
        "stock": "HD한국조선해양, HD현대중공업, 삼성중공업",
        "score": 88 if not sox_up else 80
    })

    # 점수 기준 실시간 정렬 후 TOP 1~5 할당
    strategies.sort(key=lambda x: x['score'], reverse=True)
    
    for idx, strat in enumerate(strategies):
        strat['rank'] = f"TOP {idx + 1}"
        del strat['score']
        
    return strategies

def generate_premarket_summary_bullets(quotes):
    current_hour = datetime.now().hour
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    usdkrw = quotes.get('usdkrw', {'price': '-', 'rate': '+0.00%'})
    sox = quotes.get('phlx', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    
    if current_hour >= 7:
        return [
            f"[오전 7시 이후 장전 개장 뷰] 미국 10년물 금리 장중 5.0% 상회 노이즈 및 9월 FOMC 대기 경계감 (나스닥 선물 {nasdaq_fut.get('rate')}, 환율 {usdkrw.get('price')}원 연동).",
            f"AI 반도체 쏠림 및 기술 발전 속도 노이즈로 필라델피아 반도체 지수({sox.get('rate')}) 변동성 확대 및 단기 충격 반영.",
            "지수 추격 매도를 자제하고, 연준의 추가 인상 신중론 확인 전까지 반도체 하방 경직성 및 지지선 테스트 집중 주시.",
            "코스피 반도체 의존도 완화 흐름 속 은행·보험·지주 등 주주환원 우위 업종으로의 분산 투자 대안 적극 유효."
        ]
    else:
        return [
            f"[야간/새벽 마감 요약] 전일 글로벌 증시 마감 지표 및 뉴욕 야간 선물 연동 점검 (나스닥 선물 {nasdaq_fut.get('rate')}, 환율 {usdkrw.get('price')}원).",
            f"미국 금리 및 반도체 섹터 동향({sox.get('rate')})에 따른 야간 변동성 누적 확인.",
            "오전 7시 이후 당일 장전 핵심 지표 확정 시 개장 전략 브리핑이 자동 갱신됩니다."
        ]

def generate_ai_comprehensive_briefing(quotes, news_list):
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '+0.00%'})
    usdkrw = quotes.get('usdkrw', {'price': '-', 'rate': '+0.00%'})
    top_news = news_list[0]['title'] if news_list else "경제 속보 모니터링 중"
    return f"[실시간 AI 마켓 종합 분석]\n- 나스닥 선물: {nasdaq_fut['rate']}\n- 환율: {usdkrw['price']}원\n- 주요 이슈: {top_news}\n- 종합 제언: 금리 5% 돌파 노이즈 속 9월 FOMC 대기하며 주도주 및 방어주 분산 대응 권장"

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
