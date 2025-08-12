import argparse
import os, sys, glob
import pandas as pd
from collections import defaultdict
from ase.io import write
from fairchem.core.datasets import AseDBDataset

def norm(s):
    return str(s).strip()

def detect_cols(df, id_col, db_col, idx_col):
    cols = {c.lower(): c for c in df.columns}
    if id_col:
        return id_col, None, None
    # 嘗試自動猜測
    cand_db = [k for k in cols if k in ("db","db_file","file","aselmdb","source","path")]
    cand_idx = [k for k in cols if k in ("idx","index","row","id","entry","image_id")]
    use_db = cols[cand_db[0]] if cand_db else None
    use_idx = cols[cand_idx[0]] if cand_idx else None
    if db_col: use_db = db_col
    if idx_col: use_idx = idx_col
    if use_db is None and use_idx is None:
        raise ValueError("找不到對應欄位。請用 --id-col 或 --db-col 與 --idx-col 指定。")
    return None, use_db, use_idx

def parse_id_string(s):
    # 支援像 "db_1.aselmdb:42" 或 "dir/db_2.aselmdb#17"
    s = norm(s)
    for sep in (":", "#", ","):
        if sep in s:
            left, right = s.rsplit(sep, 1)
            return norm(left), int(right)
    # 如果沒分隔符，視為 index（單一資料庫時用）
    return None, int(s)

def main():
    ap = argparse.ArgumentParser(description="Convert selected records from multiple .aselmdb into XYZ/EXTXYZ")
    ap.add_argument("--csv", required=True, help="mexen_candidate.csv")
    ap.add_argument("--db-dir", default=".", help="資料庫所在資料夾（用來補齊相對路徑）")
    ap.add_argument("--db-glob", default="*.aselmdb", help="搜尋樣式（預設 *.aselmdb）")
    ap.add_argument("--id-col", default=None, help="單欄位 ID（例如 'db.aselmdb:42' 或 '...#17'）")
    ap.add_argument("--db-col", default=None, help="CSV 裡的資料庫檔名欄位（例如 db_file）")
    ap.add_argument("--idx-col", default=None, help="CSV 裡的 index 欄位（例如 idx / index）")
    ap.add_argument("--one-based", action="store_true", help="如果 CSV 的 index 是 1-based，打開這個會減 1")
    ap.add_argument("--out", default="mexen_candidates.extxyz", help="合併輸出的檔名（extxyz/xyz）")
    ap.add_argument("--per-structure", action="store_true", help="改成一筆一檔輸出 .xyz")
    ap.add_argument("--out-dir", default="xyz_out", help="per-structure 輸出的資料夾")
    ap.add_argument("--format", default=None, help="指定 ase 格式（例如 extxyz 或 xyz；不填會依副檔名判斷）")
    ap.add_argument("--limit", type=int, default=None, help="只處理前 N 筆（測試用）")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    id_col, db_col, idx_col = detect_cols(df, args.id_col, args.db_col, args.idx_col)

    # 建立：每個 .aselmdb -> 需要的 indices（set）
    wanted = defaultdict(set)

    if id_col:
        for _, row in df.iterrows():
            rid = row[id_col]
            dbname, idx = parse_id_string(rid)
            if args.one_based:
                idx -= 1
            wanted[dbname or "__SINGLE__"].add(int(idx))
    else:
        for _, row in df.iterrows():
            dbname = norm(row[db_col])
            idx = int(row[idx_col])
            if args.one_based:
                idx -= 1
            wanted[dbname].add(idx)

    # 找到實際存在的 .aselmdb 檔
    db_candidates = {}
    for p in glob.glob(os.path.join(args.db_dir, args.db_glob)):
        base = os.path.basename(p)
        db_candidates[base] = p

    # 若只有單一資料庫且 id_col 只有 index，強制使用唯一的 .aselmdb
    if "__SINGLE__" in wanted:
        if len(db_candidates) != 1:
            sys.exit("偵測到單一索引但不只一個 .aselmdb，請提供含 db 檔名的 ID（例如 db.aselmdb:42）或用 --db-col/--idx-col。")
        only_path = list(db_candidates.values())[0]
        wanted = {os.path.basename(only_path): wanted["__SINGLE__"]}

    # 輸出模式
    per_structure = args.per_structure
    if per_structure and not os.path.isdir(args.out_dir):
        os.makedirs(args.out_dir, exist_ok=True)

    total_ok, total_miss = 0, 0
    fmt = args.format  # None -> 依副檔名

    # 合併輸出時，逐筆 append，避免一次塞 RAM
    if not per_structure:
        # 先清空舊檔
        if os.path.exists(args.out):
            os.remove(args.out)

    # 逐個資料庫處理
    for base, idxs in wanted.items():
        # 允許 CSV 裡是相對路徑或檔名
        if base in db_candidates:
            db_path = db_candidates[base]
        else:
            # 也許 CSV 已是絕對路徑或相對路徑
            candidate = base if os.path.exists(base) else os.path.join(args.db_dir, base)
            if not os.path.exists(candidate):
                print(f"[WARN] 找不到資料庫檔：{base}（略過這個集合）")
                total_miss += len(idxs)
                continue
            db_path = candidate

        print(f"[INFO] 開啟資料庫：{db_path}（{len(idxs)} 筆）")
        ds = AseDBDataset(config=dict(src=db_path))

        # 依序處理
        for k, idx in enumerate(sorted(idxs)):
            if args.limit and total_ok >= args.limit:
                break
            try:
                atoms = ds.get_atoms(idx)
            except Exception as e:
                print(f"[MISS] {base}@{idx}: {e}")
                total_miss += 1
                continue

            if per_structure:
                # 單筆一檔
                out_name = f"{os.path.splitext(base)[0]}_{idx}.xyz"
                out_path = os.path.join(args.out_dir, out_name)
                write(out_path, atoms, format=fmt)
            else:
                # 合併檔：逐筆 append
                write(args.out, atoms, format=fmt, append=True)

            total_ok += 1

    print(f"[DONE] 轉出成功 {total_ok} 筆；找不到/失敗 {total_miss} 筆。")
    if not per_structure:
        print(f"輸出檔：{args.out}")
    else:
        print(f"輸出資料夾：{args.out_dir}")

if __name__ == "__main__":
    main()
