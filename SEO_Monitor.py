import requests
import pandas as pd
import os
from datetime import datetime

# ================= 配置区域 =================
# 建议在 GitHub Secrets 中设置 SERPAPI_KEY
API_KEY = os.getenv("SERPAPI_KEY", "你的_SERPAPI_KEY") 
TARGET_ASINS = ["B0DPQ7GVJX", "B0DJ71KZXF", "B0DJ6ZPS3Y"]
KEYWORDS = ["heißluftfritteuse", "airfryer", "heißluftfritteuse 2 kammern"]
ZIP_CODE = "10115"
DOMAIN = "amazon.de"
EXCEL_FILE = "amazon_seo_history.xlsx"
# ===========================================

def get_rank_change(current, previous):
    if previous is None or pd.isna(previous):
        return "-"
    change = previous - current  # 排名变小代表上升
    if change > 0: return f"↑{int(change)}"
    if change < 0: return f"↓{int(abs(change))}"
    return "—"

def run_monitor():
    today_str = datetime.now().strftime('%Y-%m-%d')
    new_data = []

    # 1. 尝试读取历史数据
    if os.path.exists(EXCEL_FILE):
        df_history = pd.read_excel(EXCEL_FILE)
    else:
        df_history = pd.DataFrame(columns=["记录时间", "关键词", "Asin", "SEO排名", "SEO变化", "页面绝对位置", "位置变化"])

    # 2. 遍历关键词获取数据（每个关键词仅消耗1次额度）
    for keyword in KEYWORDS:
        print(f"正在抓取关键词: {keyword}...")
        params = {
            "engine": "amazon",
            "k": keyword,
            "amazon_domain": DOMAIN,
            "delivery_zip": ZIP_CODE,
            "api_key": API_KEY,
            "type": "search"
        }
        
        try:
            response = requests.get("https://serpapi.com/search", params=params, timeout=30)
            results = response.json()
            organic_results = results.get("organic_results", [])
            
            # 统计自然排名的计数器
            natural_rank_counter = 0
            
            # 建立一个临时字典保存当前关键词下找到的监控ASIN
            found_in_page = {}

            for item in organic_results:
                if not item.get("sponsored"):
                    natural_rank_counter += 1
                
                asin = item.get("asin")
                if asin in TARGET_ASINS and asin not in found_in_page:
                    is_sponsored = item.get("sponsored", False)
                    found_in_page[asin] = {
                        "seo_rank": natural_rank_counter if not is_sponsored else 999, # 广告位不计自然排名
                        "abs_pos": item.get("position"),
                        "is_sp": is_sponsored
                    }

            # 3. 组装数据并计算变化
            for asin in TARGET_ASINS:
                current_seo = found_in_page.get(asin, {}).get("seo_rank", 999) # 没找到记为999
                current_abs = found_in_page.get(asin, {}).get("abs_pos", 999)
                
                # 获取该 ASIN + 关键词 的上一次记录
                last_record = df_history[(df_history["关键词"] == keyword) & (df_history["Asin"] == asin)]
                prev_seo = last_record.iloc[-1]["SEO排名"] if not last_record.empty else None
                prev_abs = last_record.iloc[-1]["页面绝对位置"] if not last_record.empty else None

                new_data.append({
                    "记录时间": today_str,
                    "关键词": keyword,
                    "Asin": asin,
                    "SEO排名": current_seo if current_seo != 999 else "未入榜",
                    "SEO变化": get_rank_change(current_seo, prev_seo) if current_seo != 999 else "-",
                    "页面绝对位置": current_abs if current_abs != 999 else "未入榜",
                    "位置变化": get_rank_change(current_abs, prev_abs) if current_abs != 999 else "-"
                })

        except Exception as e:
            print(f"关键词 {keyword} 抓取失败: {e}")

    # 4. 保存回 Excel
    df_new = pd.DataFrame(new_data)
    df_final = pd.concat([df_history, df_new], ignore_index=True)
    
    # 简单的格式优化：确保记录不重复（如果一天运行多次）
    df_final.drop_duplicates(subset=["记录时间", "关键词", "Asin"], keep='last', inplace=True)
    
    df_final.to_excel(EXCEL_FILE, index=False)
    print(f"成功更新数据并保存至 {EXCEL_FILE}")

if __name__ == "__main__":
    run_monitor()
