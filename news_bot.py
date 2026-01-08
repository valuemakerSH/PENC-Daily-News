import os
import smtplib
import feedparser
import time
import urllib.parse
import json # JSON 처리를 위한 모듈 추가
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import google.generativeai as genai

# --- 환경 변수 설정 (GitHub Secrets) ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVERS = os.environ.get("EMAIL_RECEIVERS")

# --- 설정: 키워드 및 필터 ---
KEYWORDS = [
    "포스코이앤씨", 
    "건설 원자재 가격", 
    "공정위 하도급 건설", 
    "건설 중대재해처벌법",
    "건설사 협력사 ESG",
    "주요 건설사 구매 동향",
    "건설 자재 환율 유가",
    "해상 운임 SCFI 건설",
    "스마트 건설 모듈러 OSC",
    "건설 현장 인력난 외국인",
    "건설 노조 파업 노란봉투법",
    "납품대금 연동제 건설",
    "건설산업기본법 개정",
    "화물연대 레미콘 운송 파업",
    "건설 동반성장 상생"
]

EXCLUDE_KEYWORDS = [
    "특징주", "테마주", "관련주", "주가", "급등", "급락", "상한가", "하한가",
    "거래량", "매수", "매도", "목표가", "체결", "증시", "종목", "투자자",
    "지수", "코스피", "코스닥", "마감",
    "치킨", "맥주", "식품", "마트", "백화점", "여행", "게임", "화장품"
]

def get_korea_time():
    """서버 시간(UTC)을 한국 시간(KST)으로 변환"""
    utc_now = datetime.now(timezone.utc)
    kst_now = utc_now + timedelta(hours=9)
    return kst_now

def is_stock_noise(title):
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
                    if is_stock_noise(entry.title): continue

                    if not any(item['link'] == entry.link for item in news_items):
                        news_items.append({
                            "title": entry.title,
                            "link": entry.link,
                            "keyword": keyword,
                            "date": entry.published
                        })
                        valid_count += 1
        except Exception as e:
            print(f"⚠️ '{keyword}' 오류: {e}")
            continue
            
    print(f"✅ 총 {len(news_items)}개의 최신 뉴스 수집 완료.")
    return news_items

def generate_report_content(news_items):
    """
    Gemini AI에게 JSON 데이터만 요청하고, 
    HTML 조립은 Python이 수행하여 링크 오류를 원천 차단함.
    """
    if not news_items: return None
    
    kst_now = get_korea_time()
    today_formatted = kst_now.strftime("%Y년 %m월 %d일") 
    
    print("🧠 AI 분석 시작 (JSON 모드)...")
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-09-2025')

        # 뉴스 리스트를 텍스트로 변환 (인덱스 ID 부여)
        news_text = ""
        for idx, item in enumerate(news_items):
            news_text += f"ID[{idx}] {item['title']} (키워드: {item['keyword']})\n"

        prompt = f"""
        오늘은 {today_formatted}입니다.
        당신은 포스코이앤씨 구매계약실의 수석 애널리스트입니다.
        
        [뉴스 목록]
        {news_text}

        [임무]
        위 뉴스 목록을 분석하여 구매 업무에 가장 중요한 이슈 3~5개를 선정하고, JSON 형식으로 출력하세요.
        
        [필수 JSON 구조]
        {{
            "weather_summary": "시장 날씨 요약 (1~2문장, 날씨 아이콘 포함)",
            "selected_news": [
                {{
                    "id": 뉴스ID(숫자),
                    "category": "카테고리명 (예: 자재/시황, 공급망/물류)",
                    "summary": "핵심 요약 (육하원칙, 3~4문장)",
                    "insight": "구매계약실 대응 방안 (2문장)",
                    "risk_level": "Critical 또는 Warning 또는 Info"
                }}
            ]
        }}

        [주의사항]
        1. `id`는 위 목록의 `ID[]` 안에 있는 숫자와 정확히 일치해야 합니다. (이것으로 링크를 연결합니다)
        2. 오직 표준 JSON 형식만 출력하세요. 마크다운 태그(```json)는 사용하지 마세요.
        """
        
        response = model.generate_content(prompt)
        # 마크다운 태그 제거 및 파싱
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        
        return data

    except Exception as e:
        print(f"❌ AI 분석/파싱 중 오류: {e}")
        return None

