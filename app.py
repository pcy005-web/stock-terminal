def fetch_realtime_data(ticker):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://stock.naver.com/market/stock/kr',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    }

    try:
        # 1. 국내 지수 및 선물 폴링 API
        if ticker.startswith('NAVER_DOMESTIC_'):
            target = ticker.replace('NAVER_DOMESTIC_', '')
            api_url = f"https://polling.finance.naver.com/api/realtime/domestic/index/{target}"
            
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=5) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                stocks_data = res_json.get('datas', [])
                if not stocks_data and 'result' in res_json:
                    stocks_data = res_json.get('result', {}).get('datas', [])
                
                if stocks_data:
                    item = stocks_data[0]
                    cur_price = item.get('closePrice') or item.get('nowValue') or item.get('price')
                    fluc_rate = item.get('fluctuationsRatio') or item.get('rate') or 0
                    sign = str(item.get('sign', ''))
                    
                    if cur_price is not None:
                        price_val = float(str(cur_price).replace(',', ''))
                        rate_val = float(str(fluc_rate).replace('%', '').replace('+', '')) if fluc_rate else 0.0
                        is_up = not (sign in ['4', '5'] or str(fluc_rate).startswith('-'))
                        return {'price': f"{price_val:,.2f}", 'rate': f"{rate_val:+.2f}%", 'is_up': is_up}

        # 2. 해외 증시 선물 폴링 API
        elif ticker.startswith('NAVER_WORLD_'):
            symbol_map = {'ES': 'EScv1', 'NQ': 'NQcv1'}
            symbol = symbol_map.get(ticker.replace('NAVER_WORLD_', ''), 'NQcv1')
            api_url = f"https://polling.finance.naver.com/api/realtime/worldstock/futures/{symbol}"
            
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=5) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                stocks_data = res_json.get('datas', [])
                if not stocks_data and 'result' in res_json:
                    stocks_data = res_json.get('result', {}).get('datas', [])
                
                if stocks_data:
                    item = stocks_data[0]
                    cur_price = item.get('closePrice') or item.get('nowValue') or item.get('price')
                    fluc_rate = item.get('fluctuationsRatio') or item.get('rate') or 0
                    sign = str(item.get('sign', ''))
                    
                    if cur_price is not None:
                        price_val = float(str(cur_price).replace(',', ''))
                        rate_val = float(str(fluc_rate).replace('%', '').replace('+', '')) if fluc_rate else 0.0
                        is_up = not (sign in ['4', '5'] or str(fluc_rate).startswith('-'))
                        return {'price': f"{price_val:,.2f}", 'rate': f"{rate_val:+.2f}%", 'is_up': is_up}

        # 3. 원자재 및 기타 지표 예외 방어 처리 (오류 발생 시 기본값으로 안전 우회)
        else:
            api_url = None
            if ticker == 'NAVER_ENERGY_WTI':
                api_url = "https://stock.naver.com/api/securityService/marketindex/energy/CLcv1"
            elif ticker == 'NAVER_METAL_GOLD':
                api_url = "https://polling.finance.naver.com/api/realtime/marketindex/metals/GCcv1"
            elif ticker == 'NAVER_EXCHANGE_USD':
                api_url = "https://stock.naver.com/api/stockSecurity/exchange-rates/v2/USD?bankType=hana&size=20"

            if api_url:
                req = urllib.request.Request(api_url, headers=headers)
                with urllib.request.urlopen(req, context=get_ssl_context(), timeout=5) as response:
                    res_json = json.loads(response.read().decode('utf-8'))
                    
                    # 리스트나 딕셔너리 구조 유연하게 파싱
                    item = None
                    if isinstance(res_json, list) and len(res_json) > 0:
                        item = res_json[0]
                    elif isinstance(res_json, dict):
                        item = res_json.get('list', [res_json])[0] if 'list' in res_json else res_json.get('datas', [res_json])[0]
                    
                    if item:
                        cur_price = item.get('dealBasRate') or item.get('closePrice') or item.get('nowValue') or item.get('price')
                        fluc_rate = item.get('fluctuationsRatio') or item.get('rate') or 0
                        sign = str(item.get('sign', ''))
                        
                        if cur_price is not None:
                            price_val = float(str(cur_price).replace(',', ''))
                            rate_val = float(str(fluc_rate).replace('%', '').replace('+', '')) if fluc_rate else 0.0
                            is_up = not (sign in ['4', '5'] or str(fluc_rate).startswith('-'))
                            return {'price': f"{price_val:,.2f}", 'rate': f"{rate_val:+.2f}%", 'is_up': is_up}

    except Exception as e:
        # 통신 에러나 네이버 차단 시 서버가 뻗지 않고 로그만 남긴 뒤 안전한 기본값 반환
        print(f"통신 에러 발생 ({ticker}): {e}")
        pass
        
    # 에러 발생 시 화면이 깨지지 않도록 출력할 기본 대체 데이터
    return {'price': '0.00', 'rate': '+0.00%', 'is_up': True}
