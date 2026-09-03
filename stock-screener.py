import streamlit as st
import pandas as pd
from FinMind.data import DataLoader

# 初始化 FinMind 資料載入器
dl = DataLoader()

def get_stock_data():
    """獲取台股基本面與籌碼面數據並進行篩選"""
    # 1. 取得全台股目前的最新列表
    try:
        stock_info = dl.taiwan_stock_info()
        # 篩選出普通股（股票代號為4碼的）
        stock_list = stock_info[stock_info['stock_id'].str.len() == 4]['stock_id'].unique().tolist()
    except Exception as e:
        st.error(f"無法取得股票列表: {e}")
        return pd.DataFrame()

    results = []
    
    # 為了加速示範，我們只掃描前 50 檔股票（您可以自行擴大或拔除限制）
    # 注意：FinMind 免費版有每小時調用次數限制，實戰時建議分批或針對特定觀察清單篩選
    scan_limit = min(50, len(stock_list))
    
    progress_bar = st.progress(0)
    
    for idx, stock_id in enumerate(stock_list[:scan_limit]):
        progress_bar.progress((idx + 1) / scan_limit)
        try:
            # 🔍 條件 A & B：財報現金流量表 (資本支出大 & 現金流充足)
            # 抓取最近 4 季的現金流量表
            cf_data = dl.taiwan_stock_cash_flows(stock_id=stock_id, start_date='2024-01-01')
            if cf_data.empty:
                continue
                
            # 整理財報項目
            cf_pivot = cf_data.pivot_table(index='date', columns='type', values='value').fillna(0)
            
            # 檢查是否有必備欄位
            if '營業活動之現金流量' not in cf_pivot.columns or '取得不動產、廠房及設備' not in cf_pivot.columns:
                continue
                
            latest_operating_cf = cf_pivot['營業活動之現金流量'].iloc[-1]
            # 資本支出在財報通常紀錄為負值，取絕對值代表投入金額
            latest_capex = abs(cf_pivot['取得不動產、廠房及設備'].iloc[-1]) 
            
            # 計算自由現金流 = 營業現金流 - 資本支出
            free_cash_flow = latest_operating_cf - latest_capex
            
            # 篩選基本面：營業現金流 > 0 且 自由現金流 > 0 (代表手頭現金流充足)
            if latest_operating_cf <= 0 or free_cash_flow <= 0:
                continue

            # 🔍 條件 C：籌碼面 (大股東持股持續買進)
            # 抓取最近 4 週的集保戶股權分散表
            holding_data = dl.taiwan_stock_holding_shares_per(stock_id=stock_id, start_date='2025-01-01')
            if holding_data.empty:
                continue
                
            # 篩選出 400張以上 或 1000張以上的大股東級距 (FinMind 中 400張以上通常是級距 11-15)
            # 這裡以大於400張的持股比例加總做計算
            big_holders = holding_data[holding_data['HoldingSharesLevel'] >= 11]
            weekly_big_ratio = big_holders.groupby('date')['percent'].sum().sort_index()
            
            if len(weekly_big_ratio) < 3:
                continue
                
            # 檢查最近三週大股東持股是否連續增加
            latest_3_weeks = weekly_big_ratio.tail(3).values
            is_big_holder_buying = (latest_3_weeks[2] > latest_3_weeks[1]) and (latest_3_weeks[1] > latest_3_weeks[0])
            
            if is_big_holder_buying:
                # 取得股票名稱
                name = stock_info[stock_info['stock_id'] == stock_id]['stock_name'].values[0]
                results.append({
                    "股票代號": stock_id,
                    "股票名稱": name,
                    "最新營業現金流(元)": f"{latest_operating_cf:,.0f}",
                    "最新資本支出(元)": f"{latest_capex:,.0f}",
                    "最新自由現金流(元)": f"{free_cash_flow:,.0f}",
                    "最新大戶持股比例%": f"{latest_3_weeks[2]:.2f}%"
                })
        except Exception:
            continue
            
    return pd.DataFrame(results)

# --- Streamlit 網頁介面設計 ---
st.set_page_config(page_title="台股複合選股小幫手", layout="wide")

st.title("🏛️ 複合量化選股儀表板")
st.markdown("### 篩選策略：資本支出大 🔥 & 大股東持續買進 📈 & 現金流充足 💰")
st.caption("數據來源：FinMind 台灣股市大數據 API")

if st.button("🚀 開始掃描並收集滿足條件個股", type="primary"):
    with st.spinner("正在為您向證交所與集保所抓取最新數據，請稍候..."):
        df_result = get_stock_data()
        
        if not df_result.empty:
            st.success(f"🎉 掃描完成！共找到 {len(df_result)} 檔符合條件的潛力個股：")
            st.dataframe(df_result, use_container_width=True)
        else:
            st.warning("⚠️ 目前掃描範圍內，暫時沒有同時滿足這三項嚴格條件的股票，建議晚點再試或調整篩選範圍。")
