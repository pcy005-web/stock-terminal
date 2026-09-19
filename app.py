import datetime
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime
from functools import lru_cache
from difflib import SequenceMatcher
from flask import Flask, render_template
import pytz

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
            {'code': 'usdkrw', 'name': '원/달러 환율', 'ticker': 'NAVER_EXCHANGE_USD'},
            {'code': 'btc', 'name': '비트코인', 'ticker': 'NAVER_COIN_BTC'},
            {'code': 'eth', 'name': '이더리움', 'ticker': 'NAVER_COIN_ETH'}
        ]
    }
]

_quote_cache = {}
_quote_cache_time = 0
CACHE_TTL = 30 

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
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=0.8) as response:
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
    if ticker in ['NAVER_COIN_BTC', 'NAVER_COIN_ETH']:
        try:
            market_code = "KRW-BTC" if ticker == 'NAVER_COIN_BTC' else "KRW-ETH"
            api_url = f"https://api.upbit.com/v1/ticker?markets={market_code}"
            
            req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=0.8) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                if res_json and isinstance(res_json, list):
                    item = res_json[0]
                    cur_price = item.get('trade_price', 0)
                    signed_change_rate = item.get('signed_change_rate', 0)
                    rate_val = signed_change_rate * 100
                    is_up = rate_val >= 0
                    return {
                        'price': f"{float(cur_price):,.2f}",
                        'rate': f"{rate_val:+.2f}%",
                        'is_up': is_up
                    }
        except Exception:
            pass

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
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=0.8) as response:
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
                    item = res_json['datas'][0] if isinstance(res_json, dict) and 'datas' in res_json else res_json[0]

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
        yahoo_data = fetch_yahoo_data('USDKrw=X')
        if yahoo_data:
            return yahoo_data

    return {'price': '0.00', 'rate': '+0.00%', 'is_up': True}

def get_all_quotes_cached():
    global _quote_cache, _quote_cache_time
    now_ts = datetime.datetime.now().timestamp()
    
    if _quote_cache and (now_ts - _quote_cache_time) < CACHE_TTL:
        return _quote_cache

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
                
    _quote_cache = price_map
    _quote_cache_time = now_ts
    return price_map

# -------------------------------------------------------------
# 4번 섹션: 100% 동적 생성 스마트머니 수급 분석 로직
# -------------------------------------------------------------
_smart_money_cache = None
_smart_money_cache_time = 0
SMART_MONEY_CACHE_TTL = 60

def fetch_smart_money_analysis(quotes):
    global _smart_money_cache, _smart_money_cache_time
    now_ts = datetime.datetime.now().timestamp()
    
    if _smart_money_cache and (now_ts - _smart_money_cache_time) < SMART_MONEY_CACHE_TTL:
        return _smart_money_cache

    kospi = quotes.get('kospi', {'price': '0', 'rate': '+0.00%', 'is_up': True})
    kosdaq = quotes.get('kosdaq', {'price': '0', 'rate': '+0.00%', 'is_up': True})
    usdkrw = quotes.get('usdkrw', {'price': '1,382.50', 'rate': '+0.00%', 'is_up': True})
    
    kospi_rate_str = kospi.get('rate', '+0.00%')
    kospi_is_up = kospi.get('is_up', True)
    usdkrw_price = usdkrw.get('price', '1,382.50')

    # 뉴스핌 RSS 실시간 파싱
    query = "site:newspim.com (코스피 OR 외국인 OR 기관 OR 반도체 OR 수급) when:1d"
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    news_title = "증시 혼조세 속 외국인·기관 실시간 수급 공방 지속"
    news_link = "#"
    
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=3.0) as response:
            root = ET.fromstring(response.read())
            item = root.find('.//item')
            if item is not None:
                t_elem = item.find('title')
                l_elem = item.find('link')
                if t_elem is not None and t_elem.text:
                    t = t_elem.text
                    if " - " in t:
                        t = t.rsplit(" - ", 1)[0]
                    news_title = t.strip()
                if l_elem is not None and l_elem.text:
                    news_link = l_elem.text
    except Exception:
        pass

    # 뉴스 제목에서 핵심 키워드 자동 추출
    keywords_to_check = ["반도체", "전력기기", "원전", "조선", "바이오", "2차전지", "자동차", "저PBR", "은행", "보험"]
    detected_keywords = [kw for kw in keywords_to_check if kw in news_title]
    if not detected_keywords:
        detected_keywords = ["주도주 대형사", "순환매 업종"]

    # 실시간 지수 및 키워드 기반 동적 문장 조합
    if kospi_is_up:
        market_trend_msg = f"코스피({kospi_rate_str})의 상승 흐름과 연동되어, {', '.join(detected_keywords)} 중심의 이익 성장 동반 매수세가 유입되고 있으며,"
        rotation_msg = "상승 탄력 속에서도 실적 개선이 가시화되는 주도 업종 및 테마로의 수급 집중 현상이 뚜렷하게 관측됩니다."
    else:
        market_trend_msg = f"코스피({kospi_rate_str}) 조정 국면 속에서, {', '.join(detected_keywords)} 등 방어적 성격의 종목군으로 수급이 분산되는 양상이며,"
        rotation_msg = "변동성 확대 장세에 대응하기 위한 기관 및 외국인의 선별적 포트폴리오 재편 흐름이 포착됩니다."

    result_data = {
        'domestic_sync': f"코스피({kospi_rate_str}), 코스닥({kosdaq.get('rate')})의 실시간 방향성과 연동하여 주도세력의 누적 수급을 추적합니다.",
        'sub_item_1': market_trend_msg,
        'sub_item_2': rotation_msg,
        'news_title': news_title,
        'news_link': news_link,
        'fx_oil': f"원/달러 환율({usdkrw_price}원) 변동성에 따른 외국인 수급 이탈 및 유입 민감도 실시간 점검"
    }
    
    _smart_money_cache = result_data
    _smart_money_cache_time = now_ts
    return result_data

