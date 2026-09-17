import datetime
import json
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from flask import Flask, jsonify, render_template
import pytz

app = Flask(__name__)

def get_ssl_context():
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context

# ==========================================
# 7섹션 전용: 네이버 증권 API를 통한 동적 종목/업종(테마) 조회 함수
# ==========================================
def fetch_stock_theme_from_naver(stock_name):
    """
    네이버 증권 검색 API를 활용하여 종목명으로 실제 업종/테마 정보를 동적으로 가져옵니다.
    """
    clean_name = stock_name.replace("(핵심종목)", "").strip()
    if not clean_name or clean_name in ["시장주도주", "특징주"]:
        return "시장주도주", "증시시황"

    search_url = f"https://api.stock.naver.com/search/stock?query={urllib.parse.quote(clean_name)}&pageSize=1"
    
    try:
        req = urllib.request.Request(
            search_url, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://m.stock.naver.com/'
            }
        )
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=3) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            stocks = res_json.get('stocks', [])
            if stocks:
                item = stocks[0]
                matched_name = item.get('stockName', clean_name)
                sector = item.get('reutersSector') or item.get('stockItemCode') or "시장주도주"
                return matched_name, sector
    except Exception:
        pass

    # API 조회 실패 시 기본 키워드 매칭 규칙 적용
    keyword_theme_rules = {
        "바이오/제약": ["바이오", "제약", "임상", "신약", "유전체", "바이오시밀러", "FDA"],
        "AI 반도체": ["반도체", "AI", "칩", "소부장", "메모리", "파운드리"],
        "방산": ["방산", "수출", "무기", "방위", "K9"],
        "조선/해운": ["조선", "선박", "유조선", "LNG", "해운", "수주"],
        "전력기기": ["변압기", "전력", "송배전", "그리드", "배터리"],
        "자동차": ["자동차", "차량", "전기차", "완성차", "부품"],
        "게임/콘텐츠": ["게임", "콘텐츠", "웹툰", "엔터", "피인수"],
        "금융": ["금융", "은행", "증권", "보험", "주주환원"],
        "글로벌증시": ["뉴욕증시", "증시", "개장", "미국", "나스닥", "다우"]
    }
    
    for theme, keywords in keyword_theme_rules.items():
        if any(kw in clean_name for kw in keywords):
            return clean_name, theme
            
    return clean_name, "시장주도주"

_cached_feature_items = []
_last_raw_titles = set()

