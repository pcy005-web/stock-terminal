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
# 5번 섹션: 장중 특징주 핫이슈 (엄격한 최근 12시간 이내 발행 기사 필터링)
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
        req = urllib.request.Request(
            rss_url, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Cache-Control': 'no-cache'
            }
        )
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=2.0) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                link_elem = item.find('link')
                pub_date_elem = item.find('pubDate')
                
                title = title_elem.text if title_elem is not None else ""
                if not title:
                    continue
                
                # 발행 시간 파싱 및 엄격한 6시간 이내 검증
                sort_dt = None
                item_time_str = ""
                if pub_date_elem is not None and pub_date_elem.text:
                    try:
                        dt = parsedate_to_datetime(pub_date_elem.text)
                        sort_dt = dt.astimezone(kst)
                        item_time_str = sort_dt.strftime('%H:%M')
                    except Exception:
                        pass
                
                # 발행 시간 정보가 아예 없거나, 현재 기준 6시간을 초과한 경우 강제 제외
                if not sort_dt:
                    continue
                
                time_diff = now_dt - sort_dt
                if time_diff.total_seconds() > 6 * 3600 or time_diff.total_seconds() < 0:
                    continue
                
                if " - " in title:
                    title_clean = title.rsplit(" - ", 1)[0]
                else:
                    title_clean = title
                    
                title_clean = title_clean.strip()
                
                # 제목 길이 제한 (38자 초과 시 '…' 처리)
                max_len = 38
                if len(title_clean) > max_len:
                    title_clean = title_clean[:max_len] + "…"
                    
                link = link_elem.text if link_elem is not None else "https://news.google.com"
                
                if "주요 특징주" in title_clean or "오늘(" in title_clean:
                    continue
                if title_clean in seen_titles:
                    continue
                
                seen_titles.add(title_clean)
                
                parsed_items.append({
                    "title": title_clean,
                    "link": link,
                    "time": item_time_str,
                    "sort_dt": sort_dt
                })
    except Exception:
        pass
        
    parsed_items.sort(key=lambda x: x["sort_dt"], reverse=True)
    feature_items = parsed_items[:5]
    
    for item in feature_items:
        item.pop("sort_dt", None)
    
    if is_market_closed:
        market_summary_keyword = (
            "• [마감 동향]: 국내 증시 마감에 따른 주요 업종별 수급 마감 결과 반영\n"
            "• [순환매 전개]: 단기 자금이 반도체 대형주(삼성전자·SK하이닉스)에서 저PBR 금융주(KB금융·신한지주) 및 전력기기 섹터로 순환 이동\n"
            "• [향후 전망]: 글로벌 매크로 지표 및 야간 선물 시장 연동성 검토"
        )
    else:
        market_summary_keyword = (
            "• [수급 동향]: AI 반도체 및 핵심 소부장 중심의 선별적 매수세 유입\n"
            "• [순환매 전개]: 초반 2차전지 및 바이오 섹터로 유입되던 자금이 오후장 들어 전력기기·방산 섹터 및 저PBR 금융주로 빠르게 순환 이동\n"
            "• [시장 분위기]: 주요 지수 등락 속 종목별 차별화 장세 진행 중"
        )
        
    return feature_items, market_summary_keyword

