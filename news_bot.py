import os
import feedparser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import google.generativeai as genai
import time
import urllib.parse  # URL 띄어쓰기 인코딩용 라이브러리 추가

# --- 설정값 (GitHub Secrets에서 가져옴) ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")  # 보내는 사람 이메일 (Gmail)
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD") # Gmail 앱 비밀번호
EMAIL_RECEIVERS = os.environ.get("EMAIL_RECEIVERS") # 받는 사람 (콤마로 구분)

# --- 1. 뉴스 검색 키워드 설정 ---
# 포스코이앤씨 관련, 구매/자재, 법규 리스크 등을 포함
KEYWORDS = [
    "포스코이앤씨",
    "건설 원자재 가격",
    "공정위 하도급 건설",
    "시멘트 철근 가격",
    "건설 중대재해처벌법"
]

def fetch_news_rss(keywords):
    """구글 뉴스 RSS를 통해 키워드별 최신 뉴스를 수집합니다."""
    news_items = []
    base_url = "https://news.google.com/rss/search?q={}&hl=ko&gl=KR&ceid=KR:ko"
    
    print("🔍 뉴스 수집 시작...")
    for keyword in keywords:
        # 키워드의 띄어쓰기를 URL에 안전한 형태로 변환 (%20 등)
        encoded_keyword = urllib.parse.quote(keyword)
        feed = feedparser.parse(base_url.format(encoded_keyword))
        
        # 키워드 당 최신 3개만 가져오기 (너무 많으면 읽기 힘듦)
        for entry in feed.entries[:3]:
            # 중복 제거 로직 (링크 기준)
            if not any(item['link'] == entry.link for item in news_items):
                news_items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published,
                    "keyword": keyword
                })
    print(f"✅ 총 {len(news_items)}개의 뉴스 수집 완료.")
    return news_items

def analyze_news_with_gemini(news_items):
    """Gemini를 사용하여 뉴스를 구매팀 관점에서 요약하고 분류합니다."""
    print("🧠 AI 분석 시작...")
    
    if not GOOGLE_API_KEY:
        print("❌ Google API Key가 없습니다. AI 분석을 건너뜁니다.")
        return news_items # API 키 없으면 원본 반환

    genai.configure(api_key=GOOGLE_API_KEY)
    # [수정] Gemini 2.5 Flash 최신 모델 적용
    model = genai.GenerativeModel('gemini-2.5-flash') 

    # 프롬프트 구성
    news_text = ""
    for idx, item in enumerate(news_items):
        news_text += f"[{idx+1}] 키워드: {item['keyword']} | 제목: {item['title']} | 링크: {item['link']}\n"

    prompt = f"""
    당신은 포스코이앤씨 구매실의 노련한 전문가입니다. 
    아래 수집된 뉴스 목록을 보고 구매 업무, 리스크 관리, 자재 수급 관점에서 중요한 기사만 선별하여 브리핑해 주세요.

    [뉴스 목록]
    {news_text}

    [요청 사항]
    1. 모든 기사를 나열하지 말고, **구매팀이 꼭 봐야 할 중요 기사 5~7개**만 선별하세요.
    2. 각 기사에 대해 다음 형식으로 HTML 리스트 아이템(<li>)을 만들어 주세요.
       - **[카테고리]** (예: ⚖️법규/리스크, 🏗️자재/시황, 🏢사내/경쟁사)
       - **제목**: 기사 제목 (링크 연결)
       - **핵심 요약**: 구매 담당자가 알아야 할 핵심 내용 1~2문장.
       - **시사점**: 우리 회사(건설사 구매)에 미칠 영향이나 대응 방안 1문장.
    3. 전체적인 시장 분위기를 보여주는 '오늘의 한 줄 브리핑'을 맨 처음에 작성해 주세요.
    4. 출력은 오직 HTML body 안에 들어갈 내용만 작성하세요. (<html> 태그 제외)
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"❌ AI 분석 중 오류 발생: {e}")
        # 오류 발생 시 기본 목록이라도 반환하도록 처리
        fallback_html = "<ul>"
        for item in news_items:
            fallback_html += f"<li><a href='{item['link']}'>{item['title']}</a></li>"
        fallback_html += "</ul>"
        return fallback_html

def send_email(html_content):
    """수집 및 분석된 내용을 이메일로 발송합니다."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVERS:
        print("❌ 이메일 설정이 누락되었습니다. 발송하지 않습니다.")
        return

    print("📧 이메일 발송 준비...")
    
    today_str = datetime.now().strftime("%Y-%m-%d (%a)")
    subject = f"[구매실 Daily Briefing] {today_str} 주요 뉴스 및 리스크 점검"

    # HTML 이메일 템플릿
    full_html = f"""
    <html>
    <body style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333;">
        <div style="background-color: #0054a6; color: white; padding: 20px; text-align: center;">
            <h2 style="margin:0;">POSCO E&C 구매실 Daily Agent</h2>
        </div>
        <div style="padding: 20px; border: 1px solid #ddd; margin-top: 20px;">
            <p>안녕하세요, 구매실 여러분.<br>
            AI Agent가 취합한 오늘의 주요 구매/법규/시황 뉴스입니다.</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            
            {html_content}
            
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #888;">
                * 본 메일은 Google News 및 Gemini AI를 통해 자동 생성되었습니다.<br>
                * 문의: 구매기획 그룹
            </p>
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
        # Gmail SMTP 서버 연결
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        
        receivers_list = [r.strip() for r in EMAIL_RECEIVERS.split(',')]
        server.sendmail(EMAIL_SENDER, receivers_list, msg.as_string())
        server.quit()
        print(f"✅ 이메일 발송 성공! ({len(receivers_list)}명에게 전송)")
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")

if __name__ == "__main__":
    # 1. 뉴스 수집
    raw_news = fetch_news_rss(KEYWORDS)
    
    if raw_news:
        # 2. AI 분석 및 요약
        ai_summary_html = analyze_news_with_gemini(raw_news)
        
        # 3. 이메일 발송
        send_email(ai_summary_html)
    else:
        print("수집된 뉴스가 없습니다.")
