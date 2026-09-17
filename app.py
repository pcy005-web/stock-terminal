from flask import Flask, render_template, jsonify
import urllib.request
import urllib.parse
import json
import ssl
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import re
import pytz
from email.utils import parsedate_to_datetime

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

# [종목-테마 동적 매핑 데이터베이스] 
STOCK_THEME_MAPPING = {
    "진양화학": "화학/소재",
    "비츠로테크": "우주항공/방산",
    "나라스페이스": "우주항공/방산",
    "나라스페이스테크놀로지": "우주항공/방산",
    "앤씨앤": "AI 반도체",
    "인텔": "AI 반도체",
    "마이크론": "AI 반도체",
    "현대차": "자동차",
    "제일엠에스": "증시시황",
    "삼성전자": "AI 반도체",
    "SK하이닉스": "AI 반도체",
    "한화시스템": "방산",
    "한화에어로스페이스": "방산",
    "미투온": "게임/콘텐츠"
}

def get_dynamic_theme(title, stock_name=""):
    """뉴스 타이틀과 종목명을 기반으로 가장 정확한 테마를 동적 매칭"""
    clean_stock = stock_name.replace("(핵심종목)", "").strip()
    if clean_stock in STOCK_THEME_MAPPING:
        return STOCK_THEME_MAPPING[clean_stock]
        
    for stock_key, theme_name in STOCK_THEME_MAPPING.items():
        if stock_key in title:
            return theme_name
            
    if any(k in title for k in ["화학", "소재", "석유"]): return "화학/소재"
    if any(k in title for k in ["우주", "방산", "위성", "항공", "비츠로"]): return "우주항공/방산"
    if any(k in title for k in ["반도체", "인텔", "마이크론", "AI"]): return "AI 반도체"
    if any(k in title for k in ["자동차", "현대차", "모빌리티"]): return "자동차"
    if any(k in title for k in ["뉴욕", "증시", "나스닥", "S&P", "개장"]): return "글로벌증시"
    if any(k in title for k in ["게임", "콘텐츠", "웹툰"]): return "게임/콘텐츠"
    
    return "시장주도주"

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
            if not result_arr: return None
                
            meta = result_arr[0].get('meta', {})
            cur = meta.get('regularMarketPrice')
            prev = meta.get('previousClose') or meta.get('chartPreviousClose')
            
            if cur is None:
                quotes = result_arr[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
                valid_closes = [c for c in quotes if c is not None]
                if not valid_closes: return None
                cur = valid_closes[-1]
                prev = valid_closes[-2] if len(valid_closes) >= 2 else cur

            if prev is None: prev = cur
            diff = cur - prev
            pct = (diff / prev) * 100 if prev else 0.0
            
            return {'price': f"{cur:,.2f}", 'rate': f"{pct:+.2f}%", 'is_up': diff >= 0}
    except Exception:
        return None

def fetch_realtime_data(ticker):
    if ticker in ['NAVER_COIN_BTC', 'NAVER_COIN_ETH']:
        try:
            market_code = "KRW-BTC" if ticker == 'NAVER_COIN_BTC' else "KRW-ETH"
            api_url = f"https://api.upbit.com/v1/ticker?markets={market_code}"
            req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=2) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                if res_json and isinstance(res_json, list):
                    item = res_json[0]
                    cur_price = item.get('trade_price', 0)
                    rate_val = item.get('signed_change_rate', 0) * 100
                    return {'price': f"{float(cur_price):,.2f}", 'rate': f"{rate_val:+.2f}%", 'is_up': rate_val >= 0}
        except Exception:
            pass

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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
                item = res_json.get('result') if isinstance(res_json, dict) and 'result' in res_json else res_json
                if isinstance(item, list) and len(item) > 0: item = item[0]
                
                if item and isinstance(item, dict):
                    cur_price = item.get('closePrice') or item.get('nowValue') or item.get('price') or item.get('dealBasRate')
                    fluc_rate = item.get('fluctuationsRatio') or item.get('rate') or item.get('fluctuationRate') or 0
                    sign = str(item.get('sign', ''))
                    
                    if cur_price is not None:
                        price_val = float(str(cur_price).replace(',', ''))
                        rate_val = float(str(fluc_rate).replace('%', '').replace('+', '')) if fluc_rate else 0.0
                        is_up = not (sign in ['4', '5'] or str(fluc_rate).startswith('-'))
                        return {'price': f"{price_val:,.2f}", 'rate': f"{rate_val:+.2f}%", 'is_up': is_up}
    except Exception:
        pass
        
    if ticker == 'NAVER_EXCHANGE_USD':
        yahoo_data = fetch_yahoo_data('USDKrw=X')
        if yahoo_data: return yahoo_data

    return {'price': '0.00', 'rate': '+0.00%', 'is_up': True}

