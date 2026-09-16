from flask import Flask, render_template, jsonify
import random
import datetime

app = Flask(__name__)

# 임시 초기 데이터 및 헬퍼 함수 (실제 크롤링/API 데이터로 대체 가능)
def get_mock_quotes():
    return {
        'kospi': {'price': f"{random.uniform(2500, 2700):.2f}", 'rate': f"+{random.uniform(0.1, 1.5):.2f}%", 'is_up': True},
        'kosdaq': {'price': f"{random.uniform(800, 900):.2f}", 'rate': f"-{random.uniform(0.1, 1.2):.2f}%", 'is_up': False},
        'kospi200': {'price': f"{random.uniform(330, 350):.2f}", 'rate': f"+{random.uniform(0.1, 1.0):.2f}%", 'is_up': True},
        'sp500': {'price': f"{random.uniform(5000, 5200):.2f}", 'rate': f"+{random.uniform(0.2, 1.0):.2f}%", 'is_up': True},
        'dow': {'price': f"{random.uniform(38000, 39500):.2f}", 'rate': f"-{random.uniform(0.1, 0.8):.2f}%", 'is_up': False},
        'nasdaq': {'price': f"{random.uniform(16000, 16500):.2f}", 'rate': f"+{random.uniform(0.3, 1.8):.2f}%", 'is_up': True},
        'phlx': {'price': f"{random.uniform(4500, 4800):.2f}", 'rate': f"+{random.uniform(0.5, 2.0):.2f}%", 'is_up': True},
        'sp500_fut': {'price': f"{random.uniform(5050, 5250):.2f}", 'rate': f"+{random.uniform(0.1, 0.9):.2f}%", 'is_up': True},
        'dow_fut': {'price': f"{random.uniform(38200, 39700):.2f}", 'rate': f"+{random.uniform(0.1, 0.7):.2f}%", 'is_up': True},
        'nasdaq_fut': {'price': f"{random.uniform(16100, 16600):.2f}", 'rate': f"+{random.uniform(0.2, 1.2):.2f}%", 'is_up': True},
        'vix': {'price': f"{random.uniform(12, 18):.2f}", 'rate': f"-{random.uniform(1.0, 5.0):.2f}%", 'is_up': False},
        'usdkrw': {'price': f"{random.uniform(1330, 1370):.2f}", 'rate': f"+{random.uniform(0.1, 0.5):.2f}%", 'is_up': True},
        'wti': {'price': f"{random.uniform(75, 85):.2f}", 'rate': f"-{random.uniform(0.5, 1.5):.2f}%", 'is_up': False},
        'gold': {'price': f"{random.uniform(2100, 2200):.2f}", 'rate': f"+{random.uniform(0.1, 0.8):.2f}%", 'is_up': True},
    }

@app.route('/')
def index():
    quotes = get_mock_quotes()
    # 화면 초기 렌더링에 필요한 더미 데이터들
    theme_summary = {
        'us_driver': 'AI 반도체 및 빅테크 중심 상승세 지속',
        'core_stocks': 'NVIDIA, AMD, 마이크로소프트',
        'domestic_stocks': '삼성전자, SK하이닉스, 한미반도체',
        'risk_strategy': '환율 변동성 주의 및 실적 기반 종목 선별 접근'
    }
    smart_money_summary = {
        'badge_text': '외국인/기관 순매수 유입',
        'badge_class': 'up',
        'domestic': '코스피 대형주 중심으로 양시장 외국인 수급 양호',
        'decoupling': '일부 코스닥 개별주는 차익실현 매물 출하',
        'fx_oil': '원달러 환율 소폭 하락 안정세'
    }
    strategies = [
        {'title': '반도체 소부장 대장주 반등 공략', 'rank': 'TOP 1', 'desc': '외국인 수급이 집중되는 대형 반도체 소부장 품목 집중', 'stock': 'SK하이닉스'},
        {'title': '저PBR 금융주 밸류업 모멘텀', 'rank': 'TOP 2', 'desc': '정부 정책 기대감에 따른 저PBR 은행·증권주 수급 지속', 'stock': 'KB금융'},
        {'title': '미국 증시 연동 IT·하드웨어', 'rank': 'TOP 3', 'desc': '나스닥 신고가 경신에 따른 국내 IT 부품주 동조화', 'stock': '이수페타시스'},
        {'title': '2차전지 바닥 다지기 분할 매수', 'rank': 'TOP 4', 'desc': '낙폭 과대 구간 내 기관 저가 매수세 유입 확인', 'stock': 'LG에너지솔루션'},
        {'title': '로봇 및 인공지능(AI) 테마 순환매', 'rank': 'TOP 5', 'desc': '정책 및 대기업 투자 관련 테마주 단기 수급 포착', 'stock': '레인보우로보틱스'}
    ]
    market_summary_bullets = [
        '뉴욕증시, 엔비디아 등 기술주 강세로 혼조세 마감',
        '파이낸셜 및 반도체 업종 중심으로 외국인 순매수 유입 예상',
        '원달러 환율은 1,350원 선 부근에서 등락 예상'
    ]
    news_list = [
        {'title': '연준, 금리 인하 기대감 속 물가 지표 주시', 'link': '#', 'type': '중립', 'comment': '발표될 지표에 따라 변동성 확대 가능성', 'stock': '전체 시장'},
        {'title': '반도체 수출 호조세 지속… 메모리 가격 반등', 'link': '#', 'type': '호재', 'comment': '실적 개선 기대감 선반영 구간', 'stock': '삼성전자, SK하이닉스'}
    ]
    ai_briefing = "✨ [초기 생성된 AI 브리핑]\n현재 시각 기준 미국 증시와 국내 선물 지수를 종합한 결과, 반도체 섹터의 우위가 예상됩니다."

    return render_template('index.html', 
                           quotes=quotes, 
                           theme_summary=theme_summary,
                           smart_money_summary=smart_money_summary,
                           strategies=strategies,
                           market_summary_bullets=market_summary_bullets,
                           news_list=news_list,
                           ai_briefing=ai_briefing,
                           categories=[{}, {}, {'stocks': [{'code': 'usdkrw', 'name': '원/달러 환율'}, {'code': 'wti', 'name': 'WTI 원유'}, {'code': 'gold', 'name': '국제 금'}]}] )

@app.route('/api/quotes', methods=['GET'])
def api_quotes():
    # 3초마다 호출되어 갱신된 시세 및 등락률 데이터를 반환
    return jsonify(get_mock_quotes())

@app.route('/api/ai-briefing', methods=['GET'])
def api_ai_briefing():
    # 버튼을 누를 때마다 새롭게 생성된 AI 브리핑 텍스트를 반환
    now = datetime.datetime.now().strftime('%H:%M:%S')
    new_briefing = (
        f"✨ [실시간 업데이트된 AI 종합 분석 리포트 - {now}]\n\n"
        f"1. **시장 동향**: 실시간 수급 데이터 분석 결과 외국인 매수세가 반도체 및 자동차 업종으로 유입되고 있습니다.\n"
        f"2. **리스크 요인**: 환율 변동성이 상존하므로 과격한 추격 매수보다는 분할 관점의 접근이 유효합니다.\n"
        f"3. **주도주 전망**: 핵심 기술주 중심의 순환매 장세가 이어질 가능성이 높습니다."
    )
    return jsonify({"ai_briefing": new_briefing})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
