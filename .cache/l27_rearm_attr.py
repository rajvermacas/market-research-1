import sys, json, types, numpy as np
sys.path.insert(0, "scripts")
import strategy_lab as sl
from strat_l23a_liqconfirm import score as base
import strat_l27o_corerearm as R
P = {"b_hi": 0.65, "b_lo": 0.45, "b_mid": 0.55, "floor_lb": 19, "lookback": 16, "max_dist": 0.055, "regime_ma": 18, "lq_min": 5e6, "lq_days": 40, "lq_shift": 0.05, "lq_shift_hi": 0.05, "lq_shift_lo": 0.075, "lq_mode": "strict", "top": 25, "weighting": "invvol", "cr_k": 3, "cr_thr": 0.12, "cr_to": 1.0, "cr_min": 2e7, "cr_days": 40}
prof = dict(sl.EXEC_PROFILES["realistic"])
ctx = sl.build_context("nse_all", "2015-01-01", "2022-01-01", prof, True)
months = ctx["months"]; sp = ctx["split_i"]
_, e0 = base(ctx, P); e0 = np.asarray(e0, float)
_, e1 = R.score(ctx, P); e1 = np.asarray(e1, float)
fired = [i for i in range(ctx["start_i"], sp) if e0[i] != e1[i]]   # train firings only
def run(idx, label):
    e = e0.copy()
    for i in idx: e[i] = e1[i]
    mod = types.SimpleNamespace(score=lambda pan, pr: (base(pan, pr)[0], e))
    sc = sl.score_candidate(mod, P, ctx, {"trail_k": None, "max_hold": None})
    m = sl.run_book(sc, ctx, 25, prof["cost_bps"] / 1e4, 0)
    print(label, {k: round(v, 4) for k, v in m.items() if isinstance(v, float) and not k.startswith(("fwd", "forward")) and ("dd" in k or "cagr" in k or k == "invested")})
run([], "BASE")
run(fired, "ALL-TRAIN-FIRINGS")
run([i for i in fired if str(months[i])[:4] != "2020"], "ONLY-2016")
run([i for i in fired if str(months[i])[:4] == "2020"], "ONLY-2020")
