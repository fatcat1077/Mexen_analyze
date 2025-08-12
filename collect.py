#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv, argparse

def main():
    ap = argparse.ArgumentParser(description="輸出 CSV 的前 N 筆資料列（保留表頭）")
    ap.add_argument("input", help="輸入 CSV 檔")
    ap.add_argument("output", help="輸出 CSV 檔")
    ap.add_argument("-n", "--nrows", type=int, default=1200, help="要輸出的資料列數（不含表頭），預設 1200")
    ap.add_argument("--no-header", action="store_true", help="輸入檔沒有表頭（第一列視為資料）")
    ap.add_argument("--encoding", default="utf-8-sig", help="輸入檔編碼，預設 utf-8-sig（對 Excel 友善）")
    args = ap.parse_args()

    with open(args.input, "r", newline="", encoding=args.encoding) as fin, \
         open(args.output, "w", newline="", encoding="utf-8-sig") as fout:
        r = csv.reader(fin)
        w = csv.writer(fout)

        written = 0
        # 若有表頭，先寫出
        if not args.no_header:
            header = next(r, None)
            if header is not None:
                w.writerow(header)

        for row in r:
            if written >= args.nrows:
                break
            w.writerow(row)
            written += 1

    print(f"完成：已將 {written} 列寫入 {args.output}")

if __name__ == "__main__":
    main()
