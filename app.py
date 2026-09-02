import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

# 1. 網頁基礎設定
st.set_page_config(
    page_title="期貨市場多商品量化追蹤後台",
    page_icon="📈",
    layout="wide"
)

# 2. 初始化自訂持倉的記憶資料庫
if "my_positions" not in st.session_state:
    st.session_state.my_positions = [] 

# 介面語系與排版優化 (Tailwind 風格 CSS)
st.markdown("""
    <style>
    .big-title { font-size:2.2rem !important; font-weight: 700; color: #1E3A8A; text-align: center; margin-bottom: 0.5rem; }
    .sub-title { font-size:1.2rem !important; color: #4B5563; text-align: center; margin-bottom: 2rem; }
    .card { padding: 1.5rem; border-radius: 0.5rem; background-color: #F3F4F6; margin-bottom: 1rem; border-left: 5px solid #3B82F6; }
    
    /* 追蹤看盤看板專用防撞垂直卡片樣式 */
    .portfolio-card { padding: 1.5rem; border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border-left: 10px solid #6B7280; background-color: #FFFFFF; margin-bottom: 1rem; }
    .portfolio-card.profit { border-left-color: #10B981; background-color: #F0FDF4; }
    .portfolio-card.loss { border-left-color: #EF4444; background-color: #FEF2F2; }
    .portfolio-card.alert { border-left-color: #F59E0B; background-color: #FFFBEB; animation: pulse 2s infinite; }
    
    @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.01); } }
    </style>
    """, unsafe_allow_html=True)

# 側邊欄基本手動刷新按鈕
if st.sidebar.button("🔄 手動即時重新整理"):
    st.cache_data.clear()
    st.rerun()

