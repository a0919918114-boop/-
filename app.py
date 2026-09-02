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

# 2. 初始化自訂持倉的記憶資料庫 (session_state)
if "my_positions" not in st.session_state:
    st.session_state.my_positions = [] # 用來存放多筆持倉資料的清單

# 介面語系與排版優化 (Tailwind 風格 CSS)
st.markdown("""
    <style>
    .big-title { font-size:2.2rem !important; font-weight: 700; color: #1E3A8A; text-align: center; margin-bottom: 0.5rem; }
    .sub-title { font-size:1.2rem !important; color: #4B5563; text-align: center; margin-bottom: 2rem; }
    .card { padding: 1.5rem; border-radius: 0.5rem; background-color: #F3F4F6; margin-bottom: 1rem; border-left: 5px solid #3B82F6; }
    
    /* 追蹤看盤看板專用 RWD 網格樣式 */
    .dashboard-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
    .portfolio-card { padding: 1.2rem; border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border-left: 8px solid #6B7280; background-color: #FFFFFF; position: relative; }
    .portfolio-card.profit { border-left-color: #10B981; background-color: #F0FDF4; }
    .portfolio-card.loss { border-left-color: #EF4444; background-color: #FEF2F2; }
    .portfolio-card.alert { border-left-color: #F59E0B; background-color: #FFFBEB; animation: pulse 2s infinite; }
    
    @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.01); } }
    </style>
    """, unsafe_allow_html=True)

# 側邊欄基本手動刷新
if st.sidebar.button("🔄 手動即時重新整理"):
    st.cache_data.clear()
    st.rerun()

st.markdown('<div class="big-title">🎯 期貨智慧量化下單與多持倉即時追蹤系統</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-title">數據每 10 秒自動跳動更新 | 當前看盤時間：{datetime.now().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)

# 3. 定義要追蹤的期貨商品代號
FUTURE_MAP = {
    "台指期近月 (WTX=F)": "WTX=F",
    "微型小道瓊近月 (MYM=F)": "MYM=F",
    "黃金期貨近月 (GC=F)": "GC=F",
    "輕原油期貨近月 (CL=F)": "CL=F"
}

@st.cache_data(ttl=10) # 10秒短快取
def fetch_and_analyze(ticker_name, ticker_symbol):
    try:
        df = yf.download(ticker_symbol, period="6mo", interval="1d", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # 技術指標計算
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

# 預先抓取行情
all_data = {}
for name, symbol in FUTURE_MAP.items():
    res = fetch_and_analyze(name, symbol)
    if res: all_data[name] = res

# ==================== 📥 側邊欄：動態新增持倉面板 ====================
st.sidebar.markdown("### 📥 新增持倉部位")
add_name = st.sidebar.selectbox("欲追蹤期貨商品", list(FUTURE_MAP.keys()))
add_type = st.sidebar.radio("交易方向", ["做多 (Buy)", "做空 (Sell)"])

# 動態抓取預設建議數值
current_ref_price = all_data[add_name]["price"] if add_name in all_data else 0.0
sys_ref_sl = all_data[add_name]["stop_loss"] if add_name in all_data else 0.0

add_price = st.sidebar.number_input("您的買進/賣出價格", value=float(current_ref_price), step=1.0)
add_sl = st.sidebar.number_input("您的防守止損點", value=float(sys_ref_sl), step=1.0)
add_tp = st.sidebar.number_input("您的獲利止盈點 (0代表不設)", value=0.0, step=1.0)

# 【➕ 新增按鈕邏輯】
if st.sidebar.button("➕ 新增至即時追蹤面板", use_container_width=True):
    new_pos = {
        "id": str(time.time()), # 給予不重複的ID以便精準刪除
        "name": add_name,
        "type": add_type,
        "entry_price": add_price,
        "stop_loss": add_sl,
        "take_profit": add_tp
    }
    st.sidebar.success(f"成功新增：{add_name}")
    st.session_state.my_positions.append(new_pos)
    st.rerun()

# ==================== 📊 輸出：多筆持倉獨立小方格看板 ====================
if st.session_state.my_positions:
    st.markdown("### 🎛️ 我的即時監控持倉群組 (Active Portfolio)")
    
    # 建立多欄位排版，讓小方格可以漂亮地並排與向下延伸
    cols = st.columns(3) 
    
    # 迴圈讀取所有儲存的持倉，進行動態渲染
    for idx, pos in enumerate(list(st.session_state.my_positions)):
        if pos["name"] not in all_data: continue
        
        market = all_data[pos["name"]]
        now_p = market["price"]
        ent_p = pos["entry_price"]
        sl_p = pos["stop_loss"]
        tp_p = pos["take_profit"]
        
        # 計算損益
        if "做多" in pos["type"]:
            pnl = now_p - ent_p
            hit_sl = now_p <= sl_p
            hit_tp = (now_p >= tp_p) if tp_p > 0 else False
            tech_exit = market["kd_signal"] == "DEATH"
        else:
            pnl = ent_p - now_p
            hit_sl = now_p >= sl_p
            hit_tp = (now_p <= tp_p) if tp_p > 0 else False
            tech_exit = market["kd_signal"] == "GOLDEN"
            
        pnl_sign = "+" if pnl >= 0 else ""
        box_class = "profit" if pnl >= 0 else "loss"
        status_msg = "✅ 持倉訊號健全"
        
        if hit_sl:
            box_class = "alert"
            status_msg = "🚨 出場通知：已穿透止損！"
        elif hit_tp:
            box_class = "alert"
            status_msg = "🎯 出場通知：已達止盈目標！"
        elif tech_exit:
            box_class = "alert"
            status_msg = "⚠️ 出場通知：技術指標反轉！"
            
        # 決定擺放的位置 (透過餘數分配到 3 個 Column 內)
        with cols[idx % 3]:
            # 使用獨立小方格樣式呈現
            st.markdown(f"""
            <div class="portfolio-card {box_class}">
                <div style="font-size: 1.15rem; font-weight: bold; color: #111827;">{pos["name"]}</div>
                <div style="font-size: 0.85rem; color: #4B5563; margin-bottom:0.5rem;">交易方向：<b>{pos["type"]}</b></div>
                <hr style="margin: 0.4rem 0; border:0; border-top:1px solid #E5E7EB;">
                <div style="font-size: 0.9rem;">建倉成本：<b>{ent_p}</b></div>
                <div style="font-size: 0.9rem;">當前最新價：<b>{now_p}</b></div>
                <div style="font-size: 1.25rem; font-weight: bold; color: {'#10B981' if pnl >= 0 else '#EF4444'}; margin: 0.3rem 0;">
                    即時損益：{pnl_sign}{round(pnl, 2)} 點
                </div>
                <div style="font-size: 0.85rem; color: #4B5563;">防守止損：<b>{sl_p}</b> {'| 止盈: <b>'+str(tp_p)+'</b>' if tp_p > 0 else ''}</div>
                <div style="font-size: 0.95rem; font-weight: bold; color: {'#1F2937' if box_class != 'alert' else '#DC2626'}; margin-top:0.4rem;">
                    {status_msg}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 【❌ 刪除按鈕邏輯】
            # 使用不重複的唯一 key，確保刪除時精準對應
            if st.button(f"❌ 刪除此筆追蹤 ({pos['name'][:3]})", key=f"del_{pos['id']}", use_container_width=True):
                st.session_state.my_positions.remove(pos)
                st.rerun()
                
    st.markdown("---")

# 6. 原有每日最佳下單訊號前端呈現
st.markdown("### 📊 今日全商品推薦觀察榜單")
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
