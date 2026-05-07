import requests
import pandas as pd
import os
import json
from datetime import datetime

# ================= 配置区域 =================
# 建议从环境变量读取，本地测试时可直接替换字符串
API_KEY = os.getenv("SERPAPI_KEY", "b0d8b83ad57f08a24cdc3f30deff8c44c17f6578b0f1e2c37055c569309a6d81")
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/16cafe1a-3a0b-409a-bd80-b1b2163b5f33"

# 监控 ASIN 及其别名
ASIN_MAP = {
    "B0DPQ7GVJX": "低配",
    "B0DJ71KZXF": "R903",
    "B0DJ6ZPS3Y": "DC601",
    "B0CBC78NGX": "CP358",
    "B0FXFWQ78D": "Tenno"
}
TARGET_ASINS = list(ASIN_MAP.keys())
KEYWORDS = ["heißluftfritteuse", "airfryer", "heißluftfritteuse 2 kammern"]
ZIP_CODE = "10115"
DOMAIN = "amazon.de"
EXCEL_FILE = "amazon_seo_history.xlsx"
# ===========================================

def send_feishu_msg(title, content_list):
    """通用飞书推送函数"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": content_list
                }
            }
        }
    }
    try:
        requests.post(FEISHU_WEBHOOK, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print(f"飞书推送失败: {e}")

def self_check():
    """系统自检与初始化"""
    print("开始系统自检...")
    checks = []
    
    # 1. 检查 Key
    if len(API_KEY) < 10:
        checks.append([{"tag": "text", "text": "❌ 错误: SerpApi Key 未正确配置"}])
    else:
        checks.append([{"tag": "text", "text": "✅ SerpApi Key 状态: 已就绪"}])
        
    # 2. 检查 Excel 文件
    if not os.path.exists(EXCEL_FILE):
        df_init = pd.DataFrame(columns=["记录时间", "关键词", "产品", "Asin", "SEO排名", "SEO变化", "页面绝对位置", "位置变化"])
        df_init.to_excel(EXCEL_FILE, index=False)
        checks.append([{"tag": "text", "text": "✅ 历史数据库: 未发现旧文件，已完成初始化创建"}])
    else:
        checks.append([{"tag": "text", "text": "✅ 历史数据库: 连接正常"}])

    # 3. 发送自检报告
    send_feishu_msg("🚀 亚马逊 SEO 监控系统自检报告", checks)
    print("自检完成，报告已发送至飞书。")

def get_rank_change(current, previous):
    """计算排名升降趋势"""
    if previous is None or pd.isna(previous) or previous == "未入榜":
        return "-"
    try:
        prev_val = int(previous)
        curr_val = int(current)
        change = prev_val - curr_val
        if change > 0: return f"↑{change}"
        if change < 0: return f"↓{abs(change)}"
        return "—"
    except:
        return "-"

def run_monitor():
    """核心监控逻辑"""
    today_str = datetime.now().strftime('%Y-%m-%d')
    new_rows = []
    feishu_report = []

    # 加载历史数据用于对比
    df_history = pd.read_excel(EXCEL_FILE)

    for keyword in KEYWORDS:
        feishu_report.append([{"tag": "text", "text": f"🔍 关键词: {keyword}"}])
        params = {
            "engine": "amazon", "k": keyword, "amazon_domain": DOMAIN,
            "delivery_zip": ZIP_CODE, "api_key": API_KEY, "type": "search"
        }
        
        try:
            response = requests.get("https://serpapi.com/search", params=params, timeout=30)
            organic_results = response.json().get("organic_results", [])
            
            natural_rank_counter = 0
            found_in_page = {}

            for item in organic_results:
                if not item.get("sponsored"):
                    natural_rank_counter += 1
                asin = item.get("asin")
                if asin in TARGET_ASINS and asin not in found_in_page:
                    found_in_page[asin] = {
                        "seo_rank": natural_rank_counter if not item.get("sponsored") else "广告位",
                        "abs_pos": item.get("position")
                    }

            for asin in TARGET_ASINS:
                name = ASIN_MAP[asin]
                res = found_in_page.get(asin, {"seo_rank": "未入榜", "abs_pos": "未入榜"})
                
                # 对比逻辑
                last_record = df_history[(df_history["关键词"] == keyword) & (df_history["Asin"] == asin)]
                prev_seo = last_record.iloc[-1]["SEO排名"] if not last_record.empty else None
                prev_abs = last_record.iloc[-1]["页面绝对位置"] if not last_record.empty else None

                seo_change = get_rank_change(res['seo_rank'], prev_seo)
                pos_change = get_rank_change(res['abs_pos'], prev_abs)

                new_rows.append({
                    "记录时间": today_str, "关键词": keyword, "产品": name, "Asin": asin,
                    "SEO排名": res['seo_rank'], "SEO变化": seo_change,
                    "页面绝对位置": res['abs_pos'], "位置变化": pos_change
                })

                line = f"  • {name}: SEO {res['seo_rank']}({seo_change}) | 绝对位 {res['abs_pos']}({pos_change})"
                feishu_report.append([{"tag": "text", "text": line}])

        except Exception as e:
            print(f"抓取异常: {e}")

    # 保存并追加
    df_new = pd.DataFrame(new_rows)
    df_final = pd.concat([df_history, df_new], ignore_index=True)
    df_final.drop_duplicates(subset=["记录时间", "关键词", "Asin"], keep='last').to_excel(EXCEL_FILE, index=False)

    # 推送每日报告
    send_feishu_msg(f"📊 亚马逊 SEO 排名监控日报 ({today_str})", feishu_report)

if __name__ == "__main__":
    # 每次运行先进行自检
    self_check()
    # 然后开始同步数据
    run_monitor()
