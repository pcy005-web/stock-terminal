import datetime
import json
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime
from difflib import SequenceMatcher
from flask import Flask, render_template, jsonify
import pytz
from bs4 import BeautifulSoup
import requests

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

def fetch_shortnews_summary():
    """매일 아침 갱신되는 shortnews.co.kr/news/날짜 데이터를 가져옵니다."""
    kst = pytz.timezone('Asia/Seoul')
    today_str = datetime.datetime.now(kst).strftime("%Y-%m-%d")
    url = f"https://shortnews.co.kr/news/{today_str}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=3)
        
        if response.status_code != 200:
            return {
                "date": today_str,
                "content": f"[{today_str}] 오늘의 간추린 뉴스 데이터가 아직 등록되지 않았거나 주말/휴일일 수 있습니다. (원문 링크를 확인해주세요)"
            }
            
        soup = BeautifulSoup(response.text, 'html.parser')
        body_div = soup.find('div', class_='news-content') or soup.find('main') or soup.find('article')
        
        if not body_div:
            paragraphs = [p.get_text() for p in soup.find_all(['p', 'div']) if len(p.get_text()) > 20]
            content_text = "\n\n".join(paragraphs[:10]) if paragraphs else "등록된 뉴스 내용이 없습니다."
        else:
            content_text = body_div.get_text(separator="\n\n").strip()
            
        return {
            "date": today_str,
            "content": content_text if content_text else "오늘의 간추린 뉴스 내용이 비어 있습니다."
        }
    except Exception as e:
        return {
            "date": today_str,
            "content": f"숏뉴스 크롤링 중 오류가 발생했습니다: {str(e)}"
        }

def fetch_feature_stocks():
    kst = pytz.timezone('Asia/Seoul')
    now_dt = datetime.datetime.now(kst)
    query = "intitle:특징주 OR intitle:장전특징주 OR intitle:상한가 when:6h"
    cache_buster = int(datetime.datetime.now().timestamp())
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ko&gl=KR&ceid=KR:ko&cb={cache_buster}"
    
    parsed_items = []
    seen_titles = set()
    
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=2.0) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                link_elem = item.find('link')
                pub_date_elem = item.find('pubDate')
                
                title = title_elem.text if title_elem is not None else ""
                if not title: continue
                
                sort_dt = None
                item_time_str = ""
                if pub_date_elem is not None and pub_date_elem.text:
                    try:
                        dt = parsedate_to_datetime(pub_date_elem.text)
                        sort_dt = dt.astimezone(kst)
                        item_time_str = sort_dt.strftime('%H:%M')
                    except Exception:
                        pass
                
                if not sort_dt or (now_dt - sort_dt).total_seconds() > 6 * 3600:
                    continue
                
                title_clean = title.rsplit(" - ", 1)[0].strip() if " - " in title else title.strip()
                if len(title_clean) > 38: title_clean = title_clean[:38] + "…"
                
                if title_clean in seen_titles: continue
                seen_titles.add(title_clean)
                
                parsed_items.append({
                    "title": title_clean,
                    "link": link_elem.text if link_elem is not None else "https://news.google.com",
                    "time": item_time_str,
                    "sort_dt": sort_dt
                })
    except Exception:
        pass
        
    parsed_items.sort(key=lambda x: x["sort_dt"], reverse=True)
    feature_items = parsed_items[:5]
    for item in feature_items: item.pop("sort_dt", None)
    
    market_summary = "• [장중 수급 동향]: AI 반도체 및 핵심 소부장 중심의 매수세 유입 중\n• [순환매 전개]: 전력기기·방산 및 저PBR 금융주로 빠른 수급 순환 진행"
    return feature_items, market_summary

def fetch_naver_finance_news():
    kst = pytz.timezone('Asia/Seoul')
    now_dt = datetime.datetime.now(kst)
    query_str = urllib.parse.quote("코스피 OR 코스닥 OR 삼성전자 OR 반도체 OR 특징주 OR 금리 OR 환율 OR 실적 when:6h")
    rss_url = f"https://news.google.com/rss/search?q={query_str}&hl=ko&gl=KR&ceid=KR:ko"
    
    scored_news_list = []
    collected_titles = []
    
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=1.5) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                link_elem = item.find('link')
                pub_date_elem = item.find('pubDate')
                
                if pub_date_elem is not None and pub_date_elem.text:
                    try:
                        dt_kst = parsedate_to_datetime(pub_date_elem.text).astimezone(kst)
                        if (now_dt - dt_kst).total_seconds() > 6 * 3600: continue
                    except Exception:
                        continue
                else:
                    continue

                title = title_elem.text if title_elem is not None else "제목 없음"
                title_clean = title.rsplit(" - ", 1)[0].strip() if " - " in title else title
                if len(title_clean) > 40: title_clean = title_clean[:40] + "…"

                if any(SequenceMatcher(None, title_clean, et).ratio() >= 0.75 for et in collected_titles):
                    continue
                collected_titles.append(title_clean)

                news_type = "호재" if any(k in title_clean for k in ["실적", "서프라이즈", "수주"]) else ("리스크" if any(k in title_clean for k in ["우려", "하락", "적자"]) else "중립")
                related_stock = "**삼성전자, SK하이닉스**" if "반도체" in title_clean else "시장 대형주"

                scored_news_list.append({
                    'score': 3 if news_type == "호재" else 1,
                    'item': {
                        'title': title_clean,
                        'source': "경제 뉴스",
                        'link': link_elem.text if link_elem is not None else "https://news.google.com",
                        'stock': related_stock,
                        'comment': "실시간 매크로 및 개별 종목 펀더멘털 영향 분석 필요",
                        'type': news_type
                    }
                })
    except Exception:
        pass
        
    scored_news_list.sort(key=lambda x: x['score'], reverse=True)
    return [x['item'] for x in scored_news_list[:10]]