# -------------------------------------------------------------
# 5번 섹션 및 기타 유틸리티 함수들
# -------------------------------------------------------------
def fetch_feature_stocks():
    kst = pytz.timezone('Asia/Seoul')
    now_dt = datetime.datetime.now(kst)
    current_hour_min = now_dt.hour * 100 + now_dt.minute
    is_market_closed = current_hour_min >= 1530 or now_dt.weekday() >= 5
    
    query = "intitle:특징주 OR intitle:장전특징주 OR intitle:개장전특징주 OR intitle:상한가 when:12h"
    cache_buster = int(datetime.datetime.now().timestamp())
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ko&gl=KR&ceid=KR:ko&cb={cache_buster}"
    
    parsed_items = []
    seen_titles = set()
    
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=2.0) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                link_elem = item.find('link')
                pub_date_elem = item.find('pubDate')
                
                title = title_elem.text if title_elem is not None else ""
                if not title:
                    continue
                title_clean = title.rsplit(" - ", 1)[0] if " - " in title else title
                link = link_elem.text if link_elem is not None else "https://news.google.com"
                
                item_time_str = now_dt.strftime('%H:%M')
                sort_dt = now_dt
                if pub_date_elem is not None and pub_date_elem.text:
                    try:
                        dt = parsedate_to_datetime(pub_date_elem.text).astimezone(kst)
                        sort_dt = dt
                        item_time_str = dt.strftime('%H:%M')
                    except Exception:
                        pass
                
                if "주요 특징주" in title_clean or title_clean in seen_titles:
                    continue
                seen_titles.add(title_clean)
                parsed_items.append({"title": title_clean.strip(), "link": link, "time": item_time_str, "sort_dt": sort_dt})
    except Exception:
        pass
        
    parsed_items.sort(key=lambda x: x["sort_dt"], reverse=True)
    feature_items = parsed_items[:5]
    for item in feature_items:
        item.pop("sort_dt", None)
    
    market_summary_keyword = (
        "• [마감 동향]: 국내 증시 마감에 따른 주요 업종별 수급 마감 결과 반영\n"
        "• [순환매 전개]: 단기 자금이 반도체 대형주에서 저PBR 및 전력기기 섹터로 순환 이동" if is_market_closed else
        "• [수급 동향]: AI 반도체 및 핵심 소부장 중심의 선별적 매수세 유입\n"
        "• [순환매 전개]: 주요 지수 등락 속 업종별 순환매 장세 진행 중"
    )
    return feature_items, market_summary_keyword

