def fetch_realtime_data(ticker):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://stock.naver.com/'
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

        # 2. 해외 증시 선물 폴링 API (예: NQcv1)
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

        # 3. 원자재(WTI 원유) API
        elif ticker == 'NAVER_ENERGY_WTI':
            api_url = "https://stock.naver.com/api/securityService/marketindex/energy/CLcv1"
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=5) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                # 단일 객체이거나 리스트 형태일 수 있으므로 방어적 처리
                item = res_json[0] if isinstance(res_json, list) else res_json
                cur_price = item.get('closePrice') or item.get('nowValue') or item.get('price')
                fluc_rate = item.get('fluctuationsRatio') or item.get('rate') or 0
                sign = str(item.get('sign', ''))
                
                if cur_price is not None:
                    price_val = float(str(cur_price).replace(',', ''))
                    rate_val = float(str(fluc_rate).replace('%', '').replace('+', '')) if fluc_rate else 0.0
                    is_up = not (sign in ['4', '5'] or str(fluc_rate).startswith('-'))
                    return {'price': f"{price_val:,.2f}", 'rate': f"{rate_val:+.2f}%", 'is_up': is_up}

        # 4. 금현물 폴링 API
        elif ticker == 'NAVER_METAL_GOLD':
            api_url = "https://polling.finance.naver.com/api/realtime/marketindex/metals/GCcv1"
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

        # 5. 원/달러 환율 API
        elif ticker == 'NAVER_EXCHANGE_USD':
            api_url = "https://stock.naver.com/api/stockSecurity/exchange-rates/v2/USD?bankType=hana&size=20"
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=5) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                list_data = res_json.get('list', []) or res_json.get('datas', []) or (res_json if isinstance(res_json, list) else [])
                if list_data:
                    item = list_data[0]
                    cur_price = item.get('dealBasRate') or item.get('closePrice') or item.get('nowValue') or item.get('price')
                    fluc_rate = item.get('fluctuationsRatio') or item.get('rate') or 0
                    sign = str(item.get('sign', ''))
                    
                    if cur_price is not None:
                        price_val = float(str(cur_price).replace(',', ''))
                        rate_val = float(str(fluc_rate).replace('%', '').replace('+', '')) if fluc_rate else 0.0
                        is_up = not (sign in ['4', '5'] or str(fluc_rate).startswith('-'))
                        return {'price': f"{price_val:,.2f}", 'rate': f"{rate_val:+.2f}%", 'is_up': is_up}

    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        
    return {'price': '0.00', 'rate': '+0.00%', 'is_up': True}
