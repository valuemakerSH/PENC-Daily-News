<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>Email Report Preview (With Headline List)</title>
<style>
    /* 실제 적용되는 CSS 스타일 (news_bot.py와 동일) */
    body { font-family: 'Pretendard', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; line-height: 1.6; color: #333; background-color: #f2f4f7; margin: 0; padding: 0; }
    .email-wrapper { width: 100%; background-color: #f2f4f7; padding: 50px 0; }
    .email-container { max-width: 850px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }
    .header { background-color: #0054a6; color: #ffffff; padding: 40px 50px; }
    .header h1 { margin: 0; font-size: 32px; font-weight: 800; letter-spacing: -0.5px; }
    .header-sub { font-size: 18px; margin-top: 10px; opacity: 0.9; font-weight: 500; }
    .content { padding: 50px; background-color: #ffffff; }
    .intro-text { margin-bottom: 50px; font-size: 18px; color: #344054; padding-bottom: 30px; border-bottom: 1px solid #eaecf0; word-break: keep-all; }
    .footer { background-color: #101828; padding: 40px; text-align: center; font-size: 14px; color: #98a2b3; }
    .footer p { margin: 5px 0; }

    /* AI가 생성하는 본문 스타일 */
    .weather-section {
        background-color: #eaf4fc; 
        padding: 30px; 
        border-radius: 12px; 
        margin-bottom: 40px; 
        border: 1px solid #dbeafe; 
        word-break: keep-all;
    }
    
    .category-title {
        font-size: 24px; 
        color: #111; 
        margin: 50px 0 20px 0; 
        border-left: 5px solid #0054a6; 
        padding-left: 15px;
        font-weight: 700;
    }
    
    /* 카드 스타일 */
    .news-card {
        background-color: #ffffff; 
        border: 1px solid #eaecf0; 
        border-radius: 16px; 
        padding: 30px; 
        margin-bottom: 25px; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .news-title { font-size: 22px; font-weight: 700; color: #101828; margin-bottom: 15px; line-height: 1.4; word-break: keep-all; }
    .news-body { font-size: 17px; color: #475467; line-height: 1.8; margin-bottom: 20px; word-break: keep-all; }
    .insight-table { width: 100%; border-collapse: separate; border-spacing: 0; margin-bottom: 20px; border-radius: 8px; }
    .insight-label { padding: 15px 5px 15px 20px; width: 1%; white-space: nowrap; vertical-align: top; font-weight: bold; font-size: 16px; }
    .insight-content { padding: 15px 20px 15px 5px; font-size: 16px; line-height: 1.6; vertical-align: top; word-break: keep-all; }
    .risk-critical { background-color: #fdecea; color: #d32f2f; }
    .risk-warning  { background-color: #fff4e5; color: #ed6c02; }
    .risk-info     { background-color: #f0f9ff; color: #0288d1; }
    .link-wrapper { text-align: right; }
    .link-btn { display: inline-block; background-color: #ffffff; color: #344054; border: 1px solid #d0d5dd; padding: 10px 18px; text-decoration: none; border-radius: 8px; font-size: 14px; font-weight: 600; }
    .link-btn:hover { background-color: #f9fafb; }

    /* [NEW] 하단 단신 리스트 스타일 */
    .headline-list-box {
        background-color: #f8f9fa;
        border-top: 2px solid #0054a6;
        padding: 20px 25px;
        margin-top: 10px;
        margin-bottom: 40px;
    }
    .headline-title {
        font-size: 16px;
        font-weight: 700;
        color: #0054a6;
        margin-bottom: 15px;
    }
    .headline-ul {
        margin: 0;
        padding-left: 20px;
    }
    .headline-li {
        margin-bottom: 8px;
        font-size: 15px;
        color: #555;
    }
    .headline-link {
        text-decoration: none;
        color: #333;
        transition: color 0.2s;
    }
    .headline-link:hover {
        color: #0054a6;
        text-decoration: underline;
    }
</style>
</head>
<body>
    <div class="email-wrapper">
        <div class="email-container">
            <div class="header">
                <h1>Daily Market & Risk Briefing</h1>
                <div class="header-sub">POSCO E&C 구매계약실 | 2026년 1월 8일</div>
            </div>
            
            <div class="content">
                <div class="intro-text">
                    안녕하십니까, 구매계약실 여러분.<br>
                    <strong>2026년 1월 8일</strong> 주요 시장 이슈와 리스크 요인을 보고드립니다.
                </div>
                
                <!-- 시장 날씨 -->
                <div class="weather-section">
                    <h2 style="margin:0 0 15px 0; color:#0054a6; font-size:22px;">🌤️ Today's Market Weather</h2>
                    <div style="font-size: 18px; line-height: 1.6;">
                        전반적인 건설 자재 시장은 <strong>'약간 흐림'</strong>입니다.
                    </div>
                </div>

                <!-- [카테고리 1] 자재/시황 -->
                <div class="category-title">[자재/시황]</div>

                <!-- 메인 카드 -->
                <div class="news-card">
                    <div class="news-title">시멘트 업계, 전력비 상승으로 내달 12% 가격 인상 통보</div>
                    <div class="news-body">
                        국내 주요 시멘트사들이 유연탄 가격 상승세와 산업용 전기요금 인상을 근거로... (중략)
                    </div>
                    <table class="insight-table risk-warning">
                        <tr>
                            <td class="insight-label">💡 Insight:</td>
                            <td class="insight-content">월말 고시 가격 확정 전 가용 물량 선발주 검토 필요.</td>
                        </tr>
                    </table>
                    <div class="link-wrapper"><a href="#" class="link-btn">🔗 원문 기사 보기</a></div>
                </div>

                <!-- [NEW] 해당 카테고리 단신 모음 -->
                <div class="headline-list-box">
                    <div class="headline-title">📌 관련 주요 단신 (Headlines)</div>
                    <ul class="headline-ul">
                        <li class="headline-li">
                            <a href="#" class="headline-link">레미콘 공업협동조합, 시멘트 가격 인상에 강력 반발 예고</a>
                        </li>
                        <li class="headline-li">
                            <a href="#" class="headline-link">국제 유연탄 가격, 3주 만에 소폭 하락세 전환</a>
                        </li>
                        <li class="headline-li">
                            <a href="#" class="headline-link">건설 자재 수급 안정화 민관 협의체 개최 결과</a>
                        </li>
                    </ul>
                </div>

            </div>
            <div class="footer">
                <p>본 리포트는 AI Agent 시스템에 의해 실시간으로 생성되었습니다.</p>
                <p>문의: 구매계약기획그룹 | © POSCO E&C</p>
            </div>
        </div>
    </div>
</body>
</html>
