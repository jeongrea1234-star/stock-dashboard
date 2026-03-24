import re
from datetime import datetime

import requests
import streamlit as st
from bs4 import BeautifulSoup
import yfinance as yf

st.set_page_config(
    page_title="주식 매매 대시보드",
    page_icon="📊",
    layout="wide"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


# -----------------------------
# 데이터 수집 함수
# -----------------------------
@st.cache_data(ttl=300)
def get_yfinance_change(ticker: str):
    try:
        data = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
        if len(data) < 2:
            return {"price": 0.0, "change_pct": 0.0}

        prev_close = float(data["Close"].iloc[-2])
        last_close = float(data["Close"].iloc[-1])

        if prev_close == 0:
            return {"price": last_close, "change_pct": 0.0}

        change_pct = (last_close - prev_close) / prev_close * 100
        return {"price": last_close, "change_pct": change_pct}
    except Exception:
        return {"price": 0.0, "change_pct": 0.0}


@st.cache_data(ttl=300)
def get_naver_stock(code: str):
    url = f"https://finance.naver.com/item/main.naver?code={code}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        text = soup.get_text(" ", strip=True)

        # 예시:
        # 현재가 189,700 전일대비 상승 3,400 플러스 1.83 퍼센트
        pattern = re.search(
            r"현재가\s*([\d,]+)\s*전일대비\s*(상승|하락)\s*([\d,]+)\s*(플러스|마이너스)\s*([\d.]+)\s*퍼센트",
            text
        )

        if not pattern:
            return {
                "ok": False,
                "price": 0,
                "change_pct": 0.0,
                "url": url,
            }

        price = int(pattern.group(1).replace(",", ""))
        sign_text = pattern.group(4)
        pct = float(pattern.group(5))

        if sign_text == "마이너스":
            pct = -pct

        return {
            "ok": True,
            "price": price,
            "change_pct": pct,
            "url": url,
        }

    except Exception:
        return {
            "ok": False,
            "price": 0,
            "change_pct": 0.0,
            "url": url,
        }


def calc_pnl(avg_price: float, qty: int, current_price: float):
    if avg_price <= 0 or qty <= 0 or current_price <= 0:
        return 0.0, 0.0, 0.0, 0.0

    invested = avg_price * qty
    evaluated = current_price * qty
    pnl = evaluated - invested
    pnl_pct = (pnl / invested) * 100 if invested else 0.0
    return invested, evaluated, pnl, pnl_pct


def signal_text(score: int):
    if score >= 8:
        return "🔥 매우 강한 상승 우세", "공격 매수 가능"
    elif score >= 6:
        return "✅ 상승 우세", "선별 매수 / 반도체 우선"
    elif score >= 4:
        return "⚖️ 중립", "짧은 단타만 / 추격매수 주의"
    elif score >= 2:
        return "📉 약세 우세", "관망 우선 / 무리한 진입 금지"
    else:
        return "🚨 강한 하락 우세", "관망 또는 곱버스 고려"


def color_box(message: str, detail: str, level: str):
    if level == "good":
        st.success(f"{message} → {detail}")
    elif level == "mid":
        st.warning(f"{message} → {detail}")
    else:
        st.error(f"{message} → {detail}")


# -----------------------------
# 사이드바 입력
# -----------------------------
st.sidebar.title("내 보유 종목")

samsung_avg = st.sidebar.number_input("삼성전자 평단", value=202239.0, step=100.0)
samsung_qty = st.sidebar.number_input("삼성전자 수량", value=46, step=1)

hynix_avg = st.sidebar.number_input("하이닉스 평단", value=1023478.0, step=100.0)
hynix_qty = st.sidebar.number_input("하이닉스 수량", value=20, step=1)

st.sidebar.divider()

kospi_night = st.sidebar.number_input(
    "코스피 야간선물 변동률(%)",
    value=0.0,
    step=0.01,
    format="%.2f",
    help="예: +0.82면 0.82 입력, -0.55면 -0.55 입력"
)

st.sidebar.caption("야간선물 화면 캡처를 보고 수치만 직접 넣으면 가장 정확함")


# -----------------------------
# 글로벌 지표
# -----------------------------
nasdaq = get_yfinance_change("^IXIC")
sp500 = get_yfinance_change("^GSPC")
sox = get_yfinance_change("^SOX")
oil = get_yfinance_change("CL=F")
usdkrw = get_yfinance_change("KRW=X")
nvidia = get_yfinance_change("NVDA")

samsung = get_naver_stock("005930")
hynix = get_naver_stock("000660")

# 네이버 실패 시 yfinance 백업
if not samsung["ok"]:
    samsung_yf = get_yfinance_change("005930.KS")
    samsung = {
        "ok": True,
        "price": round(samsung_yf["price"]),
        "change_pct": samsung_yf["change_pct"],
        "url": "https://finance.naver.com/item/main.naver?code=005930",
    }

if not hynix["ok"]:
    hynix_yf = get_yfinance_change("000660.KS")
    hynix = {
        "ok": True,
        "price": round(hynix_yf["price"]),
        "change_pct": hynix_yf["change_pct"],
        "url": "https://finance.naver.com/item/main.naver?code=000660",
    }


# -----------------------------
# 손익 계산
# -----------------------------
s_invested, s_eval, s_pnl, s_pnl_pct = calc_pnl(
    samsung_avg, int(samsung_qty), samsung["price"]
)
h_invested, h_eval, h_pnl, h_pnl_pct = calc_pnl(
    hynix_avg, int(hynix_qty), hynix["price"]
)

total_invested = s_invested + h_invested
total_eval = s_eval + h_eval
total_pnl = s_pnl + h_pnl
total_pnl_pct = (total_pnl / total_invested) * 100 if total_invested else 0.0


# -----------------------------
# 점수 계산
# -----------------------------
score = 0
detail_scores = []

if kospi_night > 0:
    score += 1
    detail_scores.append("야간선물 +")
else:
    detail_scores.append("야간선물 -")

if nasdaq["change_pct"] > 0:
    score += 1
    detail_scores.append("나스닥 +")
else:
    detail_scores.append("나스닥 -")

if sp500["change_pct"] > 0:
    score += 1
    detail_scores.append("S&P500 +")
else:
    detail_scores.append("S&P500 -")

if sox["change_pct"] > 0:
    score += 1
    detail_scores.append("SOX +")
else:
    detail_scores.append("SOX -")

if nvidia["change_pct"] > 0:
    score += 1
    detail_scores.append("엔비디아 +")
else:
    detail_scores.append("엔비디아 -")

if usdkrw["change_pct"] < 0:
    score += 1
    detail_scores.append("환율 하락(+)")
else:
    detail_scores.append("환율 상승(-)")

if oil["change_pct"] < 0:
    score += 1
    detail_scores.append("유가 하락(+)")
else:
    detail_scores.append("유가 상승(-)")

if samsung["change_pct"] > 0:
    score += 1
    detail_scores.append("삼성전자 +")
else:
    detail_scores.append("삼성전자 -")

if hynix["change_pct"] > 0:
    score += 1
    detail_scores.append("하이닉스 +")
else:
    detail_scores.append("하이닉스 -")

semi_score = 0
if sox["change_pct"] > 0:
    semi_score += 1
if nvidia["change_pct"] > 0:
    semi_score += 1
if hynix["change_pct"] > 0:
    semi_score += 1
if samsung["change_pct"] > 0:
    semi_score += 1

signal_main, signal_detail = signal_text(score)


# -----------------------------
# 화면
# -----------------------------
st.title("📊 주식 매매 대시보드")
st.caption(f"업데이트 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 상단 요약
r1c1, r1c2, r1c3, r1c4, r1c5, r1c6 = st.columns(6)
r1c1.metric("코스피 야간선물", f"{kospi_night:.2f}%")
r1c2.metric("나스닥", f"{nasdaq['change_pct']:.2f}%")
r1c3.metric("S&P500", f"{sp500['change_pct']:.2f}%")
r1c4.metric("SOX", f"{sox['change_pct']:.2f}%")
r1c5.metric("유가", f"{oil['change_pct']:.2f}%")
r1c6.metric("환율", f"{usdkrw['change_pct']:.2f}%")

st.divider()

r2c1, r2c2, r2c3, r2c4 = st.columns(4)
r2c1.metric("엔비디아", f"{nvidia['change_pct']:.2f}%")
r2c2.metric("삼성전자", f"{samsung['change_pct']:.2f}%", f"{samsung['price']:,}원")
r2c3.metric("하이닉스", f"{hynix['change_pct']:.2f}%", f"{hynix['price']:,}원")
r2c4.metric("반도체 점수", f"{semi_score} / 4")

st.divider()

# 자동 판단
st.subheader("오늘 매매 판단")

if score >= 8:
    color_box(signal_main, signal_detail, "good")
elif score >= 4:
    color_box(signal_main, signal_detail, "mid")
else:
    color_box(signal_main, signal_detail, "bad")

j1, j2, j3 = st.columns(3)
j1.metric("시장 점수", f"{score} / 9")
j2.metric("반도체 점수", f"{semi_score} / 4")
j3.metric("총 손익", f"{total_pnl:,.0f}원", f"{total_pnl_pct:.2f}%")

st.caption("기준: 야간선물, 미국지수, 반도체, 환율, 유가, 보유종목 흐름 종합")

st.divider()

# 반도체 집중 해석
st.subheader("반도체 집중 분석")

semi_comments = []

if sox["change_pct"] > 0 and nvidia["change_pct"] > 0:
    semi_comments.append("미국 반도체 분위기는 강한 편")
elif sox["change_pct"] < 0 and nvidia["change_pct"] < 0:
    semi_comments.append("미국 반도체 분위기는 약한 편")
else:
    semi_comments.append("미국 반도체는 혼조세")

if hynix["change_pct"] > samsung["change_pct"]:
    semi_comments.append("오늘은 하이닉스가 상대적으로 더 강한 흐름")
elif samsung["change_pct"] > hynix["change_pct"]:
    semi_comments.append("오늘은 삼성전자가 상대적으로 더 강한 흐름")
else:
    semi_comments.append("삼성전자와 하이닉스 강도는 비슷함")

if kospi_night > 0 and semi_score >= 3:
    semi_comments.append("국내 반도체는 시초가 이후 눌림목 매매 유리 가능성")
elif kospi_night < 0 and semi_score <= 1:
    semi_comments.append("반도체 추격매수는 위험, 초반 변동성 주의")
else:
    semi_comments.append("반도체는 장중 확인 후 짧게 대응하는 게 유리")

for comment in semi_comments:
    st.write(f"- {comment}")

st.divider()

# 보유 종목 손익
st.subheader("보유 종목 손익")

c1, c2 = st.columns(2)

with c1:
    st.markdown("### 삼성전자")
    st.metric("현재가", f"{samsung['price']:,}원")
    st.metric("매입금액", f"{s_invested:,.0f}원")
    st.metric("평가금액", f"{s_eval:,.0f}원")
    st.metric("손익", f"{s_pnl:,.0f}원", f"{s_pnl_pct:.2f}%")
    st.link_button("네이버 삼성전자 차트", samsung["url"])

with c2:
    st.markdown("### SK하이닉스")
    st.metric("현재가", f"{hynix['price']:,}원")
    st.metric("매입금액", f"{h_invested:,.0f}원")
    st.metric("평가금액", f"{h_eval:,.0f}원")
    st.metric("손익", f"{h_pnl:,.0f}원", f"{h_pnl_pct:.2f}%")
    st.link_button("네이버 하이닉스 차트", hynix["url"])

st.divider()

# 총합
st.subheader("총합")

t1, t2, t3 = st.columns(3)
t1.metric("총 매입금액", f"{total_invested:,.0f}원")
t2.metric("총 평가금액", f"{total_eval:,.0f}원")
t3.metric("총 손익", f"{total_pnl:,.0f}원", f"{total_pnl_pct:.2f}%")

st.divider()

# 차트/바로가기
st.subheader("차트 바로가기")

l1, l2, l3, l4 = st.columns(4)
with l1:
    st.link_button("나스닥 차트", "https://finance.yahoo.com/quote/%5EIXIC/chart/")
with l2:
    st.link_button("엔비디아 차트", "https://finance.yahoo.com/quote/NVDA/chart/")
with l3:
    st.link_button("삼성전자 차트", "https://finance.naver.com/item/main.naver?code=005930")
with l4:
    st.link_button("하이닉스 차트", "https://finance.naver.com/item/main.naver?code=000660")

st.divider()

# 세부 점수
with st.expander("세부 점수 보기"):
    for item in detail_scores:
        st.write(f"- {item}")

with st.expander("초보자용 해석"):
    st.write("- 야간선물 플러스면 한국장 시작 분위기가 좋은 편")
    st.write("- SOX와 엔비디아가 같이 강하면 반도체 확률이 좋아짐")
    st.write("- 환율 하락은 외국인 수급에 상대적으로 긍정적")
    st.write("- 유가 급등은 시장 부담일 수 있음")
    st.write("- 점수가 높아도 시초가 추격매수는 조심하고 눌림 확인이 중요")
