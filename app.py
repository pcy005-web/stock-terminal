from flask import Flask, render_template
import urllib.request
import json

app = Flask(__name__)

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
            sign = res_data.get('sign', '3')
            
            is_up = sign in ['1', '2']
            formatted_rate = f"+{rate}%" if is_up and not rate.startswith('+') and not rate.startswith('-') else f"{rate}%"
            
            return {
                'price': price,
                'rate': formatted_rate,
                'is_up': is_up
            }
    except Exception:
        return None

def fetch_nasdaq100_index():
    try:
        # 야후 파이낸스에서 나스닥 100 실제 지수(^NDX)를 올바른 URL 인코딩(%5E)으로 호출
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENDX?interval=1d&range=2d"
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            result = res_data['chart']['result'][0]
            meta = result['meta']
            
            current_price = meta['regularMarketPrice']
            prev_close = meta.get('chartPreviousClose', meta.get('previousClose', current_price))
            
            change = current_price - prev_close
            change_rate = (change / prev_close) * 100
            is_up = change >= 0
            
            return {
                'price': f"{current_price:,.2f}",
                'rate': f"{change_rate:+.2f}%",
                'is_up': is_up
            }
    except Exception:
        return None

@app.route('/')
def index():
    kospi = fetch_naver_index('KOSPI') or {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}
    kosdaq = fetch_naver_index('KOSDAQ') or {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}
    
    # QQQ 대신 실제 나스닥 100 지수 수치(^NDX)를 반영
    nasdaq = fetch_nasdaq100_index() or {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}

    data = {
        'kospi': kospi,
        'kosdaq': kosdaq,
        'nasdaq': nasdaq,
    }
    
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
