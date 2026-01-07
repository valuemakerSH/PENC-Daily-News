import os
import smtplib
import feedparser
import time
import urllib.parse
import random 
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

            # 수집량 넉넉하게 (키워드당 최대 10개)
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

def generate_report(news_items):
    """Gemini AI 리포트 (Deep Dive만 AI가, 리스트는 Python이)"""
    if not news_items: return None
    
    kst_now = get_korea_time()
    today_formatted = kst_now.strftime("%Y년 %m월 %d일") 
    
    print("🧠 AI 분석 시작...")
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-09-2025')

        news_text = ""
        link_map = {}
        
        for idx, item in enumerate(news_items):
            placeholder = f"__LINK_{idx}__"
            link_map[placeholder] = item['link']
            # AI에게 제공하는 목록
            news_text += f"[{idx+1}] {item['title']} (키워드: {item['keyword']}) | LinkID: {placeholder}\n"

        prompt = f"""
        오늘은 {today_formatted}입니다.
        당신은 **포스코이앤씨 구매계약실**의 수석 애널리스트입니다.
        
        [뉴스 목록]
        {news_text}

        [작성 원칙]
        1. **역할**: 위 뉴스 목록 중 가장 중요하고 파급력이 큰 이슈 **3~5개**를 선정하여 심층 분석(Deep Dive) 하세요.
        2. **제외**: 선정하지 않은 나머지 뉴스들에 대한 리스트는 작성하지 마세요. (시스템이 자동으로 붙일 예정입니다)
        3. **날짜 준수**: 반드시 오늘 날짜({today_formatted})를 기준으로 작성.
        4. **링크 규칙**: 뉴스 목록의 `__LINK_N__`을 사용하여 기사 제목이나 버튼에 링크를 거세요.

        [보고서 형식 (HTML Style)]
        - `<div>`, `<table>`, `<ul>`, `<li>` 등 Body 내부 태그로만 작성.
        - **디자인 핵심**: `word-break: keep-all;` 필수 적용.
        
        [HTML 구조 가이드]
        1. **시장 날씨 (Hero Section)**: (기존과 동일)
        
        2. **카테고리 섹션**: 
           - 섹션 제목: `<h3 style="font-size: 24px; color: #111; margin: 50px 0 20px 0; border-left: 5px solid #0054a6; padding-left: 15px;">[카테고리명]</h3>`
        
        3. **상세 기사 카드 (Deep Dive)**:
           `<div style="background-color: #ffffff; border: 1px solid #eaecf0; border-radius: 16px; padding: 30px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">`
           - 제목: `<div style="font-size: 22px; font-weight: 700; color: #101828; margin-bottom: 15px; line-height: 1.4; word-break: keep-all;">제목</div>`
           - 내용: `<div style="font-size: 17px; color: #475467; line-height: 1.8; margin-bottom: 20px; word-break: keep-all;">핵심 요약...</div>`
           
           - 인사이트(Table): 
             `<table style="background-color: [배경색]; border-radius: 8px; width: 100%; border-collapse: separate; border-spacing: 0; margin-bottom: 20px;">`
             `<tr>`
             `<td style="padding: 15px 5px 15px 20px; width: 1%; white-space: nowrap; vertical-align: top; color: [텍스트색]; font-weight: bold; font-size: 16px;">💡 Insight:</td>`
             `<td style="padding: 15px 20px 15px 5px; color: [텍스트색]; font-size: 16px; line-height: 1.6; vertical-align: top; word-break: keep-all;">대응 방안...</td>`
             `</tr></table>`
             
           - 버튼: `<div style="text-align: right;"><a href="__LINK_N__" style="display: inline-block; background-color: #ffffff; color: #344054; border: 1px solid #d0d5dd; padding: 10px 18px; text-decoration: none; border-radius: 8px; font-size: 14px; font-weight: 600;">🔗 원문 기사 보기</a></div>`
        """
        
        response = model.generate_content(prompt)
        ai_html = response.text.replace("```html", "").replace("```", "")
        
        # 1. AI가 만든 본문 내 링크 치환
        for placeholder, real_url in link_map.items():
            ai_html = ai_html.replace(placeholder, real_url)
            
        # 2. [Python 생성] 전체 뉴스 리스트 붙이기 (링크 오류 0%)
        # AI가 놓쳤거나 선택하지 않은 뉴스까지 포함하여 전체를 하단에 리스트업
        full_list_html = """
        <div style="background-color: #f8f9fa; border-top: 2px solid #0054a6; padding: 30px; margin-top: 50px;">
            <div style="font-size: 18px; font-weight: 700; color: #0054a6; margin-bottom: 20px;">📌 금일 수집된 전체 뉴스 목록 (Reference)</div>
            <ul style="margin: 0; padding-left: 20px;">
        """
        
        for item in news_items:
            # 안전하게 Python 변수에서 직접 제목과 링크를 가져옴
            full_list_html += f"""
            <li style="margin-bottom: 10px; font-size: 15px; color: #555; line-height: 1.5;">
                <span style="display:inline-block; background:#e9ecef; color:#495057; font-size:11px; padding:2px 6px; border-radius:4px; margin-right:5px; vertical-align:middle;">{item['keyword']}</span>
                <a href="{item['link']}" style="text-decoration: none; color: #333; word-break: keep-all;" target="_blank">{item['title']}</a>
            </li>
            """
        
        full_list_html += "</ul></div>"
        
        # 최종 합체
        final_html = ai_html + full_list_html
        return final_html

    except Exception as e:
        print(f"❌ AI 분석 중 오류: {e}")
        return None

