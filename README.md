啟用conda環境並且下載environment.yml中的檔案

conda env create -f environment.yml
(或是其他方式都可以)

將.aselmdb檔案放到跟python檔案同一層級的資料夾並且執行
python filter.py --root . --pattern "db_*.aselmdb"

透過這一部初步找出可能為mexen的元素，並匯出成mxene_candidates.csv

接著透過上個步驟找出的Mexen元素筆數修改下一個指令紅色的數字
python collect.py mxene_candidates.csv mexen_candidate.csv -n 1026
透過這一步讓.csv只剩下我們需要的資料

透過這些資料回去.aselmdb檔案將特定檔案轉成.extxyz檔案
python aselmdb2xyz_batch.py `
  --csv mexen_candidate.csv `
  --db-dir . `
  --db-col db_file --idx-col row_id `
  --out mexen_candidates.extxyz
