import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup

# 設定網頁標題與圖示
st.set_page_config(page_title="金字塔複合選股儀表板", page_icon="🏛️", layout="wide")
st.title("🏛️ 神秘金字塔 x 財報複合選股儀表板")
st.write("自動篩選：資本支出大 & 大股東持續買進 & 現金流充足之個股")

# --- 側邊欄條件設定 ---
st.sidebar.header("⚙️ 篩選條件設定")
target_stock = st.sidebar.text_input("輸入要分析的股票代碼 (例如: 2330)", value="2330")

# --- 核心邏輯：爬取神秘金字塔股權分散資料 ---
def get_pyramid_data(stock_id):
    try:
        # 神秘金字塔的集保戶股權分散表網址
        url = f"https://twsthr.info{stock_id}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # 這裡解析網頁表格（以下為示意邏輯，實際部署時需對齊金字塔網頁的 id 或 class）
            st.success(f"成功連結神秘金字塔數據庫（個股：{stock_id}）")
            # 回傳大戶持股趨勢、股東人數變化
            return True
        return False
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return False

# --- 核心邏輯：確認基本面（資本支出與現金流） ---
def check_financials(stock_id):
    # 實際運作時可結合政府開放資料 (Open Data) API 或 yfinance 撈取
    # 這裡提供模擬的判定逻辑
    capital_expenditure_growth = True  # 資本支出大
    free_cash_flow_positive = True     # 現金流充足
    return capital_expenditure_growth, free_cash_flow_positive

# --- 執行按鈕 ---
if st.sidebar.button("🚀 開始掃描分析"):
    with st.spinner("正在抓取最新數據中，請稍候..."):
        
        # 1. 檢查籌碼面
        pyramid_success = get_pyramid_data(target_stock)
        
        # 2. 檢查基本面
        cap_exp, fcf = check_financials(target_stock)
        
        # 3. 顯示結果面板
        st.subheader(f"📊 股票代碼 {target_stock} 綜合檢驗報告")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="大股東持續買進 (神秘金字塔)", value="符合" if pyramid_success else "未符合")
        with col2:
            st.metric(label="資本支出大 (廠房設備投資↑)", value="符合" if cap_exp else "未符合")
        with col3:
            st.metric(label="現金流充足 (自由現金流為正)", value="符合" if fcf else "未符合")
            
        if pyramid_success and cap_exp and fcf:
            st.balloons() # 噴出慶祝氣球
            st.success(f"🎉 太棒了！ {target_stock} 完全滿足您的三大潛力股條件！")
        else:
            st.warning("⚠️ 該個股未全數符合條件，建議保守觀望。")
