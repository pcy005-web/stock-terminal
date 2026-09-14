from flask import Flask, render_template
import urllib.request
import json

app = Flask(__name__)

@app.route('/')
def index():
    # Vercel 환경에서 안정적으로 동작하도록 기본 데이터 구조 제공
    # 추후 외부 API 연동 시 이곳을 수정할 수 있습니다.
    data = {
        'kospi': {'price': '2,680.15', 'rate': '+0.75%', 'is_up': True},
        'kosdaq': {'price': '775.40', 'rate': '-0.32%', 'is_up': False},
        'nasdaq': {'price': '18,518.61', 'rate': '+1.12%', 'is_up': True},
    }
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
