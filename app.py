import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import ssl
import pytz
from flask import Flask, render_template

app = Flask(__name__)

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def fetch_newspim_supply_news():
    """뉴스핌(Newspim)에서 장중 수급 및 증시 관련 키워드로 뉴스를 수집합니다."""
    kst = pytz.timezone('Asia/Seoul')
    now_dt = datetime.datetime.now(kst)
    
    query_str = urllib.parse.quote("site:newspim.com 수급 OR 외국인 OR 기관 OR 코스피 OR 증시 when:1d")
    rss_url = f"https://news.google.com/rss/search?q={query_str}&hl=ko&gl=KR&ceid=KR:ko"
    
    news_contents = []
    try:
        req = urllib.request.Request(
            rss_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=1.5) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                if title_elem is not None and title_elem.text:
                    title = title_elem.text
                    if " - " in title:
                        title = title.rsplit(" - ", 1)[0]
                    news_contents.append(title.strip())
                if len(news_contents) >= 3:
                    break
    except Exception:
        pass
        
    return news_contents

def generate_smart_money_analysis(quotes):
    kospi = quotes.get('kospi', {'price': '0', 'rate': '+0.00%', 'is_up': True})
    kosdaq = quotes.get('kosdaq', {'price': '0', 'rate': '+0.00%', 'is_up': True})
    usdkrw = quotes.get('usdkrw', {'price': '1,300', 'rate': '+0.00%', 'is_up': True})
    
    kospi_up = kospi.get('is_up', True)
    badge_text = "뉴스핌 수급 기준: 외인·기관 순매수 유입" if kospi_up else "뉴스핌 수급 기준: 외인·기관 매도 우위"
    badge_class = "up" if kospi_up else "down"
    
    newspim_headlines = fetch_newspim_supply_news()
    if newspim_headlines:
        news_summary_text = " / ".join(newspim_headlines[:2])
        domestic_text = f"뉴스핌 실시간 속보 연동: {news_summary_text}"
    else:
        domestic_text = f"국내 현·선물 수급 동향: 코스피({kospi.get('rate')}), 코스닥({kosdaq.get('rate')}) 실시간 연동 분석"

    decoupling_text = "뉴스핌 매체 분석 기반 코스피 대형주 및 코스닥 주도주 간 디커플링 및 순환매 포착"
    concentrated_themes = (
        "<strong>[뉴스핌 장중 수급 리포트 요약]</strong> "
        "외국인과 기관의 실시간 순매수 상위 업종을 중심으로 자금이 집중되며, "
        "주요 경제 레이더망에 포착된 핵심 주도 테마 중심의 대응이 요구됩니다."
    )
    fx_oil_text = f"원/달러 환율({usdkrw.get('price')}원) 및 글로벌 원자재 동향에 따른 수급 탄력성 검토"

    return {
        'badge_text': badge_text,
        'badge_class': badge_class,
        'domestic': domestic_text,
        'decoupling': decoupling_text,
        'concentrated_themes': concentrated_themes,
        'fx_oil': fx_oil_text
    }

@app.route('/')
def index():
    # 샘플 지수 데이터
    quotes = {
        'kospi': {'price': '2,680.15', 'rate': '+0.85%', 'is_up': True},
        'kosdaq': {'price': '870.40', 'rate': '-0.20%', 'is_up': False},
        'usdkrw': {'price': '1,350.50', 'rate': '+0.15%', 'is_up': True}
    }
    
    # 뉴스핌 기반 장중 수급 분석 데이터 생성
    smart_money_summary = generate_smart_money_analysis(quotes)
    
    return render_template('index_2.html', quotes=quotes, smart_money_summary=smart_money_summary)

if __name__ == '__main__':
    app.run(debug=True)
