import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

# 1. 網頁基礎設定
st.set_page_config(
    page_title="期貨市場每日交易訊號自動更新網頁",
    page_icon="📈",
    layout="wide"
)

# 2. 自動定時刷新機制 (每 10 秒網頁自動在背景重新載入最新價格)
# 透過 Streamlit 內建 session_state 模擬計時器，免額外安裝套件
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

# 介面語系與排版優化 (Tailwind 風格 CSS)
st.markdown("""
    <style>
    .big-title { font-size:2.2rem !important; font-weight: 700; color: #1E3A8A; text-align: center; margin-bottom: 0.5rem; }
    .sub-title { font-size:1.2rem !important; color: #4B5563; text-align: center; margin-bottom: 2rem; }
    .card { padding: 1.5rem; border-radius: 0.5rem; background-color: #F3F4F6; margin-bottom: 1rem; border-left: 5px solid #3B82F6; }
    
    /* 追蹤小方格專用樣式 */
    .track-grid { display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 2rem; }
    .track-box { flex: 1; min-width: 250px; max-width: 350px; padding: 1.2rem; border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border-top: 6px solid #6B7280; background-color: #FFFFFF; }
    .track-box.profit { border-top-color: #10B981; background-color: #F0FDF4; }
    .track-box.loss { border-top-color: #EF4444; background-color: #FEF2F2; }
    .track-box.alert { border-top-color: #F59E0B; background-color: #FFFBEB; animation: pulse 2s infinite; }
    
    @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.02); } }
    </style>
    """, unsafe_allow_html=True)

# 側邊欄：手動手動刷新按鈕
if st.sidebar.button("🔄 手動即時重新整理"):
    st.cache_data.clear()
    st.rerun()

