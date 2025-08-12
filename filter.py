#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
從多個 .aselmdb 檔（ASE LMDB 後端）以「元素組成 + 化學計量」規則篩選 MXene-like 結構。
不檢查幾何/配位；但要求：
  1) 元素集合 ⊆ (M ∪ X ∪ 端基)
  2) 同時含 ≥1 種 M 與 ≥1 種 X
  3) M_total / X_total ≈ (n+1)/n，其中 n ∈ {1,2,3}（可調），比例容許誤差可調
  4) （可選）至少含一種端基元素

輸出：mxene_candidates.csv
"""

import argparse
from pathlib import Path
from typing import List, Set, Dict, Tuple
import sys
from collections import Counter
import pandas as pd

try:
    from ase.db import connect
except Exception as e:
    print("請先安裝 ASE：pip install ase", file=sys.stderr)
    raise

# ---- 收斂後的預設 M 清單（早過渡金屬，常見於 MAX/MXene 家族）----
DEFAULT_M_LIST = [
    # 3d（常見）
    "Sc", "Ti", "V", "Cr",
    # 4d
    "Zr", "Nb", "Mo",
    # 5d
    "Hf", "Ta", "W",
]
DEFAULT_X_LIST = ["C", "N"]
DEFAULT_TERMINATIONS = ["O", "F", "Cl", "Br", "I", "H"]  # OH 會以 O+H 形式出現

ALLOWED_N_SET = [1, 2, 3]  # 對應 M_{n+1}X_n
DEFAULT_RATIO_TOL = 0.20   # 允許 ±20% 相對誤差

def parse_args():
    ap = argparse.ArgumentParser(
        description="Filter MXene-like entries by element sets and stoichiometry from multiple .aselmdb files (ASE LMDB)."
    )
    ap.add_argument("--root", type=Path, default=Path("."),
                    help="資料夾根目錄（會在裡面找 db_*.aselmdb；預設為當前資料夾）")
    ap.add_argument("--pattern", type=str, default="db_*.aselmdb",
                    help="檔名樣式（預設：db_*.aselmdb）")
    ap.add_argument("--m-list", type=str, nargs="*", default=DEFAULT_M_LIST,
                    help=f"M（過渡金屬）清單，預設：{DEFAULT_M_LIST}")
    ap.add_argument("--x-list", type=str, nargs="*", default=DEFAULT_X_LIST,
                    help=f"X 清單，預設：{DEFAULT_X_LIST}")
    ap.add_argument("--terminations", type=str, nargs="*", default=DEFAULT_TERMINATIONS,
                    help=f"允許的端基/共存元素，預設：{DEFAULT_TERMINATIONS}")
    ap.add_argument("--require-only-allowed", action="store_true", default=True,
                    help="（預設啟用）要求所有元素 ∈ (M ∪ X ∪ 端基)")
    ap.add_argument("--no-require-only-allowed", dest="require_only_allowed",
                    action="store_false",
                    help="停用『只能出現在允許集合內』的限制")
    ap.add_argument("--require-has-m-and-x", action="store_true", default=True,
                    help="（預設啟用）要求同時包含至少一種 M 與至少一種 X")
    ap.add_argument("--require-termination", action="store_true", default=True,
                    help="（預設啟用）要求至少含一種端基元素（O/F/Cl/Br/I/H 其一）")
    ap.add_argument("--n", type=int, nargs="*", default=ALLOWED_N_SET,
                    help=f"允許的 n（對應 M_(n+1)X_n），預設：{ALLOWED_N_SET}")
    ap.add_argument("--ratio-tol", type=float, default=DEFAULT_RATIO_TOL,
                    help=f"M/X 比例的相對誤差容許值（例如 0.2 表示 ±20%），預設：{DEFAULT_RATIO_TOL}")
    ap.add_argument("--output", type=Path, default=Path("mxene_candidates.csv"),
                    help="輸出 CSV 檔名（預設：mxene_candidates.csv）")
    return ap.parse_args()

def mxene_ratio_ok(m_total: int, x_total: int, n_set: List[int], tol: float) -> Tuple[bool, float, int, float]:
    """
    檢查 M/X 比是否接近 (n+1)/n；回傳 (ok, ratio, best_n, rel_err)
    """
    if x_total == 0 or m_total == 0:
        return False, float("nan"), -1, float("inf")
    ratio = m_total / x_total
    best_n, best_err = -1, float("inf")
    for n in n_set:
        target = (n + 1) / n
        rel_err = abs(ratio - target) / target
        if rel_err < best_err:
            best_err = rel_err
            best_n = n
    return (best_err <= tol), ratio, best_n, best_err

def is_mxene_like(
    counts: Counter,
    m_set: Set[str],
    x_set: Set[str],
    term_set: Set[str],
    require_only_allowed: bool,
    require_has_m_and_x: bool,
    require_termination: bool,
    n_set: List[int],
    ratio_tol: float
) -> Dict[str, object]:
    elements = set(counts.keys())
    has_m = any(e in m_set for e in elements)
    has_x = any(e in x_set for e in elements)
    has_term = any(e in term_set for e in elements)

    allowed_union = m_set | x_set | term_set
    disallowed = sorted(list(elements - allowed_union))

    ok_only_allowed = not (require_only_allowed and disallowed)
    ok_mx_pair = not (require_has_m_and_x and not (has_m and has_x))
    ok_term = not (require_termination and not has_term)

    # ---- 計量檢查 ----
    m_total = sum(cnt for e, cnt in counts.items() if e in m_set)
    x_total = sum(cnt for e, cnt in counts.items() if e in x_set)
    ratio_ok, ratio, best_n, rel_err = mxene_ratio_ok(m_total, x_total, n_set, ratio_tol)

    # 最終判定：四個條件皆需成立
    is_like = ok_only_allowed and ok_mx_pair and ok_term and ratio_ok

    reasons = []
    if not ok_only_allowed:
        reasons.append(f"含未允許元素: {disallowed}")
    if not ok_mx_pair:
        reasons.append("未同時包含 M 與 X")
    if not ok_term:
        reasons.append("未含任何端基元素")
    if not ratio_ok:
        target_str = ", ".join([f"{(n+1)/n:.2f}" for n in sorted(set(n_set))])
        reasons.append(f"M/X={ratio:.2f} 不符合 {target_str}（誤差 {rel_err:.2%} > 容許 {ratio_tol:.0%}）")
    if not reasons:
        reasons.append("通過元素集合與計量規則")

    return {
        "is_mxene_like": is_like,
        "has_M": has_m,
        "has_X": has_x,
        "has_term": has_term,
        "disallowed_elements": disallowed,
        "m_total": m_total,
        "x_total": x_total,
        "mx_ratio": ratio,
        "best_n": best_n,
        "ratio_rel_err": rel_err,
        "reason": "; ".join(reasons)
    }

def main():
    args = parse_args()
    m_set, x_set, term_set = set(args.m_list), set(args.x_list), set(args.terminations)

    files: List[Path] = sorted(args.root.glob(args.pattern))
    if not files:
        print(f"在 {args.root} 找不到樣式 {args.pattern} 的檔案。", file=sys.stderr)
        sys.exit(1)

    rows_out = []
    total_rows = 0
    hit_rows = 0

    for db_path in files:
        try:
            db = connect(db_path.as_posix(), type="aselmdb", readonly=True, use_lock_file=False)
        except Exception as e:
            print(f"[跳過] 無法開啟 {db_path}: {e}", file=sys.stderr)
            continue

        for row in db.select():  # 全部
            total_rows += 1
            try:
                atoms = row.toatoms()
            except Exception as e:
                print(f"[警告] 取出 atoms 失敗：{db_path} row id {row.id}：{e}", file=sys.stderr)
                continue

            symbols = atoms.get_chemical_symbols()
            counts = Counter(symbols)
            formula = atoms.get_chemical_formula(empirical=True)

            check = is_mxene_like(
                counts=counts,
                m_set=m_set,
                x_set=x_set,
                term_set=term_set,
                require_only_allowed=args.require_only_allowed,
                require_has_m_and_x=args.require_has_m_and_x,
                require_termination=args.require_termination,
                n_set=args.n,
                ratio_tol=args.ratio_tol
            )

            row_dict = {
                "db_file": db_path.name,
                "row_id": row.id,
                "formula": formula,
                "elements": ",".join(sorted(set(symbols))),
                "m_total": check["m_total"],
                "x_total": check["x_total"],
                "mx_ratio": f"{check['mx_ratio']:.4f}" if check["x_total"] else "",
                "best_n": check["best_n"] if check["best_n"] != -1 else "",
                "has_M": check["has_M"],
                "has_X": check["has_X"],
                "has_term": check["has_term"],
                "disallowed_elements": ",".join(check["disallowed_elements"]),
                "is_mxene_like": check["is_mxene_like"],
                "reason": check["reason"]
            }
            rows_out.append(row_dict)
            if check["is_mxene_like"]:
                hit_rows += 1

    df = pd.DataFrame(rows_out)
    df.sort_values(["is_mxene_like", "db_file", "row_id"], ascending=[False, True, True], inplace=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"掃描檔案數：{len(files)}")
    print(f"資料列總數：{total_rows}")
    print(f"符合 MXene-like（元素+計量規則）筆數：{hit_rows}")
    print(f"已輸出：{args.output}")

if __name__ == "__main__":
    main()