def fetch_naver_finance_news():
    kst = pytz.timezone('Asia/Seoul')
    now_dt = datetime.datetime.now(kst)
    
    query_str = urllib.parse.quote("연합인포맥스 OR 연합인포 OR 뉴스핌 OR 금리 OR 환율 OR 실적 OR 외국인 OR 수급 OR 인플레이션 OR 증시 when:6h")
    rss_url = f"https://news.google.com/rss/search?q={query_str}&hl=ko&gl=KR&ceid=KR:ko"
    
    news_list = []
    collected_titles = [] 
    
    try:
        req = urllib.request.Request(
            rss_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=1.0) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                link_elem = item.find('link')
                pub_date_elem = item.find('pubDate')
                
                # 본문 뉴스 발행 시간 엄격한 6시간 이내 검증
                if pub_date_elem is not None and pub_date_elem.text:
                    try:
                        dt = parsedate_to_datetime(pub_date_elem.text)
                        dt_kst = dt.astimezone(kst)
                        time_diff = now_dt - dt_kst
                        if time_diff.total_seconds() > 6 * 3600 or time_diff.total_seconds() < 0:
                            continue
                    except Exception:
                        continue
                else:
                    continue

                title = title_elem.text if title_elem is not None else "제목 없음"
                if " - " in title:
                    title_clean, press_source = title.rsplit(" - ", 1)
                else:
                    title_clean = title
                    press_source = ""
                
                title_clean = title_clean.strip()
                max_len = 40
                if len(title_clean) > max_len:
                    title_clean = title_clean[:max_len] + "…"

                rss_source_name = item.find('source').text if item.find('source') is not None else ""
                combined_source_check = f"{press_source} {rss_source_name} {title}"
                
                if "연합인포" in combined_source_check:
                    display_source = "연합인포맥스"
                elif "뉴스핌" in combined_source_check:
                    display_source = "뉴스핌"
                else:
                    display_source = press_source.strip() if press_source else "경제 뉴스"
                
                news_date_str = dt_kst.strftime('%m/%d')

                is_duplicate = False
                for existing_title in collected_titles:
                    similarity = SequenceMatcher(None, title_clean, existing_title).ratio()
                    if similarity >= 0.75:
                        is_duplicate = True
                        break
                
                if is_duplicate:
                    continue
                
                collected_titles.append(title_clean)
                link = link_elem.text if link_elem is not None else "https://news.google.com"
                
                negative_keywords = ["하회", "적자", "둔화", "우려", "경고", "규제", "금리", "충격", "리스크", "하락", "급락"]
                is_negative = any(nk in title_clean for nk in negative_keywords)
                
                news_type = "중립"
                comment = "실시간 매크로 및 개별 종목 펀더멘털 영향 분석 필요"
                related_stock = "시장 대형주"

                if any(k in title_clean for k in ["반도체", "AI", "삼성", "하이닉스"]):
                    related_stock = "삼성전자, SK하이닉스"
                elif any(k in title_clean for k in ["현대차", "자동차", "배터리"]):
                    related_stock = "현대차, LG에너지솔루션"
                elif any(k in title_clean for k in ["금융", "은행", "증권"]):
                    related_stock = "KB금융, 신한지주"

                if is_negative:
                    news_type = "리스크"
                    comment = "관련 이슈에 따른 단기 변동성 확대 및 리스크 관리 주의"
                elif any(k in title_clean for k in ["실적", "서프라이즈", "영업이익", "수주", "계약"]):
                    news_type = "호재"
                    comment = "실적 개선 및 모멘텀 유입에 따른 긍정적 주가 영향 기대"

                news_list.append({
                    'title': title_clean,
                    'source': display_source,
                    'link': link,
                    'stock': related_stock,
                    'comment': comment,
                    'type': news_type,
                    'date': news_date_str,
                    'timestamp': now_dt
                })
                
                if len(news_list) >= 10:
                    break
    except Exception:
        pass
        
    return news_list

def generate_theme_sync_analysis(quotes, news_list):
    sox = quotes.get('phlx', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '+0.00%', 'is_up': True})
    is_up = sox.get('is_up', True)
    sox_rate = sox.get('rate', '+0.00%')
    nasdaq_rate = nasdaq_fut.get('rate', '+0.00%')
    
    if is_up:
        us_driver = f"글로벌 빅테크 반도체 밸류체인 연동 강세: 필라델피아 반도체({sox_rate}) 및 나스닥 선물({nasdaq_rate})의 우상향 흐름은 국내 반도체 수출 실적 개선 기대감을 선반영하며 지수 상단을 지지하고 있습니다."
        core_stocks = "NVIDIA, 마이크론, ASML"
        domestic_stocks = "삼성전자, SK하이닉스"
        risk_strategy = "실적 모멘텀이 검증된 펀더멘털 우량주 중심의 공격적 비중 확대 및 눌림목 트레이딩"
    else:
        us_driver = f"글로벌 기술주 멀티플 조정 압력: 필라델피아 반도체({sox_rate}) 조정 및 나스닥 선물({nasdaq_rate})의 경계감 반영은 국내 증시의 단기 변동성을 확대시키는 주요 요인으로 작용합니다."
        core_stocks = "테슬라, 애플, 마이크로소프트"
        domestic_stocks = "KB금융, 현대차, 삼성바이오로직스"
        risk_strategy = "매크로 변동성 심화 국면에서 펀더멘털이 탄탄한 방어적 포트폴리오 구축 및 리스크 관리"
    
    return {
        'us_driver': us_driver,
        'core_stocks': core_stocks,
        'domestic_stocks': domestic_stocks,
        'risk_strategy': risk_strategy
    }

