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
