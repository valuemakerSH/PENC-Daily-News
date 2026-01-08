import os
import smtplib
import feedparser
import time
import urllib.parse
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import google.generativeai as genai

# --- 환경 변수 ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVERS = os.environ.get("EMAIL_RECEIVERS")

# --- 설정: 키워드 및 카테고리 매핑 ---
CATEGORY_MAP = {
    "자재/시황": [
        "건설 원자재 가격", "건설 자재 환율 유가", "납품대금 연동제 건설"
    ],
    "공급망/물류": [
        "건설 노조 파업 노란봉투법", "화물연대 레미콘 운송 파업", 
        "해상 운임 SCFI 건설", "건설 현장 인력난 외국인"
    ],
    "전사/리스크": [
        "포스코이앤씨", "공정위 하도급 건설", "건설 중대재해처벌법", "건설산업기본법 개정"
    ],
    "미래/혁신/ESG": [
        "건설사 협력사 ESG", "건설 동반성장 상생", 
        "스마트 건설 모듈러 OSC", "주요 건설사 구매 동향"
    ]
}

# 키워드 리스트 생성 (검색용)
KEYWORDS = [k for category in CATEGORY_MAP.values() for k in category]

# 불필요한 노이즈 차단
EXCLUDE_KEYWORDS = [
    "특징주", "테마주", "관련주", "주가", "급등", "급락", "상한가", "하한가",
    "거래량", "매수", "매도", "목표가", "체결", "증시", "종목", "투자자",
    "지수", "코스피", "코스닥", "마감",
    "치킨", "맥주", "식품", "마트", "백화점", "여행", "게임", "화장품",
    "카지노", "바카라", "토토", "슬롯", "홀덤", "포커", "도박", "배팅", "잭팟",
    "룰렛", "블랙잭", "성인", "만남", "출장", "마사지", "대출", "금리인하요구권",
    "코인", "비트코인", "가상화폐", "리딩방"
]

def get_korea_time():
    utc_now = datetime.now(timezone.utc)
    kst_now = utc_now + timedelta(hours=9)
    return kst_now

def is_spam_news(title):
    for bad_word in EXCLUDE_KEYWORDS:
        if bad_word in title: return True
    return False

def is_recent(published_str):
    if not published_str: return False
    try:
        pub_date = parsedate_to_datetime(published_str)
        if pub_date.tzinfo:
            pub_date = pub_date.astimezone(timezone.utc)
        else:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        one_day_ago = now_utc - timedelta(hours=24)
        return pub_date > one_day_ago
    except:
        return True

def get_category(keyword):
    for cat, keywords in CATEGORY_MAP.items():
        if keyword in keywords:
            return cat
    return "기타"

def fetch_news():
    news_items = []
    print("🔍 뉴스 수집 시작...")
    
    for keyword in KEYWORDS:
        negative_query = " -주식 -종목 -테마 -특징주"
        encoded_query = urllib.parse.quote(f"{keyword}{negative_query} when:1d")
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        
        try:
            feed = feedparser.parse(url)
            if not feed.entries and hasattr(feed, 'bozo_exception'): pass

            valid_count = 0
            for entry in feed.entries[:20]: 
                if valid_count >= 10: break 

                if is_recent(entry.published):
                    if is_spam_news(entry.title): continue

                    if not any(item['link'] == entry.link for item in news_items):
                        news_items.append({
                            "id": len(news_items),
                            "title": entry.title,
                            "link": entry.link,
                            "keyword": keyword,
                            "category": get_category(keyword),
                            "date": entry.published
                        })
                        valid_count += 1
        except Exception as e:
            print(f"⚠️ '{keyword}' 오류: {e}")
            continue
            
    print(f"✅ 총 {len(news_items)}개의 최신 뉴스 수집 완료.")
    return news_items

