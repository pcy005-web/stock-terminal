from flask import Flask, render_template
import yfinance as yf

app = Flask(__name__)

@app.route('/')
def index():
    try:
        # 야후 파이낸스에서 주요 지수 가져오기 (코스피: ^KS11, 코스닥: ^KQ11, 나스닥100: ^NDX)
        tickers = {
            'kospi': '^KS11',
            'kosdaq': '^KQ11',
            'nasdaq': '^NDX'
        }
        
        data = {}
        for key, symbol in tickers.items():
            t = yf.Ticker(symbol)
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
        # 에러 발생 시 기본값 처리
        data = {
            'kospi': {'price': '데이터 로드 실패', 'rate': '0.00%', 'is_up': True},
            'kosdaq': {'price': '데이터 로드 실패', 'rate': '0.00%', 'is_up': True},
            'nasdaq': {'price': '데이터 로드 실패', 'rate': '0.00%', 'is_up': True},
        }

    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
