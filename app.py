import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import requests
import time

# 1. 網頁基礎設定
st.set_page_config(
    page_title="期貨市場多商品量化追蹤後台",
    page_icon="📈",
    layout="wide"
)

# 強制初始化持倉資料庫
if "my_positions" not in st.session_state:
    st.session_state["my_positions"] = []

# ==================== 🔑 【您的個人專屬免鎖 IP 專業密鑰】 ====================
api_key = "387a43f63e6749c1af87b62a962f4b7f"

if st.sidebar.button("🔄 手動即時重新整理"):
    st.cache_data.clear()
    st.rerun()

st.title("🎯 期貨智慧量化下單與多持倉即時追蹤系統")
st.write(f"數據每 30 分鐘自動跳動更新（Twelve Data 專業版引擎） | 當前看盤時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown("---")

# Twelve Data 標準全球熱門商品字典
FUTURE_MAP = {
    "台綜合股價指數 (TWII)": "TWII",
    "道瓊工業指數 (DJI)": "DJI",
    "那斯達克100指數 (NDX)": "NDX",
    "標普500指數 (SPX)": "SPX",
    "日經225指數 (N225)": "N225",
    "現貨黃金美金 (XAU/USD)": "XAU/USD",
    "現貨白銀美金 (XAG/USD)": "XAG/USD",
    "布蘭特原油美金 (BRENT)": "BRENT",
    "亨利港天然氣 (NG)": "NG"
}

@st.cache_data(ttl=1800) # 30分鐘長快取
def fetch_and_analyze_pro(ticker_name, ticker_symbol, api_key):
    try:
        url = f"https://twelvedata.com{ticker_symbol}&interval=1day&outputsize=130&apikey={api_key}"
        response = requests.get(url).json()
        
        if "values" not in response:
            return None
            
        data = response["values"]
        df = pd.DataFrame(data)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime').reset_index(drop=True)
        
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col])
            
        df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'})
        df.set_index('datetime', inplace=True)

        # 原生技術指標計算 (KD, MACD)
        low_9 = df['Low'].rolling(window=9).min()
        high_9 = df['High'].rolling(window=9).max()
        rsv = ((df['Close'] - low_9) / (high_9 - low_9)) * 100
        
        k_list, d_list = [], []
        current_k, current_d = 50.0, 50.0
        for r in rsv:
            if pd.isna(r):
                k_list.append(None); d_list.append(None)
            else:
                current_k = (2/3) * current_k + (1/3) * r
                current_d = (2/3) * current_d + (1/3) * current_k
                k_list.append(current_k); d_list.append(current_d)
        df['K'], df['D'] = k_list, d_list
        
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = ema12 - ema26
        df['MACD_signal'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_hist'] = df['DIF'] - df['MACD_signal']
        
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        score = 0
        
        break_up = today['Close'] > yesterday['High']
        break_down = today['Close'] < yesterday['Low']
        kd_golden = (yesterday['K'] < yesterday['D']) and (today['K'] > today['D'])
        kd_death = (yesterday['K'] > yesterday['D']) and (today['K'] < today['D'])
        macd_up = today['MACD_hist'] > yesterday['MACD_hist']
        macd_down = today['MACD_hist'] < yesterday['MACD_hist']
        
        if break_up: score += 2
        if kd_golden: score += 3
        if macd_up and today['MACD_hist'] > 0: score += 1
        if break_down: score -= 2
        if kd_death: score -= 3
        if macd_down and today['MACD_hist'] < 0: score -= 1
        
        score_100 = int(((score + 6) / 12) * 100)
        
        if score > 0:
            direction = f"偏多 (分數: {score_100}/100)"
            stop_loss_val = float(df['Low'].iloc[-5:].min())
        elif score < 0:
            direction = f"偏空 (分數: {score_100}/100)"
            stop_loss_val = float(df['High'].iloc[-5:].max())
        else:
            direction = f"中性觀望 (分數: {score_100}/100)"
            stop_loss_val = float(df['Close'].iloc[-1])
            
        return {
            "name": ticker_name,
            "symbol": ticker_symbol,
            "price": round(float(today['Close']), 2),
            "score_100": score_100,
            "direction": direction,
            "stop_loss": round(stop_loss_val, 2),
            "kd_signal": "GOLDEN" if kd_golden else ("DEATH" if kd_death else "NONE"),
            "df": df
        }
    except:
        return None

# 執行資料抓取
all_data = {}
for name, symbol in FUTURE_MAP.items():
    res = fetch_and_analyze_pro(name, symbol, api_key)
    if res:
        all_data[name] = res

# ==================== 📥 持倉輸入面板 ====================
st.sidebar.markdown("### 📥 持倉設定面板")
if all_data:
    trade_name = st.sidebar.selectbox("持有商品", list(all_data.keys()))
    trade_type = st.sidebar.radio("交易方向", ["做多 (Buy)", "做空 (Sell)"])
    
    current_market_price = all_data[trade_name]["price"]
    sys_suggest_sl = all_data[trade_name]["stop_loss"]
    
    user_price = st.sidebar.number_input("您的買進價格 (Entry)", value=float(current_market_price), step=1.0)
    user_sl = st.sidebar.number_input("自訂固定止損點", value=float(sys_suggest_sl), step=1.0)
    user_tp = st.sidebar.number_input("自訂止盈目標價 (0代表不設)", value=0.0, step=1.0)
    
    if st.sidebar.button("➕ 新增至即時追蹤面板", use_container_width=True):
        new_pos = {
            "id": str(time.time()), 
            "name": trade_name,
            "type": trade_type,
            "entry_price": user_price,
            "stop_loss": user_sl,
            "take_profit": user_tp
        }
        st.session_state.my_positions.append(new_pos)
        st.sidebar.success(f"成功新增：{trade_name}")
        st.rerun()

# ==================== 📊 輸出：持倉追蹤 ====================
if st.session_state.my_positions and all_data:
    st.subheader("🎛️ 我的即時監控持倉群組 (Active Portfolio)")
    for pos in list(st.session_state.my_positions):
        if pos["name"] not in all_data: continue
        
        target = all_data[pos["name"]]
        now_p = target["price"]
        ent_p = pos["entry_price"]
        sl_p = pos["stop_loss"]
        tp_p = pos["take_profit"]
        
        if "做多" in pos["type"]:
            pnl = now_p - ent_p
            hit_sl = now_p <= sl_p
            hit_tp = (now_p >= tp_p) if tp_p > 0 else False
            tech_exit = target["kd_signal"] == "DEATH"
        else:
            pnl = ent_p - now_p
            hit_sl = now_p >= sl_p
            hit_tp = (now_p <= tp_p) if tp_p > 0 else False
            tech_exit = target["kd_signal"] == "GOLDEN"
            
        pnl_sign = "+" if pnl >= 0 else ""
        exit_status_text = "✅ 持倉狀態：健全持股中"
        
        if hit_sl: exit_status_text = "🚨 出場訊號通知：價格已穿透您的自訂止損點！"
        elif hit_tp: exit_status_text = "🎯 出場訊號通知：價格已達到您的預設止盈點！"
        elif tech_exit: exit_status_text = "⚠️ 出場訊號通知：技術指標出現反轉交叉！"

        # 用原生看板方格呈現
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label=f"📈 {pos['name']} ({pos['type']})", value=f"成本: {ent_p}")
        with col2:
            st.metric(label="當前市場報價", value=str(now_p), delta=f"{pnl_sign}{round(pnl, 2)} 點")
        with col3:
            st.metric(label="防守止損線", value=str(sl_p))
            
        if "🚨" in exit_status_text or "⚠️" in exit_status_text:
            st.error(exit_status_text)
        else:
            st.success(exit_status_text)
            
        if st.button(f"❌ 刪除「{pos['name']}」監控", key=f"del_{pos['id']}", use_container_width=True):
            st.session_state.my_positions.remove(pos)
            st.rerun()
    st.markdown("---")

# 4. 每日技術分析榜單呈現
if all_data:
    st.subheader("📊 今日全商品推薦觀察榜單")
    results = sorted(list(all_data.values()), key=lambda x: x["score_100"], reverse=True)
    
    for item in results:
        # 用內建元件代替HTML三引號
        st.info(f"📌 觀察商品：{item['name']} | 【{item['direction']}】 | 當前價格: {item['price']} | 系統建議止損: {item['stop_loss']}")
        
        df_plot = item["df"].tail(40)
        fig = go.Figure(data=[go.Candlestick(
            x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name='K線'
        )])
        fig.update_layout(margin=dict(l=20, r=20, t=10, b=10), height=220, xaxis_rangeslider_visible=False, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

st.caption(f"系統最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (每30分鐘自動跳動更新)")

# 30分鐘刷新
time.sleep(1800)
st.rerun()