def send_email(html_body):
    if not html_body: return

    kst_now = get_korea_time()
    today_str = kst_now.strftime("%Y년 %m월 %d일")
    subject = f"[Daily] {today_str} 구매계약실 시장 동향 보고"
    
    # [이스터에그] 20% 확률
    easter_egg_css = ""
    easter_egg_html = ""
    if random.random() < 0.2: 
        easter_egg_css = """
        .easter-egg { 
            margin-top: 30px; font-size: 11px; color: #f2f4f7; cursor: help; 
            transition: all 0.5s ease; text-align: center; letter-spacing: 1px;
        }
        .easter-egg:hover { color: #ff6b6b; transform: scale(1.05); font-weight: bold; }
        """
        easter_egg_html = """
        <div class="easter-egg">
            오? 저를 발견하셨군요! 연락주시면 커피 한잔 사드릴께요 ☕ (Developed by You)
        </div>
        """

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Pretendard', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; line-height: 1.6; color: #333; background-color: #f2f4f7; margin: 0; padding: 0; }}
        .email-wrapper {{ width: 100%; background-color: #f2f4f7; padding: 50px 0; }}
        .email-container {{ max-width: 850px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }}
        .header {{ background-color: #0054a6; color: #ffffff; padding: 40px 50px; }}
        .header h1 {{ margin: 0; font-size: 32px; font-weight: 800; letter-spacing: -0.5px; }}
        .header-sub {{ font-size: 18px; margin-top: 10px; opacity: 0.9; font-weight: 500; }}
        .content {{ padding: 50px; background-color: #ffffff; }}
        .intro-text {{ margin-bottom: 50px; font-size: 18px; color: #344054; padding-bottom: 30px; border-bottom: 1px solid #eaecf0; word-break: keep-all; }}
        .footer {{ background-color: #101828; padding: 40px; text-align: center; font-size: 14px; color: #98a2b3; }}
        .footer p {{ margin: 5px 0; }}
        
        {easter_egg_css}
    </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="email-container">
                <!-- 헤더 -->
                <div class="header">
                    <h1>Daily Market & Risk Briefing</h1>
                    <div class="header-sub">
                        POSCO E&C 구매계약실 | {today_str}
                    </div>
                </div>
                
                <!-- 본문 -->
                <div class="content">
                    <div class="intro-text">
                        안녕하십니까, 구매계약실 여러분.<br>
                        <strong>{today_str}</strong> 주요 시장 이슈와 리스크 요인을 보고드립니다.
                    </div>
                    
                    {html_body}
                </div>
                
                <!-- 푸터 -->
                <div class="footer">
                    <p>본 리포트는 AI Agent 시스템에 의해 실시간으로 생성되었습니다.</p>
                    <p>문의: 구매계약기획그룹 | © POSCO E&C</p>
                    {easter_egg_html}
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVERS
    msg['Subject'] = subject
    msg.attach(MIMEText(full_html, 'html'))

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
            report_html = generate_report(items)
            if report_html:
                send_email(report_html)
            else:
                print("❌ 리포트 생성 실패")
        else:
            print("수집된 뉴스가 없습니다.")