def build_html_email(data, news_items):
    """AI가 준 데이터(JSON)와 원본 뉴스(List)를 결합하여 HTML 생성"""
    
    # 1. 스타일 정의 (PC 최적화 + Card UI)
    style_block = """
    <style>
        body { font-family: 'Pretendard', 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333; background-color: #f2f4f7; margin: 0; padding: 0; }
        .email-wrapper { width: 100%; background-color: #f2f4f7; padding: 40px 0; }
        .email-container { max-width: 850px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        .header { background-color: #0054a6; color: #ffffff; padding: 40px 50px; }
        .header h1 { margin: 0; font-size: 28px; font-weight: 700; }
        .content { padding: 50px; }
        .weather-section { background-color: #eaf4fc; padding: 30px; border-radius: 12px; margin-bottom: 40px; border: 1px solid #dbeafe; word-break: keep-all; }
        .news-card { background-color: #ffffff; border: 1px solid #eaecf0; border-radius: 16px; padding: 30px; margin-bottom: 30px; box-shadow: 0 2px 5px rgba(0,0,0,0.03); }
        .news-title { font-size: 22px; font-weight: 700; color: #101828; margin-bottom: 15px; line-height: 1.4; word-break: keep-all; }
        .news-body { font-size: 17px; color: #475467; line-height: 1.8; margin-bottom: 20px; word-break: keep-all; }
        .insight-table { width: 100%; border-collapse: separate; border-spacing: 0; margin-bottom: 20px; border-radius: 8px; }
        .insight-label { padding: 15px 5px 15px 20px; width: 1%; white-space: nowrap; vertical-align: top; font-weight: bold; font-size: 16px; }
        .insight-content { padding: 15px 20px 15px 5px; font-size: 16px; line-height: 1.6; vertical-align: top; word-break: keep-all; }
        .link-btn { display: inline-block; background-color: #ffffff; color: #344054; border: 1px solid #d0d5dd; padding: 10px 18px; text-decoration: none; border-radius: 8px; font-size: 14px; font-weight: 600; }
        
        /* 리스크 색상 */
        .risk-Critical { background-color: #fdecea; color: #d32f2f; }
        .risk-Warning  { background-color: #fff4e5; color: #ed6c02; }
        .risk-Info     { background-color: #f0f9ff; color: #0288d1; }
        
        /* 단신 리스트 */
        .headline-box { background-color: #f8f9fa; border-top: 2px solid #0054a6; padding: 30px; margin-top: 20px; }
        .headline-item { margin-bottom: 12px; font-size: 15px; color: #555; }
        .headline-link { text-decoration: none; color: #333; transition: color 0.2s; }
        .headline-link:hover { color: #0054a6; text-decoration: underline; }
    </style>
    """

    kst_now = get_korea_time()
    today_str = kst_now.strftime("%Y년 %m월 %d일")

    # 2. 본문 조립
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8">{style_block}</head>
    <body>
        <div class="email-wrapper">
            <div class="email-container">
                <div class="header">
                    <h1>Daily Market & Risk Briefing</h1>
                    <div style="font-size: 16px; opacity: 0.9; margin-top: 10px;">POSCO E&C 구매계약실 | {today_str}</div>
                </div>
                
                <div class="content">
                    <div class="weather-section">
                        <h2 style="margin:0 0 15px 0; color:#0054a6; font-size:22px;">🌤️ Today's Market Weather</h2>
                        <div style="font-size: 18px;">{data['weather_summary']}</div>
                    </div>
    """

    # 3. 주요 이슈 카드 생성 (AI 선택)
    selected_ids = []
    
    for card in data['selected_news']:
        idx = card['id']
        # ID 유효성 체크
        if idx >= len(news_items): continue
        
        original_item = news_items[idx]
        selected_ids.append(idx)
        
        # 리스크 등급에 따른 스타일 선택
        risk_class = f"risk-{card.get('risk_level', 'Info')}"
        
        # 텍스트 컬러 설정 (배경색에 맞춤)
        text_color = "#0288d1" # 기본 Info
        if card.get('risk_level') == 'Critical': text_color = "#d32f2f"
        elif card.get('risk_level') == 'Warning': text_color = "#ed6c02"

        html += f"""
        <div class="news-card">
            <div style="color: #0054a6; font-weight: 700; margin-bottom: 10px; font-size: 14px;">[{card['category']}]</div>
            <div class="news-title">{original_item['title']}</div>
            <div class="news-body">{card['summary']}</div>
            
            <table class="insight-table {risk_class}">
                <tr>
                    <td class="insight-label" style="color: {text_color};">💡 Insight:</td>
                    <td class="insight-content" style="color: {text_color};">{card['insight']}</td>
                </tr>
            </table>
            
            <div style="text-align: right;">
                <a href="{original_item['link']}" class="link-btn" target="_blank">🔗 원문 기사 보기</a>
            </div>
        </div>
        """

    # 4. 나머지 단신 리스트 생성 (Python 자동 생성)
    html += """
        <div class="headline-box">
            <div style="font-size: 18px; font-weight: 700; color: #0054a6; margin-bottom: 20px;">📌 금일 전체 뉴스 목록 (Reference)</div>
            <ul style="padding-left: 20px; margin: 0;">
    """
    
    for idx, item in enumerate(news_items):
        # 이미 카드뉴스에 나온 기사는 제외하고 싶으면 아래 주석 해제
        # if idx in selected_ids: continue
        
        html += f"""
            <li class="headline-item">
                <span style="background:#e9ecef; color:#495057; font-size:11px; padding:2px 6px; border-radius:4px; margin-right:6px; vertical-align:middle;">{item['keyword']}</span>
                <a href="{item['link']}" class="headline-link" target="_blank">{item['title']}</a>
            </li>
        """

    html += """
            </ul>
        </div>
    """

    # 5. 푸터 및 닫기
    html += """
                </div>
                <div style="background-color: #101828; padding: 40px; text-align: center; color: #98a2b3; font-size: 14px;">
                    <p>본 리포트는 AI Agent 시스템에 의해 실시간으로 생성되었습니다.</p>
                    <p>문의: 구매계약기획그룹 | © POSCO E&C</p>
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
    subject = f"[Daily] {today_str} 구매계약실 시장 동향 보고"

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVERS
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        receivers = [r.strip() for r in EMAIL_RECEIVERS.split(',')]
        server.sendmail(EMAIL_SENDER, receivers, msg.as_string())
        server.quit()
        print(f"📧 발송 성공: {len(receivers)}명에게 전송 완료.")
    except Exception as e:
        print(f"❌ 발송 실패: {e}")

if __name__ == "__main__":
    if not GOOGLE_API_KEY:
        print("❌ API Key가 설정되지 않았습니다.")
    else:
        items = fetch_news()
        if items:
            # 1. AI에게 JSON 데이터 요청
            ai_data = generate_report_content(items)
            if ai_data:
                # 2. Python이 HTML 조립 (링크 매칭 보장)
                final_html = build_html_email(ai_data, items)
                send_email(final_html)
            else:
                print("❌ AI 응답 실패")
        else:
            print("수집된 뉴스가 없습니다.")
