from flask import Flask, render_template
import yfinance as yf
from requests import Session

app = Flask(__name__)

@app.route('/')
def index():
    try:
        # 야후 파이낸스 차단 우회를 위한 세션 설정
        session = Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        
        tickers = {
            'kospi': '^KS11',
            'kosdaq': '^KQ11',
            'nasdaq': '^NDX'
        }
        
        data = {}
        for key, symbol in tickers.items():
            t = yf.Ticker(symbol, session=session)
            todays_data = t.history(period='2d')
            
            if len(todays_data) >= 2:
                current_price = todays_data['Close'].iloc[-1]
                prev_close = todays_data['Close'].iloc[-2]
                change_rate = ((current_price - prev_close) / prev_close) * 100
            else:
                current_price = todays_data['Close'].iloc[-1]
                change_rate = 0.0
                
            data[key] = {
                'price': f"{current_price:,.2f}",
                'rate': f"{change_rate:+.2f}%",
                'is_up': change_rate >= 0
            }
            
    except Exception as e:
        # 에러 원인 확인용
        err_msg = str(e)
        data = {
            'kospi': {'price': f"에러: {err_msg[:15]}", 'rate': '0.00%', 'is_up': True},
            'kosdaq': {'price': '데이터 로드 실패', 'rate': '0.00%', 'is_up': True},
            'nasdaq': {'price': '데이터 로드 실패', 'rate': '0.00%', 'is_up': True},
        }

    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
