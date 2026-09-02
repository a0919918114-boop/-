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
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="big-title">🎯 今日最佳下單訊號商品</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">系統每日自動更新，依據多重技術指標綜合評分篩選之最佳訊號</div>', unsafe_allow_html=True)

# 2. 定義要追蹤的期貨商品代號
FUTURE_MAP = {
    "台指期近月 (WTX=F)": "WTX=F",
    "微型小道瓊近月 (MYM=F)": "MYM=F",
    "黃金期貨近月 (GC=F)": "GC=F",
    "輕原油期貨近月 (CL=F)": "CL=F"
}

@st.cache_data(ttl=3600)  # 快取 1 小時
def fetch_and_analyze(ticker_name, ticker_symbol):
    try:
        # 獲取日 K 線數據
        df = yf.download(ticker_symbol, period="6mo", interval="1d", progress=False)
        if df.empty:
            return None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 3. 純原生數學公式計算技術指標
        # --- 計算 KD 指標 (9, 3, 3) ---
        low_9 = df['Low'].rolling(window=9).min()
        high_9 = df['High'].rolling(window=9).max()
        rsv = ((df['Close'] - low_9) / (high_9 - low_9)) * 100
        
        k_list, d_list = [], []
        current_k, current_d = 50.0, 50.0
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
        
        # 取得最新數據
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        
        score = 0
        
        # 策略 A: 價格突破前日高低點
        break_up = today['Close'] > yesterday['High']
        break_down = today['Close'] < yesterday['Low']
        
        # 策略 B: KD 交叉
        kd_golden = (yesterday['K'] < yesterday['D']) and (today['K'] > today['D'])
        kd_death = (yesterday['K'] > yesterday['D']) and (today['K'] < today['D'])
        
        # 策略 C: MACD 柱狀圖轉折
        macd_up = today['MACD_hist'] > yesterday['MACD_hist']
        macd_down = today['MACD_hist'] < yesterday['MACD_hist']
        
        # 綜合評分
        if break_up: score += 2
        if kd_golden: score += 3
        if macd_up and today['MACD_hist'] > 0: score += 1
            
        if break_down: score -= 2
        if kd_death: score -= 3
        if macd_down and today['MACD_hist'] < 0: score -= 1
        
        # 根據最終正負分決定建議方向與停損點
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

# 執行分析
results = []
for name, symbol in FUTURE_MAP.items():
    res = fetch_and_analyze(name, symbol)
    if res:
        results.append(res)

# 按照訊號強烈程度（絕對值分數）排序，選出前 3 名
results = sorted(results, key=lambda x: x["abs_score"], reverse=True)[:3]

# 4. 網頁前端呈現
if not results:
    st.info("💡 暫時無法獲取數據，請稍後再試。")
else:
    for i, item in enumerate(results):
        st.markdown(f"""
        <div class="card" style="border-left-color: {item["color"]};">
            <span style="font-size:1.2rem; font-weight:bold; color:#1F2937;">Top {i+1} 推薦觀察：{item["name"]}</span><br>
            <span style="font-size:1.4rem; font-weight:bold; color:{item["color"]};">{item["direction"]}</span> | 
            當前價格: <b>{item["price"]}</b> | 
            建議停損參考: <b style="color:#DC2626;">{item["stop_loss"]}</b>
        </div>
        """, unsafe_allow_html=True)
        
        # 繪製 K 線圖
        df_plot = item["df"].tail(40)
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
            height=280,
            xaxis_rangeslider_visible=False,
            template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)

st.caption(f"系統最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (每小時自動重新整理)")
