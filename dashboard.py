import re
from datetime import datetime

import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(layout="wide", page_title="주식 매매 대시보드")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# -----------------------------
# 네이버 증권 종목 정보 가져오기
# -----------------------------
@st.cache_data(ttl=300)
def get_naver_stock(code: str):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        text = resp.text

        soup = BeautifulSoup(text, "lxml")
        plain = soup.get_text(" ", strip=True)

        # "현재가 189,700 전일대비 상승 3,400 플러스 1.83 퍼센트"
        m = re.search(
            r"현재가\s*([\d,]+)\s*전일대비\s*(상승|하락)\s*([\d,]+)\s*(플러스|마이너스)\s*([\d.]+)\s*퍼센트",
            plain,
        )
        if not m:
            return {
                "ok": False,
                "price": 0,
                "change_pct": 0.0,
                "url": url,
            }

        price = int(m.group(1).replace(",", ""))
        sign_word = m.group(4)
        pct = float(m.group(5))
        if sign_word == "마이너스":
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


# -----------------------------
# 코스피 야간선물 자동 수집
# -----------------------------
@st.cache_data(ttl=300)
def get_kospi_night_futures():
    url = "https://www.investing.com/indices/korea-200-futures"
    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        html = resp.text

        pct_match = re.search(r'([+-]?\d+\.\d+)%', html)
        price_match = re.search(r'"last"\s*:\s*"?(\\?[\d,]+\.\d+)"?', html)

        pct = None
        price = None

        if pct_match:
            pct = float(pct_match.group(1))
        if price_match:
            price = float(price_match.group(1).replace("\\", "").replace(",", ""))

        if pct is None:
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(" ", strip=True)
            pct_match2 = re.search(r'([+-]?\d+\.\d+)%', text)
            if pct_match2:
                pct = float(pct_match2.group(1))

        return {
            "ok": pct is not None,
            "change_pct": pct if pct is not None else 0.0,
            "price": price,
            "url": url,
        }
    except Exception:
        return {
            "ok": False,
            "change_pct": 0.0,
            "price": None,
            "url": url,
        }


def calc_pnl(avg_price: float, qty: int, current_price: int):
    if avg_price <= 0 or qty <= 0 or current_price <= 0:
        return 0, 0.0, 0
    invested = avg_price * qty
    evaluated = current_price * qty
    pnl = evaluated - invested
    pnl_pct = (pnl / invested) * 100 if invested else 0.0
    return pnl, pnl_pct, evaluated


# -----------------------------
# 데이터 가져오기
# -----------------------------
samsung = get_naver_stock("005930")
hynix = get_naver_stock("000660")
night_data = get_kospi_night_futures()

# 사용자 보유 정보
st.sidebar.header("내 보유 종목")

samsung_avg = st.sidebar.number_input("삼성전자 평단", value=202239.0, step=100.0)
samsung_qty = st.sidebar.number_input("삼성전자 수량", value=46, step=1)

hynix_avg = st.sidebar.number_input("하이닉스 평단", value=1023478.0, step=100.0)
hynix_qty = st.sidebar.number_input("하이닉스 수량", value=20, step=1)

# 손익 계산
samsung_pnl, samsung_pnl_pct, samsung_eval = calc_pnl(
    samsung_avg, int(samsung_qty), samsung["price"]
)
hynix_pnl, hynix_pnl_pct, hynix_eval = calc_pnl(
    hynix_avg, int(hynix_qty), hynix["price"]
)

# -----------------------------
# 화면
# -----------------------------
st.title("📊 주식 매매 대시보드")
st.caption(f"업데이트 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 상단 지표
c1, c2, c3 = st.columns(3)
if night_data["ok"]:
    c1.metric("코스피 야간선물", f"{night_data['change_pct']:.2f}%")
else:
    c1.metric("코스피 야간선물", "수집 실패")

c2.metric("삼성전자 등락률", f"{samsung['change_pct']:.2f}%")
c3.metric("하이닉스 등락률", f"{hynix['change_pct']:.2f}%")

st.divider()

# 보유 종목 손익
st.subheader("보유 종목 손익")

a1, a2 = st.columns(2)

with a1:
    st.markdown("### 삼성전자")
    st.metric("현재가", f"{samsung['price']:,}원")
    st.metric("평가금액", f"{samsung_eval:,.0f}원")
    st.metric("손익", f"{samsung_pnl:,.0f}원", f"{samsung_pnl_pct:.2f}%")
    st.link_button("네이버 삼성전자 차트", "https://finance.naver.com/item/main.naver?code=005930")

with a2:
    st.markdown("### SK하이닉스")
    st.metric("현재가", f"{hynix['price']:,}원")
    st.metric("평가금액", f"{hynix_eval:,.0f}원")
    st.metric("손익", f"{hynix_pnl:,.0f}원", f"{hynix_pnl_pct:.2f}%")
    st.link_button("네이버 하이닉스 차트", "https://finance.naver.com/item/main.naver?code=000660")

st.divider()

# 총 손익
total_pnl = samsung_pnl + hynix_pnl
total_eval = samsung_eval + hynix_eval
total_invested = samsung_avg * int(samsung_qty) + hynix_avg * int(hynix_qty)
total_pnl_pct = (total_pnl / total_invested) * 100 if total_invested else 0.0

st.subheader("총합")
t1, t2, t3 = st.columns(3)
t1.metric("총 매입금액", f"{total_invested:,.0f}원")
t2.metric("총 평가금액", f"{total_eval:,.0f}원")
t3.metric("총 손익", f"{total_pnl:,.0f}원", f"{total_pnl_pct:.2f}%")