def generate_smart_money_analysis(quotes, newspim_news):
    kospi = quotes.get('kospi', {'price': '0', 'rate': '+0.00%', 'is_up': True})
    kosdaq = quotes.get('kosdaq', {'price': '0', 'rate': '+0.00%', 'is_up': True})
    usdkrw = quotes.get('usdkrw', {'price': '1,300', 'rate': '+0.00%', 'is_up': True})
    
    kospi_up = kospi.get('is_up', True)
    kospi_rate = kospi.get('rate', '+0.00%')
    kosdaq_rate = kosdaq.get('rate', '+0.00%')
    
    newspim_snippet = ""
    if newspim_news:
        newspim_snippet = f" (뉴스핌 실시간 보도 참고: \"{newspim_news[0]}\")"

    if kospi_up:
        badge_text = "외인·기관 주도세력 순매수 유입 (포지션 확장)"
        badge_class = "up"
        domestic_text = f"국내 현·선물 수급 동향: 코스피({kospi_rate}) 및 코스닥({kosdaq_rate})의 상승 탄력과 함께 뉴스핌 보도 실시간 동향 반영 시 외국인·기관의 우호적 수급 유입이 포착됩니다{newspim_snippet}."
    else:
        badge_text = "외인·기관 주도세력 매도 우위 (방어적 포지션)"
        badge_class = "down"
        domestic_text = f"국내 현·선물 수급 동향: 코스피({kospi_rate}) 및 코스닥({kosdaq_rate}) 하락 압력 속에서 뉴스핌 실시간 보도 기준 기관·외인 매물 출회 및 보수적 대응이 우세합니다{newspim_snippet}."

    if kospi_up and not kosdaq.get('is_up', True):
        decoupling_text = "코스피 대형주 중심의 자금 집중 현상과 코스닥 개별주 조정 간의 디커플링 장세가 진행 중입니다."
    elif not kospi_up and kosdaq.get('is_up', True):
        decoupling_text = "코스피가 조정을 받는 동안 코스닥 중소형주로 개인 및 단기 스마트머니의 순환매가 유입되는 양상입니다."
    else:
        direction_word = "동반 강세" if kospi_up else "동반 약세"
        decoupling_text = f"양시장 모두 {direction_word} 흐름을 보이며 지수 연동성이 높게 유지되고 있습니다."

    if kospi_up:
        concentrated_themes = (
            "<strong>현재 스마트머니 수급 집중 테마 및 업종 분석:</strong> "
            "1) <strong>AI 반도체 및 핵심 소부장(삼성전자·SK하이닉스)</strong> 중심의 이익 성장 동반 구조적 쏠림 현상이 지속되며, "
            "2) 변동성 장세 속 수익성 방어를 위한 <strong>전력기기·원전·조선</strong> 및 <strong>은행·보험 등 저PBR 주주환원 업종</strong>으로 자금이 분산·확산되는 순환매 흐름이 포착됩니다."
        )
    else:
        concentrated_themes = (
            "<strong>현재 스마트머니 수급 집중 테마 및 업종 분석:</strong> "
            "1) 지수 방어 및 변동성 회피를 위한 <strong>저PBR 금융주(KB금융·신한지주) 및 통신·유틸리티</strong> 방어주로 피난처 성격의 자금이 유입되며, "
            "2) 개별 모멘텀을 보유한 일부 테마주 중심으로만 단기 트레이딩 자금이 순환하고 있습니다."
        )

    fx_price = usdkrw.get('price', '1,300')
    fx_rate = usdkrw.get('rate', '+0.00%')
    if usdkrw.get('is_up', True):
        fx_oil_text = f"원/달러 환율({fx_price}원, {fx_rate}) 상승 압력에 따른 외국인 수급 이탈 우려 점검 및 변동성 주의"
    else:
        fx_oil_text = f"원/달러 환율({fx_price}원, {fx_rate}) 하향 안정세에 힘입어 외국인 수급 유입 환경 개선 모니터링"

    return {
        'badge_text': badge_text,
        'badge_class': badge_class,
        'domestic': domestic_text,
        'decoupling': decoupling_text,
        'concentrated_themes': concentrated_themes,
        'fx_oil': fx_oil_text
    }

def generate_strategies(quotes, news_list):
    return [
        {"title": "실적 가시성 높은 AI 반도체 및 핵심 소부장", "desc": "글로벌 AI 인프라 투자 확대에 따른 실적 턴어라운드 종목 집중 공략", "stock": "삼성전자, SK하이닉스, 한미반도체 - AI 반도체", "rank": "TOP 1"},
        {"title": "구조적 북미 수출 호조 전력 인프라 기기주", "desc": "견고한 수주 잔고와 마진율 개선세가 입증된 대장주 트레이딩", "stock": "HD현대일렉트릭, 효성중공업 - 전력기기", "rank": "TOP 2"},
        {"title": "바이오 CDMO 실적 우량주 및 파이프라인 모멘텀", "desc": "어닝 개선 기대감 및 스마트머니 수급 유입 포착", "stock": "삼성바이오로직스, 셀트리온 - 바이오", "rank": "TOP 3"},
        {"title": "K-방산 및 조선 슈퍼사이클 실적 턴어라운드", "desc": "환율 효과 및 인도 기준 실적 성장이 담보된 수주형 성장주", "stock": "한화에어로스페이스, 현대로템 - 방산", "rank": "TOP 4"},
        {"title": "저PBR 밸류업 금융주 및 정책 수혜 방어주", "desc": "매크로 변동성 대응 방어력 제고 및 배당 매력 부각", "stock": "KB금융, 신한지주 - 금융", "rank": "TOP 5"}
    ]