st.markdown('<div class="big-title">🎯 期貨智慧量化下單與即時持倉追蹤系統</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-title">數據每 10 秒背景自動跳動更新 | 最後同步時間：{datetime.now().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)

# 3. 定義要追蹤的期貨商品代號
FUTURE_MAP = {
    "台指期近月 (WTX=F)": "WTX=F",
    "微型小道瓊近月 (MYM=F)": "MYM=F",
    "黃金期貨近月 (GC=F)": "GC=F",
    "輕原油期貨近月 (CL=F)": "CL=F"
}

@st.cache_data(ttl=10)  # 快取縮短為 10 秒，達成自動追蹤效果
def fetch_and_analyze(ticker_name, ticker_symbol):
    try:
        df = yf.download(ticker_symbol, period="6mo", interval="1d", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # 技術指標計算 (KD, MACD)
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
            "kd_signal": "GOLDEN" if kd_golden else ("DEATH" if kd_death else "NONE"),
            "df": df
        }
    except Exception as e:
        return None

# 撈取最新資料
all_data = {}
for name, symbol in FUTURE_MAP.items():
    res = fetch_and_analyze(name, symbol)
    if res: all_data[name] = res

# ==================== 📥 側邊欄：持倉輸入面板 ====================
st.sidebar.markdown("### 📥 持倉設定面板")
enable_trade = st.sidebar.checkbox("開啟持倉追蹤功能", value=True)

user_position = None
if enable_trade:
    trade_name = st.sidebar.selectbox("持有商品", list(FUTURE_MAP.keys()))
    trade_type = st.sidebar.radio("交易方向", ["做多 (Buy)", "做空 (Sell)"])
    
    current_market_price = all_data[trade_name]["price"] if trade_name in all_data else 0.0
    sys_suggest_sl = all_data[trade_name]["stop_loss"] if trade_name in all_data else 0.0
    
    user_price = st.sidebar.number_input("您的買進價格 (Entry)", value=float(current_market_price), step=1.0)
    user_sl = st.sidebar.number_input("自訂固定止損點", value=float(sys_suggest_sl), step=1.0)
    user_tp = st.sidebar.number_input("自訂止盈目標價 (0代表不設)", value=0.0, step=1.0)
    
    user_position = {
        "name": trade_name,
        "type": trade_type,
        "entry_price": user_price,
        "stop_loss": user_sl,
        "take_profit": user_tp
    }

# ==================== 📊 輸出：持倉追蹤小方格與出場訊號 ====================
if user_position and user_position["name"] in all_data:
    st.markdown("### 🎛️ 即時持倉追蹤看板 (Trading Dashboard)")
    
    target = all_data[user_position["name"]]
    now_p = target["price"]
    ent_p = user_position["entry_price"]
    sl_p = user_position["stop_loss"]
    tp_p = user_position["take_profit"]
    
    # 計算未實現損益點數
    if "做多" in user_position["type"]:
        pnl = now_p - ent_p
        hit_sl = now_p <= sl_p
        hit_tp = (now_p >= tp_p) if tp_p > 0 else False
        tech_exit = target["kd_signal"] == "DEATH"  # 多單遇到指標死亡交叉提示出場
    else:
        pnl = ent_p - now_p
        hit_sl = now_p >= sl_p
        hit_tp = (now_p <= tp_p) if tp_p > 0 else False
        tech_exit = target["kd_signal"] == "GOLDEN" # 空單遇到指標黃金交叉提示出場
        
    pnl_sign = "+" if pnl >= 0 else ""
    
    # 判斷方格狀態與出場訊號內容
    box_class = "profit" if pnl >= 0 else "loss"
    exit_status_text = "正常持股中"
    
    if hit_sl:
        box_class = "alert"
        exit_status_text = "🚨 出場訊號：已跌破自訂止損點！"
    elif hit_tp:
        box_class = "alert"
        exit_status_text = "🎯 出場訊號：已達到止盈目標價！"
    elif tech_exit:
        box_class = "alert"
        exit_status_text = "⚠️ 出場訊號：技術指標出現反轉交叉！"

    # 用 HTML + CSS 渲染出精緻的獨立小方格
    st.markdown(f"""
    <div class="track-grid">
        <div class="track-box {box_class}">
            <div style="font-size: 0.9rem; color: #6B7280; font-weight: bold;">MONITORING 商品</div>
            <div style="font-size: 1.3rem; font-weight: bold; color: #111827; margin-bottom: 0.5rem;">{user_position["name"]}</div>
            <div style="font-size: 0.85rem; color: #4B5563;">方向：<b>{user_position["type"]}</b></div>
            <div style="font-size: 0.85rem; color: #4B5563;">成本：<b>{ent_p}</b> | 止損：<b>{sl_p}</b></div>
        </div>
        <div class="track-box {box_class}">
            <div style="font-size: 0.9rem; color: #6B7280; font-weight: bold;">REAL-TIME MARKET</div>
            <div style="font-size: 1.8rem; font-weight: bold; color: #111827;">{now_p}</div>
            <div style="font-size: 0.85rem; color: #6B7280;">最新市場報價</div>
        </div>
        <div class="track-box {box_class}">
            <div style="font-size: 0.9rem; color: #6B7280; font-weight: bold;">UNREALIZED PNL</div>
            <div style="font-size: 1.8rem; font-weight: bold; color: {'#10B981' if pnl >= 0 else '#EF4444'};">{pnl_sign}{round(pnl, 2)} 點</div>
            <div style="font-size: 0.85rem; color: #6B7280;">當前持倉未實現損益</div>
        </div>
        <div class="track-box {box_class}">
            <div style="font-size: 0.9rem; color: #6B7280; font-weight: bold;">SIGNAL STATUS</div>
            <div style="font-size: 1.1rem; font-weight: bold; color: {'#111827' if box_class != 'alert' else '#DC2626'}; margin-top: 0.3rem;">{exit_status_text}</div>
            <div style="font-size: 0.85rem; color: #6B7280;">系統智慧出場提示</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

# 5. 原有每日最佳下單訊號前端呈現
st.markdown("### 📊 今日推薦觀察商品榜單")
results = sorted(list(all_data.values()), key=lambda x: x["abs_score"], reverse=True)[:3]

if not results:
    st.info("💡 暫時無法獲取數據，請稍後再試。")
else:
    for i, item in enumerate(results):
        color = item["color"]
        st.markdown(f"""
        <div class="card" style="border-left-color: {color};">
            <span style="font-size:1.2rem; font-weight:bold; color:#1F2937;">Top {i+1} 推薦觀察：{item["name"]}</span><br>
            <span style="font-size:1.4rem; font-weight:bold; color:{color};">{item["direction"]}</span> | 
            當前價格: <b>{item["price"]}</b> | 
            系統建議止損參考: <b style="color:#DC2626;">{item["stop_loss"]}</b>
        </div>
        """, unsafe_allow_html=True)
        
        df_plot = item["df"].tail(40)
        fig = go.Figure(data=[go.Candlestick(