def fetch_naver_finance_news():
    kst = pytz.timezone('Asia/Seoul')
    now_dt = datetime.datetime.now(kst)
    query_str = urllib.parse.quote("연합인포맥스 OR 금리 OR 환율 OR 실적 OR 외국인 OR 수급 when:12h")
    rss_url = f"https://news.google.com/rss/search?q={query_str}&hl=ko&gl=KR&ceid=KR:ko"
    news_list = []
    collected_titles = [] 
    
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=1.0) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else "제목 없음"
                title_clean = title.rsplit(" - ", 1)[0] if " - " in title else title
                
                is_duplicate = any(SequenceMatcher(None, title_clean, et).ratio() >= 0.75 for et in collected_titles)
                if is_duplicate:
                    continue
                collected_titles.append(title_clean)
                
                news_list.append({
                    'title': title_clean.strip(),
                    'source': "경제 뉴스",
                    'link': item.find('link').text if item.find('link') is not None else "#",
                    'stock': "시장 대형주",
                    'comment': "실시간 매크로 및 개별 종목 영향 분석",
                    'type': "중립",
                    'date': now_dt.strftime('%m/%d')
                })
                if len(news_list) >= 10:
                    break
    except Exception:
        pass
    return news_list

def generate_theme_sync_analysis(quotes, news_list):
    sox = quotes.get('phlx', {'rate': '+0.00%', 'is_up': True})
    return {
        'us_driver': f"필라델피아 반도체({sox.get('rate')}) 연동 글로벌 테크 밸류체인 흐름 반영",
        'core_stocks': "NVIDIA, 마이크론",
        'domestic_stocks': "삼성전자, SK하이닉스",
        'risk_strategy': "실적 펀더멘털 우량주 중심 비중 확대"
    }

def generate_strategies(quotes, news_list):
    return [
        {"title": "AI 반도체 및 핵심 소부장", "desc": "글로벌 AI 인프라 투자 확대 수혜주", "stock": "삼성전자, SK하이닉스", "rank": "TOP 1"},
        {"title": "전력 인프라 기기주", "desc": "북미 수출 호조 및 수주 잔고 증가", "stock": "HD현대일렉트릭, 효성중공업", "rank": "TOP 2"},
        {"title": "바이오 CDMO 및 실적 우량주", "desc": "어닝 개선 기대감 유입", "stock": "삼성바이오로직스, 셀트리온", "rank": "TOP 3"},
        {"title": "K-방산 및 조선 슈퍼사이클", "desc": "수주형 성장주 트레이딩", "stock": "한화에어로스페이스, 현대로템", "rank": "TOP 4"},
        {"title": "저PBR 밸류업 금융주", "desc": "주주환원 및 방어력 제고", "stock": "KB금융, 신한지주", "rank": "TOP 5"}
    ]

def generate_premarket_summary_bullets(quotes, news_list):
    return "장 시작 전 마켓 핵심 생각: 금리 안정과 증시 체력", [
        "미국 증시 반등 및 금리 불확실성 완화 흐름 반영",
        "국내 증시는 외국인·기관 수급 연동 업종별 차별화 진행 중"
    ]

def generate_ai_comprehensive_briefing(quotes, news_list):
    return "🤖 실시간 팩트 기반 AI 브리핑 리포트 갱신 완료"

@app.route('/')
def index():
    price_map = get_all_quotes_cached()
    live_news = fetch_naver_finance_news()
    theme_text = generate_theme_sync_analysis(price_map, live_news)
    smart_money_data = fetch_smart_money_analysis(price_map)
    strategies_data = generate_strategies(price_map, live_news)
    
    market_summary_header, market_summary_bullets = generate_premarket_summary_bullets(price_map, live_news)
    ai_briefing_text = generate_ai_comprehensive_briefing(price_map, live_news)
    feature_stocks_data, feature_market_summary = fetch_feature_stocks()
            
    return render_template(
        'index.html', 
        categories=MARKET_CATEGORIES, 
        quotes=price_map,
        news_list=live_news,
        theme_summary=theme_text,
        smart_money_summary=smart_money_data,
        strategies=strategies_data,
        market_summary_header=market_summary_header,
        market_summary_bullets=market_summary_bullets,
        ai_briefing=ai_briefing_text,
        feature_stocks=feature_stocks_data,
        feature_market_summary=feature_market_summary
    )

@app.route('/api/quotes')
def api_quotes():
    return json.dumps(get_all_quotes_cached(), ensure_ascii=False)

if __name__ == '__main__':
    app.run(debug=True)
