import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# 1. 網頁基礎設定 (RWD 響應式配置，修正 layout 為 wide)
st.set_page_config(
    page_title="期貨市場每日交易訊號自動更新網頁",
    page_icon="📈",
    layout="wide"
)

# 介面語系與排版優化 (Tailwind 風格 CSS)
st.markdown("""
    <style>
    .big-title { font-size:2.2rem !important; font-weight: 700; color: #1E3A8A; text-align: center; margin-bottom: 1rem; }
    .sub-title { font-size:1.2rem !important; color: #4B5563; text-align: center; margin-bottom: 2rem; }
    .card { padding: 1.5rem; border-radius: 0.5rem; background-color: #F3F4F6; margin-bottom: 1rem; border-left: 5px solid #3B82F6; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="big-title">🎯 今日最佳下單訊號商品</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">系統每日自動更新，依據多重技術指標綜合評分篩選之最佳訊號</div>', unsafe_allow_html=True)

# 2. 定義要追蹤的期貨商品代號 (Ticker)
FUTURE_MAP = {
    "台指期近月 (WTX=F)": "WTX=F",
    "微型小道瓊近月 (MYM=F)": "MYM=F",
    "黃金期貨近月 (GC=F)": "GC=F",
    "輕原油期貨近月 (CL=F)": "CL=F"
}

@st.cache_data(ttl=3600)  # 快取 1 小時，避免頻繁發送請求
def fetch_and_analyze(ticker_name, ticker_symbol):
    try:
        # 獲取日 K 線數據
        df = yf.download(ticker_symbol, period="6mo", interval="1d", progress=False)
        if df.empty:
            return None
        
        # 移除多重索引
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 3. 純原生數學公式計算技術指標 (不依賴外部套件)
        # --- 計算 KD 指標 (9, 3, 3) ---
        low_9 = df['Low'].rolling(window=9).min()
        high_9 = df['High'].rolling(window=9).max()
        rsv = ((df['Close'] - low_9) / (high_9 - low_9)) * 100
        
        k_list, d_list = [], []
        current_k, current_d = 50.0, 50.0 # 初始值
        for r in rsv:
            if pd.isna(r):
                k_list.append(None)
                d_list.append(None)
            else:
                current_k = (2/3) * current_k + (1/3) * r
                current_d = (2/3) * current_d + (1/3) * current_k
                k_list.append(current_k)
                d_list.append(current_d)
        df['K'] = k_list
        df['D'] = d_list
        
        # --- 計算 MACD 指標 (12, 26, 9) ---
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = ema12 - ema26
        df['MACD_signal'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_hist'] = df['DIF'] - df['MACD_signal']
        
        # 取得最新兩日數據做判斷
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        
        score = 0
        direction = "觀望"
        stop_loss_val = 0.0
        
        # 策略 A: 價格突破前日高低點
        break_up = today['Close'] > yesterday['High']
        break_down = today['Close'] < yesterday['Low']
        
        # 策略 B: KD 交叉
        kd_golden = (yesterday['K'] < yesterday['D']) and (today['K'] > today['D'])
        kd_death = (yesterday['K'] > yesterday['D']) and (today['K'] < today['D'])
        
        # 策略 C: MACD 柱狀圖轉折
        macd_up = today['MACD_hist'] > yesterday['MACD_hist']
        macd_down = today['MACD_hist'] < yesterday['MACD_hist']
        
        # 綜合評分評估
        if break_up: score += 2
        if kd_golden: score += 3
        if macd_up and today['MACD_hist'] > 0: score += 1
            
        if break_down: score -= 2
        if kd_death: score -= 3
        if macd_down and today['MACD_hist'] < 0: score -= 1
        
        # 決定方向與停損
        if score >= 3:
            direction = "多 (Long)"
            stop_loss_val = float(df['Low'].iloc[-5:].min()) # 以5日最低點當停損
        elif score <= -3:
            direction = "空 (Short)"
            stop_loss_val = float(df['High'].iloc[-5:].max()) # 以5日最高點當停損
            
        return {
            "name": ticker_name,
            "symbol": ticker_symbol,
            "price": round(float(today['Close']), 2),
            "score": abs(score),
            "direction": direction,
            "stop_loss": round(stop_loss_val, 2),
            "df": df
        }
    except Exception as e:
        return None

# 執行所有商品的數據獲取與分析
results = []
for name, symbol in FUTURE_MAP.items():
    res = fetch_and_analyze(name, symbol)
    if res and res["direction"] != "觀望":
        results.append(res)

# 依據分數排序，篩選出前 3 個最明確的商品
results = sorted(results, key=lambda x: x["score"], reverse=True)[:3]

# 4. 網頁前端呈現
if not results:
    st.info("💡 今日市場波動較平緩，目前無特明顯之技術面觸發訊號。建議維持原本部位觀望。")
else:
    # 呈現前三名商品卡片
    for i, item in enumerate(results):
        color = "#EF4444" if "空" in item["direction"] else "#10B981"
        st.markdown(f"""
        <div class="card" style="border-left-color: {color};">
            <span style="font-size:1.1rem; font-weight:bold; color:#1F2937;">Top {i+1} : {item["name"]}</span><br>
            <span style="font-size:1.5rem; font-weight:bold; color:{color};">{item["direction"]} 訊號</span> | 
            現在價格: <b>{item["price"]}</b> | 
            建議停損點 (Stop Loss): <b style="color:#DC2626;">{item["stop_loss"]}</b>
        </div>
        """, unsafe_allow_html=True)
        
        # 使用 Plotly 繪製 Chart
        df_plot = item["df"].tail(40) # 顯示最近40根 K 線
        fig = go.Figure(data=[go.Candlestick(
            x=df_plot.index,
            open=df_plot['Open'],
            high=df_plot['High'],
            low=df_plot['Low'],
            close=df_plot['Close'],
            name='K線'
        )])
        
        fig.update_layout(
            margin=dict(l=20, r=20, t=10, b=10),
            height=300,
            xaxis_rangeslider_visible=False,
            template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)

st.caption(f"系統最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (每小時自動重新整理)")