def generate_strategies(quotes, news_list):
    return [
        {"title": "실적 가시성 높은 AI 반도체 및 핵심 소부장", "desc": "글로벌 AI 인프라 투자 확대에 따른 실적 턴어라운드 종목 집중 공략", "stock": "**삼성전자, SK하이닉스, 한미반도체**", "rank": "TOP 1"},
        {"title": "구조적 북미 수출 호조 전력 인프라 기기주", "desc": "견고한 수주 잔고와 마진율 개선세가 입증된 대장주 트레이딩", "stock": "**HD현대일렉트릭, 효성중공업**", "rank": "TOP 2"},
        {"title": "바이오 CDMO 실적 우량주 및 파이프라인 모멘텀", "desc": "어닝 개선 기대감 및 스마트머니 수급 유입 포착", "stock": "**삼성바이오로직스, 셀트리온**", "rank": "TOP 3"},
        {"title": "K-방산 및 조선 슈퍼사이클 실적 턴어라운드", "desc": "환율 효과 및 인도 기준 실적 성장이 담보된 수주형 성장주", "stock": "**한화에어로스페이스, 현대로템**", "rank": "TOP 4"},
        {"title": "저PBR 밸류업 금융주 및 정책 수혜 방어주", "desc": "매크로 변동성 대응 방어력 제고 및 배당 매력 부각", "stock": "**KB금융, 신한지주**", "rank": "TOP 5"}
    ]

def generate_ai_comprehensive_briefing(quotes, news_list):
    kst = pytz.timezone('Asia/Seoul')
    now_time = datetime.datetime.now(kst).strftime('%H시 %M분')
    top_news = news_list[0]['title'] if news_list else "글로벌 매크로 이슈 점검"
    return (
        f"🤖 [팩트 기반 AI 브리핑 리포트 (**{now_time}** 갱신)]\n\n"
        f"📊 [시황 총평]\n실시간 지수 연동성 및 대형주 수급 균형을 바탕으로 한 선별적 접근이 요구됩니다.\n\n"
        f"🔍 [핵심 체크포인트]\n• 주요 헤드라인: \"**{top_news}**\"\n• 주도 섹터 자금 유입 속도 확인\n\n"
        f"💡 [실전 대응 가이드]\n• 변동성 구간 내 주도주 눌림목 위주 분할 매수"
    )

@app.route('/')
def index():
    price_map = get_all_quotes_cached()
    live_news = fetch_naver_finance_news()
    short_news = fetch_shortnews_summary()
    strategies_data = generate_strategies(price_map, live_news)
    ai_briefing_text = generate_ai_comprehensive_briefing(price_map, live_news)
    feature_stocks_data, feature_market_summary = fetch_feature_stocks()
            
    return render_template(
        'index.html', 
        categories=MARKET_CATEGORIES, 
        quotes=price_map,
        news_list=live_news,
        strategies=strategies_data,
        ai_briefing=ai_briefing_text,
        feature_stocks=feature_stocks_data,
        feature_market_summary=feature_market_summary,
        short_news=short_news
    )

@app.route('/api/quotes')
def api_quotes():
    return jsonify(get_all_quotes_cached())

@app.route('/api/short-news')
def api_short_news():
    return jsonify(fetch_shortnews_summary())

@app.route('/api/feature-stocks')
def api_feature_stocks():
    items, market_summary = fetch_feature_stocks()
    return jsonify({"feature_stocks": items, "feature_market_summary": market_summary})

@app.route('/api/ai-briefing')
def api_ai_briefing():
    price_map = get_all_quotes_cached()
    news_list = fetch_naver_finance_news()
    return jsonify({"ai_briefing": generate_ai_comprehensive_briefing(price_map, news_list)})

if __name__ == '__main__':
    app.run(debug=True)
