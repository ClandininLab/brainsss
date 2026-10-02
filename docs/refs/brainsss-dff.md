# brainsss-dff — map against `YDPlayground`

Repo: `../refs/brainsss-dff`. It is a git worktree of *this* repo, detached at `e25e58b` (`origin/dff`, Ilana Zucker-Scharff, 2026-07-17); see [00-index.md](00-index.md). Compared with `YDPlayground` at `b553af7`. Surveyed 2026-10-02.

Tags: **[from code]** = read in the file, the diff or the git log; **[inferred]** = interpretation. Unless a commit is named, line references are to `e25e58b`.

## 0. Summary

- **Common ancestor** is `cf9fcf5` (2026-02-13, "changing email") [from code].
  - Since then `dff` has **76 commits**, all by Ilana. `YDPlayground` has **15 commits**, all yours.
  - On Ilana's side, outside notebooks, only `brainsss/{fictrac,utils}.py`, the postprocess layer and `convert_2p_to_nwb.py` changed. **No preprocessing worker changed** (moco, background subtraction, warp, blur, high-pass, dff).
- **The F0 is not loom-specific.** It is a whole-recording 0.01 Hz Butterworth low-pass (§4.1), and it is the same code on both branches [from code]. Two parts of it are fragile for OMR:
  - the hard-coded `fs = 1.8` Hz;
  - the global-minimum offset in the denominator.
- **What *is* loom-specific** is everything downstream of the event pickle:
  - photodiode onset detection;
  - the 1 s loom and the forward-velocity `inc`/`dec`/`flat` split;
  - the ±3 s windows;
  - superclusters defined on the 10-fly loom `total` response;
  - the 2-bin `[-600,0]`/`[700,1300]` ms intervals;
  - the RF "before" window (§5).
- **Worth pulling over:**
  - the `bigmem` sbatch option;
  - centralising `event_times_path` in the orchestrator;
  - skip-if-exists / `--redo` guards;
  - looping over both channels (needed for `regress_noise`);
  - `-sc [N]` / `-cc [N]`;
  - reading behaviour labels from the pickle in `build_STA`.
- **Do not pull:**
  - `make_supervoxels.py` (it does not parse on `dff`);
  - the `tf_to_STA` scratch deletion;
  - `get_ind_vox` / `individual_clusters` as-is.
- **Expect merge conflicts** in `postprocess.py`, `filter_bins.py`, `build_STA.py`, `tf_to_STA.py` and `make_supervoxels.py`, because both sides edited them [from code].

## 1. What changed on `dff` and is not on `YDPlayground`

