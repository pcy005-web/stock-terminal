def fetch_realtime_data(ticker):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://stock.naver.com/',
        'Accept': 'application/json, text/plain, */*'
    }

    try:
        api_url = None

        # 1. 국내 지수 및 선물 (Polling API)
        if ticker.startswith('NAVER_DOMESTIC_'):
            target = ticker.replace('NAVER_DOMESTIC_', '')
            api_url = f"https://polling.finance.naver.com/api/realtime/domestic/index/{target}"

        # 2. 해외 증시 선물 (Polling API)
        elif ticker.startswith('NAVER_WORLD_'):
            symbol_map = {'ES': 'EScv1', 'NQ': 'NQcv1'}
            symbol = symbol_map.get(ticker.replace('NAVER_WORLD_', ''), 'NQcv1')
            api_url = f"https://polling.finance.naver.com/api/realtime/worldstock/futures/{symbol}"

        # 3. 원자재 - WTI 원유 (Polling API 규격 적용)
        elif ticker == 'NAVER_ENERGY_WTI':
            api_url = "https://stock.naver.com/api/securityFe/api/fchart/marketindex/energy/CLcv1"

        # 4. 금현물 (Polling API)
        elif ticker == 'NAVER_METAL_GOLD':
            api_url = "https://polling.finance.naver.com/api/realtime/marketindex/metals/GCcv1"

        # 5. 원/달러 환율 (Polling API 규격 적용)
        elif ticker == 'NAVER_EXCHANGE_USD':
            api_url = "https://stock.naver.com/api/stockSecurity/exchange-rates/v2/USD?bankType=hana&size=20"

        if api_url:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=5) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                
                # 네이버 폴링 API 공통 응답 구조 파싱 (datas 또는 result.datas)
                stocks_data = res_json.get('datas', [])
                if not stocks_data and 'result' in res_json:
                    stocks_data = res_json.get('result', {}).get('datas', [])
                # 단일 객체로 떨어지는 경우 방어
                if not stocks_data and isinstance(res_json, dict):
                    stocks_data = [res_json]

                if stocks_data:
                    item = stocks_data[0]
                    # 네이버 폴링 API의 다양한 가격 필드명 대응
                    cur_price = item.get('closePrice') or item.get('nowValue') or item.get('price') or item.get('dealBasRate')
                    fluc_rate = item.get('fluctuationsRatio') or item.get('rate') or 0
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

    except Exception as e:
        print(f"통신 에러 발생 ({ticker}): {e}")
        pass
        
    # 오류 발생 시 화면 깨짐 방지용 기본값
    return {'price': '0.00', 'rate': '+0.00%', 'is_up': True}
