import os
import smtplib
import feedparser
import time
import urllib.parse
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
    "화물연대 레미콘 운송 파업"
]

# 주식/투자 관련 노이즈 제거를 위한 금지어 목록
EXCLUDE_KEYWORDS = [
    "특징주", "테마주", "관련주", "주가", "급등", "급락", "상한가", "하한가",
    "거래량", "매수", "매도", "목표가", "체결", "증시", "종목", "투자자",
    "지수", "코스피", "코스닥", "마감"
]

def get_korea_time():
    """서버 시간(UTC)을 한국 시간(KST)으로 변환"""
    utc_now = datetime.now(timezone.utc)
    kst_now = utc_now + timedelta(hours=9)
    return kst_now

def is_stock_noise(title):
    """제목에 주식 관련 금지어가 있는지 검사"""
    for bad_word in EXCLUDE_KEYWORDS:
        if bad_word in title:
            return True
    return False

def is_recent(published_str):
    """뉴스 날짜가 24시간 이내인지 확인"""
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
    """RSS 뉴스 수집 (스크랩 제거로 속도 향상)"""
    news_items = []
    print("🔍 뉴스 수집 시작...")
    
    for keyword in KEYWORDS:
        # 검색어 뒤에 '-주식 -종목' 등을 붙여서 구글 검색 단계에서도 1차 필터링
        negative_query = " -주식 -종목 -테마 -특징주"
        encoded_query = urllib.parse.quote(f"{keyword}{negative_query} when:1d")
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        
        try:
            feed = feedparser.parse(url)
            
            if not feed.entries and hasattr(feed, 'bozo_exception'): pass

            for entry in feed.entries[:3]:
                if is_recent(entry.published):
                    # 2차 필터링: 제목에 금지어 포함 여부 확인
                    if is_stock_noise(entry.title):
                        continue

                    if not any(item['link'] == entry.link for item in news_items):
                        news_items.append({
                            "title": entry.title,
                            "link": entry.link,
                            "keyword": keyword,
                            "date": entry.published
                        })
        except Exception as e:
            print(f"⚠️ '{keyword}' 오류: {e}")
            continue
            
    print(f"✅ 총 {len(news_items)}개의 최신 뉴스 수집 완료.")
    return news_items

