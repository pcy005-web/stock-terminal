    ]

def generate_ai_comprehensive_briefing(quotes, news_list):
    nasdaq_fut = quotes.get('nasdaq_fut', {'price': '-', 'rate': '+0.00%'})
    usdkrw = quotes.get('usdkrw', {'price': '-', 'rate': '+0.00%'})
    top_news = news_list[0]['title'] if news_list else "경제 속보 모니터링 중"
    return f"[실시간 AI 마켓 종합 분석]\n- 나스닥 선물: {nasdaq_fut['rate']}\n- 환율: {usdkrw['price']}원\n- 주요 이슈: {top_news}\n- 종합 제언: 글로벌 매크로 변동성 속 주도주 및 방어주 분산 대응 권장"

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
