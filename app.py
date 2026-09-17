def api_quotes():
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
            except Exception:
                pass

    news_list = fetch_naver_finance_news()
    ai_briefing_text = generate_ai_comprehensive_briefing(price_map, news_list)
    return json.dumps({"ai_briefing": ai_briefing_text}, ensure_ascii=False)

if __name__ == '__main__':
    app.run(debug=True)