def generate_report(news_items):
    """Gemini AI 리포트 (가독성 개선 및 버튼형 링크 적용)"""
    if not news_items: return None
    
    kst_now = get_korea_time()
    today_formatted = kst_now.strftime("%Y년 %m월 %d일") 
    
    print("🧠 AI 분석 시작...")
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-09-2025')

        news_text = ""
        for idx, item in enumerate(news_items):
            news_text += f"[{idx+1}] {item['title']} (키워드: {item['keyword']}) | Link: {item['link']}\n"

        # 프롬프트 수정: 가독성을 위한 카드형 디자인 및 별도 링크 버튼 요청
        prompt = f"""
        오늘은 {today_formatted}입니다.
        당신은 **포스코이앤씨 구매계약실**의 수석 애널리스트입니다.
        아래 뉴스들을 바탕으로 'Daily Market & Risk Briefing' 이메일을 작성하세요.

        [뉴스 목록]
        {news_text}

        [작성 원칙]
        1. **날짜 준수**: 반드시 오늘 날짜({today_formatted})를 기준으로 작성하세요.
        2. **주식/투자 배제**: 건설 테마주, 주가 등락 내용은 절대 포함하지 마세요.
        3. **구매계약실 관점**: 계약, 납기, 단가, 법적 리스크 위주로 분석하세요.

        [보고서 형식 (HTML Style)]
        - **절대** `<html>`, `<head>`, `<body>` 태그를 쓰지 마세요. `<div>`로 시작하는 본문 내용만 작성하세요.
        - **가독성 강화**: 글자 크기를 키우고(15px 이상), 줄 간격을 넉넉히(1.6) 잡으세요.
        - **링크 분리**: 제목에 링크를 걸지 말고, 별도의 '🔗 기사 원문 보기' 버튼을 만드세요.
        
        [HTML 구조 가이드]
        1. **시장 날씨 요약**: 
           `<div style="background-color: #e3f2fd; padding: 20px; border-radius: 12px; margin-bottom: 30px; border-left: 6px solid #0054a6;">`
           안에 ☀️/☁️/☔ 아이콘과 함께 시장 요약 1문장을 굵은 글씨로 작성.
        
        2. **카테고리 섹션**: 
           `[규제/리스크]`, `[자재/시황]`, `[글로벌/물류]` 등 섹션 제목을 `<h3>` 태그로 명확히 구분 (`color: #222; margin-top: 30px; border-bottom: 2px solid #ddd; padding-bottom: 10px;`).
        
        3. **기사 카드**:
           각 기사는 아래 스타일을 적용하세요:
           `<div style="background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.03);">`
           
           - **제목**: `<div style="font-size: 18px; font-weight: bold; color: #111; margin-bottom: 10px;">제목</div>`
           - **내용**: `<div style="font-size: 15px; color: #444; line-height: 1.6; margin-bottom: 15px;">기사 핵심 요약...</div>`
           - **인사이트**: `<div style="background-color: #f8f9fa; padding: 12px; border-radius: 8px; font-size: 14px; color: #0054a6; font-weight: 600; margin-bottom: 15px;">💡 Insight: 구매계약실 대응 방안...</div>`
           - **버튼**: `<a href="..." style="display: inline-block; background-color: #0054a6; color: #ffffff; padding: 10px 15px; text-decoration: none; border-radius: 6px; font-size: 13px; font-weight: bold;">🔗 기사 원문 보기</a>`
        """
        
        response = model.generate_content(prompt)
        return response.text.replace("```html", "").replace("```", "")
    except Exception as e:
        print(f"❌ AI 분석 중 오류: {e}")
        return None

def send_email(html_body):
    """이메일 발송 (디자인 템플릿 개선 - 헤더 가독성 및 줄바꿈 방지)"""
    if not html_body: return

    kst_now = get_korea_time()
    today_str = kst_now.strftime("%Y년 %m월 %d일")
    subject = f"[Daily] {today_str} 구매계약실 시장 동향 보고"
    
    # 이메일 클라이언트를 위한 인라인 스타일이 적용된 HTML 템플릿
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; line-height: 1.6; color: #333; background-color: #f4f6f8; margin: 0; padding: 0; }}
        .email-container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; }}
        .header {{ background-color: #0054a6; color: #ffffff; padding: 25px 20px; text-align: center; }}
        .header h1 {{ margin: 0 0 10px 0; font-size: 26px; font-weight: bold; letter-spacing: -0.5px; }}
        .header-info {{ font-size: 14px; opacity: 0.9; line-height: 1.4; }}
        .content {{ padding: 30px 20px; }}
        .intro-text {{ margin-bottom: 30px; font-size: 16px; color: #444; }}
        .footer {{ background-color: #f9f9f9; padding: 20px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #eee; }}
    </style>
    </head>
    <body>
        <div class="email-container">
            <!-- 헤더 -->
            <div class="header">
                <h1>Daily Market Briefing</h1>
                <div class="header-info">
                    POSCO E&C 구매계약실<br>
                    {today_str}
                </div>
            </div>
            
            <!-- 본문 -->
            <div class="content">
                <div class="intro-text">
                    안녕하십니까, 구매계약실 여러분.<br>
                    오늘의 주요 건설/자재 시장 이슈와 리스크 요인을 보고드립니다.
                </div>
                
                {html_body}
            </div>
            
            <!-- 푸터 -->
            <div class="footer">
                <p>본 메일은 AI Agent에 의해 자동 생성 및 발송되었습니다.</p>
                <p>© POSCO E&C Purchase Contract Division</p>
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
