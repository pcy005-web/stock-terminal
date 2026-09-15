from flask import Flask, render_template
import urllib.request
import urllib.parse
import json
import ssl
import xml.etree.ElementTree as ET
import re

app = Flask(__name__)

# 대시보드 카테고리 구조 (각 API 특성에 맞는 ticker 매핑)
MARKET_CATEGORIES = [
    {
        'title': '🇰🇷 국내 증시 주요 지수',
        'stocks': [
            {'code': 'kospi', 'name': '코스피', 'ticker': 'NAVER_INDEX_KOSPI'},
            {'code': 'kosdaq', 'name': '코스닥', 'ticker': 'NAVER_INDEX_KOSDAQ'},
            {'code': 'kospi200', 'name': '코스피 200', 'ticker': 'NAVER_INDEX_KPI200'},
            {'code': 'fut', 'name': '코스피200 선물', 'ticker': 'NAVER_INDEX_FUT'}
        ]
    },
    {
        'title': '📈 주요 관심 종목 및 ETF',
        'stocks': [
            {'code': 'samsung', 'name': '삼성전자', 'ticker': 'NAVER_STOCK_005930'},
            {'code': 'hynix', 'name': 'SK하이닉스', 'ticker': 'NAVER_STOCK_000660'},
            {'code': 'lgensol', 'name': 'LG에너지솔루션', 'ticker': 'NAVER_STOCK_373220'},
            {'code': 'kodex200', 'name': 'KODEX 200', 'ticker': 'NAVER_STOCK_069500'},
            {'code': 'kodex_lev', 'name': 'KODEX 레버리지', 'ticker': 'NAVER_STOCK_122630'},
            {'code': 'kodex_inv', 'name': 'KODEX 인버스2X', 'ticker': 'NAVER_STOCK_252670'}
        ]
    },
    {
        'title': '🛢️ 환율 및 원자재',
        'stocks': [
            {'code': 'usdkrw', 'name': '원/달러 환율', 'ticker': 'NAVER_EXCHANGE_FX_USDKRW'},
            {'code': 'wti', 'name': 'WTI원유', 'ticker': 'NAVER_ENERGY_CLcv1'},
            {'code': 'gold', 'name': '금현물', 'ticker': 'NAVER_METAL_GCcv1'}
        ]
    }
]

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def fetch_all_market_data():
    """네이버 금융 폴링 API들을 호출하여 필요한 모든 데이터를 한 번에 수집 및 매핑"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://m.stock.naver.com/',
        'Accept': 'application/json, text/plain, */*'
    }
    
    price_map = {}

    # 1. 국내 증시 주요 지수 조회 (domestic/index)
    try:
        index_url = "https://polling.finance.naver.com/api/realtime/domestic/index/KOSPI,KOSDAQ,KPI200,FUT"
        req = urllib.request.Request(index_url, headers=headers)
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=5) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            datas = res_json.get('datas', [])
            for item in datas:
                code = item.get('itemCode') or item.get('code')
                cur_price = item.get('closePrice') or item.get('nowValue') or item.get('price')
                fluc_rate = item.get('fluctuationsRatio') or item.get('rate') or 0
                sign = str(item.get('sign', ''))
                
                if code and cur_price is not None:
                    price_val = float(str(cur_price).replace(',', ''))
                    rate_val = float(str(fluc_rate).replace('%', '').replace('+', '')) if fluc_rate else 0.0
                    is_up = not (sign in ['4', '5'] or str(fluc_rate).startswith('-'))
                    
                    # 매핑용 키 설정
                    key_map = {'KOSPI': 'kospi', 'KOSDAQ': 'kosdaq', 'KPI200': 'kospi200', 'FUT': 'fut'}
                    if code in key_map:
                        price_map[key_map[code]] = {
                            'price': f"{price_val:,.2f}" if '.' in str(cur_price) else f"{price_val:,.2f}",
                            'rate': f"{rate_val:+.2f}%",
                            'is_up': is_up
                        }
    except Exception as e:
        print(f"국내 지수 통신 에러: {e}")

    # 2. 국내 주요 종목 및 ETF 다중 조회 (domestic/stock)
    try:
        stock_codes = "005930,000660,373220,069500,122630,252670"
        stock_url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{stock_codes}"
        req = urllib.request.Request(stock_url, headers=headers)
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=5) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            datas = res_json.get('datas', [])
            for item in datas:
                code = item.get('itemCode') or item.get('code')
                cur_price = item.get('closePrice') or item.get('nowValue') or item.get('price')
                fluc_rate = item.get('fluctuationsRatio') or item.get('rate') or 0
                sign = str(item.get('sign', ''))
                
                if code and cur_price is not None:
                    price_val = float(str(cur_price).replace(',', ''))
                    rate_val = float(str(fluc_rate).replace('%', '').replace('+', '')) if fluc_rate else 0.0
                    is_up = not (sign in ['4', '5'] or str(fluc_rate).startswith('-'))
                    
                    key_map = {
                        '005930': 'samsung', '000660': 'hynix', '373220': 'lgensol',
                        '069500': 'kodex200', '122630': 'kodex_lev', '252670': 'kodex_inv'
                    }
                    if code in key_map:
                        price_map[key_map[code]] = {
                            'price': f"{price_val:,.2f}",
                            'rate': f"{rate_val:+.2f}%",
                            'is_up': is_up
                        }
    except Exception as e:
        print(f"국내 종목 통신 에러: {e}")

    # 3. 환율 및 원자재 개별 폴링 API 조회
    exchange_targets = {
        'usdkrw': 'https://polling.finance.naver.com/api/realtime/marketindex/exchange/FX_USDKRW',
        'wti': 'https://polling.finance.naver.com/api/realtime/marketindex/energy/CLcv1',
        'gold': 'https://polling.finance.naver.com/api/realtime/marketindex/metals/GCcv1'
    }

    for key, url in exchange_targets.items():
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=5) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                datas = res_json.get('datas', [])
                if not datas and 'result' in res_json:
                    datas = res_json.get('result', {}).get('datas', [])
                if not datas and isinstance(res_json, dict):
                    datas = [res_json]
                
                if datas:
                    item = datas[0]
                    cur_price = item.get('closePrice') or item.get('nowValue') or item.get('price') or item.get('dealBasRate')
                    fluc_rate = item.get('fluctuationsRatio') or item.get('rate') or item.get('fluctuationRate') or 0
                    sign = str(item.get('sign', ''))
                    
                    if cur_price is not None:
                        price_val = float(str(cur_price).replace(',', ''))
                        rate_val = float(str(fluc_rate).replace('%', '').replace('+', '')) if fluc_rate else 0.0
                        is_up = not (sign in ['4', '5'] or str(fluc_rate).startswith('-'))
                        price_map[key] = {
                            'price': f"{price_val:,.2f}",
                            'rate': f"{rate_val:+.2f}%",
                            'is_up': is_up
                        }
        except Exception as e:
            print(f"환율/원자재 통신 에러 ({key}): {e}")

    return price_map

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
        news_list.append({
            'title': '글로벌 증시 및 국내 금융시장 실시간 동향 점검',
            'link': 'https://search.naver.com/search.naver?where=news&query=국내증시',
            'stock': '시장 전체'
        })
            
    return news_list

@app.route('/')
def index():
    # 일괄 데이터 수집 실행
    price_map = fetch_all_market_data()
    
    # 누락된 데이터가 있을 경우 기본값 처리
    for cat in MARKET_CATEGORIES:
        for stock in cat['stocks']:
            code = stock['code']
            if code not in price_map:
                price_map[code] = {'price': '0.00', 'rate': '+0.00%', 'is_up': True}
                
    live_news = fetch_naver_finance_news()
    
    usdkrw_val = price_map.get('usdkrw', {}).get('price', '1,300.00')
    kospi_val = price_map.get('kospi', {}).get('rate', '+0.00%')
    
    theme_text = f"현재 코스피 등락률({kospi_val})과 연동하여 국내 대형주 및 지수 중심의 수급 흐름이 이어지고 있습니다."
    smart_money_text = f"현재 원/달러 환율({usdkrw_val}원) 변동성에 따른 외국인 및 기관의 수급 동향을 주시해야 합니다."
    premarket_text = f"원/달러 환율({usdkrw_val}원) 및 주요 지수 실시간 시세를 반영하여 모니터링 중입니다."
    ai_briefing_text = f"[AI 종합 리포트]\n- 원/달러 환율: {usdkrw_val}원\n- 코스피 변동: {kospi_val}\n- 주요 이슈 실시간 반영 중"
                
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
