#!/bin/bash
# 信用卡優惠每週更新腳本
cd "$(dirname "$0")"

echo "=== 開始更新信用卡優惠資料 ==="
echo "時間: $(date)"

# 安裝依賴（如果尚未安裝）
pip3 install -q requests beautifulsoup4 2>/dev/null

# 執行爬蟲
python3 scraper/scraper.py

# 同步到 /tmp 供預覽使用
cp -r data /tmp/cc-rewards/ 2>/dev/null

echo "=== 更新完成 ==="