Source: `git diff YDPlayground...e25e58b` (Ilana's side only) plus `git log cf9fcf5..e25e58b`. Verdicts are **bug fix**, **loom-specific** or **general** (consider pulling).

### 1.1 Library

| File | Change | Verdict |
|---|---|---|
| `brainsss/utils.py` `sbatch(...)` | Adds a `bigmem=False` kwarg that submits with `--partition=bigmem` instead of `trc` (`2d28ec0`) [from code]. The `global_resources` branch still has the stray comma in `--cpus-per-task={},` that predates both branches [from code]. | **General.** Useful for the 500 GB jobs. |
| `brainsss/fictrac.py` `smooth_and_interp_fictrac` | `dRotLabX` ("sideslip", `a37cc6c`/`e25e58b`) now gets the same conversion as `dRotLabZ`: `* 180/pi * fps`, giving deg/s [from code]. | **General, but check it.** Rotation about lab-X is lateral *translation* of the fly, so by analogy with `dRotLabY` (× sphere radius, giving mm/s) it arguably should be mm/s, not deg/s [inferred]. Ask (Q7). |

### 1.2 Orchestrator and shell (`postprocess.py`, `postprocess.sh`, `preprocess.sh`)

| Change | Verdict |
|---|---|
| `event_times_path` is resolved once in `postprocess.py` (`{event}_event_times_split_dic.pkl` or the unlabelled default) and passed to every worker. Workers stop rebuilding it [from code]. | **General.** Removes 8 copies of the same logic. |
| If neither `--flies` nor `-best` is given, the fly list is the event pickle's keys (`f67bc01`) [from code]. | **General**, but it opens the pickle **unconditionally at startup**, so every postprocess run fails unless that pickle exists, even for steps that don't use it [from code]. |
| **Regression:** for `--flies`, the `fly_` prefix stripping is gone. It now always builds `f"fly_{fly}"`, so `--flies fly_240` becomes `fly_fly_240` [from code]. | **Bug introduced.** Fix this if you take the refactor. |
| Channels: `-cc` with no value processes ch 1, `-cc N` processes ch N, and **no flag now processes both `['1','2']`**. The old default was ch 2 only. The `channel_change` key in the settings JSON is no longer read [from code]. | **General.** Both channels are required by `regress_noise`. It doubles runtime, and the default changes silently. |
| `-sc` with no value enables superclustering with `clust_num=500`; `-sc N` uses N. `--after` flag added (consumed by `individual_clusters`) [from code]. | General (`-sc`); loom-specific (`--after`). |
| Every per-fly step loops over `ch_nums`. `later_transfer` now runs **before** `tf_to_STA` (it was after) [from code]. | **Bug fix.** `tf_to_STA` reads what `later_transfer` writes. |
| sbatch resources: `filter_bins`, `relative_ts` and `temp_filter` go to `bigmem` with 500 GB and 5 h; `supercluster` 24 h. `postprocess.sh` wall time 4 → 5 days plus `--mail-type` [from code]. | Cluster tuning. Take it if you hit OOM. |
| `make_supervoxels` passes `func_path = fly_directory`, and the worker appends `func_0` itself. `wait_for_job` sits outside the channel loop, so it waits only on the last job [from code]. | Neither branch is right. Your version (`func_path=.../func_0`, single job) works. |
| `preprocess.sh`: hard-coded `--mail-user` commented out [from code]. | Trivial. You already set your own. |

### 1.3 Postprocess workers

All of these gained `event_times_path` and `redo` args (see §1.2). The table lists only the substantive changes.

| Script | What changed on `dff` | Verdict |
|---|---|---|
| `filter_bins.py` | Window −2000/3000 → **−3000/3000** ms (`8c10f31`, "6 secs"). Skips flies missing from the event dict [from code]. | Window: **loom-specific**. Fly guard: **bug fix**, but `A and B or redo` precedence means `--redo` still raises KeyError for a fly that isn't in the dict [from code]. You re-added `np.sort(starts)`, which Ilana has commented out; keep yours (§5.6). |
| `relative_ts.py`, `temp_filter.py` | Only take `event_times_path` [from code]. | General. |
| `later_transfer.py` | Skip if the destination exists, unless `--redo` [from code]. Note that it copies into **`scratch_path/tf/{behavior}/`**, not into `later_path` [from code]. | **General.** |
| `tf_to_STA.py` | Window **−3000/3000**. Skip if the STA exists. `int`/`str` fly match (you fixed the same thing differently in `24c1c28`). **Deletes inputs after writing** (`415d8cd`, `f72251c`): the `scratch/fly_N/*{event}*{behavior}*` files and the `scratch/tf/{behavior}/*_tf_*` files for that channel [from code]. | Skip guard: general. Cleanup: **risky.**<br>• `event in file` raises `TypeError` when `event` is `None`.<br>• `os.listdir(scratch/fly_N)` crashes if that directory is missing.<br>• If no file matches, `save_file` is never assigned, giving a `NameError`.<br>• The fly-dir cleanup ignores channel, so the ch-1 pass deletes ch-2 `filter_needs`/`ts_rel` files [from code].<br>Commit `63d1f7a` says "gotta be careful with the remove situation". |
| `build_STA.py` | Behaviours read from the pickle instead of the hard-coded `['inc','dec','flat','total']` [from code]. | **General.** It replaces your hard-coded OMR list. But it still loads `..._filtered_{behavior}.h5` without the `_{event}` suffix that `temp_filter` writes when `-e` is set, so it only works for event-less runs on both branches [from code]. |
| `make_supervoxels.py` | Skip if labels and signals exist. Cluster dir moved to `func_path/func_0/clustering` [from code]. | **Do not pull.**<br>• The file raises `TabError` on parse (mixed tabs and spaces) [from code: `ast.parse`].<br>• `save_labels` uses `cluster_dir` before it is defined [from code].<br>• The base version also failed to parse; your re-indent (`eb4e54b`) is the only one that compiles. |
| `regress_noise.py` | Skip if the output exists [from code]. | General. |
| `supercluster.py` | Skip guard. Supervoxel labels switched to `10flies_cluster_labels_best_flies.npy`. Supercluster labels are **fit once** on `behave_dict_total_10flies.pkl['total']` and reused for every event (`355d3ca` "clusters should always stay the same") [from code]. | **Loom-specific** (§5.4). |
| `get_ind_vox.py` | Wrapped in a skip guard [from code]. | **Bug introduced.** The output name `individual_fly_superclusters_2bin_total.pkl` has no channel or event in it, and the orchestrator now loops `ch_nums=['1','2']`. The ch-1 run writes the file and the ch-2 run skips it [from code]. |
| `individual_clusters.py` | Cluster count from `-sc`; event dict from `event_times_path` (it was hard-coded to `10flies_5sec`). The pre-event window was rewritten. `--after` mode added (`edeb203`) [from code]. | **Loom-specific** (§3, §5.5). |
| `convert_2p_to_nwb.py` (new, 714 lines, "made by claude") | Standalone NWB export of imaging, FicTrac and the visual-stim HDF5. Not called by any orchestrator [from code]. `imaging_rate` is taken from the Bruker `frameRate`, which is the per-plane rate, not the volume rate [inferred]. | Optional. Not pipeline-relevant. |

### 1.4 Things on `YDPlayground` only (for context)

- **Preprocess I/O**: outputs moved to `func_0/playground/` (`e81b20e`), so `bg → warp → blur → hpf → dff` all live there [from code]. Ilana's `temp_filter` still loads from `fly_N/dff/` and `warp/timestamps_warp.h5` [from code]. If you merge her orchestrator, repoint `load_directory`.
- **Windows** [from code]:
  - `filter_bins` −500/1100: the effective end is 1000, because `end = loom + bin_end - bin_size`.
  - `tf_to_STA` −500/1000.
  - `build_STA` −1000/1000. Bins from −1000 to −500 will be all-NaN, because no data was kept there [inferred].
- **`build_STA` labels**: `syn_turn_{0,180}`, `anti_turn_{0,180}`, `flat_{0,180}`, `total` are hard-coded [from code]. Ilana's pickle-driven version removes the need for this.

## 2. Notebooks

**Location:** everything is in `dff/notebooks/` (81 notebooks, flat; `notebooks/scratch/` is only a joblib cache) [from code].
- Figure notebooks are named `YYYYMMDD_figN_*`. The `_FINAL` suffix marks the paper versions.
- Data paths in the notebooks point at `/oak/stanford/groups/trc/data/Ilana/2P/data/{later,fly_N}`.
- Paper figure numbers below come from notebook and `savefig` names [from code]. Which paper they belong to is [inferred]: Ilana's loom/whole-brain paper.

### 2.1 Paper-facing notebooks

| Notebook | One line | Figure |
|---|---|---|
| `20251109_fig1_FINAL` | Voxel z-scored loom STA maps, pre vs post, heatmaps of visual (PVLP/AVLP/AOTU/MED/LO/LP) vs non-visual ROIs, from `behave_dict_total_10flies.pkl` | **Fig 1** |
| `20251107_fig2_FINAL` | Behaviour: trial classification, KMeans (k=3) on forward velocity, run lengths vs null, Sankey of trial-to-trial labels | **Fig 2** |
| `20250918_fig3_FINAL` | Supercluster (500) heatmaps for inc/dec/flat, Mann-Whitney + Bonferroni, KMeans (k=6) trace types, PCA | **Fig 3** |
| `20251106_fig4_FINAL` | Random-forest decoding of inc/dec/flat from per-fly supercluster activity: accuracy, confusion matrix, top-5 clusters | **Fig 4** |
| `20251015_figS1_FINAL` | Photodiode loom times, FicTrac, warped-brain frames, per-fly step-10 ms STA traces (fly 241) | **Fig S1** |
| `20251103_figS3_FINAL` | Per-ROI (e.g. IPS) voxel z-score maps at selected timepoints | **Fig S3** |
| `20251205_moviemaking` | Movie frames from fly 208 warp plus the z-scored STA | Supplementary movie [inferred] |

### 2.2 Drafts, data-building and exploratory notebooks

| Notebook | One line |
|---|---|
| `20250504_fig1_images`, `20250508_fig2_images`, `20250512_fig4_images`, `20250714_fig2s_images`, `20250730_fig5_images` | Earlier drafts. `fig5_images` turned into Fig 3 [inferred] |
| `20251017_figure4+`, `20251102_random_forest`, `20260309_top_superclust`, `20260317_newclust_rf` | Fig 4 development and revision. `newclust_rf` uses the `--after` cluster files |
| `20250918_avg_preclus` | Fig 3 analysis on voxels instead of superclusters |
| `20250826_individual_vox` | Builds `individual_fly_superclusters_2bin_total.pkl`; it is the notebook twin of `get_ind_vox.py` |
| `HOWTO_split_behavior` | **How the event pickle is made** (§5.1). Read this first |
| `HOWTO_create_supervox_mask` | **How `10flies_cluster_labels_best_flies.npy` is made** (§3, `supercluster`) |
| `20260203_behavior_all`, `20260302_new_behave_dicts` | Newer event-dict variants (pairwise `prev_behavior`, `non_*` splits) |
| `20260317_first5` | Control: pseudo-trials every 7 s before the first loom |
| `20250428_red_channel_norm`, `20250612_noiseremoval` | Prototypes of the red-channel regression |
| `20250621_clustering_fucking_around`, `20250807_mesh_thingy`, `20251029_new_behavior`, `20260310_look@brains`, `20250924_toms_impossible_fig` | Exploration and QC |
| `20240521_deltafoverf` | Only notebook that tries a **pre-stimulus F0**; it was never adopted (§4.2) |

## 3. Postprocess workers

All workers use ms timestamps from `warp/timestamps_warp.h5` (`load_timestamps` returns ms) [from code]. The template grid is 314×146×91 (FDA mean brain, 2 µm) [from code]. Behaviours are the pickle's keys for its *first* fly [from code].

| Worker | Inputs | Outputs | Hard-coded constants |
|---|---|---|---|
| `filter_bins` | event pickle; `fly_N/warp/timestamps_warp.h5` | `scratch/fly_N/filter_needs_{ch}_{beh}[_{event}].h5`, holding `bins` (np.digitize index per voxel×t), `loom_starts` and `bin_shape` | `bin_start=-3000`, `bin_end=3000`, `bin_size=100` ms (window = `[on-3000, on+2900)`); fly id = `fly[4:7]` (3-digit flies only); events outside the recording dropped |
| `relative_ts` | `filter_needs_*`, timestamps | `scratch/fly_N/ts_rel_odd_mask_{ch}_{beh}[_{event}].h5`: `ts_rel` = t − onset inside window *i* (bin 2i+1); `odd_mask` = in-window | — |
| `temp_filter` | `fly_N/dff/functional_channel_{ch}_moco_warp_blurred_hpf_dff.h5` (`data`); timestamps and the two files above, copied to scratch | `fly_N/temp_filter/..._dff_filtered_{beh}[_{event}].h5`: `brain` and `time_stamps`, all in-window samples from all events concatenated and **sorted by relative time** per voxel, NaN-padded | `fs` from `ts[0,0,0,1]-ts[0,0,0,0]`; `max_len = 6 s·fs·n_events + 100`; gzip 4 |
| `make_supervoxels` | `temp_filter/..._filtered_{beh}.h5` | `func_0/clustering/cluster_labels_{ch}_{beh}_2000.npy`, `cluster_signals_…` | 2000 Ward clusters per z, 2-D grid connectivity. **Broken on `dff`** (§1.3) |
| `build_STA` | per-fly cluster labels and signals; `ts` from the filtered file | `fly_N/STA/stepsize_100_STA_{beh}.h5` | `brain_dims=[314,146]`; Gaussian σ=1 over time (truncate 1); range **−500 to 1900** ms, step 100 (24 bins) |
| `later_transfer` | `fly_N/temp_filter/..._filtered_{beh}_{event}.h5` | `scratch/tf/{beh}/{fly}_tf_{beh}_{ch}_{event}.h5` | — |
| `tf_to_STA` | `scratch/tf/{beh}/*` | `later/temp_filter/{beh}/STA_{ch}_{beh}_100_{event}.h5` (`data`, 60 × 314×146×91) | **−3000 to 3000**, step 100. Per-fly `nanmean` per bin, then `nanmean` across flies, so each fly gets equal weight. No baseline subtraction [from code] |
| `regress_noise` | `STA_{1,2}_*_{event}.h5` | `later/temp_filter/behave_dict_total_{event}.pkl` | Per voxel, fit green = a·red + b over the 60 STA bins and keep the residual. Before the fit: **NaN→0, inf→4** (`make_multi_behave_dict`). `step_size=100` |
| `supercluster` | `behave_dict_total_{event}.pkl`; `clustering/10flies_cluster_labels_best_flies.npy`; for fitting, `behave_dict_total_10flies.pkl['total']` | `clustering/supercluster_labels_total_{N}.npy` (fit once); `superclust_clusters_{N}_{event}.pkl` | `super_vox=2000`, N=500 by default; FDA meanbrain mask `>0.1`; 3-D grid connectivity, Ward |
| `get_ind_vox` | `fly_N/temp_filter/*_{beh}_*{event}*_{ch}_*`; `supercluster_labels_total_500.npy` | `clustering/individual_fly_superclusters_2bin_total.pkl` ({beh: {fly: 500×…×2}}) | intervals **`[-600,0]`, `[700,1300]` ms**; `super_clust=500`; skips names containing `500_` |
| `individual_clusters` | **hard-coded** `/oak/.../Ilana/2P/data/fly_N/{dff,warp}` (*full* dF/F, not temp-filtered); 500-cluster `total` labels reshaped to (314,146,91); event pickle `[str(fly)]['total']` | `later/{fly}_[after_]individual_clusters_new_ch_{ch}_dict_{event}.pkl`: {cluster: {event_idx: mean of 10 samples}} | See below. |

**`individual_clusters` window details** [from code]:
- **Default mode:** the last 10 samples in `[prev_onset + units, onset]`, where `units = 2000//10 = 200`. The first event uses `(-inf, onset]`.
- **`--after` mode:** the last 10 samples in `[onset + 50, next_onset − 200]`.
- **Possible unit bug** [inferred]: the comments say "2 seconds" and "0.5 s", but timestamps are in ms, so these offsets are 200 ms and 50 ms. The code computes `units` as if one unit were 10 ms. See Q3.

Preprocess workers that set F0 are covered in §4.1.

## 4. F0 / dF/F

### 4.1 What the pipeline does (identical on both branches) [from code]

1. **`blur.py`**: 3-D `gaussian_filter(vol, sigma=2)` per volume. This also blurs across z.
2. **`butter_highpass.py`**: second-order Butterworth high-pass, `cutoff=0.01` Hz, **`fs=1.8` Hz hard-coded**, applied with `filtfilt` (zero-phase) along time per z-plane. It then sets `lpf = brain − hpf` ("low pass filter data as f nought") and saves both `hpf` and `lpf`.
3. **`dff.py:53-56`**: `lpf_min = np.min(lpf)`, then `dff = hpf / (lpf − lpf_min)`.
   - The minimum is a **single scalar over the whole 4-D array**: all voxels, all timepoints.
   - The voxel/timepoint that holds the minimum divides by 0 and gives `inf`.
   - Downstream code patches this: `inf→4` in `make_multi_behave_dict`, `inf→5` in `HOWTO_create_supervox_mask`.

So F0 = (slow trend, periods > ~100 s) − (global brain minimum).
- It is not a pre-stimulus baseline.
- Its value depends on the dimmest voxel anywhere, so dim voxels get inflated dF/F, and the scale differs between flies [inferred].

### 4.2 History [from code, via notebooks and git log]

- The formula went through these versions: `hpf/lpf` → zero-division fix → `hpf/(lpf − min + 100)` ("to get normalized numbers", 2024) → `+1` → `− min` with no offset (`56b7860`).
- A FDA-meanbrain mask was added, then removed (`65f2244`).
- The only pre-stimulus F0 attempt is in `20240521_deltafoverf`, cells 33–46 (mean of frames between looms, Otsu mask). It was abandoned.
- The figure notebooks do **no extra baseline subtraction**. They z-score each trace along time, over the full axis (Fig 1) or a trimmed window `[14:41]` (Fig 3/S3), which includes ~6 pre-stim bins.
- No written justification for the global-min subtraction exists [inferred: it reads as a fix for divide-by-zero and negative `lpf` after background subtraction].

### 4.3 Implications for OMR [inferred]

- **`fs=1.8` is a constant, not read from the data.**
  - If your OMR volumes are acquired at a different rate, the real cutoff is 0.01·(true_fs/1.8) Hz.
  - `temp_filter` already derives fs from timestamps; `butter_highpass` should too.
- **Long OMR epochs.** A 0.01 Hz high-pass with `filtfilt` attenuates anything sustained for tens of seconds, and the loom (1 s) never came near that limit.
  - If OMR epochs or their adaptation run ≥ ~20–30 s, part of the sustained response moves into `lpf`, which is your F0. That both shrinks the numerator and inflates the denominator.
  - Check the stimulus period against the cutoff before reusing it.
- **The global-min offset.** Comparing flies, or ipsi- vs contra-lateral regions, is sensitive to the global-min offset. A per-voxel F0 would be safer: a per-voxel `lpf` percentile, or a pre-epoch window.
- **What you can reuse.** If you keep the pipeline F0, compare conditions within voxel (syn vs anti, 0° vs 180°), where the shared denominator cancels.

## 5. Loom-specific assumptions that must NOT carry into OMR

1. **Event definition** (`HOWTO_split_behavior`, `brainsss/visual.py:191`) [from code]:
   - Onsets are photodiode "frame flips" thresholded at 0.8, at 10 kHz.
   - A new epoch starts after a gap > **0.9 s**.
   - If fewer than **150** events are found on pd1, it falls back to pd2.
   - Event times are truncated to 10 ms.
   - An OMR stimulus with continuous flicker, or with a different epoch structure, will break the 0.9 s epoch rule and the ≥150 heuristic.
2. **Trial windows and labels** [from code]:
   - Behaviour traces run −2 s to +3 s at 10 ms, and the loom is 1 s (samples 200–300).
   - Labels use **forward velocity `dRotLabY`**: pre = mean over [−0.5, 0) s, post = mean over [+0.5, +1.0) s.
   - The rules are `flat` (|pre|, |post| < 0.1), then `inc` (post > |2·pre|), then `dec` (post < pre/2), else `non`.
   - OMR needs turning (`dRotLabZ`) relative to stimulus direction, so these thresholds, windows and the variable itself are wrong for OMR.
   - The "best" label sets (`fixed_best_final`, etc.) use stricter thresholds that are also loom-specific.
3. **Windows**: `filter_bins` and `tf_to_STA` use ±3 s; `build_STA` uses −500 to 1900; `get_ind_vox` uses `[-600,0]`/`[700,1300]`; notebooks use trims `[14:41]` and stimulus lines at bins 6/16 [from code]. All of these assume a 1 s stimulus.
4. **Superclusters are fit on loom data** [from code]:
   - `supercluster_labels_total_500.npy` is fit on the 10-fly loom `total` STA.
   - The supervoxels come from 10 loom flies' `total` temp-filtered data.
   - The labels are reused for every event, and the largest cluster (index 8) is dropped as background in the notebooks.
   - Running `-sc` with an OMR event would silently reuse loom-defined clusters if `supercluster_labels_total_500.npy` already exists in your `later_path`. Fit your own.
5. **`individual_clusters`** [from code]:
   - It reads Ilana's Oak paths directly.
   - It uses only the `'total'` key.
   - Its "before"/"after" windows assume a sparse loom train with ≥2 s between events (and note the 10× unit question, Q3).
6. **Non-overlapping windows** [from code]:
   - `filter_bins` builds `[start, end]` pairs and `np.digitize`s against them.
   - If events are closer than the window length (6 s on `dff`; 1.5 s on yours), the edges are non-monotonic and `np.digitize` raises. If they are only mis-sorted, the odd/even "in-window" logic breaks.
   - Ilana commented out the sort, so loom events must already be sorted and ≥6 s apart. Keep your `np.sort` and check the minimum inter-event interval.
7. **Fly lists and dims** [from code]:
   - `BEST_FLIES = [226,227,228,234,239,240,241,242,249,250]` ("best by correlation QC").
   - `fly[4:7]` assumes three-digit fly numbers.
   - `HOWTO_create_supervox_mask` pads each fly to `nt=1100`.
8. **Red-channel regression** (`regress_noise`) [from code]:
   - It fits green on red across only the **60 STA bins** of one behaviour, per voxel.
   - With few or short OMR bins the fit gets noisy. It also removes any stimulus-locked signal that is shared with red, for example motion artefacts during turning [inferred].
9. **Behaviour units** [inferred]: the event notebooks use raw `load_fictrac` output, with no unit conversion, and thresholds of 0.1 and 1.5. These numbers don't port to `smooth_and_interp_fictrac` output (mm/s, deg/s).

## 6. Open questions for Ilana

1. **F0.** Was `hpf / (lpf − global_min)` a deliberate choice, or a divide-by-zero fix? Did you check how much the global minimum varies across flies? Would you now use a per-voxel F0?
2. **`fs = 1.8`** in `butter_highpass.py`: is that your measured volume rate, and did any of your flies run at a different rate?
3. **`individual_clusters` units**: `units = (seconds*1000)//10` gives 200 and 50, but timestamps are in ms. Did you intend 2 s and 0.5 s (so it's a bug that affects the Fig 4 RF inputs), or 200 ms and 50 ms?
4. **Which event pickle and cluster files back each FINAL figure?** The FINAL notebooks mix `fixed_best_final`, `fixed_10flies_final`, `best_5sec` and `new_*`. Is `supercluster_labels_total_500.npy` the fit from `behave_dict_total_10flies.pkl`?
5. **`tf_to_STA` scratch cleanup**: is it safe? It deletes ch-2 `filter_needs`/`ts_rel` files during the ch-1 pass, and it crashes when `event` is `None`. Has a two-channel run gone through end-to-end since `415d8cd`?
6. **`make_supervoxels.py`** on `dff` doesn't parse (TabError). Is per-fly supervoxelling dead, with `HOWTO_create_supervox_mask` replacing it?
7. **Sideslip (`dRotLabX`)**: why deg/s rather than mm/s like `dRotLabY`? What are you using it for?
8. **Red-channel regression**: why fit on STA bins rather than on the raw time series? Did you check that it doesn't remove real signal during strong locomotion?
9. **`get_ind_vox` output** has no channel or event in its name, so with both channels looped only ch 1 is written. Do you rely on that file now (Fig 3 uses `individual_fly_superclusters_2bin.pkl`)?
10. **Inter-loom interval and photodiode thresholds**: what is the loom ISI? Is the 0.9 s epoch-gap / 150-event heuristic written down anywhere, so it can be adapted for OMR stimulus timing?
11. **Merging**: are you planning to merge `dff` into `main`? That decides whether I should rebase my OMR changes onto your orchestrator refactor (`event_times_path`, `ch_nums`, `bigmem`) or cherry-pick.
