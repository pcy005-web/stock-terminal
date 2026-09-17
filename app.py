from flask import Flask, render_template, jsonify
import random
import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# 전역 변수로 장전 마켓 요약 데이터 관리 (매일 아침 8시 자동 갱신)
morning_briefing_data = {
    "date_title": "9/17, 장 시작 전 생각: 9월 FOMC와 증시 추세, 키움 한지영",
    "market_indices": "- 다우 -1.21%, S&P500 -0.45%, 나스닥 -0.01%\n- 엔비디아 +0.8%, 마이크론 -0.1%, 샌디스크 -0.7%\n- 미 10년물 금리 5.02%, 미 30년물 금리 5.36%, WTI 101.9달러",
    "paragraphs": [
        "미국 증시는 매파적이었던 9월 FOMC 결과로 상승분을 반납하면서 약세로 마감했네요.\n\n이번 인상 이외에도 연내 추가 1회 인상(12월 FOMC 유력) 가능성을 대비해야 할듯 합니다.\n\n그러나 9월 FOMC 이후 2년물 등 단기물 금리가 상승했지만, 10년물 등 장기물 금리의 상승폭이 제한됐다는 점도 생각해볼 부분입니다.\n\n장기물 금리에는 연준의 긴축 및 인플레이션 우려가 선반영됐음을 보여주는 대목이기에, 주식시장 입장에서는 향후 매크로 변수에서 추가 25bp 인상 자체보다 10년물 금리 향방, 국제 유가 향방에 더 많은 가중치를 두고 가는 것이 적절함을 시사합니다.",
        "일단 금일 국내 증시는 매파적이었던 9월 FOMC 여진을 소화하면서 변동성 확대 장세를 보일 것으로 전망합니다.\n\n지금도 그렇고 올해 금리인상 우려가 부각될 때마다 변동성이 확대된 데에는 2022년 긴축 충격에 대한 부정적인 경험이 트라우마로 작용하고 있는 측면이 있습니다.\n\n당시 17개월에 걸쳐 525bp 인상을 할 때 S&P500은 고점 대비 최대 -25%, 코스피는 고점대비 최대 -35%를 겪었기 때문입니다.\n\n그러나 역사적으로 연준의 정책 사이클과 주식시장을 살펴보면, 금리인상 자체가 증시의 추세 하락으로 이어진 경우가 많지 않았다는 점에 주목할 필요가 있습니다.",
        "연준의 첫 금리인상 이후의 흐름만 따로 분석을 해봐도 비슷하네요.\n\n1994년부터 현재까지 코스피 기준으로, 연준의 첫 금리인상 이후 코스피의 평균 수익률이 1개월 +1.4%, 3개월 +2.2%, 6개월 +3.9%를 기록했다는 점이 이를 뒷받침합니다.\n\n첫 인상 자체보다는 이후 긴축의 강도와 이익 향방이 더 중요했음을 시사하기에(+현재 국면에서는 국제 유가 향방도 추가), 이번 9월 FOMC 결과가 국내 증시의 추세를 훼손시킬 것이라고 해석하는 건 지양할 필요가 있습니다.",
        "이런 측면에서 현재 코스피의 26년 영업이익 컨센서스가 990조원대 내외로 견조한 흐름을 보이고 있다는 점은 안도 요인입니다.\n\n물론 달러/원 환율 급락(2분기 평균 환율 1,502원대 -> 3분기 평균환율 1,420원대, -5.0%)이 반도체, 자동차, 디스플레이 등 수출주들의 이익 전망에 부담으로 작용할 수 있기는 합니다.\n\n실제로 3분기 프리뷰 시즌에 진입하는 과정에서 일부 하우스들의 수출주 추정치 하향이 나타나는 움직임들이 포착되고 있으며, 이는 시간이 지날수록 3분기 컨센서스에 반영될 것으로 보이네요.",
        "결론적으로, 이번 9월 FOMC는 예상보다 매파적이었던 만큼, 이번 주 남은 기간동안 변동성 확대 압력에 직면될 수 있습니다.\n\n그러나 향후 장기금리 상승 속도 진정 및 3분기 실적시즌을 앞둔 코스피 이익 모멘텀이 유지된다는 전제 하에, FOMC 직후 시장의 해석이 충돌하는 과정에서 발생할 수 있는 변동성은 비중 축소보다 매수 기회로 활용할 필요가 있습니다.\n\n업종 측면에서는 1) 금리 상승에 따른 멀티플 부담을 EPS 증가로 상쇄할 수 있는 반도체, IT 하드웨어 등 AI 인프라와 같은 이익 모멘텀 우위 업종, 2) 금리의 부정적인 주가 민감도가 낮으면서 수익률 방어력이 있는 금융(은행, 지주, 보험) 등 주주환원 업종으로 대응해 나가는 것이 적절하지 않을까 싶네요."
    ],
    "closing": "오늘도 날씨가 무척이나 좋다고 합니다.\n공기도 맑고 낮에도 그리 덥지 않다고 하니,\n바쁘고 분주한 하루를 보내시겠지만, 중간중간 바깥 공기 쐬시면서 리프레쉬도 잘하셨으면 좋겠습니다.\n\n늘 건강도 잘 챙기시고요.\n오늘 하루도 화이팅 하시길 바랍니다.\n\n키움 한지영\n\nhttps://www.kiwoom.com/h/invest/research/VMarketSDDetailView?sqno=7198",
    "stocks": ["삼성전자", "SK하이닉스", "한미반도체", "KB금융", "신한지주", "현대차"]
}

