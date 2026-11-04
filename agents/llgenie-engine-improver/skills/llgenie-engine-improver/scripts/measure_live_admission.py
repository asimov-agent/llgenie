#!/usr/bin/env python3
"""Measure a live wrong-tier acceptance red (#1649): reproduce the EXACT sync path the
acceptance test consumes, then classify (a) engine-lane regression vs (b) upstream drift.

Usage:
  python3 measure_live_admission.py /path/to/repo-worktree MODEL_ID 8  # gb=8
Persists: <out>/models.json (live store), <out>/measurements.json,
<out>/synced-README.md, <out>/measure.json (the classified evidence).
"""
import sys, os, json, subprocess, argparse, tempfile
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('worktree', help='llgenie checkout (has scripts/)')
ap.add_argument('model', help='model id, e.g. qwen3.8-27b')
ap.add_argument('gb', type=float, help='card gb, e.g. 8.0')
ap.add_argument('--out', default='/tmp/measure-live-admission', help='persist dir')
ap.add_argument('--arch', default='cuda', help='arch for card_evidence/fits')
args = ap.parse_args()

sys.path.insert(0, args.worktree)
os.chdir(args.worktree)
from scripts import sync_registry as sr   # noqa: E402
import scripts.model_engine_pick as mp      # noqa: E402

OUT = Path(args.out); OUT.mkdir(parents=True, exist_ok=True)
dest = OUT/'models.json'
print(f'[1] sync (upstream master via {sr._UPSTREAM_DATA}) -> {dest}', flush=True)
rc = sr.sync(sr.UPSTREAM, dest, sr.UPSTREAM_README, measurements_src=sr.UPSTREAM_MEASUREMENTS)
print(f'[1] sync rc={rc}', flush=True)
reg = json.loads(dest.read_text())
readme = OUT/'synced-README.md'
if (OUT/'trending-README.md').exists():
    (OUT/'trending-README.md').rename(readme)  # sync vendors README beside dest
if not readme.exists():
    raise SystemExit('vendored README bookend not found under OUT')

qm = next((m for m in reg['models'] if m['id'] == args.model), None)
if qm is None:
    raise SystemExit(f'model {args.model} not in live store (117 rows?)')
head = subprocess.run(['git','rev-parse','--short','HEAD'], capture_output=True, text=True).stdout.strip()
res = {'head': head, 'sync_rc': rc, 'model': args.model, 'gb': args.gb, 'arch': args.arch}

txt = readme.read_text(); lines = txt.split('\n')
sec = next((i for i,l in enumerate(lines) if 'Up to %d' % int(args.gb) in l or ('8' in l and 'GB' in l and 'Up to' in l)), None)
if sec is not None:
    block = lines[sec:sec+45]
    res['readme_tier_section'] = block
    res['readme_tier_places_model'] = any(args.model.lower() in l.lower() for l in block)
else:
    res['readme_tier_section'] = None; res['readme_tier_places_model'] = None

for gb in (args.gb, 16.0):
    for arch in (args.arch, 'metal', None):
        key = f'gb{int(gb)}_{arch}'
        try:
            res[f'card_evidence_{key}'] = mp.card_evidence(qm, gb, arch)
            res[f'fits_{key}'] = bool(mp.fits(qm, gb, arch=arch))
        except Exception as e:
            res[f'card_evidence_{key}'] = f'ERR {e}'

m = mp.admitting_measurement(qm, args.gb, args.arch)
res['admitting_this'] = ({'engine':m.get('engine'),'tps':m.get('tps'),'hardware':m.get('hardware')} if m else None)
res['vram_min_gb'] = mp.vram_min_gb(qm) if hasattr(mp,'vram_min_gb') else qm.get('vram_min')
res['stated_budget_gb'] = mp.stated_budget_gb(qm) if hasattr(mp,'stated_budget_gb') else qm.get('weight_gb')

rows = mp.rank_models(reg, args.arch, args.gb)
res['rank_this_count'] = len(rows)
res['rank_this_has_model'] = any(r['model']['id']==args.model for r in rows)
res['rank_this_top_ids'] = [r['model']['id'] for r in rows[:10]]
tl = mp.trend_list(reg, args.gb, arch=args.arch, readme_text=txt)
res['trend_this_has_model'] = any(m.get('id')==args.model for m in tl)
res['trend_this_count'] = len(tl)

card_runs = []
for e in qm.get('engines', []):
    hw = e.get('hardware','')
    mc = None
    try: mc = mp.measurement_card_gb(hw)
    except Exception: mc = '?'
    apple = any(k in hw for k in ('Apple','Mac','M','unified'))
    card_runs.append({'engine':e.get('engine'),'tps':e.get('tps'),'hw':hw[:50],'card_gb':mc,'apple':apple})
res['engine_runs'] = card_runs

(OUT/'measure.json').write_text(json.dumps(res, indent=1, default=str))
min_card = sorted([r['card_gb'] for r in card_runs if r['card_gb'] and not r['apple']] or [])
print(json.dumps({'head':head,'sync_rc':rc,'readme_tier_places_model':res['readme_tier_places_model'],
    'card_evidence':res[f'card_evidence_gb{int(args.gb)}_{args.arch}'],'fits':res[f'fits_gb{int(args.gb)}_{args.arch}'],
    'rank_has_model':res['rank_this_has_model'],'trend_has_model':res['trend_this_has_model'],
    'vram_min':res['vram_min_gb'],'weight':res['stated_budget_gb'],'admitting':res['admitting_this'],
    'min_nonapple_card':min_card[:3]}, default=str))
