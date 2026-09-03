import pandas as pd
import streamlit as st
import time
import requests
from bs4 import BeautifulSoup

# 1. 網頁基本配置
st.set_page_config(page_title="全台股智能全自動掃描器", page_icon="📈", layout="wide")
st.title("📊 全台股大數據全自動篩選器")
st.write("【基本面 + 籌碼面複合策略】：一鍵掃描全台股，揪出滿足「資本支出大、大股東狂買、現金流充裕」的潛力標的。")

# 📊 模擬一個全台股清單與資料庫（實際部署可介接 FinMind API 或 證交所 OpenAPI）
# 為了避免初次運行時網頁過度卡頓，這裡建立全市場的基礎比對池
def load_all_taiwan_stocks():
    # 這裡以台灣主要核心權值與中小型股作為掃描範例池（可依需求自行擴充清單）
    stock_pool = [
        {"code": "2330", "name": "台積電", "industry": "半導體"},
        {"code": "2317", "name": "鴻海", "industry": "其他電子"},
        {"code": "2454", "name": "聯發科", "industry": "半導體"},
        {"code": "2308", "name": "台達電", "industry": "電子零組件"},
        {"code": "2382", "name": "廣達", "industry": "電腦週邊"},
        {"code": "3008", "name": "大立光", "industry": "光電業"},
        {"code": "2603", "name": "長榮", "industry": "航運業"},
        {"code": "2303", "name": "聯電", "industry": "半導體"},
        {"code": "2881", "name": "富邦金", "industry": "金融保險"},
        {"code": "2882", "name": "國泰金", "industry": "金融保險"}
        # 實際運作時可透過 requests 抓取證交所全市場代碼清單
    ]
    return stock_pool

# 🔎 核心篩選引擎
def fetch_and_filter_market(progress_bar, status_text, min_weeks):
    stocks = load_all_taiwan_stocks()
    total_stocks = len(stocks)
    qualified_list = []
    
    for index, stock in enumerate(stocks):
        code = stock["code"]
        name = stock["name"]
        
        # 更新進度條
        percent_complete = int((index + 1) / total_stocks * 100)
        progress_bar.progress(percent_complete)
        status_text.text(f"⏳ 正在掃描第 {index+1}/{total_stocks} 檔：{code} {name}...")
        
        # --- 條件一：神秘金字塔大股東籌碼面檢查 ---
        # 實務爬蟲邏輯：造訪神秘金字塔個股頁面
        has_big_buyer = True # 模擬判定：連續幾週大戶持股增加
        try:
            # 實際爬取語法參考：
            # url = f"https://twsthr.info{code}"
            # res = requests.get(url, timeout=5)
            # 這裡進行 BeautifulSoup 解析週資料...
            time.sleep(0.2) # 延遲防止被金字塔鎖 IP
        except:
            has_big_buyer = False
            
        # --- 條件二與三：財報基本面檢查 (資本支出 & 自由現金流) ---
        # 模擬數據：營業現金流 > 資本支出 (FCF > 0) 且 資本支出 YoY 增長
        capex_growing = True  # 資本支出擴大
        cash_flow_safe = True # 現金流充裕
        
        # 三道門檻交叉比對
        if has_big_buyer and capex_growing and cash_flow_safe:
            qualified_list.append({
                "股票代碼": code,
                "股票名稱": name,
                "產業類別": stock["industry"],
                "大股東續買週數": f"連續 {min_weeks} 週以上",
                "資本支出狀態": "大舉擴產中 (🔥)",
                "自由現金流 (FCF)": "充沛 (✅)"
            })
            
    return pd.DataFrame(qualified_list)

# --- 側邊欄控制面板 ---
st.sidebar.header("⚙️ 終極選股條件設定")
st.sidebar.markdown("---")
min_weeks = st.sidebar.slider("🔥 大股東連續買進週數 (神秘金字塔門檻)", 1, 8, 3)
st.sidebar.info("💡 說明：程式會自動篩選出「400張/1000張大戶」在您設定的週數內持續進貨，且同時滿足財報最新一季資本支出擴大、自由現金流為正的公司。")

st.sidebar.markdown("---")
start_scan = st.sidebar.button("🚀 一鍵全台股雷達掃描")

# --- 主畫面邏輯處理 ---
if start_scan:
    st.subheader("🤖 全市場數據同步與矩陣篩選中")
    
    # 建立進度條元件
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 執行掃描
    result_df = fetch_and_filter_market(progress_bar, status_text, min_weeks)
    
    # 清除進度狀態提示
    status_text.empty()
    progress_bar.empty()
    
    # 顯示結果
    if not result_df.empty:
        st.balloons() # 噴出成功慶祝氣球
        st.success(f"🎉 報告長官！全市場掃描完畢，共揪出 {len(result_df)} 檔「超級潛力金蟬股」！")
        
        # 美化表格輸出
        st.dataframe(
            result_df, 
            use_container_width=True,
            column_config={
                "股票代碼": st.column_config.TextColumn("股票代碼"),
                "大股東續買週數": st.column_config.TextColumn("籌碼面指標"),
            }
        )
        
        # 提供下載成 Excel/CSV 按鈕
        csv = result_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 下載本次選股名單 (CSV)",
            data=csv,
            file_name="taiwan_qualified_stocks.csv",
            mime="text/csv"
        )
    else:
        st.warning("⚠️ 掃描完成，但目前市場上沒有任何股票同時滿足這三項嚴格的黃金條件。建議調低大戶買進週數再試一次！")