def fetch_feature_stocks():
    kst = pytz.timezone('Asia/Seoul')
    now_dt = datetime.datetime.now(kst)
    current_hour_min = now_dt.hour * 100 + now_dt.minute
    is_market_closed = current_hour_min >= 1530 or now_dt.weekday() >= 5
    
    query = "intitle:특징주 OR intitle:장전특징주 OR intitle:개장전특징주 OR intitle:상한가 when:6h"
    cache_buster = int(datetime.datetime.now().timestamp() / 60)
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ko&gl=KR&ceid=KR:ko&cb={cache_buster}"
    
    parsed_items = []
    seen_titles = set()
    known_companies = list(STOCK_THEME_MAPPING.keys())
    
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=4) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else ""
                title_clean = title.rsplit(" - ", 1)[0] if " - " in title else title
                link = item.find('link').text if item.find('link') is not None else "https://news.google.com"
                
                if not any(kw in title_clean for kw in ["특징주", "장전특징주", "개장전특징주", "상한가"]): continue
                if "주요 특징주" in title_clean or title_clean in seen_titles: continue
                
                seen_titles.add(title_clean)
                pub_dt = now_dt
                pub_date_elem = item.find('pubDate')
                if pub_date_elem is not None and pub_date_elem.text:
                    try:
                        pub_dt = parsedate_to_datetime(pub_date_elem.text)
                        if pub_dt.tzinfo is None: pub_dt = pytz.utc.localize(pub_dt)
                        pub_dt = pub_dt.astimezone(kst)
                    except Exception: pass
                
                if (now_dt - pub_dt).total_seconds() / 3600 > 6: continue
                
                raw_stock_name = next((comp for comp in known_companies if comp in title_clean), "")
                if not raw_stock_name:
                    quoted_matches = re.findall(r"'([^']+)'", title_clean)
                    exclude_words = ["특징주", "급등", "상한가", "하락", "코스피", "코스닥", "장중"]
                    for qm in quoted_matches:
                        if len(qm) <= 12 and not any(ew in qm for ew in exclude_words):
                            raw_stock_name = qm
                            break
                if not raw_stock_name: raw_stock_name = "시장주도주"
                
                theme_result = get_dynamic_theme(title_clean, raw_stock_name)
                formatted_title = f"[{pub_dt.strftime('%H:%M')}] {title_clean}"
                
                parsed_items.append({
                    "stock": raw_stock_name,
                    "theme": theme_result,
                    "title": formatted_title,
                    "link": link,
                    "timestamp": pub_dt
                })
    except Exception:
        pass
        
    parsed_items = sorted(parsed_items, key=lambda x: x['timestamp'], reverse=True)
    feature_items = parsed_items[:5]
    
    if len(feature_items) < 5:
        fallbacks = [
            {"stock": "진양화학", "theme": "화학/소재", "title": "[21:30] [상한가 종목] 진양화학-비츠로테크 이어 나라스페이스테크놀로지-앤씨앤 등 마감", "link": "https://news.google.com"}
        ]
        for fb in fallbacks:
            if len(feature_items) < 5: feature_items.append(fb)
            
    feature_market_summary = (
        "• [마감 동향]: 국내 증시 마감에 따른 주요 업종별 수급 마감 결과 반영\n"
        "• [주요 특징]: 주도 섹터별 마감 가격 제안 및 시간외 단일가 동향 모니터링 체제 전환\n"
        "• [향후 전망]: 글로벌 매크로 지표 및 야간 선물 시장 연동성 검토"
    ) if is_market_closed else (
        "• [수급 동향]: AI 반도체 및 핵심 소부장 중심의 선별적 매수세 유입\n"
        "• [순환매 전개]: 전력기기·바이오·방산 섹터 간 빠른 순환매 장세 포착\n"
        "• [시장 분위기]: 주요 지수 등락 속 종목별 차별화 장세 진행 중"
    )
    
    return feature_items, feature_market_summary

def fetch_naver_finance_news():
    query_str = urllib.parse.quote("코스피 주식 증권 실적 공시 when:6h")
    rss_url = f"https://news.google.com/rss/search?q={query_str}&hl=ko&gl=KR&ceid=KR:ko"
    news_list, seen_titles = [], set()
    
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=4) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else ""
                title_clean = title.rsplit(" - ", 1)[0] if " - " in title else title
                if title_clean in seen_titles: continue
                seen_titles.add(title_clean)
                
                news_list.append({
                    'title': title_clean,
                    'link': item.find('link').text if item.find('link') is not None else "https://news.google.com",
                    'stock': "코스피 대형주",
                    'comment': "펀더멘털 및 밸류에이션 리스크 검증 필요",
                    'type': "중립"
                })
    except Exception: pass
    return news_list[:10]

@app.route('/')
def index():
    price_map = {}
    tasks = [(s['code'], s['ticker']) for cat in MARKET_CATEGORIES for s in cat['stocks']]
    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_code = {executor.submit(fetch_realtime_data, ticker): code for code, ticker in tasks}
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            try: price_map[code] = future.result() or {'price': '0.00', 'rate': '+0.00%', 'is_up': True}
            except Exception: price_map[code] = {'price': '0.00', 'rate': '+0.00%', 'is_up': True}
                
    live_news = fetch_naver_finance_news()
    feature_stocks_data, feature_market_summary = fetch_feature_stocks()
    
    return render_template(
        'index.html', 
        categories=MARKET_CATEGORIES, 
        quotes=price_map,
        news_list=live_news,
        theme_summary={'us_driver': '필라델피아 반도체 연동 강세', 'core_stocks': 'NVIDIA', 'domestic_stocks': '삼성전자', 'risk_strategy': '우량주 중심 분할 매수'},
        smart_money_summary={'badge_text': '외인·기관 순매수 유입', 'badge_class': 'up', 'domestic': '코스피 수급 집중', 'decoupling': '대형주 방어력 우수', 'concentrated_themes': '<strong>집중 테마:</strong> 반도체, 우주항공', 'fx_oil': '환율 안정세'},
        strategies=[{'title': 'AI 반도체 후공정', 'desc': '실적 가시화 종목 공략', 'stock': '삼성전자', 'rank': 'TOP 1'}],
        ai_briefing="🤖 [AI 종합 브리핑]\n지수 완만한 수급 균형 유지 중",
        feature_stocks=feature_stocks_data,
        feature_market_summary=feature_market_summary
    )

@app.route('/api/feature-stocks')
def api_feature_stocks():
    items, market_summary = fetch_feature_stocks()
    return jsonify({"feature_stocks": items, "feature_market_summary": market_summary})

if __name__ == '__main__':
    app.run(debug=True)
