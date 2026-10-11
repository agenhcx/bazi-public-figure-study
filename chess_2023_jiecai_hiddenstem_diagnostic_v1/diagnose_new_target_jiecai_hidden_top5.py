#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Diagnose why Jie-Cai (劫财) increases under hidden-stem coding
in 2023 M NEW_TARGET.

Reads:
  chess_2023_cohorts_v1/validation_2023_M_NEW_TARGET.csv

Finds players with:
  M1_5pos_hidden Jie-Cai count > M0_5pos_mainqi Jie-Cai count

Sorts by Elo/rating descending and prints top 5, including:
  - name, rating, DOB
  - Y/M/D pillars
  - Day Master
  - visible stems used for transparency = Year Stem + Month Stem
  - M0 Jie-Cai count
  - M1 Jie-Cai count
  - which branch changed
  - branch hidden stems
  - which hidden stems were exposed
  - main-qi Ten God -> selected exposed Ten God

Dependencies:
  pip install pandas sxtwl
"""

import argparse
from pathlib import Path
import pandas as pd
import sxtwl

STEMS=list("甲乙丙丁戊己庚辛壬癸")
BRANCHES=list("子丑寅卯辰巳午未申酉戌亥")
ELEM=["木","木","火","火","土","土","金","金","水","水"]
YANG=[1,0,1,0,1,0,1,0,1,0]

HIDDEN={
    0:[9],          # 子 癸
    1:[5,9,7],      # 丑 己癸辛
    2:[0,2,4],      # 寅 甲丙戊
    3:[1],          # 卯 乙
    4:[4,1,9],      # 辰 戊乙癸
    5:[2,4,6],      # 巳 丙戊庚
    6:[3,5],        # 午 丁己
    7:[5,3,1],      # 未 己丁乙
    8:[6,8,4],      # 申 庚壬戊
    9:[7],          # 酉 辛
    10:[4,7,3],     # 戌 戊辛丁
    11:[8,0],       # 亥 壬甲
}

def ten_god(dm,target):
    de,te=ELEM[dm],ELEM[target]
    same=YANG[dm]==YANG[target]
    gen={"木":"火","火":"土","土":"金","金":"水","水":"木"}
    ctl={"木":"土","土":"水","水":"火","火":"金","金":"木"}

    if te==de:
        return "比肩" if same else "劫财"
    if gen[de]==te:
        return "食神" if same else "伤官"
    if ctl[de]==te:
        return "偏财" if same else "正财"
    if ctl[te]==de:
        return "七杀" if same else "正官"
    if gen[te]==de:
        return "偏印" if same else "正印"
    raise RuntimeError((dm,target))

def detect_col(df,candidates,label):
    low={c.lower():c for c in df.columns}
    for c in candidates:
        if c.lower() in low:
            return low[c.lower()]
    raise RuntimeError(f"Cannot detect {label}. Columns={list(df.columns)}")

def diagnose_date(dob):
    dt=pd.Timestamp(str(dob)[:10])
    x=sxtwl.fromSolar(dt.year,dt.month,dt.day)
    yg,mg,dg=x.getYearGZ(),x.getMonthGZ(),x.getDayGZ()

    ys,yb=int(yg.tg),int(yg.dz)
    ms,mb=int(mg.tg),int(mg.dz)
    dm,db=int(dg.tg),int(dg.dz)

    visible={ys,ms}

    # Stem target contributions: Y stem + M stem only.
    m0 = int(ten_god(dm,ys)=="劫财") + int(ten_god(dm,ms)=="劫财")
    m1 = m0

    details=[]

    for label,b in [("年支",yb),("月支",mb),("日支",db)]:
        hs=HIDDEN[b]
        exposed=[s for s in hs if s in visible]

        main=hs[0]
        selected=exposed[0] if exposed else main

        tg_main=ten_god(dm,main)
        tg_sel=ten_god(dm,selected)

        c0=int(tg_main=="劫财")
        c1=int(tg_sel=="劫财")
        m0+=c0
        m1+=c1

        details.append({
            "branch_pos":label,
            "branch":BRANCHES[b],
            "hidden_stems":"".join(STEMS[s] for s in hs),
            "visible_stems":"".join(STEMS[s] for s in sorted(visible)),
            "exposed_hidden":"".join(STEMS[s] for s in exposed) if exposed else "-",
            "main_stem":STEMS[main],
            "main_tg":tg_main,
            "selected_stem":STEMS[selected],
            "selected_tg":tg_sel,
            "jiecai_change":c1-c0,
        })

    return {
        "year_pillar":STEMS[ys]+BRANCHES[yb],
        "month_pillar":STEMS[ms]+BRANCHES[mb],
        "day_pillar":STEMS[dm]+BRANCHES[db],
        "day_master":STEMS[dm],
        "visible_stems":"".join(STEMS[s] for s in sorted(visible)),
        "M0_jiecai":m0,
        "M1_jiecai":m1,
        "delta":m1-m0,
        "details":details,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",default="chess_2023_cohorts_v1/validation_2023_M_NEW_TARGET.csv")
    ap.add_argument("--repo",default=".")
    ap.add_argument("--top",type=int,default=5)
    ap.add_argument("--output",default="new_target_jiecai_hidden_top5.csv")
    a=ap.parse_args()

    root=Path(a.repo).resolve()
    p=Path(a.input)
    if not p.is_absolute():
        p=(root/p).resolve()

    df=pd.read_csv(p)

    name_col=detect_col(df,["name","player_name","full_name"],"name")
    rating_col=detect_col(df,["rating","elo","fide_rating","standard_rating","rating_standard"],"rating")
    dob_col=detect_col(df,["exact_dob_frozen","dob","exact_dob"],"DOB")

    rows=[]
    detail_rows=[]

    for _,r in df.iterrows():
        q=diagnose_date(r[dob_col])
        if q["delta"]<=0:
            continue

        rec={
            "name":r[name_col],
            "rating":pd.to_numeric(r[rating_col]),
            "dob":str(r[dob_col])[:10],
            "year_pillar":q["year_pillar"],
            "month_pillar":q["month_pillar"],
            "day_pillar":q["day_pillar"],
            "day_master":q["day_master"],
            "visible_stems":q["visible_stems"],
            "M0_jiecai":q["M0_jiecai"],
            "M1_jiecai":q["M1_jiecai"],
            "delta":q["delta"],
        }
        rows.append(rec)

        for d in q["details"]:
            if d["jiecai_change"]!=0:
                detail_rows.append({
                    **rec,
                    **d,
                })

    out=pd.DataFrame(rows).sort_values(["rating","name"],ascending=[False,True]).head(a.top)
    selected=set(out["name"].astype(str))
    det=pd.DataFrame(detail_rows)
    if len(det):
        det=det[det["name"].astype(str).isin(selected)].sort_values(
            ["rating","name","branch_pos"],ascending=[False,True,True]
        )

    out_path=root/a.output
    out.to_csv(out_path,index=False,encoding="utf-8-sig")

    detail_path=out_path.with_name(out_path.stem+"_branch_details.csv")
    det.to_csv(detail_path,index=False,encoding="utf-8-sig")

    print("="*110)
    print("2023 M NEW_TARGET — TOP PLAYERS WHO GAIN 劫财 UNDER HIDDEN-STEM PRIORITY")
    print("="*110)

    for i,(_,r) in enumerate(out.iterrows(),1):
        print()
        print(f"#{i} {r['name']} | Elo={r['rating']} | DOB={r['dob']}")
        print(f"   八字(date-known): {r['year_pillar']} {r['month_pillar']} {r['day_pillar']} | 日主={r['day_master']}")
        print(f"   透干可见: {r['visible_stems']} | 劫财 M0={r['M0_jiecai']} -> M1={r['M1_jiecai']} | Δ={r['delta']:+d}")

        dd=det[det["name"].astype(str)==str(r["name"])]
        for _,x in dd.iterrows():
            sign="GAIN" if x["jiecai_change"]>0 else "LOSS"
            print(
                f"   {x['branch_pos']}{x['branch']}: 藏干={x['hidden_stems']} | "
                f"透出={x['exposed_hidden']} | "
                f"本气 {x['main_stem']}({x['main_tg']}) -> "
                f"选中 {x['selected_stem']}({x['selected_tg']}) | {sign} 劫财"
            )

    print()
    print("Saved:",out_path)
    print("Saved:",detail_path)

if __name__=="__main__":
    main()