def generate_analysis_data(news_items):
    if not news_items: return None
    
    kst_now = get_korea_time()
    today_formatted = kst_now.strftime("%Y년 %m월 %d일") 
    
    print("🧠 AI 분석 시작 (JSON 모드)...")
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-09-2025')

        news_text = ""
        for item in news_items:
            news_text += f"ID:{item['id']} | [{item['category']}] {item['title']}\n"

        prompt = f"""
        오늘은 {today_formatted}입니다.
        당신은 포스코이앤씨 구매계약실의 수석 애널리스트입니다.
        
        [뉴스 목록]
        {news_text}

        [임무]
        1. 전체적인 **시장 날씨 요약** (1~2문장).
        2. 위 목록에서 구매 업무에 가장 중요한 **핵심 기사 3~5개**를 선정하여 심층 분석(Deep Dive).
        
        [필수 출력 형식 (JSON)]
        ```json
        {{
            "weather_summary": "시장 날씨 요약 문구 (날씨 아이콘 포함)",
            "selected_cards": [
                {{
                    "id": 뉴스ID(숫자),
                    "summary": "핵심 내용 요약 (3문장 내외, 수치 포함)",
                    "insight": "구매계약실 대응 방안 (2문장)",
                    "risk_level": "Critical" 또는 "Warning" 또는 "Info"
                }}
            ]
        }}
        ```
        """
        
        response = model.generate_content(prompt)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)

    except Exception as e:
        print(f"❌ AI 분석 중 오류: {e}")
        return None

