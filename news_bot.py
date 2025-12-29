import os
import smtplib
import feedparser
import time
import urllib.parse # 주소 변환을 위한 도구 추가
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import google.generativeai as genai

# --- 환경 변수 설정 (GitHub Secrets) ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")      # 발신자 Gmail 주소
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")  # 발신자 Gmail 앱 비밀번호
EMAIL_RECEIVERS = os.environ.get("EMAIL_RECEIVERS") # 수신자 이메일 (콤마로 구분)

# --- 설정: 키워드 ---
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
    "건설 노조 동향"
]

def is_recent(published_str):
    """뉴스 날짜가 24시간 이내인지 확인"""
    if not published_str: return False
    try:
        pub_date = parsedate_to_datetime(published_str)
        if pub_date.tzinfo:
            pub_date = pub_date.replace(tzinfo=None)
        
        one_day_ago = datetime.now() - timedelta(hours=24)
        return pub_date > one_day_ago
    except:
        return True

def fetch_news():
    """RSS를 통해 뉴스 수집 (띄어쓰기 에러 해결 버전)"""
    news_items = []
    
    print("🔍 뉴스 수집 시작...")
    for keyword in KEYWORDS:
        # [중요] 검색어와 명령어를 URL 전용 문자로 변환 (인코딩)
        # 예: "건설 자재" -> "%EA%B1%B4%EC%84%A4%20%EC%9E%90%EC%9E%AC"
        encoded_query = urllib.parse.quote(f"{keyword} when:1d")
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        
        try:
            feed = feedparser.parse(url)
            
            # 피드 파싱 자체에러 체크
            if hasattr(feed, 'bozo_exception') and feed.bozo_exception:
                 # 인코딩 문제 등으로 파싱 실패시 무시하고 계속 진행
                 continue

            for entry in feed.entries[:3]: # 키워드 당 3개
                if is_recent(entry.published):
                    if not any(item['link'] == entry.link for item in news_items):
                        news_items.append({
                            "title": entry.title,
                            "link": entry.link,
                            "keyword": keyword
                        })
        except Exception as e:
            print(f"⚠️ '{keyword}' 수집 중 오류 (건너뜀): {e}")
            continue
            
    print(f"✅ 총 {len(news_items)}개의 최신 뉴스 수집 완료.")
    return news_items

def generate_report(news_items):
    """Gemini AI로 리포트 생성"""
    if not news_items: return None
    
    print("🧠 AI 분석 시작...")
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-09-2025')

        news_text = ""
        for idx, item in enumerate(news_items):
            news_text += f"[{idx+1}] 키워드: {item['keyword']} | 제목: {item['title']} | 링크: {item['link']}\n"

        prompt = f"""
        당신은 포스코이앤씨 구매실의 노련한 전문가입니다. 
        아래 수집된 뉴스 목록을 보고, 구매 담당자에게 보낼 'Daily Market & Risk Briefing' 이메일 본문을 HTML로 작성해 주세요.

        [뉴스 목록]
        {news_text}

        [작성 지침 - 중요]
        1. **주식/투자 제외:** '주가 상승/하락', '목표 주가', '증권사 리포트' 등 주식 투자와 관련된 내용은 **절대 제외**하세요.
        2. **관점:** 철저히 '구매/자재/공사/법규' 실무 담당자 입장에서 작성하세요.
        
        [출력 형식 - HTML Body 내부]
        1. 상단에 **[오늘의 시장 날씨]** 섹션을 만들고 ☀️/☁️/☔와 함께 전체 요약을 1줄 작성하세요. (배경색: #f3f4f6, padding: 10px)
        2. 각 기사는 아래 포맷을 엄수하세요:
            - <h4 style="margin-bottom:2px; margin-top:15px; color:#0054a6;">[카테고리] 제목 (링크)</h4>
            - <ul style="margin-top:0; padding-left:20px; font-size:14px; color:#333;">
                <li><b>핵심:</b> 기사 내용 요약</li>
                <li><b>💡시사점:</b> 건설사 구매팀 대응 방안 (1줄)</li>
            </ul>
        3. 카테고리 분류: [규제/리스크], [자재/시황], [글로벌/물류], [기술/혁신], [ESG/상생], [경쟁사/동향], [노무/인력]
        4. HTML 코드만 출력하세요 (```html 등 마크다운 태그 제외).
        """
        
        response = model.generate_content(prompt)
        return response.text.replace("```html", "").replace("```", "")
    except Exception as e:
        print(f"❌ AI 분석 중 오류: {e}")
        return None

def send_email(html_body):
    """이메일 발송"""
    if not html_body: return

    today_str = datetime.now().strftime("%Y년 %m월 %d일 (%a)")
    subject = f"[구매실 Daily] {today_str} Market & Risk Briefing"
    
    full_html = f"""
    <html>
    <body style="font-family: 'Malgun Gothic', sans-serif; color: #333; line-height: 1.6;">
        <div style="background-color: #0054a6; color: white; padding: 15px; text-align: center;">
            <h2 style="margin:0;">POSCO E&C 구매실 News Agent</h2>
        </div>
        <div style="padding: 20px; border: 1px solid #ddd;">
            <p>안녕하십니까, 구매실 여러분.<br>
            AI Agent가 선별한 오늘의 주요 리스크 및 시황 정보입니다.</p>
            <hr style="border:0; border-top:1px solid #eee; margin: 20px 0;">
            
            {html_body}
            
            <hr style="border:0; border-top:1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #888;">
                * 본 메일은 Google News 및 Gemini AI를 통해 자동 발송되었습니다.<br>
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
                print("❌ 리포트 생성 실패 (AI 응답 없음)")
        else:
            print("수집된 뉴스가 없습니다.")
