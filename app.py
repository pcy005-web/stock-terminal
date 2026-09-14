from flask import Flask, render_template
import FinanceDataReader as fdr
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/')
def index():
    try:
        # 최근 5일간의 데이터 가져오기 (주말/휴일 대비)
        end_date = datetime.today().strftime('%Y-%m-%d')
        start_date = (datetime.today() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # 코스피, 코스닥, 나스닥 지수 심볼
        symbols = {
            'kospi': 'KS11',
            'kosdaq': 'KQ11',
            'nasdaq': 'IXIC'
        }
        
        data = {}
        for key, symbol in symbols.items():
            df = fdr.DataReader(symbol, start_date, end_date)
            if not df.empty and len(df) >= 2:
                current_price = df['Close'].iloc[-1]
                prev_close = df['Close'].iloc[-2]
                change_rate = ((current_price - prev_close) / prev_close) * 100
            elif not df.empty:
                current_price = df['Close'].iloc[-1]
                change_rate = 0.0
            else:
                raise Exception("데이터 없음")
                
            data[key] = {
                'price': f"{current_price:,.2f}",
                'rate': f"{change_rate:+.2f}%",
                'is_up': change_rate >= 0
            }
            
    except Exception as e:
        # 오류 발생 시 확인용 메시지 표시
        data = {
            'kospi': {'price': '조회 중단(API 제한)', 'rate': '0.00%', 'is_up': True},
            'kosdaq': {'price': '조회 중단(API 제한)', 'rate': '0.00%', 'is_up': True},
            'nasdaq': {'price': '조회 중단(API 제한)', 'rate': '0.00%', 'is_up': True},
        }

    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