def update_morning_briefing():
    """매일 오전 8시에 실행되어 글로벌 시장 데이터를 기반으로 요약을 갱신하는 함수"""
    global morning_briefing_data
    now_str = datetime.datetime.now().strftime('%m/%d')
    # 실제 운영 시 이 부분에 크롤링 또는 LLM API 연동 코드를 넣어 갱신할 수 있습니다.
    morning_briefing_data["date_title"] = f"{now_str}, 장 시작 전 생각: 글로벌 증시 동향 및 주요 매크로 점검, 키움 한지영 스타일"
    print(f"[{datetime.datetime.now()}] 장전 5분 마켓 핵심 요약 데이터가 아침 8시 기준으로 자동 갱신되었습니다.")

# APScheduler 백그라운드 스케줄러 설정 (매일 오전 8시 0분 실행)
scheduler = BackgroundScheduler()
scheduler.add_job(update_morning_briefing, 'cron', hour=8, minute=0)
scheduler.start()

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
    
    news_list = [
        {'title': '연준, 금리 인하 기대감 속 물가 지표 주시', 'link': '#', 'type': '중립', 'comment': '발표될 지표에 따라 변동성 확대 가능성', 'stock': '전체 시장'},
        {'title': '반도체 수출 호조세 지속… 메모리 가격 반등', 'link': '#', 'type': '호재', 'comment': '실적 개선 기대감 선반영 구간', 'stock': '삼성전자, SK하이닉스'},
        {'title': '정부, 밸류업 프로그램 세제 혜택 가시화', 'link': '#', 'type': '호재', 'comment': '저PBR 종목군 저가 매수세 지속 유입', 'stock': 'KB금융, 신한지주'},
        {'title': '중국 경기 회복 지연 우려에 원자재 가격 조정', 'link': '#', 'type': '악재', 'comment': '철강 및 화학 섹터 단기 수급 부담', 'stock': 'POSCO홀딩스, LG화학'},
        {'title': '글로벌 AI 인프라 투자 확대 가속화', 'link': '#', 'type': '호재', 'comment': '서버 및 기판 관련 부품주 동반 강세', 'stock': '이수페타시스, 대덕전자'},
        {'title': '환율 변동성 확대… 외국인 수급 주의보', 'link': '#', 'type': '중립', 'comment': '환율 1,350원 안착 여부 모니터링 필요', 'stock': '외인 수급 대형주'},
        {'title': '2차전지 유럽 전기차 보조금 축소 여파', 'link': '#', 'type': '악재', 'comment': '셀 메이커 및 소재 업체 주가 하방 압력', 'stock': 'LG에너지솔루션, 포스코퓨처엠'},
        {'title': '로봇 및 인공지능 관련 정부 정책 모멘텀', 'link': '#', 'type': '호재', 'comment': '개별 종목별 순환매 장세 전개', 'stock': '레인보우로보틱스, 두산로보틱스'},
        {'title': '해운 운임 지수 소폭 반등세 기록', 'link': '#', 'type': '중립', 'comment': '지속성 여부는 글로벌 물동량에 연동', 'stock': 'HMM'},
        {'title': '바이오 섹터 신약 기술 수출 기대감 유효', 'link': '#', 'type': '호재', 'comment': '임상 결과 발표 앞둔 종목들 변동성 주의', 'stock': '셀트리온, 유한양행'}
    ]
    
    ai_briefing = (
        "📊 [시황 총평]\n"
        "미국 증시 혼조세 및 국내 반도체 중심의 수급 유입으로 양시장 완만한 반등 흐름이 전개되고 있습니다.\n\n"
        "🔍 [핵심 체크포인트]\n"
        "• 외국인 및 기관의 코스피 대형주 순매수 지속 여부\n"
        "• 원달러 환율의 1,350원선 안착 및 변동성 추이\n"
        "• 주요 빅테크 실적 및 글로벌 반도체 수출 지표\n\n"
        "💡 [실전 대응 가이드]\n"
        "• 추격 매수보다는 주도주 조정 시 분할 매수 관점 접근\n"
        "• 환율 및 대외 변수에 따른 리스크 관리 병행"
    )

    return render_template('index.html', 
                           quotes=quotes, 
                           theme_summary=theme_summary,
                           smart_money_summary=smart_money_summary,
                           strategies=strategies,
                           morning_briefing=morning_briefing_data,
                           news_list=news_list,
                           ai_briefing=ai_briefing,
                           categories=[{}, {}, {'stocks': [{'code': 'usdkrw', 'name': '원/달러 환율'}, {'code': 'wti', 'name': 'WTI 원유'}, {'code': 'gold', 'name': '국제 금'}]}] )

@app.route('/api/quotes', methods=['GET'])
def api_quotes():
    return jsonify(get_mock_quotes())

@app.route('/api/ai-briefing', methods=['GET'])
def api_ai_briefing():
    now = datetime.datetime.now().strftime('%H:%M:%S')
    new_briefing = (
        f"📊 [시황 총평 - {now} 갱신]\n"
        f"실시간 수급 데이터 분석 결과, 외국인 매수세가 반도체 소부장 및 자동차 섹터로 집중되며 지수 하방을 견조하게 지지하고 있습니다.\n\n"
        f"🔍 [핵심 체크포인트]\n"
        f"• 양시장 거래대금 증가 여부 및 코스닥 주도 테마 순환매 속도\n"
        f"• 환율 안정화 흐름에 따른 외국인 선물 수급 동향\n\n"
        f"💡 [실전 대응 가이드]\n"
        f"• 지수 반등 시 단기 과열권 종목은 차익실현 우선\n"
        f"• 실적 모멘텀이 확실한 핵심 주도주 위주로 압축 대응"
    )
    return jsonify({"ai_briefing": new_briefing})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