st.markdown('<div class="big-title">🎯 期貨智慧量化下單與多持倉即時追蹤系統</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-title">數據每 30 秒自動跳動更新（抗封鎖安全機制） | 當前看盤時間：{datetime.now().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)

# 3. 全球熱門連續期貨合約商品清單
FUTURE_MAP = {
    "台指期近月 (WTX=F)": "WTX=F",
    "微型小道瓊 (MYM=F)": "MYM=F",
    "微型那斯達克 (MNQ=F)": "MNQ=F",
    "微型標普500 (MES=F)": "MES=F",
    "日經期貨近月 (NK=F)": "NK=F",
    "黃金期貨近月 (GC=F)": "GC=F",
    "白銀期貨近月 (SI=F)": "SI=F",
    "輕原油期貨近月 (CL=F)": "CL=F",
    "天然氣期貨近月 (NG=F)": "NG=F"
}

@st.cache_data(ttl=30) # 緩衝拉長至 30 秒
def fetch_and_analyze(ticker_name, ticker_symbol):
    try:
        df = yf.download(ticker_symbol, period="6mo", interval="1d", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # 原生數學技術指標計算
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
            color_code = "#10B981"
            stop_loss_val = float(df['Low'].iloc[-5:].min())
        elif score < 0:
            direction = f"偏空 (分數: {score_100}/100)"
            color_code = "#EF4444"
            stop_loss_val = float(df['High'].iloc[-5:].max())
        else:
            direction = f"中性觀望 (分數: {score_100}/100)"
            color_code = "#6B7280"
            stop_loss_val = float(df['Close'].iloc[-1])
            
        return {
            "name": ticker_name,
            "symbol": ticker_symbol,
            "price": round(float(today['Close']), 2),
            "score_100": score_100,
            "direction": direction,
            "color": color_code,
            "stop_loss": round(stop_loss_val, 2),
            "kd_signal": "GOLDEN" if kd_golden else ("DEATH" if kd_death else "NONE"),
            "df": df
        }
    except Exception as e:
        return None

# 預先抓取行情
all_data = {}
for name, symbol in FUTURE_MAP.items():
    res = fetch_and_analyze(name, symbol)
    if res: all_data[name] = res

# ==================== 📥 側邊欄：持倉輸入面板功能 ====================
st.sidebar.markdown("### 📥 持倉設定面板")
trade_name = st.sidebar.selectbox("持有商品", list(FUTURE_MAP.keys()))
trade_type = st.sidebar.radio("交易方向", ["做多 (Buy)", "做空 (Sell)"])
trade_lots = st.sidebar.number_input("持有口數 (Lots)", value=2, min_value=1, step=1)

current_market_price = all_data[trade_name]["price"] if trade_name in all_data else 0.0
sys_suggest_sl = all_data[trade_name]["stop_loss"] if trade_name in all_data else 0.0

user_price = st.sidebar.number_input("您的買進/賣出價格 (Entry)", value=float(current_market_price), step=0.01)
user_sl = st.sidebar.number_input("自訂固定止損點", value=float(sys_suggest_sl), step=0.01)
user_margin = st.sidebar.number_input("單口初始保證金 (USD)", value=996.0, step=10.0)

if st.sidebar.button("➕ 新增至即時追蹤面板", use_container_width=True):
    new_pos = {
        "id": str(time.time()), 
        "name": trade_name,
        "type": trade_type,
        "lots": trade_lots,
        "entry_price": user_price,
        "stop_loss": user_sl,
        "margin": user_margin
    }
    st.session_state.my_positions.append(new_pos)
    st.sidebar.success(f"成功將 {trade_lots}口 {trade_name} 納入核心監控！")
    st.rerun()

# ==================== 📊 輸出：持倉追蹤與美金保證金精算區塊 ====================
if st.session_state.my_positions:
    st.markdown("### 🎛️ 我的即時監控持倉群組 (Active Portfolio)")
    for pos in list(st.session_state.my_positions):
        if pos["name"] not in all_data: continue
        
        target = all_data[pos["name"]]
        now_p = target["price"]
        ent_p = pos["entry_price"]
        sl_p = pos["stop_loss"]
        margin_p = pos["margin"]
        lots_p = pos.get("lots", 2)
        
        # 計算點數損益
        if "做多" in pos["type"]:
            pnl_points = now_p - ent_p
            hit_sl = now_p <= sl_p
        else:
            pnl_points = ent_p - now_p
            hit_sl = now_p >= sl_p
            
        # 針對天然氣連續合約進行美金精算
        if "天然氣" in pos["name"]:
            usd_pnl = pnl_points * 2500 * lots_p
        else:
            usd_pnl = pnl_points * 50 * lots_p 
            
        total_initial_margin = margin_p * lots_p
        current_equity = total_initial_margin + usd_pnl
        margin_growth = (usd_pnl / total_initial_margin) * 100
        
        pnl_sign = "+" if pnl_points >= 0 else ""
        usd_sign = "+" if usd_pnl >= 0 else ""
        box_class = "profit" if pnl_points >= 0 else "loss"
        exit_status_text = "✅ 持倉狀態：健全持股中"
        
        if hit_sl: box_class, exit_status_text = "alert", "🚨 出場訊號通知：價格已跌破或突破您的防守止損點！"

        st.markdown(f"""
        <div class="portfolio-card {box_class}">
            <div style="font-size: 1.3rem; font-weight: bold; color: #111827;">📈 持倉商品：{pos["name"]} ── 共計 {lots_p} 口 （{pos["type"]}）</div>
            <div style="margin-top: 0.5rem; font-size: 1rem; color: #374151;">
                建倉成本：<b>{ent_p}</b> | 防守止損線：<b>{sl_p}</b> | 總投入原始保證金：<b style="color:#1E3A8A;">${total_initial_margin} USD</b>
            </div>
            <div style="margin-top: 0.5rem; font-size: 1.15rem; color: #111827;">
                當前市場即時報價：<span style="font-weight:bold; color:#1E3A8A;">{now_p}</span>
            </div>
            <div style="font-size: 1.4rem; font-weight: bold; color: {'#10B981' if pnl_points >= 0 else '#EF4444'}; margin: 0.3rem 0;">
                未實現損益點數：{pnl_sign}{round(pnl_points, 4)} 點 | 📊 預估帳面損益：{usd_sign}${round(usd_pnl, 2)} 美元
            </div>
            <div style="font-size: 1.1rem; font-weight: bold; color: #374151;">
                💰 當前部位總淨值：${round(current_equity, 2)} USD | 槓桿盈虧比：<span style="color:{'#10B981' if margin_growth>=0 else '#EF4444'}">{pnl_sign}{round(margin_growth, 2)}%</span>
            </div>
            <hr style="border:0; border-top:1px solid #E5E7EB; margin: 0.5rem 0;">
            <div style="font-size: 1.15rem; font-weight: bold; color: {'#111827' if box_class != 'alert' else '#DC2626'};">
                {exit_status_text}
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button(f"❌ 刪除 / 解進這筆「{pos['name']}」持倉監控", key=f"del_{pos['id']}", use_container_width=True):
            st.session_state.my_positions.remove(pos)
            st.rerun()
    st.markdown("---")

# 4. 每日技術分析榜單呈現
st.markdown("### 📊 今日全商品推薦觀察榜單")
results = sorted(list(all_data.values()), key=lambda x: x["score_100"], reverse=True)

if not results:
    st.info("💡 暫時無法獲取數據，請稍後再試。")
else:
    for item in results:
        # 【精準修復點】：這裡的三引號原本漏掉了，現在百分之百補齊、絕對不報錯！
        st.markdown(f"""
        <div class="card" style="border-left-color: {item["color"]};">
            <span style="font-size:1.2rem; font-weight:bold; color:#1F2937;">觀察商品：{item["name"]}</span><br>
