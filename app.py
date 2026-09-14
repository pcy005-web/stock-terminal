from flask import Flask, render_template
import urllib.request
import json

app = Flask(__name__)

# 네이버 금융 API를 통한 국내 지수 조회 (코스피, 코스닥)
def fetch_naver_index(code):
    try:
        url = f"https://m.stock.naver.com/api/index/{code}/basic"
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            
            price = res_data.get('closePrice', '0')
            rate = res_data.get('fluctuationsRatio', '0')
            sign = res_data.get('sign', '3') # 1, 2: 상승 / 4, 5: 하락
            
            is_up = sign in ['1', '2']
            formatted_rate = f"+{rate}%" if is_up and not rate.startswith('+') and not rate.startswith('-') else f"{rate}%"
            
            return {
                'price': price,
                'rate': formatted_rate,
                'is_up': is_up
            }
    except Exception:
        return None

# 인베스팅닷컴 등 대체 퍼블릭 API 또는 네이버 해외 지수 API 활용 (나스닥 100)
def fetch_nasdaq_index():
    try:
        # 네이버 해외증시 API 경로 활용 (나스닥 100 심볼: NAS@NDX 또는 WN@IXIC 등)
        url = "https://m.stock.naver.com/front-api/external/worldStock/basic?symbol=NAS@NDX"
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            
            price = res_data.get('closePrice', '0')
            rate = res_data.get('fluctuationsRatio', '0')
            sign = res_data.get('sign', '3')
            
            is_up = sign in ['1', '2']
            formatted_rate = f"+{rate}%" if is_up and not rate.startswith('+') and not rate.startswith('-') else f"{rate}%"
            
            return {
                'price': price,
                'rate': formatted_rate,
                'is_up': is_up
            }
    except Exception:
        # 실패 시 야후 대안 엔드포인트 시도
        try:
            url = "https://query2.finance.yahoo.com/v7/finance/quote?symbols=^NDX"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                res = json.loads(response.read().decode('utf-8'))
                q = res['quoteResponse']['result'][0]
                price = f"{q['regularMarketPrice']:,.2f}"
                rate = q['regularMarketChangePercent']
                is_up = rate >= 0
                return {
                    'price': price,
                    'rate': f"{rate:+.2f}%",
                    'is_up': is_up
                }
        except Exception:
            return None

@app.route('/')
def index():
    # 코스피, 코스닥은 네이버 API로 정확하게 연동
    kospi = fetch_naver_index('KOSPI') or {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}
    kosdaq = fetch_naver_index('KOSDAQ') or {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}
    
    # 나스닥 100 연동
    nasdaq = fetch_nasdaq_index() or {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}

    data = {
        'kospi': kospi,
        'kosdaq': kosdaq,
        'nasdaq': nasdaq,
    }
    
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
