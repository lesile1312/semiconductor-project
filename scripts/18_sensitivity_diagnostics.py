"""Exploratory weight-sensitivity diagnostics; not a final GTRI score/ranking."""
from __future__ import annotations
import shutil
import numpy as np
import pandas as pd
from gtri_config import OUTPUT_DIR, PROJECT_ROOT, append_progress, ensure_directories

MASTER=OUTPUT_DIR/"master_country_year.csv"
OUT=OUTPUT_DIR/"sensitivity_diagnostics_2022.csv"
REPORT=PROJECT_ROOT/"docs"/"sensitivity_diagnostics.md"

def main()->int:
    ensure_directories(); p=pd.read_csv(MASTER); p=p[p.year==2022].copy()
    fields=["n2_china_hs8542_import_share","n3_us_hs8542_export_share","n4_dual_dependency","v1_hs8542_import_hhi"]
    z=p[fields].rank(pct=True)
    scenarios={"equal_N4_V1": {"n2_china_hs8542_import_share":.125,"n3_us_hs8542_export_share":.125,"n4_dual_dependency":.5,"v1_hs8542_import_hhi":.25},"network_heavy": {"n2_china_hs8542_import_share":.3,"n3_us_hs8542_export_share":.3,"n4_dual_dependency":.3,"v1_hs8542_import_hhi":.1},"vulnerability_heavy": {"n2_china_hs8542_import_share":.15,"n3_us_hs8542_export_share":.15,"n4_dual_dependency":.2,"v1_hs8542_import_hhi":.5}}
    rows=[]
    baseline=sum(z[k]*v for k,v in scenarios["equal_N4_V1"].items())
    for name,w in scenarios.items():
        score=sum(z[k]*v for k,v in w.items()); rows.append({"scenario":name,"weight_vector":"; ".join(f"{k}={v:.2f}" for k,v in w.items()),"score_mean":score.mean(),"score_std":score.std(ddof=1),"top_country_exploratory":p.loc[score.idxmax(),"country"],"spearman_vs_equal_N4_V1":score.rank().corr(baseline.rank())})
    out=pd.DataFrame(rows); out.to_csv(OUT,index=False,encoding="utf-8-sig")
    REPORT.write_text("# 2022权重敏感性诊断\n\n本文件只比较N/V贸易与供应脆弱性指标在不同权重情景下的排序变化，不构成最终GTRI权重或正式排名。P2不在本组N/V情景内；P3候选规则仍是非穷尽证据层，未入分。\n\n```text\n"+out.to_string(index=False)+"\n```\n\n解释：若不同情景与基准情景的Spearman相关较高，说明初步结论不完全依赖某个权重设定；若相关较低，则应强调权重不确定性。该诊断回答的是N/V权重选择问题，不检验P2或P3，也不代表指数的预测效度。\n",encoding="utf-8")
    public=PROJECT_ROOT/"outputs"; public.mkdir(exist_ok=True); shutil.copy2(OUT,public/OUT.name); shutil.copy2(REPORT,public/REPORT.name)
    append_progress("Exploratory weight sensitivity diagnostics","complete without final GTRI",[f"Compared {len(scenarios)} N/V-only scenarios for 2022.","P2 was outside the defined N/V-only sensitivity question; selected BIS P3 candidate evidence remains non-exhaustive and non-scoring.","No final GTRI weights or formal country ranking was produced."])
    print(out.to_string(index=False)); return 0
if __name__=="__main__": raise SystemExit(main())
