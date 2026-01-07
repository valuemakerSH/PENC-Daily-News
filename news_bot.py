import os
import smtplib
import feedparser
import time
import urllib.parse
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

# [수정] 건설과 무관한 노이즈(식품, 유통 등) 및 주식 키워드 차단 강화
EXCLUDE_KEYWORDS = [
    "특징주", "테마주", "관련주", "주가", "급등", "급락", "상한가", "하한가",
    "거래량", "매수", "매도", "목표가", "체결", "증시", "종목", "투자자",
    "지수", "코스피", "코스닥", "마감",
    "치킨", "맥주", "식품", "마트", "백화점", "여행", "게임", "화장품" # 타 산업군 제외
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
            # 뉴스 목록 제공 시 [제목]과 [Link]가 한 쌍임을 명확히 전달
            news_text += f"[{idx+1}] 제목: {item['title']} | LinkID: {placeholder}\n"

        # 프롬프트: 링크 정합성 유지 강조
        prompt = f"""
        오늘은 {today_formatted}입니다.
        당신은 **포스코이앤씨 구매계약실**의 수석 애널리스트입니다.
        
        [뉴스 목록]
        {news_text}

        [작성 원칙]
        1. **날짜 준수**: 반드시 오늘 날짜({today_formatted})를 기준으로 작성.
        2. **주식/투자 배제**: 건설 테마주, 주가 등락 내용 절대 포함 금지.
        3. **구조**: 각 카테고리별로 가장 중요한 1~2개 기사는 '상세 카드(Deep Dive)'로 작성하고, 나머지 관련 기사는 하단에 '단신 리스트(Headlines)'로 모아서 정리.
        
        [🚨 중요: 링크 정합성 절대 준수]
        - 기사의 제목과 링크(`__LINK_N__`)는 반드시 위 [뉴스 목록]에 있는 **원래 짝꿍끼리만** 연결해야 합니다.
        - **절대로** A기사 제목에 B기사 링크를 붙이지 마세요.
        - 제목을 임의로 창작하지 말고, 목록에 있는 제목을 그대로(또는 다듬어서) 사용하세요.

        [보고서 형식 (HTML Style)]
        - `<div>`, `<table>`, `<ul>`, `<li>` 등 Body 내부 태그로만 작성.
        - **디자인 핵심**: `word-break: keep-all;` 필수 적용.
        
        [HTML 구조 가이드]
        1. **시장 날씨 (Hero Section)**: 
           `<div style="background-color: #eaf4fc; padding: 30px; border-radius: 12px; margin-bottom: 40px; border: 1px solid #dbeafe; word-break: keep-all;">`
           - 제목: `<h2 style="margin:0 0 15px 0; color:#0054a6; font-size:22px;">🌤️ Today's Market Weather</h2>`
           - 내용: 시장 요약 1~2문장.
        
        2. **카테고리 섹션**: 
           - 섹션 제목: `<h3 style="font-size: 24px; color: #111; margin: 50px 0 20px 0; border-left: 5px solid #0054a6; padding-left: 15px;">[카테고리명]</h3>`
        
        3. **상세 기사 카드 (중요 기사 1~2개)**:
           `<div style="background-color: #ffffff; border: 1px solid #eaecf0; border-radius: 16px; padding: 30px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">`
           - 제목, 내용(상세 요약), 인사이트(Table) 작성.
           - 버튼: `<div style="text-align: right;"><a href="LinkID" style="display: inline-block; background-color: #ffffff; color: #344054; border: 1px solid #d0d5dd; padding: 10px 18px; text-decoration: none; border-radius: 8px; font-size: 14px; font-weight: 600;">🔗 원문 기사 보기</a></div>`
           
        4. **📌 관련 주요 단신 (Headlines List - 카테고리 마지막에 추가)**:
           상세 카드로 다루지 않은 나머지 뉴스들을 아래 스타일로 리스트업하세요.
           (반드시 LinkID가 일치하는 제목과 함께 사용)
           
           `<div style="background-color: #f8f9fa; border-top: 2px solid #0054a6; padding: 20px 25px; margin-top: 10px; margin-bottom: 40px;">`
           `<div style="font-size: 16px; font-weight: 700; color: #0054a6; margin-bottom: 15px;">📌 관련 주요 단신 (Headlines)</div>`
           `<ul style="margin: 0; padding-left: 20px;">`
           
           `<!-- 리스트 아이템 반복 -->`
           `<li style="margin-bottom: 8px; font-size: 15px; color: #555;">`
           `<a href="LinkID" style="text-decoration: none; color: #333;">기사 제목 (클릭 시 이동)</a>`
           `</li>`
           
           `</ul></div>`
        """
        
        response = model.generate_content(prompt)
        html_content = response.text.replace("```html", "").replace("```", "")
        
        for placeholder, real_url in link_map.items():
            html_content = html_content.replace(placeholder, real_url)
            
        return html_content
    except Exception as e:
        print(f"❌ AI 분석 중 오류: {e}")
        return None

def send_email(html_body):
    if not html_body: return

    kst_now = get_korea_time()
    today_str = kst_now.strftime("%Y년 %m월 %d일")
    subject = f"[Daily] {today_str} 구매계약실 시장 동향 보고"
    
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
