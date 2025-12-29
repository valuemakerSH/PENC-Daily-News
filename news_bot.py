import os
import smtplib
import feedparser
import time
import urllib.parse
import urllib.request
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import google.generativeai as genai

# --- 환경 변수 설정 (GitHub Secrets) ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVERS = os.environ.get("EMAIL_RECEIVERS")

# --- 설정: 디자인 및 키워드 ---
COLOR_PRIMARY = "#0054a6"     # 포스코 블루
COLOR_BG = "#f5f5f7"          # 애플 스타일 연회색 배경

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
    # --- [추가] 법안 및 파업 리스크 집중 감시 ---
    "건설 노조 파업 노란봉투법",    # 노동조합법 개정안 이슈
    "납품대금 연동제 건설",         # 자재 가격 변동분 반영 의무화 법안
    "건설산업기본법 개정",          # 건설 관련 기본 법규 변화
    "화물연대 레미콘 운송 파업"     # 물류 마비 리스크
]

def get_korea_time():
    """서버 시간(UTC)을 한국 시간(KST)으로 변환"""
    utc_now = datetime.now(timezone.utc)
    kst_now = utc_now + timedelta(hours=9)
    return kst_now

def is_recent(published_str):
    """뉴스 날짜가 24시간 이내인지 확인 (UTC 기준 통일)"""
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
    """RSS를 통해 뉴스 수집"""
    news_items = []
    print("🔍 뉴스 수집 시작...")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    for keyword in KEYWORDS:
        encoded_query = urllib.parse.quote(f"{keyword} when:1d")
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        
        try:
            feed = feedparser.parse(url)
            
            if not feed.entries and hasattr(feed, 'bozo_exception'):
                pass

            for entry in feed.entries[:3]:
                if is_recent(entry.published):
                    if not any(item['link'] == entry.link for item in news_items):
                        news_items.append({
                            "title": entry.title,
                            "link": entry.link,
                            "keyword": keyword,
                            "date": entry.published
                        })
        except Exception as e:
            print(f"⚠️ '{keyword}' 수집 중 경미한 오류: {e}")
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
            news_text += f"[{idx+1}] {item['title']} ({item['keyword']})\n"

        prompt = f"""
        당신은 포스코이앤씨 구매전략실의 수석 애널리스트입니다.
        아래 뉴스들을 바탕으로 경영진 및 실무진에게 보고할 'Daily Insight Report'를 작성하세요.

        [뉴스 목록]
        {news_text}

        [작성 원칙]
        1. **주식/투자 정보 완전 배제**: 오직 자재 수급, 원가 리스크, 공급망, 법규 영향만 분석합니다.
        2. **법안/파업 이슈 강조**: '노란봉투법', '납품대금연동제', '파업' 관련 소식은 구매 영향도(납기/원가)를 반드시 언급하세요.
        3. **HTML 출력**: `<html>` 태그 없이 `<div>`로 시작하는 본문 내용만 작성합니다.

        [보고서 구조]
        1. **Executive Summary**: 시장 분위기 1문장 요약 (날씨 아이콘 포함).
        2. **Key Issues**: [Risk & Law], [Material & Cost], [Global & SC], [Tech & ESG] 카테고리로 분류.
        3. 각 기사마다 'Insight' 항목에 구매 실무 대응 방안(1줄) 포함.

        위 가이드에 맞춰 세련된 HTML 코드를 작성해주세요.
        """
        
        response = model.generate_content(prompt)
        return response.text.replace("```html", "").replace("```", "")
    except Exception as e:
        print(f"❌ AI 분석 중 오류: {e}")
        return None