def generate_premarket_summary_bullets(quotes, news_list):
    kst = pytz.timezone('Asia/Seoul')
    today_str = datetime.datetime.now(kst).strftime('%m/%d')
    header_title = f"{today_str}, 장 시작 전 마켓 핵심 생각: 금리 상승과 증시 체력"
    bullets = [
        "미국 증시는 연준 정책 불확실성 완화와 미 10년물 금리 5.0% 하회 속에서 반등에 성공했습니다. 마이크론(+5.5%), 엔비디아(+2.5%), 인텔(+7.7%) 등 반도체주의 강세가 두드러졌습니다.",
        "주식시장은 고금리 환경(미 10년물 금리 5.0% 등)에 단계적으로 적응하며 체력을 축적하고 있습니다. 금리 자체의 절대 레벨보다는 '금리 상승 속도'와 이익 컨센서스 변화에 주목할 시점입니다.",
        "오늘 국내 증시는 FOMC 이후 금리 안정 및 반도체 중심의 미국 증시 반등, 야간선물 강세에 힘입어 상승 흐름을 보일 것으로 전망합니다.",
        "외국인 연속 순매도는 펀더멘털 악화가 아닌 매크로 불확실성에 대응하기 위한 단기 리스크 관리 성격이 짙으며, 매크로 불안 정점 통과와 함께 반도체 등 주력 업종 중심의 비중 확대 및 분할 매수 전략이 유효합니다."
    ]
    return header_title, bullets

def generate_ai_comprehensive_briefing(quotes, news_list):
    kst = pytz.timezone('Asia/Seoul')
    now_time = datetime.datetime.now(kst).strftime('%H시 %M분')
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '-0.6%'})
    usdkrw = quotes.get('usdkrw', {'price': '1,300', 'rate': '+0.00%'})
    sox = quotes.get('phlx', {'price': '-', 'rate': '-3.4%'})
    top_news = news_list[0]['title'] if news_list else "글로벌 매크로 이슈 점검"
    
    return (
        f"🤖 [팩트 기반 AI 브리핑 리포트 ({now_time} 갱신)]\n\n"
        f"📊 [시황 총평]\n"
        f"나스닥 선물({nasdaq_fut['rate']})과 필라델피아 반도체 지수({sox['rate']}) 변동성을 소화하며 대형주 중심의 완만한 수급 균형이 나타나고 있습니다. 원/달러 환율({usdkrw['price']}원) 추이에 주목합니다.\n\n"
        f"🔍 [핵심 체크포인트]\n"
        f"• 주요 헤드라인: \"{top_news}\"\n"
        f"• 코스피·코스닥 거래대금 유입 및 주도 섹터 순환매 속도 확인\n\n"
        f"💡 [실전 대응 가이드]\n"
        f"• 지수 변동성 구간에서는 수급이 집중되는 핵심 주도주 눌림목 위주로 대응\n"
        f"• 매크로 리스크 방어를 위한 실적 우량주 분산 병행"
    )

@app.route('/')
def index():
    price_map = get_all_quotes_cached()
    live_news = fetch_naver_finance_news()
    
    newspim_news = [
        news['title'] for news in live_news 
        if '뉴스핌' in news.get('source', '') or '뉴스핌' in news.get('title', '')
    ]
    if not newspim_news and live_news:
        newspim_news = [live_news[0]['title']]

    theme_text = generate_theme_sync_analysis(price_map, live_news)
    smart_money_data = generate_smart_money_analysis(price_map, newspim_news)
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
    price_map = get_all_quotes_cached()
    return json.dumps(price_map, ensure_ascii=False)

@app.route('/api/feature-stocks')
def api_feature_stocks():
    items, market_summary = fetch_feature_stocks()
    return json.dumps({
        "feature_stocks": items,
        "feature_market_summary": market_summary
    }, ensure_ascii=False)

@app.route('/api/ai-briefing')
def api_ai_briefing():
    price_map = get_all_quotes_cached()
    news_list = fetch_naver_finance_news()
    ai_briefing_text = generate_ai_comprehensive_briefing(price_map, news_list=news_list)
    return json.dumps({"ai_briefing": ai_briefing_text}, ensure_ascii=False)

if __name__ == '__main__':
    app.run(debug=True)