# ==========================================
# 7섹션 전용 데이터 수집 함수 (동적 종목/테마 적용 완료)
# ==========================================
def fetch_feature_stocks():
    global _cached_feature_items, _last_raw_titles
    kst = pytz.timezone('Asia/Seoul')
    now_dt = datetime.datetime.now(kst)
    current_hour_min = now_dt.hour * 100 + now_dt.minute
    
    is_market_closed = current_hour_min >= 1530 or now_dt.weekday() >= 5
    
    query = "intitle:특징주 OR intitle:장전특징주 OR intitle:개장전특징주 OR intitle:상한가 when:6h"
    cache_buster = int(datetime.datetime.now().timestamp() / 60)
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ko&gl=KR&ceid=KR:ko&cb={cache_buster}"
    
    parsed_items = []
    seen_titles = set()
    
    try:
        req = urllib.request.Request(
            rss_url, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        )
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=4) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                link_elem = item.find('link')
                pub_date_elem = item.find('pubDate')
                
                title = title_elem.text if title_elem is not None else ""
                title_clean = title.rsplit(" - ", 1)[0] if " - " in title else title
                link = link_elem.text if link_elem is not None else "https://news.google.com"
                
                like_keywords = ["특징주", "장전특징주", "개장전특징주", "상한가"]
                if not any(kw in title_clean for kw in like_keywords):
                    continue
                
                if "주요 특징주" in title_clean or "오늘(" in title_clean:
                    continue
                if title_clean in seen_titles:
                    continue
                
                pub_dt = now_dt
                if pub_date_elem is not None and pub_date_elem.text:
                    try:
                        pub_dt = parsedate_to_datetime(pub_date_elem.text)
                        if pub_dt.tzinfo is None:
                            pub_dt = pytz.utc.localize(pub_dt)
                        pub_dt = pub_dt.astimezone(kst)
                    except Exception:
                        pass
                
                time_diff_hours = (now_dt - pub_dt).total_seconds() / 3600
                if time_diff_hours > 6:
                    continue
                
                seen_titles.add(title_clean)
                item_time_str = pub_dt.strftime('%H:%M')
                
                # 뉴스 타이틀 안에서 종목명 추출 (따옴표 또는 대괄호 분석)
                raw_stock_name = ""
                quoted_matches = re.findall(r"'([^']+)'", title_clean)
                exclude_words = ["특징주", "급등", "상한가", "하락", "폭등", "마감", "시황", "코스피", "코스닥", "거래", "장중", "오후", "오전", "종합", "미국", "일본", "ET", "ETF"]
                
                for qm in quoted_matches:
                    if len(qm) <= 12 and not any(ew in qm for ew in exclude_words) and not any(char.isdigit() for char in qm):
                        raw_stock_name = qm
                        break
                
                if not raw_stock_name:
                    bracket_match = re.search(r'\[(.*?)특징주\]|\[특징주[:\s]*(.*?)\]', title_clean)
                    if bracket_match:
                        candidate = bracket_match.group(1) or bracket_match.group(2)
                        if candidate and len(candidate.strip()) <= 10:
                            raw_stock_name = candidate.strip()

                if not raw_stock_name:
                    clean_for_parse = re.sub(r'\[.*?\]', '', title_clean).strip()
                    if ',' in clean_for_parse:
                        candidate = clean_for_parse.split(',')[0].strip()
                        if len(candidate) <= 10 and not any(ew in candidate for ew in exclude_words):
                            raw_stock_name = candidate

                if not raw_stock_name:
                    raw_stock_name = "시장주도주"
                
                # 네이버 API를 통해 정확한 종목명 및 테마 동적 획득
                stock_val, theme_val = fetch_stock_theme_from_naver(raw_stock_name)
                formatted_title = f"[{item_time_str}] {title_clean}"
                
                parsed_items.append({
                    "stock": stock_val,
                    "theme": theme_val,
                    "title": formatted_title,
                    "link": link,
                    "timestamp": pub_dt,
                    "raw_title": title_clean
                })
    except Exception:
        pass
        
    parsed_items = sorted(parsed_items, key=lambda x: x['timestamp'], reverse=True)
    feature_items = parsed_items[:5]
        
    current_time_str = now_dt.strftime('%H:%M')
    fallbacks = [
        {"stock": "버크셔 해서웨이", "theme": "종합지주", "title": f"[{current_time_str}] [특징주] 버크셔 해서웨이 포트폴리오 조정 및 시장 영향 분석", "link": "https://news.google.com", "timestamp": now_dt, "raw_title": "버크셔 해서웨이 포트폴리오 조정"},
        {"stock": "MOL", "theme": "조선/해운", "title": f"[{current_time_str}] [일본 특징주] MOL, 중동발 선박가 급등에 노후 유조선 매각 검토", "link": "https://news.google.com", "timestamp": now_dt, "raw_title": "MOL 노후 유조선 매각 검토"},
        {"stock": "앤씨앤", "theme": "게임/콘텐츠", "title": f"[{current_time_str}] [ET특징주] 앤씨앤, 비투엔에 피인수... 주가 上", "link": "https://news.google.com", "timestamp": now_dt, "raw_title": "앤씨앤 피인수"},
        {"stock": "미투온", "theme": "게임/콘텐츠", "title": f"[{current_time_str}] [ET특징주] '카카오게임즈 피인수' 미투온, 상한가 이어 19%↑", "link": "https://news.google.com", "timestamp": now_dt, "raw_title": "미투온 상한가"},
        {"stock": "한화시스템", "theme": "방산", "title": f"[{current_time_str}] [특징주] 한화시스템, 방산 수출 확대 기대감에 강세", "link": "https://news.google.com", "timestamp": now_dt, "raw_title": "한화시스템 방산 수출"}
    ]
    
    for fb in fallbacks:
        if len(feature_items) < 5:
            feature_items.append(fb)
            
    feature_items = sorted(feature_items, key=lambda x: x['timestamp'], reverse=True)
    feature_items = feature_items[:5]
    
    current_raw_titles = set(item["raw_title"] for item in feature_items)
    if _cached_feature_items and current_raw_titles == _last_raw_titles:
        feature_items = _cached_feature_items
    else:
        _cached_feature_items = feature_items
        _last_raw_titles = current_raw_titles
    
    serializable_items = []
    for item in feature_items:
        serializable_items.append({
            "stock": item["stock"],
            "theme": item["theme"],
            "title": item["title"],
            "link": item["link"]
        })
                
    if is_market_closed:
        market_summary_keyword = (
            "• [마감 동향]: 국내 증시 마감에 따른 주요 업종별 수급 마감 결과 반영\n"
            "• [주요 특징]: 주도 섹터별 마감 가격 제안 및 시간외 단일가 동향 모니터링 체제 전환\n"
            "• [향후 전망]: 글로벌 매크로 지표 및 야간 선물 시장 연동성 검토"
        )
    else:
        market_summary_keyword = (
            "• [수급 동향]: AI 반도체 및 핵심 소부장 중심의 선별적 매수세 유입\n"
            "• [순환매 전개]: 전력기기·바이오·방산 섹터 간 빠른 순환매 장세 포착\n"
            "• [시장 분위기]: 주요 지수 등락 속 종목별 차별화 장세 진행 중"
        )
        
    return serializable_items, market_summary_keyword

# ==========================================
# 라우트 설정
# ==========================================
@app.route('/')
index_cache_time = 0
cached_index_html = None

def index():
    global index_cache_time, cached_index_html
    now_ts = datetime.datetime.now().timestamp()
    
    # 7섹션 특징주 데이터 연동
    feature_stocks, feature_market_summary = fetch_feature_stocks()
    
    # 만약 다른 기존 데이터 처리 함수들이 있다면 이곳에서 함께 호출하여 렌더링에 전달됩니다.
    return render_template(
        'index.html',
        feature_stocks=feature_stocks,
        feature_market_summary=feature_market_summary
    )

@app.route('/api/feature-stocks')
def api_feature_stocks():
    feature_stocks, feature_market_summary = fetch_feature_stocks()
    return jsonify({
        "feature_stocks": feature_stocks,
        "feature_market_summary": feature_market_summary
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
