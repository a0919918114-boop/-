import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# 1. 網頁基礎設定
st.set_page_config(
    page_title="期貨市場每日交易訊號自動更新網頁",
    page_icon="📈",
    layout="wide"
)

# 介面語系與排版優化 (Tailwind 風格 CSS)
st.markdown("""
    <style>
    .big-title { font-size:2.2rem !important; font-weight: 700; color: #1E3A8A; text-align: center; margin-bottom: 0.5rem; }
    .sub-title { font-size:1.2rem !important; color: #4B5563; text-align: center; margin-bottom: 2rem; }
    .card { padding: 1.5rem; border-radius: 0.5rem; background-color: #F3F4F6; margin-bottom: 1rem; border-left: 5px solid #3B82F6; }
    .alert-card { padding: 1.5rem; border-radius: 0.5rem; background-color: #FEE2E2; margin-bottom: 1rem; border: 2px solid #EF4444; border-left: 10px solid #EF4444; animation: blinker 1.5s linear infinite; }
    @keyframes blinker { 50% { opacity: 0.8; } }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="big-title">🎯 今日最佳下單訊號與持倉追蹤系統</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">系統每日自動更新，結合多重指標評分與個人持倉即時止損追蹤通知</div>', unsafe_allow_html=True)

# 2. 定義要追蹤的期貨商品代號
FUTURE_MAP = {
    "台指期近月 (WTX=F)": "WTX=F",
    "微型小道瓊近月 (MYM=F)": "MYM=F",
    "黃金期貨近月 (GC=F)": "GC=F",
    "輕原油期貨近月 (CL=F)": "CL=F"
}

@st.cache_data(ttl=60)  # 將快取縮短為 60 秒，以便即時追蹤您的買進價損益
def fetch_and_analyze(ticker_name, ticker_symbol):
    try:
        df = yf.download(ticker_symbol, period="6mo", interval="1d", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # 3. 技術指標計算 (KD, MACD)
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
        
        if score > 0:
            direction = f"偏多 (Score: +{score})"
            color_code = "#10B981"
            stop_loss_val = float(df['Low'].iloc[-5:].min())
        elif score < 0:
            direction = f"偏空 (Score: {score})"
            color_code = "#EF4444"
            stop_loss_val = float(df['High'].iloc[-5:].max())
        else:
            direction = "中性觀望 (Score: 0)"
            color_code = "#6B7280"
            stop_loss_val = float(df['Close'].iloc[-1])
            
        return {
            "name": ticker_name,
            "symbol": ticker_symbol,
            "price": round(float(today['Close']), 2),
            "abs_score": abs(score),
            "direction": direction,
            "color": color_code,
            "stop_loss": round(stop_loss_val, 2),
            "df": df
        }
    except Exception as e:
        return None

# 執行基礎數據獲取
all_data = {}
for name, symbol in FUTURE_MAP.items():
    res = fetch_and_analyze(name, symbol)
    if res: all_data[name] = res

# ==================== 【新功能：輸入與追蹤面板】 ====================
st.sidebar.markdown("### 📥 個人持倉輸入面板 (Trace Panel)")
enable_trade = st.sidebar.checkbox("開啟持倉追蹤功能", value=False)

user_position = None
if enable_trade:
    trade_name = st.sidebar.selectbox("請選擇已買進商品", list(FUTURE_MAP.keys()))
    trade_type = st.sidebar.radio("交易方向", ["做多 (Buy)", "做空 (Sell)"])
    
    # 根據選中商品帶入當前價做為參考預設值
    current_market_price = all_data[trade_name]["price"] if trade_name in all_data else 0.0
    sys_suggest_sl = all_data[trade_name]["stop_loss"] if trade_name in all_data else 0.0
    
    user_price = st.sidebar.number_input("您的成交價格 (Entry Price)", value=float(current_market_price), step=1.0)
    user_sl = st.sidebar.number_input("您的自訂止損點 (Stop Loss)", value=float(sys_suggest_sl), step=1.0)
    
    user_position = {
        "name": trade_name,
        "type": trade_type,
        "entry_price": user_price,
        "stop_loss": user_sl
    }

# ==================== 【新功能：輸出損益與通知機制】 ====================
if user_position and user_position["name"] in all_data:
    st.markdown("### 🔔 即時持倉追蹤與通知狀態")
    target = all_data[user_position["name"]]
    now_p = target["price"]
    ent_p = user_position["entry_price"]
    sl_p = user_position["stop_loss"]
    
    # 計算未實現損益點數
    if "做多" in user_position["type"]:
        pnl = now_p - ent_p
        is_triggered = now_p <= sl_p
    else:
        pnl = ent_p - now_p
        is_triggered = now_p >= sl_p
        
    pnl_color = "#DC2626" if pnl < 0 else "#10B981"
    pnl_sign = "+" if pnl >= 0 else ""
    
    # 輸出通知卡片
    if is_triggered:
        st.markdown(f"""
        <div class="alert-card">
            <span style="font-size: 1.5rem; font-weight: bold; color: #DC2626;">⚠️ 觸發止損通知！！</span><br>
            您持有的 <b>{user_position["name"]}</b> 當前市場價為 <span style="font-size:1.3rem; font-weight:bold;">{now_p}</span>，
            已{'跌破' if '做多' in user_position['type'] else '突破'}您設定的止損價 <b>{sl_p}</b>！<br>
            當前持倉損益：<b style="color:{pnl_color}; font-size:1.2rem;">{pnl_sign}{round(pnl, 2)} 點</b>。建議立即評估出場！
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="card" style="border-left-color: #3B82F6; background-color: #EFF6FF;">
            <span style="font-size: 1.2rem; font-weight: bold; color: #1E3A8A;">✅ 持倉正常追蹤中</span><br>
            監控商品：<b>{user_position["name"]} ({user_position["type"]})</b> | 
            買進價格：<b>{ent_p}</b> | 
            自訂止損：<b>{sl_p}</b><br>
            當前最新價：<b>{now_p}</b> | 
            未實現損益：<b style="color:{pnl_color}; font-size:1.3rem;">{pnl_sign}{round(pnl, 2)} 點</b> (未觸及止損，請安心持有)
        </div>
        """, unsafe_allow_html=True)
    st.markdown("---")

# 4. 原有每日最佳下單訊號前端呈現
st.markdown("### 📊 今日推薦觀察商品榜單")
results = sorted(list(all_data.values()), key=lambda x: x["abs_score"], reverse=True)[:3]

if not results:
    st.info("💡 暫時無法獲取數據，請稍後再試。")
else:
    for i, item in enumerate(results):
        st.markdown(f"""
        <div class="card" style="border-left-color: {item["color"]};">
            <span style="font-size:1.2rem; font-weight:bold; color:#1F2937;">Top {i+1} 推薦觀察：{item["name"]}</span><br>
            <span style="font-size:1.4rem; font-weight:bold; color:{item["color"]};">{item["direction"]}</span> | 
            當前價格: <b>{item["price"]}</b> | 
            系統建議止損參考: <b style="color:#DC2626;">{item["stop_loss"]}</b>
        </div>
        """, unsafe_allow_html=True)
        
        df_plot = item["df"].tail(40)
        fig = go.Figure(data=[go.Candlestick(
            x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name='K線'
        )])
        fig.update_layout(margin=dict(l=20, r=20, t=10, b=10), height=240, xaxis_rangeslider_visible=False, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

st.caption(f"系統最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (每分鐘自動追蹤整理)")
