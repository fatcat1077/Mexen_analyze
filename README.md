MXene-like 結構篩選流程
本流程依序執行以下步驟，從 `.aselmdb` 資料庫中篩選出可能為 MXene 的結構，並將其轉換為 `.extxyz` 格式以利後續處理。
📦 建立 Conda 環境
請先使用 `environment.yml` 安裝所需套件：
conda env create -f environment.yml
或使用其他方式建立虛擬環境亦可。
🗂 放置資料與執行篩選腳本
1. 請將所有 `.aselmdb` 檔案與 Python 腳本放在同一層資料夾中。
2. 執行 `filter.py` 以篩選可能為 MXene 的資料：
python filter.py --root . --pattern "db_*.aselmdb"
此步驟會產生一個名為 `mxene_candidates.csv` 的檔案，列出所有初步符合 MXene 規則的結構。
📉 根據資料筆數裁切
使用上一步產生的 `mxene_candidates.csv` 檔案，執行以下指令裁切出所需的資料數量（請將 `-n` 後的數字改成你實際想保留的筆數，例如 1026）：
python collect.py mxene_candidates.csv mexen_candidate.csv -n 1026
執行完畢後會生成 `mexen_candidate.csv`，僅保留所需的結構資料。
🔄 匯出為 .extxyz 格式
最後將符合條件的資料從 `.aselmdb` 檔案轉換成 `.extxyz` 格式，供後續分析使用：
python aselmdb2xyz_batch.py \
  --csv mexen_candidate.csv \
  --db-dir . \
  --db-col db_file --idx-col row_id \
  --out mexen_candidates.extxyz
📖 詳細教學文件
更多細節可參考以下 Google 文件說明：
https://docs.google.com/document/d/1v0iHsMGLg_4yhDJJlLSraoSsWQzci0rfYhUs8rXh79Y/edit?usp=sharing