def build_html_report(ai_data, news_items):
    kst_now = get_korea_time()
    today_str = kst_now.strftime("%Y년 %m월 %d일")

    selected_map = {item['id']: item for item in ai_data['selected_cards']}
    
    grouped_news = {cat: [] for cat in CATEGORY_MAP.keys()}
    grouped_news["기타"] = []
    
    for item in news_items:
        cat = item['category']
        if cat in grouped_news:
            grouped_news[cat].append(item)
        else:
            grouped_news["기타"].append(item)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: 'Pretendard', 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333; background-color: #f2f4f7; margin: 0; padding: 0; }}
        .email-container {{ max-width: 850px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
        .header {{ background-color: #0054a6; color: #ffffff; padding: 40px 50px; }}
        .content {{ padding: 50px; }}
        
        .weather-box {{ background-color: #eaf4fc; padding: 25px; border-radius: 12px; margin-bottom: 50px; border: 1px solid #dbeafe; }}
        .weather-title {{ margin: 0 0 10px 0; color: #0054a6; font-size: 20px; font-weight: 700; }}
        
        .cat-title {{ font-size: 22px; color: #111; margin: 60px 0 20px 0; border-left: 5px solid #0054a6; padding-left: 15px; font-weight: 700; }}
        
        .card {{ background-color: #ffffff; border: 1px solid #eaecf0; border-radius: 16px; padding: 30px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }}
        .card-title {{ font-size: 20px; font-weight: 700; color: #101828; margin-bottom: 12px; line-height: 1.4; word-break: keep-all; }}
        .card-body {{ font-size: 16px; color: #475467; line-height: 1.7; margin-bottom: 20px; word-break: keep-all; }}
        
        .insight-table {{ width: 100%; border-collapse: separate; border-spacing: 0; margin-bottom: 20px; border-radius: 8px; }}
        .insight-label {{ padding: 15px; width: 1%; white-space: nowrap; vertical-align: top; font-weight: 700; font-size: 15px; }}
        .insight-text {{ padding: 15px; font-size: 15px; line-height: 1.6; vertical-align: top; word-break: keep-all; }}
        
        .risk-Critical {{ background-color: #fdecea; color: #d32f2f; }}
        .risk-Warning {{ background-color: #fff4e5; color: #ed6c02; }}
        .risk-Info {{ background-color: #f0f9ff; color: #0288d1; }}
        
        .btn {{ display: inline-block; background-color: #fff; color: #344054; border: 1px solid #d0d5dd; padding: 8px 16px; text-decoration: none; border-radius: 6px; font-size: 13px; font-weight: 600; }}
        
        .headline-box {{ background-color: #f9fafb; padding: 20px; border-radius: 8px; margin-top: 10px; }}
        .headline-title {{ font-size: 15px; font-weight: 700; color: #667085; margin-bottom: 10px; }}
        .headline-item {{ margin-bottom: 8px; font-size: 14px; color: #555; list-style: none; }}
        .headline-link {{ text-decoration: none; color: #4b5563; transition: color 0.2s; word-break: keep-all; }}
        .headline-link:hover {{ color: #0054a6; text-decoration: underline; }}

        /* 이스터에그 스타일 (배경색과 동일하게 숨김 처리) */
        .easter-egg {
            margin-top: 30px;
            font-size: 11px;
            color: #101828; /* 푸터 배경색과 동일하게 설정하여 숨김 */
            cursor: help;
            transition: all 0.5s ease;
            text-align: center;
            letter-spacing: 1px;
        }
        .easter-egg:hover {
            color: #ff6b6b; /* 마우스 오버 시 색상 등장 */
            transform: scale(1.05);
            font-weight: bold;
        }
    </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <h1 style="margin:0; font-size:28px;">Daily Market & Risk Briefing</h1>
                <div style="margin-top:10px; opacity:0.9;">POSCO E&C 구매계약실 | {today_str}</div>
            </div>
            <div class="content">
                <div class="weather-box">
                    <h2 class="weather-title">🌤️ Today's Market Weather</h2>
                    <div style="font-size: 17px;">{ai_data.get('weather_summary', '시장 분석 데이터 없음')}</div>
                </div>
    """

    for cat_name, items in grouped_news.items():
        if not items: continue

        html += f'<div class="cat-title">[{cat_name}]</div>'
        
        # 상세 카드
        for item in items:
            if item['id'] in selected_map:
                ai_info = selected_map[item['id']]
                risk_level = ai_info.get('risk_level', 'Info')
                
                bg_color = "#f0f9ff"
                text_color = "#0288d1"
                if risk_level == 'Critical': 
                    bg_color, text_color = "#fdecea", "#d32f2f"
                elif risk_level == 'Warning':
                    bg_color, text_color = "#fff4e5", "#ed6c02"

                html += f"""
                <div class="card">
                    <div class="card-title">{item['title']}</div>
                    <div class="card-body">{ai_info['summary']}</div>
                    
                    <table class="insight-table" style="background-color: {bg_color};">
                        <tr>
                            <td class="insight-label" style="color: {text_color};">💡 Insight:</td>
                            <td class="insight-text" style="color: {text_color};">{ai_info['insight']}</td>
                        </tr>
                    </table>
                    <div style="text-align: right;">
                        <a href="{item['link']}" class="btn" target="_blank">🔗 원문 기사 보기</a>
                    </div>
                </div>
                """
        
        # 단신 리스트
        headlines = [item for item in items if item['id'] not in selected_map]
        
        if headlines:
            html += f"""
            <div class="headline-box">
                <div class="headline-title">📌 관련 주요 단신</div>
                <ul style="padding-left: 20px; margin: 0;">
            """
            for h_item in headlines:
                html += f"""
                <li class="headline-item">
                    <a href="{h_item['link']}" class="headline-link" target="_blank">{h_item['title']}</a>
                </li>
                """
            html += "</ul></div>"

    # 푸터 (수정됨)
    html += """
                <div style="background-color: #101828; padding: 40px; text-align: center; color: #98a2b3; font-size: 14px;">
                    <p>본 리포트는 AI Agent 시스템에 의해 실시간으로 생성되었습니다.</p>
                    <p>문의: 구매계약기획그룹 송승호 프로 | © POSCO E&C</p>
                    <div class="easter-egg">
                        오? 저를 발견하셨군요! 연락주시면 커피 한잔 사드릴께요 ☕
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_email(html_body):
    if not html_body: return
    
    kst_now = get_korea_time()
    today_str = kst_now.strftime("%Y년 %m월 %d일")
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVERS
    msg['Subject'] = f"[Daily] {today_str} 구매계약실 시장 동향 보고"
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        receivers = [r.strip() for r in EMAIL_RECEIVERS.split(',')]
        server.sendmail(EMAIL_SENDER, receivers, msg.as_string())
        server.quit()
        print(f"📧 발송 성공: {len(receivers)}명")
    except Exception as e:
        print(f"❌ 발송 실패: {e}")

if __name__ == "__main__":
    if not GOOGLE_API_KEY:
        print("❌ API Key가 설정되지 않았습니다.")
    else:
        items = fetch_news()
        if items:
            ai_data = generate_analysis_data(items)
            if ai_data:
                final_html = build_html_report(ai_data, items)
                send_email(final_html)
            else:
                print("❌ AI 분석 데이터 생성 실패")
        else:
            print("수집된 뉴스가 없습니다.")
