from flask import Flask, render_template
import urllib.request
import json

app = Flask(__name__)

def fetch_naver_index(code):
    try:
        # 국내 및 해외 지수를 모두 지원하는 네이버 모바일 금융 API 엔드포인트
        url = f"https://m.stock.naver.com/api/index/{code}/basic"
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
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

@app.route('/')
def index():
    # 코스피(KOSPI), 코스닥(KOSDAQ), 나스닥100(NAS@NDX) 지수 연동
    kospi = fetch_naver_index('KOSPI') or {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}
    kosdaq = fetch_naver_index('KOSDAQ') or {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}
    nasdaq = fetch_naver_index('NAS@NDX') or {'price': '데이터 확인중', 'rate': '0.00%', 'is_up': True}

    data = {
        'kospi': kospi,
        'kosdaq': kosdaq,
        'nasdaq': nasdaq,
    }
    
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