# --- PDF 생성 (fpdf2) ---
def create_pdf(news_items, ai_summary_html):
    print("📄 PDF 생성 시작...")
    try:
        from fpdf import FPDF
    except ImportError:
        print("❌ fpdf2 라이브러리가 없습니다.")
        return None

    font_path = 'NanumGothic.ttf'
    font_bold_path = 'NanumGothicBold.ttf'
    
    if not os.path.exists(font_path):
        urllib.request.urlretrieve("https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Regular.ttf", font_path)
    if not os.path.exists(font_bold_path):
         urllib.request.urlretrieve("https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Bold.ttf", font_bold_path)

    class ReportPDF(FPDF):
        def header(self):
            self.set_font('NanumBold', size=10)
            self.set_text_color(134, 134, 139)
            self.cell(0, 10, 'POSCO E&C Purchase Division', ln=0, align='L')
            self.cell(0, 10, 'Daily Insight', ln=1, align='R')
            self.set_draw_color(230, 230, 230)
            self.line(10, 20, 200, 20)
            self.ln(15)

        def footer(self):
            self.set_y(-15)
            self.set_font('Nanum', size=8)
            self.set_text_color(180, 180, 180)
            self.cell(0, 10, f'Page {self.page_no()}', align='C')

    pdf = ReportPDF()
    
    # [수정됨] 페이지 추가 전에 폰트 등록을 먼저 해야 합니다. (header에서 폰트를 사용하므로)
    pdf.add_font('Nanum', '', font_path)
    pdf.add_font('NanumBold', '', font_bold_path)
    
    pdf.add_page()

    kst_now = get_korea_time()
    date_str = kst_now.strftime("%B %d, %Y")

    pdf.set_font('NanumBold', size=24)
    pdf.set_text_color(29, 29, 31)
    pdf.cell(0, 10, 'Daily Market Briefing', ln=True)
    
    pdf.set_font('Nanum', size=12)
    pdf.set_text_color(134, 134, 139)
    pdf.cell(0, 8, date_str, ln=True)
    pdf.ln(10)

    pdf.set_font('NanumBold', size=14)
    pdf.set_text_color(0, 84, 166)
    pdf.cell(0, 10, 'Executive Summary', ln=True)
    
    clean_summary = re.sub('<[^<]+?>', '', ai_summary_html).strip()
    clean_summary = re.sub(r'\n\s*\n', '\n\n', clean_summary)
    
    pdf.set_font('Nanum', size=11)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 7, clean_summary)
    pdf.ln(15)

    pdf.set_font('NanumBold', size=14)
    pdf.set_text_color(0, 84, 166)
    pdf.cell(0, 10, 'Selected News List', ln=True)
    
    pdf.set_draw_color(240, 240, 240)
    
    for item in news_items:
        pdf.ln(2)
        pdf.set_font('NanumBold', size=8)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(150, 150, 150)
        tag_width = pdf.get_string_width(item['keyword']) + 6
        pdf.cell(tag_width, 6, item['keyword'], 0, 0, 'C', fill=True)
        pdf.ln(7)
        
        pdf.set_font('NanumBold', size=11)
        pdf.set_text_color(29, 29, 31)
        pdf.cell(0, 6, item['title'], ln=True, link=item['link'])
        
        pdf.set_font('Nanum', size=9)
        pdf.set_text_color(134, 134, 139)
        pdf.cell(0, 5, "Google News Source", ln=True)
        
        pdf.set_draw_color(230, 230, 230)
        pdf.line(pdf.get_x(), pdf.get_y()+2, 200, pdf.get_y()+2)
        pdf.ln(5)

    filename = f"Purchase_Report_{kst_now.strftime('%Y%m%d')}.pdf"
    pdf.output(filename)
    print(f"✅ 디자인 PDF 생성 완료: {filename}")
    return filename

def send_email(html_body, pdf_file=None):
    if not html_body: return

    kst_now = get_korea_time()
    today_str = kst_now.strftime("%Y년 %m월 %d일")
    subject = f"[Daily Insight] {today_str} 구매 시장 동향 보고"
    
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ margin: 0; padding: 0; font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; background-color: {COLOR_BG}; }}
        .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 40px; border-radius: 12px; margin-top: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
        .header {{ margin-bottom: 30px; border-bottom: 1px solid #eeeeee; padding-bottom: 20px; }}
        .header h1 {{ margin: 0; color: #1d1d1f; font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }}
        .header p {{ margin: 5px 0 0; color: #86868b; font-size: 14px; }}
        .content {{ color: #333; line-height: 1.6; font-size: 15px; }}
        .footer {{ margin-top: 40px; border-top: 1px solid #eeeeee; padding-top: 20px; font-size: 12px; color: #86868b; text-align: center; }}
        .btn {{ display: inline-block; background-color: {COLOR_PRIMARY}; color: white; padding: 10px 20px; text-decoration: none; border-radius: 20px; font-size: 14px; font-weight: bold; margin-top: 20px; }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Daily Insight Report</h1>
                <p>{today_str} | POSCO E&C Purchase Division</p>
            </div>
            
            <div class="content">
                <p>안녕하세요, 구매실 여러분.<br>
                오늘의 주요 시장 이슈와 리스크 요인을 정리해 드립니다.</p>
                
                {html_body}
                
                <div style="text-align: center; margin-top: 30px;">
                    <p style="font-size: 14px; color: #666;">
                        📎 <b>상세 뉴스 목록은 첨부된 PDF</b>를 확인해주세요.
                    </p>
                </div>
            </div>

            <div class="footer">
                Generated by AI Agent • Powered by Gemini<br>
                본 메일은 발신 전용입니다.
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

    if pdf_file and os.path.exists(pdf_file):
        with open(pdf_file, "rb") as f:
            attach = MIMEApplication(f.read(), _subtype="pdf")
            attach.add_header('Content-Disposition', 'attachment', filename=pdf_file)
            msg.attach(attach)

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
            pdf_filename = create_pdf(items, report_html)
            
            if report_html:
                send_email(report_html, pdf_filename)
            else:
                print("❌ 리포트 생성 실패")
        else:
            print("수집된 뉴스가 없습니다.")
