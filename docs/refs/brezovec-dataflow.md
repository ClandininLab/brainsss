# brezovec-dataflow / sherlock_scripts — detailed map

Repo: `../refs/brezovec-dataflow` (bellabrez/dataflow). Scope: `sherlock_scripts/` (83 entries, ≈15.3k lines including `deprecated/`), plus the `dataflow/` library functions those scripts call. The FTP and transfer code (`dataflow/` ripper/ftp/transfer, `scripts/*.bat`) is skipped, except where `fly_builder.py` fixes file names that brainsss inherits (§3.4). Surveyed 2026-10-02. See [00-index.md](00-index.md) and [brezovec-topography.md](brezovec-topography.md).

Tags: **[from code]** = read in the file or in its git history; **[inferred]** = interpretation. Line numbers refer to the current `HEAD` (`a301c8a`) unless a commit is named.

## 0. Summary

- This is the **full working set** behind the topography paper. Most topography files are trimmed copies of scripts here [from code: shared helper classes, paths and constants].
- **The real chain that produced the paper's temporal filters**:
  1. `create_behavior_X_matrix.py` writes `20210316_neural_weighted_behavior/master_X.npy`, with 4 behaviours: `Y_pos`, `Z_pos`, `Z_neg`, `W`.
  2. `20210318_neu_weighted_beh.py` **as of commit `53385e3` (2021-03-18)** reads `master_X.npy` and writes `20210316_neural_weighted_behavior/responses_{z}.npy` for z 9…39.
  3. topography's `deconvolution.py` reads those `responses_*` files as shape `(31, 2000, 4, 500)` [from code; `git show 53385e3^…62bca99^`].

  At `HEAD`, `20210318_neu_weighted_beh.py` has since been repointed to `master_X_jerk.npy` and writes to `.../jerk/` [from code]. So no file at `HEAD` reproduces the paper's responses; you need the `53385e3` version.
- The two-argument `np.sqrt` bug (§5) sits in **20 files**. In the X matrix it reaches only the `W` (walking) behaviour; in the GLMs it reaches the `walking` regressor [from code].
- brainsss-dff absorbed the **preprocessing and infrastructure** layer: fly building, QC, moco, z-score, mean brains, alignment, correlation and supervoxels. It did **not** absorb the behaviour-filter, GLM, bootstrap, PCA/ICA/UMAP or meanbrain-building layer (§4) [from code].

## 1. Behaviour pipeline

### 1.1 Loading FicTrac

- **`bbb.load_fictrac(dir)`** [from code: `bigbadbrain/fictrac.py:11`]:
  - parses the FicTrac `.dat` into a 23-column DataFrame;
  - if several `.dat` files exist, it takes the **last** one in `listdir` order;
  - raises if `max(speed) > 10`.
  - Its body is identical to brainsss's `load_fictrac` (see topography doc §3).
- **Columns used:** `dRotLabY` → **Y** (forward) and `dRotLabZ` → **Z** (yaw rotation), in **raw FicTrac units (rad per camera frame)**. `correlation.py` also smooths `dRotLabX` but never uses it [from code].
- **Timebase** [from code]:
  - the camera clock is rebuilt as `np.arange(0, expt_len, 1000/fps)` ms, with `fps = 50` and `expt_len = 1000*30*60` (30 min) hard-coded everywhere;
  - no sync pulse is used, so camera frame 0 is assumed to coincide with imaging t = 0.
- **Smoothing:** `scipy.signal.savgol_filter(trace, 25, 3)` (25 frames = 0.5 s at 50 fps), then `interp1d(..., bounds_error=False)`, then `nan_to_num`. Anything outside 0–30 min therefore becomes **0** [from code].
- **Neural timestamps:** `bbb.load_timestamps(func_0/imaging)` returns `[t, z]` in ms from the Bruker XML (identical to brainsss). Behaviour is sampled at `timestamps[:, z]`. Which `z` is used differs by script, see 1.3 [from code].

### 1.2 Copy-pasted `Fictrac` helper variants

Each analysis script defines its own `Fictrac` class inside `main` [from code; variants confirmed with `diff -w`].

| Variant | Files | `interp_fictrac` produces | Normalisation | z used |
|---|---|---|---|---|
| **X-matrix** (`interp_fictrac()` + `make_walking_vector()`) | `create_behavior_X_matrix*.py` (5 files) | `Y`, `Z` = smoothed 50 Hz traces; `Yi`, `Zi` = interp objects; `W`, `Wi` = walking 0/1 (nearest interp) | `W` threshold applied to Y/std(Y), Z/std(Z); `Y`/`Z` stay raw | any: shifts are applied later, at `timestamps[:,z]+shift` |
| **FicA** (`interp_fictrac(z)`) | `final_9_correlation.py`, `20210322_final_9_correlation.py`, `final_9_idv_correlation.py`, `20210420_voxelres_correlation.py`, `bootstrap_map.py`, `bout_triggered.py`, `neu_weighted_beh.py`, `neu_weighted_beh_single.py` | `Y`, `Z`, `*_pos`, `*_neg`, `Yh`/`Zh` (10 ms grid), `Ya`/`Za` (accel), `Ya_pos`…, `YZ`, `YZh` | `Yh`, `Zh` ÷ std; the rest raw (`#/np.std` commented out). `bootstrap_map` later divides by the **pooled 10-fly** std | template/superslice `z` |
| **FicB** (`interp_fictrac()`) | `instantaneous_glm_unique{,_single,_state_subtraction,_reconstructed,_single_reconstructed}.py` | per-z lists for all 49 z: `Y`, `Z` (÷ per-fly per-z std), `*_pos`, `*_neg`, `walking` | ÷ std | each fly's **original z** (median of `warp/20201220_warped_z_depth.nii` over the supervoxel) |
| **FicC** (`interp_fictrac(shift)`) | `shaul_temporal_glm{,_singles}.py` | FicB plus `Y_s`, `Z_s`, `*_pos_s`, `*_neg_s`, `walking_s` at `timestamps+shift` | ÷ std | original z |
| **standalone `interp_fictrac(...)`** | `correlation.py` (`timestamps[:,25]`), `correlation_z_correction.py` (`timestamps[:,z]`) | one behaviour string | raw | slice 25 for all z / own z |

### 1.3 Behaviour label dictionary (every label constructed)

Y and Z below are the savgol-smoothed, interpolated traces from 1.1. All entries are [from code].

| Label | Definition | Where |
|---|---|---|
| `Y` | smoothed `dRotLabY` at neural timestamps. Raw in FicA, X-matrix and correlation; ÷ std(Y) per fly per z in FicB/FicC | all |
| `Z` | smoothed `dRotLabZ`, same rules as `Y` | all |
| `Y_pos`, `Z_pos` | `clip(x, 0, None)` | FicA/B/C, X-matrix, `correlation_z_correction` |
| `Y_neg`, `Z_neg` | `clip(x, None, 0) * -1` (≥ 0) in FicA/B/C and X-matrix. **Not negated (≤ 0)** in `correlation.py` and `correlation_z_correction.py` | see column |
| `Z_abs` | `abs(dz)` | `correlation.py`, `correlation_z_correction.py` |
| `Yh`, `Zh` | trace on a 10 ms grid (`arange(0, 1800000, 10)`) ÷ its std | FicA |
| `Ya`, `Za` | `savgol(diff(10 ms trace), 25, 3)`, append 0, interpolate to `timestamps[:,z]`, set the last sample to 0. Raw units per 10 ms | FicA |
| `Ya_pos/neg`, `Za_pos/neg` | clip of `Ya`/`Za`; `_neg` is ×−1 | FicA |
| `YZ`, `YZh` | `np.sqrt(Y**2, Z**2)`, which **evaluates to \|Y\|** (§5). Computed but effectively unused | FicA |
| `W` | 1 where `np.sqrt((Y/std Y)**2, (Z/std Z)**2) > .2` on the 50 Hz trace, i.e. **\|Y\|/std(Y) > 0.2**; interpolated with `kind='nearest'` | X-matrix `make_walking_vector` |
| `walking` | 1 where `np.sqrt(Y[z]**2, Z[z]**2) > .2` with Y, Z already ÷ std, i.e. **\|Y_std\| > 0.2**. Length 3384 | FicB |
| `walking_s` | the same on the shifted traces | FicC |
| X-matrix suffixes `*_plus` / `*_minus` | after velocity clipping: `diff` along the **neural time axis** (one volume ≈ 0.53 s [inferred]), append 0, then clip ≥0 / (≤0)×−1 | `create_behavior_X_matrix_acceleration.py` |
| X-matrix suffixes `*_up` / `*_down` | a second `diff` (jerk), then clip | same file |
| bootstrap `forward` | `(Y>2) & (\|Z\|<1) & (Y<12)`, in pooled-std units | `bootstrap_map.get_behavior_times` |
| bootstrap `rotation_pos` | `(Z>0) & (Z<12) & (Y>0) & (Y<12)` | same |
| bootstrap `rotation_neg` | `(Z<-0) & (Z>-12) & (Y>0) & (Y<12)` | same |
| bootstrap `stop` / `moving` | `Y**2 + Z**2 < 0.2**2` / not stop. Written correctly, without the sqrt bug | same |
| bout start / stop | on `Yh`: up-state once `Yh > std(Yh)/4` (= 0.25) for 100 consecutive 10 ms samples (1 s); down-state after 100 samples ≤ threshold. A start counts only if mean `\|Yh\|` over the preceding 1 s is < .2 | `bout_triggered.find_bouts` |
| GLM targets (`glm.py`) | `Y/std` and `\|Z/std\|` from `bbb.smooth_and_interp_fictrac(..., resolution=100, smoothing=51)` | `glm.py` |

**Turn direction:** topography's `find_temporal_break_point.py` documents the X-matrix behaviour order as `0: forward, 1: left_turn, 2: right_turn, 3: walking`. Against `behaviors = ['Y_pos','Z_pos','Z_neg','W']`, that makes **`Z_pos` = left turn** and **`Z_neg` = right turn** under that rig's FicTrac configuration [from code by cross-reference; rig-specific, see §6].

### 1.4 Thresholds and numeric constants (behaviour side)

| Constant | Value | Where |
|---|---|---|
| camera fps | 50 | everywhere |
| experiment length | `1000*30*60` ms | everywhere |
| savgol window/order | 25 / 3. `glm.py` uses `smoothing=51` | everywhere |
| high-res grid | 10 ms | FicA, `bout_triggered` |
| walking threshold | `.2`, on \|Y\|/std (bugged; meant √(Y²+Z²)) | X-matrix, FicB, FicC |
| X-matrix lag window | `range(-5000, 5000, 20)` ms → 500 lags, centre index 250 | all `create_behavior_X_matrix*` |
| reviewer threshold `STD_BEH` | `{'Y': 0.00809, 'Z_pos': 0.0118, 'Z_neg': 0.0152}`, raw rad/frame, comment "actually 0.75 std". Applied as `X[block] < thr → 0` | `20231205_neu_weighted_beh_threshold.py:74-77` |
| bout threshold | `std(Yh)/4`; alive/dead time 1000 ms; pre-bout quiet < .2 | `bout_triggered.py:133-176` |
| bout window | ±3000 ms; keep only `len(ys)==10` (≈5 volumes each side) | `bout_triggered.py:179-203` |
| bootstrap thresholds | forward 2–12, \|Z\|<1; rotation 0–12 with Y 0–12; stop r 0.2 (pooled-std units) | `bootstrap_map.py:161-205` |
| temporal GLM shifts | `[-450, -300, -150, 150, 300, 450]` ms | `shaul_temporal_glm*.py` |
| GLM regularisation | `RidgeCV()` defaults (alphas 0.1, 1, 10); score = in-sample `sqrt(R²)` | `instantaneous_glm_unique*` |
| 3D hist lags | `arange(-200, 200, 1)` rows (20 ms each); bins 25×25 over x −2…6, y −4…4; min count 9; σ = 3 | `20230123_3d_hists_accel.py` |

### 1.5 Building the behaviour X matrix (`create_behavior_X_matrix*.py`)

Common core [from code: `create_behavior_X_matrix.py:104-168`]:

1. For each of 9 flies, run `interp_fictrac()` and `make_walking_vector()`.
2. `build_timeshifted_behavior_matrix(time_shifts, fly, z, behavior)`:
   - picks the interp object by **substring** (`'Z'`→`Zi`, `'Y'`→`Yi`, `'W'`→`Wi`, last match wins);
   - for each shift, evaluates at `timestamps[:,z] + shift`, applies `nan_to_num`, then the `pos`/`neg` clip.
3. `build_X` stacks `(behaviours × 500 lags, 3384)` per fly into `(9, n_beh·500, 3384)`.
4. The loop over all 49 z gives `master_X` with shape **`(49, 9, n_beh·500, 3384)`**. At 4 behaviours, float64, that is ≈ 23.9 GB [inferred from shape].

| File | `behaviors` | Differences | Output (`.../20210316_neural_weighted_behavior/`) |
|---|---|---|---|
| `create_behavior_X_matrix.py` | `['Y_pos','Z_pos','Z_neg','W']` | base. **Paper version** | `master_X.npy` |
| `20221202_create_behavior_X_matrix_noYclip.py` | `['Y','Z_pos','Z_neg','W']` | Y unclipped (signed) | `20221202_master_X_noYclip.npy` |
| `create_behavior_X_matrix_acceleration.py` | `['Y_pos_plus_up','Y_pos_plus_down','Y_pos_minus_up','Y_pos_minus_down','Z_pos_plus_up','Z_pos_plus_down']` | velocity clip → diff → accel clip → **append** → diff → jerk clip → **append again**. Two appends per shift give 1000 rows per behaviour, with acceleration and jerk **interleaved** (bug) | `master_X_jerk.npy` |
| `20230117_create_behavior_X_matrix_acceleration.py` | `['Y','Z']` | acceleration only (one diff), no clipping; `W` branch removed | `20230117_master_X_accel_noclip.npy` |
| `20231204_create_behavior_X_matrix_threshold_reviewer.py` | `['Y','Z_pos','Z_neg','W']` | clips **everything** to ≥ 0 after pos/neg (so `Y` becomes `Y_pos`); adds a pooled-std block. **Does not parse**: tab/space `SyntaxError` at line 168, missing comma at line 167, `STD_BEH` and `behavior_super` undefined | `20231204_master_X_threshold_reviewer.npy` |

The X-matrix loaders are inconsistent [from code]:
- `neu_weighted_beh.py` reads `20201221_neural_weighted_behavior/master_X_corrected.npy`, and `20220921_neu_weighted_beh_clipped.py` reads `20220921_.../master_X_clipped.npy`.
- **No script in this repo writes either file.**

### 1.6 Neural-weighted behaviour filters (`neu_weighted_beh*.py`)

Core computation [from code: `neu_weighted_beh.py:162-200`]. For one superslice `z`:

1. Load `superslice_{z}.nii` with shape `(256, 128, 3384, n_flies)`, and the shared `cluster_labels.npy[z]` (2000 supervoxels).
2. For each supervoxel, average each fly's voxels to get `(3384,)`, then concatenate the flies: `Y` is `(n_flies·3384,)`.
3. For each fly, look up `original_z = int(median(z_correction[:,:,z][cluster voxels]))` and take `X[original_z, fly]`, of shape `(n_beh·500, 3384)`.
4. Stack the flies, then `moveaxis` + reshape to `(n_beh·500, n_flies·3384)`.
5. `response = X_cluster @ Y`, an **un-normalised sum over time** of behaviour(t + lag) × neural(t). It is a reverse-correlation / cross-covariance filter. It is not regression and not divided by N [inferred].
6. Output `responses_{z}.npy` has shape `(2000, n_beh·500)`.

The neural signal is the superslice content: z-scored, Gaussian high-passed, warped data (`brain_zscored_green_high_pass_masked_warped` lineage) [inferred from the superslice and correlation inputs].

| File | Flies | X source | z | Extras | Output |
|---|---|---|---|---|---|
| `neu_weighted_beh.py` | **10** incl. fly_095, no delete (reshape 33840) | `20201221/.../master_X_corrected.npy` | `args['z']` | defines FicA but never uses it | `20201221_.../corrected/responses_{z}` |
| `neu_weighted_beh_single.py` | 10 | `20201221/.../master_X.npy` | arg | per fly, no pooling | `20210210_neural_weighted_behavior_singles/{fly}/responses_{z}` |
| `20210318_neu_weighted_beh.py` @ **`53385e3`** | 9, delete idx 3 (30456) | `20210316/master_X.npy` | loop 9…39 | **paper version** | `20210316_.../responses_{z}` |
| `20210318_neu_weighted_beh.py` @ HEAD | 9 | `20210316/master_X_jerk.npy` | 9…39 | jerk X has 6 behaviours × 1000 rows (see 1.5) | `20210316_.../jerk/responses_{z}` |
| `20210419_neu_weighted_beh_exclude_fly_087.py` | 8 (also drops fly_087: X axis-1 index 0, then brain index 3 then 0) | `master_X.npy` | 9…39 | the comment on the second delete mislabels fly_087 as fly_095 | `20210419_..._exclude_fly_087/responses_{z}` |
| `20220921_neu_weighted_beh_clipped.py` | 9 | `20220921/master_X_clipped.npy` (no producer here) | 9…39 | — | `20220921_neural_weighted_behavior/responses_{z}` |
| `20221120_neu_weighted_beh_indiv_flies.py` | 9 | `master_X.npy` | 9…39 | per fly | `20220921_.../indiv_flies/responses_fly{fly}_{z}` (filename renders as `flyfly_087`) |
| `20231205_neu_weighted_beh_threshold.py` | 9 | `master_X.npy` | 9…39 | zeroes X below `STD_BEH` in blocks 0–499, 500–999, 1000–1499; the `W` block 1500–1999 is untouched. Thresholds sized for signed `Y` are applied to the `Y_pos` block | `20210316_.../threshold/responses_{z}` |

`loop.py:331-343` currently submits only `20231205_neu_weighted_beh_threshold.py` (z = 19, 48 h, `mem=23`) [from code].

Downstream consumers (§2.2):
- `cluster_filters.py` / `20210322_cluster_filters.py`: FFT notch, then Ward clustering of the filters, which is the "superclusters".
- `20230123_3d_hists_accel.py`.
- topography's `deconvolution.py` and `find_temporal_break_point.py`.

## 2. Function table

Exact duplicates are grouped. Unless marked otherwise, every `main(args)` worker is invoked as `python3 <script> '<json>'` and logs via `flow.Printlog`. Rows from agent reads were spot-checked. All rows are [from code].

### 2.1 Behaviour X matrix and neural-weighted filters

| Function | File(s) | Inputs | Outputs | Hardcoded constants |
|---|---|---|---|---|
| `Fly.__init__/load_timestamps/load_fictrac/load_brain_slice/load_anatomy/load_z_depth_correction/get_cluster_averages/get_cluster_id` | all `create_behavior_X_matrix*`, all `neu_weighted_beh*` (+ FlyV1/V2 in §2.2) | fly_name, fly_idx; labels | timestamps, Fictrac, brain slice, z-map, `cluster_signals (2000,3384)` | `DS/{fly}/func_0`; `warp/anat-to-meanbrain.nii`; `warp/20201220_warped_z_depth.nii`; reshape `(-1, 3384)`; `x*128+y` |
| `Fictrac.make_interp_object` | X-matrix (returns `(smoothed, interp)`); FicA/B/C (returns interp only) | behaviour column | interp1d | fps 50, 30 min, savgol(25,3) |
| `Fictrac.pull_from_interp_object` | X-matrix, FicA/B/C | interp, times | values, NaN→0 | — |
| `Fictrac.interp_fictrac()` | X-matrix | — | `Y`, `Z`, `Yi`, `Zi` | `dRotLabY`, `dRotLabZ` |
| `Fictrac.make_walking_vector` | 5 `create_behavior_X_matrix*` files (:92) | — | `W`, `Wi` | **sqrt bug**; `.2`; fps 50; 30 min; `kind='nearest'` |
| `Fictrac.interp_fictrac(z)` (FicA) | `neu_weighted_beh.py`, `neu_weighted_beh_single.py` (+ §2.2) | z | see 1.2 | 10 ms grid; **sqrt bug** :123-124 |
| `build_timeshifted_behavior_matrix` | all `create_behavior_X_matrix*` | shifts, fly, z, behaviour | (shifts, list of lagged traces) | substring dispatch; acceleration variants add `diff`/`plus`/`minus`/`up`/`down` |
| `build_X` | all `create_behavior_X_matrix*` | shifts, behaviours, z | `(9, n·500[·2], 3384)` | reshape `(-1, 3384)` |
| `main` | `create_behavior_X_matrix*` | `logfile` | `master_X*.npy` | FINAL9, `20190101_walking_dataset`, shifts −5000:5000:20, 49 z |
| `main` | `neu_weighted_beh*` | `logfile` (+ `z` in the undated ones) | `responses_*.npy` | see the 1.6 table; `n_clusters = 2000`; `cluster_labels.npy`; `superslice_{z}.nii` |

### 2.2 Correlation, GLM, bouts, bootstrap, clustering, dimensionality reduction

| Function | File(s) | Inputs | Outputs | Hardcoded constants |
|---|---|---|---|---|
| `main` + `interp_fictrac(fictrac,fps,res,len,ts,behavior)` | `correlation.py` | `directory`, `behavior` | `{dir}/corr/20201020_corr_{beh}.nii` (256,128,49) | input `brain_zscored_green_high_pass_masked.nii`; slice **25** for every z; `Y`/`Z_abs`/`Z_pos`/`Z_neg` |
| same, with `z` | `correlation_z_correction.py` | same | `.../20201104_corr_{beh}.nii` | per-z timestamps; adds `Y_pos`/`Y_neg` (not negated) |
| `main` (FicA, FlyV1) | `final_9_correlation.py`, `20210322_final_9_correlation.py` | `save_directory`, `z`, `behavior_to_corr` | `rvalues_{b}_z{z}.npy`, `pvalues_…` | FINAL9; delete idx 3; 2000 clusters; labels `final_9_cluster_labels_2000.npy` / `cluster_labels.npy` |
| `main` | `final_9_idv_correlation.py` | same | `{save}/{fly}/rvalues_…` | per fly |
| `main` | `20210420_voxelres_correlation.py` | same | r/p over 256×128 voxels | no clusters |
| `create_clusters`, `main` | `final_9_depth_correct_clustering.py` | — | `20210130_superv_depth_correction/labels.pickle` | `n = int(1000*depth_correction[z])`; Ward; `grid_to_graph(256,128)`; reshape `(-1, 3384*9)` |
| `main` | `final_9_full_volume_clustering.py` | — | `20210128_superv_simul_full_vol/cluster_labels.npy` | time ÷12; `grid_to_graph(256,128,49)`; 30000 clusters |
| `main` | `build_final_9_pooled_brain.py` | — | `20210115_super_brain.npy` `(2000,49,3384,9)` | — |
| `main` | `build_final_9_pooled_brain_for_pca.py` | — | `super_brain.pickle` {z: (n,3384,9)} | — |
| `main` (FicB, FlyV2) | `instantaneous_glm_unique.py`, `_single.py` | — | `20210208_inst_uniq_glm/[fly/]Z{z}.pickle` | `RidgeCV()`; in-sample `sqrt(R²)`; models ALL, singles, leave-one-out (`*_unique` = score **without** that regressor) |
| `main` | `instantaneous_glm_unique_state_subtraction.py` | — | `20210309_inst_uniq_glm_state_sub/Z{z}.pickle` | fits `walking`, subtracts its prediction, fits the rest; `scores_walking_unique` empty |
| `main` | `instantaneous_glm_unique_reconstructed.py`, `_single_reconstructed.py` | `num_pcs` | `20210216_inst_uniq_glm_recon/...` | z 9…39; input hardcoded `..._100_fromindivpcs.npy` regardless of `num_pcs` |
| `main` (FicC) | `shaul_temporal_glm.py`, `_singles.py` | — | `20210131_temporal_glm/[fly/]Z{z}_shift{s}.pickle` | **10 flies** incl. fly_095, no delete; shifts ±150/300/450 ms |
| `main` | `glm.py` | `directory`, `pca_subfolder`, `glm_date` | `glm/{date}_{Y\|Z}.nii`, score txt | `LassoCV()`; 1000 PCs (hardcoded slice); res 100; smoothing 51 |
| `create_clusters`, `get_behavior_times`, `main` | `bootstrap_map.py` | `z`, `bootstrap_type`, `values_a/b`, `comparison` | `{type}_{a}_{b}_values_z{z}.npy`, `…_sigs_…` | **10 flies**; 6000 Ward clusters (reshape 33840); 1000 reps; thresholds in 1.4; "sigs" = count of reps < 0, not a p-value |
| `find_bouts`, `bout_triggered`, `main` | `bout_triggered.py` | `z` | `20210111_bout_triggered/{xss,yss,behavior}_{z}.npy` | 1.4 constants; `sum_bouts[1:-1]` drops the first and last bouts (count mismatch) |
| `main` | `cluster_filters.py`, `20210322_cluster_filters.py` | — | nothing saved (Ward cache only) | reshape `(49,2000,3,500)` / `(31,2000,4,500)`; FFT notch zeroes bins 15–22 and 475–484 (asymmetric); 75th percentile. 20210322 is missing its `fft` import |
| `main` | `pca.py` | `file`, `save_subfolder` | `pca/scores_(spatial).npy`, `loadings_(temporal).npy` | full `PCA()` |
| `main` | `pca_of_final_9.py` | `fly_idx` | `20210214_eigen_{values,vectors}_ztrim_fly{i}.npy` | `np.linalg.eig` (unsorted, not `eigh`); z 9…39 |
| `fastIca`, `main` | `20221107_ICA.py` | — | `20221107_ICA_ztrim_fly.npy` | tanh; thresh 1e-4; 200 iterations; no whitening |
| `main` | `umap_.py` | — | PNG (crashes: `plt` not imported) | `UMAP(n_neighbors=60, min_dist=0)` |
| `bin_2D`, `bin_2D_plot`, `main` | `20230123_3d_hists_accel.py` | SC signals, noYclip + accel X | `20230117_3d_hists_accel_{X,Y}.npy` | 501 superclusters, pairs (c, c+250); see 1.4 |
| `main` | `image_cross_corr.py` | — | — | **broken**: `file` and `meanbrain` undefined. Despite the name, it is a mean-brain/mask routine |
| `main` | `20220726_connectome_dice.py` | unique-GLM map, hemibrain synapses | `all_neuron_dice.npy` | bbox x46–147, y5–89, z5–34; threshold `.01`; ×.38 µm; bins 2.6/2.6/5 µm |
| `main` | `20220805_connectome_synpervox.py` | synapses | `synpervox.npy` `(24691,101,84,29)` uint16 | hardcoded 24691 neurons |

### 2.3 Meanbrain / template building and alignment

"MB-family" means the 10 dated `*meanbrain_creation*.py` files plus `20240912_FDA_replication.py`. They share functions and differ mainly in constants. All save with `np.eye(4)` affines, so voxel spacing is not stored on disk [from code].

| Function | File(s) | Inputs | Outputs | Hardcoded constants |
|---|---|---|---|---|
| `main` | MB-family | — | `affine_0/1`, `syn_0…syn_6` dirs + `.nii` (+ `_sharp`) | `main_dir`, `resolution` and seed per file: 20210125 `(0.65,0.65,1)`; 20210218 `(0.65,0.65,1)`, seed `anat_143.nii` (→ `anat_143.nii.nii`, bug); diego `(0.58,0.58,1)`; 20220421 `(2,2,2)`; subvol `(1.3,1.3,1)`; DSX `(0.49,0.49,1)`; Aragon 0906 `(0.49,0.49,2)`; FDA_replication / Aragon 0913/0918 `(.6,.6,1)`, seed `seed_fly91_clean_20200803` |
| `alignment_iteration` | MB-family | main_dir, moving_dir, name_out, name_fixed, transform, res, sharpen_output | one averaged round | mirror `[True, False]` (diego `[False]`) |
| `align_anat` | MB-family | fixed, moving, out, transform, res, mirror | `<moving>[_m]-to-<fixed>.nii` | ANTs defaults; subvol SyN uses `flow_sigma=5, total_sigma=5`; mirror = `[::-1,:,:]` |
| `avg_brains` | MB-family, `avg_brains.py` | dir | mean `.nii` | **hardcoded dims**: `(1024,512,256)`, `(250,250,100)`, `(1485,772,273)`, `(333,166,121)`, `(222,82,71)`; DSX/2024 take the shape from the registration |
| `clean_anat` | MB-family, `clean_anat.py` | anat | `*_clean.nii` / `anat_red_clean.nii` | Gaussian σ 10; triangle/2; largest blob; `quantile_transform(500)` (subvol: quantile only) |
| `sharpen_anat` | MB-family, `sharpen_anat.py` | clean anat | `*_sharp.nii` | rescale .3–.7; `unsharp_mask(r=3, amount=7)`; bg < .31; 500 quantiles |
| `load_numpy_brain` | MB-family | path | array | `.nii`/`.nrrd` (+ `.npy` in subvol); other extensions, including `.nii.gz`, raise `UnboundLocalError` |
| `main` | `align_anat.py` | fixed/moving path+fly+res, flips, `low_res`, `very_low_res`, `iso_2um_*`, `grad_step`, `flow_sigma`, `total_sigma`, `syn_sampling`, mimic | warped `.nii`, `*_fwdtransforms[_lowres]/`, `*_invtransforms/` | low res `(256,128,49)`; very low `(128,64,49)`; iso `(2,2,2)` |
| `main` | `apply_transforms.py` | fixed/moving | `<moving>-applied-<fixed>.nii` | `func-to-anat_fwdtransforms`, `anat-to-meanbrain_fwdtransforms`; `final_2um_iso` |
| `main` | `apply_transforms_to_raw_data.py` | warp_directory, fixed/moving | `functional_channel_2_moco_zscore_highpass_warped.nii` | `*_lowres` transforms; `(256,128,49)`; `imagetype=3` |
| `main` | `20230117_warp_all_raw_data_to_FDA.py` | — | `..._masked_warped_to_FDA.nii` per fly | 10 flies; Luke mean `20210310_luke_exp_thresh.nii` (0.65,0.65,1), z-flip → JRC2018 0.38 iso resampled to 2 µm; manual spacing `(2.6076, 2.6154, 5.3125, 1)` |
| module | `build_meanbrain.py` | — | `20200803_meanbrain/`, `20200811_meanbrain/syn_0*` | 16 flies; `flow.sbatch` align 4/4, 1/2, 8/4; avg 1/4. **Out of sync with `align_anat.py` keys** (would `KeyError`) |
| `main` | `make_mean_anat.py`, `make_mean_brain.py` | dir (+ `dirtype`) | `*_mean.nii`; prints `n_timepoints` | casts to `uint16` |
| `main` | `smooth.py` | file | `brain_zscored_red_high_pass.nii` (hardcoded "red") | `gaussian_filter1d(σ=200, truncate=1)` + mean |
| `main` | `mask.py` | file | `mask.nii`, `brain_zscored_red_high_pass_masked.nii` | threshold `0.00475597*tri + 0.01330587*yen − 0.04362137*iso + 0.1478071*li + 36.46`; erode/dilate 5×5×1; edges zeroed |
| `sec_to_hms`, `stderr_redirected` | `align_anat`, `apply_transforms*`, 20230117, MB-family | — | — | identical to topography/brainsss |

### 2.4 Infrastructure: orchestration, fly building, moco, QC

| Function | File(s) | Inputs | Outputs | Hardcoded constants |
|---|---|---|---|---|
| `sbatch` | `dataflow/utils.py:149` | jobname, script, modules, args, logfile, `time=1`, `mem=1`, `dep`, `nice`, `nodes=2` | job id | see §3.1. **`mem` → `--cpus-per-task`**; `--partition=trc`; `-o ./com/%j.out` |
| `get_job_status` / `wait_for_job` | `utils.py:171/213` | job id | sacct state / `com/<id>.out` text | poll every 5 s; terminal states COMPLETED, CANCELLED, TIMEOUT, FAILED, OUT_OF_MEMORY; `7.77 GB` per core |
| `moco_progress`, `print_progress_table`, `progress_bar` | `utils.py:230-330` | job dict | log table | poll every 5 min; only the **last** partial job is checked |
| `Printlog.print_to_log` | `utils.py:136` | message | flock append | — |
| `Logger_stderr_sherlock` | `utils.py:119` | logfile | stderr tee (no lock) | — |
| `send_email` | `utils.py:30` | — | email | **plaintext SMTP credentials committed in `utils.py:44`** (values not reproduced here) |
| `sort_nicely` / `get_resolution` | `utils.py:339-351` | list / xml | — | `micronsPerPixel` |
| `align_volume`, `motion_correction`, `save_motCorr_brain` | `dataflow/moco.py` | master, slave | `motcorr_{red,green}{suffix}.nii`, params `.npy` | SyN |
| module | `main.py` | — | full preprocessing of one flagged import | no CLI flags; fixed sequence (§3.2) |
| module | `loop.py` | — | ad-hoc analysis submits | `flies=['fly_143']`; steps toggled by commenting |
| `main`, `copy_fly`, `copy_bruker_data`, `copy_visual`, `copy_fictrac`, `create_imaging_json`, `add_date_to_fly`, `get_new_fly_number`, `add_fly_to_xlsx`, … | `fly_builder.py` | flagged import dir | `fly_NNN/` tree (§3.4); prints `func:`/`anat:` | 3-min matching window for fictrac and visual; `.dat` > 30 MB; `master_2P.xlsx` |
| `main`, `load_partial_brain` | `moco_partial.py` | dir, dirtype, start, stop | `moco/motcorr_{red,green}_<start>.nii`, params | ch1 = red = master; ch2 = green = slave |
| `main`, `save_motion_figure` | `moco_stitcher.py` | moco dir | `stitched_brain_{red,green}.nii`, `motcorr_params_stitched.npy`, `motion_correction.png` | casts to `uint16`; deletes partials (and could delete its own output on rerun) |
| `main` | `zscore.py` | dir, `smooth`, `colors` | `brain_zscored_{color}[_smooth].nii` | σ 200; `uint16` math underflows. `main.py` omits `smooth`/`colors` → `KeyError` |
| `main` | `check_for_flag.py` | imports path | prints the next flagged folder | never removes the flag |
| `main` | `fictrac_qc.py`, `bleaching_qc.py`, `make_mean_brain.py` | dir | PNGs / `*_mean.nii` | fictrac_qc: 30 min, 50 fps, 100 bins |
| — | `deprecated/*` (≈37 files) | — | — | old positional-argument chain (`motcorr_splitter` → `motcorr_partial.sh` → `motcorr_stitcher` → `zscore.sh` → bleaching/pca/quick_glm). Several wrappers point at scripts that no longer exist. `result.json` shows example `visual.json`/`fly.json` schemas |

## 3. How Slurm jobs are structured

### 3.1 Submission (`dataflow.utils.sbatch`) [from code: `utils.py:149-169`]

```
sbatch -J {jobname} -o ./com/%j.out -e {logfile} -t {time}:00:00 --nice={nice} --partition=trc \
       [-w sh02-07n34 ] --open-mode=append --cpus-per-task={mem} --wrap='ml {modules}; python3 {script} {json.dumps(json.dumps(args))}' \
       [--dependency=afterok:{ids} --kill-on-invalid-dep=yes]
```

- **`mem` is CPU count.** There is no `--mem`, so memory comes from CPUs × the per-core default. `get_job_status` assumes 7.77 GB per core. A call like `mem=23` asks for 23 cores (≈179 GB) [from code + inferred].
- `time` is in whole hours. `nice=True` becomes `--nice=1000000`, while `nice=False` would emit `--nice=False`. `nodes == 1` pins the job to node `sh02-07n34`; any other value does nothing.
- Arguments are double-JSON-encoded into one argv string; the worker runs `main(json.loads(sys.argv[1]))`.
- **No array jobs anywhere.** Fan-out is a Python `for` loop of individual `sbatch` calls: moco chunks, and per-z jobs in `loop.py`. The only Slurm-native dependency is moco stitcher `afterok` on its partials (`main.py:219`).

### 3.2 Orchestration

- `main.sh`/`loop.sh` are single-core `#SBATCH --partition=trc --time=3-00:00:00 --cpus-per-task=1 --output=./logs/mainlog.out --open-mode=append --mail-type=ALL` wrappers. They run `ml python/3.6.1; python3 -u .../main.py|loop.py`. In `loop.sh:14-15`, `#SBATCH` lines appear after commands and are ignored [from code].
- `main.py` always runs one fixed sequence, blocking with `wait_for_job` after each stage: check_for_flag (1 h / 1 cpu) → fly_builder (1/1) → fictrac_qc (1/1) → bleaching_qc (1/1) → make_mean_brain (1/1) → moco_partial ×N (func 4 h / 4 cpus per 100 volumes; anat 6/7 per 10 volumes) → moco_stitcher (2/12, afterok) → zscore (8/18) [from code].
- `loop.py` toggles analysis steps by commenting code. The resource sets used there, as hours/"mem" (= cpus):

  | Job | Hours/cpus |
  |---|---|
  | neuwebeh | 48/23, 12/22 |
  | glm | 24/8 |
  | cluster | 24/23 |
  | umap | 96/23 |
  | ICA | 24/32 |
  | corr | 2/3 |
  | bootstrap | 2/6 |
  | align | 8/4 – 4/16 |
  | apply transforms | 2/22 |

  Per-z analyses are submitted one job per z in a loop [from code].
- Meanbrain scripts run as one long job: `meanbrain_creation.sh` is 3 days / 22 cpus, `20210125_meanbrain_creation.sh` is 1 day / 8 cpus. `20210125_meanbrain_creation.sh` actually launches `20220627_meanbrain_creation_subvol.py` [from code].

### 3.3 Logging and return values [from code]

- **Log file:** each orchestrator creates `./logs/%Y%m%d-%H%M%S.txt`. Workers append through `flow.Printlog` (flock), and Slurm `-e {logfile}` routes every worker's stderr into the same file. The orchestrator's own stderr goes through `Logger_stderr_sherlock` (no lock).
- **Return values:** worker stdout goes to `./com/<jobid>.out`, and `wait_for_job` returns that text.
  - `check_for_flag` prints the folder path.
  - `fly_builder` prints `func:<path>`/`anat:<path>`.
  - `make_mean_brain` prints the timepoint count.
  - moco prints `[i]` per volume for the progress table.
- **Paths:** `com/` and `logs/` are relative to the submit directory, but `com_path` is the absolute path `/home/users/brezovec/projects/dataflow/sherlock_scripts/com`. They agree only when submitted from there.
- brainsss kept this whole design: `Printlog`, `com/<jobid>.out` as return channel, `logs/<timestamp>.txt` and `mainlog.out`. It changed the `sbatch` signature (§4).

### 3.4 File naming set by `fly_builder.py` and moco, inherited by brainsss [from code]

```
imports/build_queue/<flag>        → imports/<flag>/fly*/{fly.json, <dirs containing 'anat' or 'func'>}
dataset_path/fly_NNN/             (NNN = max+1, zfill(3); older flies unpadded e.g. fly_24)
  fly.json (+date, time)
  func_X/ expt.json
    imaging/ functional_channel_{1,2}.nii, functional.xml, scan.json, voltage_output.xml, *_mean.nii
    fictrac/ files matching the .dat datetime (YYYYMMDD_HHMMSS, ±3 min), fictrac.xml (empty)
    visual/  photodiode.csv (every .csv overwrites this name), stimulus files, visual.json
    moco/    stitched_brain_{red,green}.nii, motcorr_params_stitched.npy, motion_correction.png
  anat_X/ imaging/anatomy_channel_{1,2}.nii, anatomy.xml ; moco/ …
```

- **Channel convention:** channel 1 = red = moco master; channel 2 = green = functional. brainsss keeps `ch_num` 2 as the default processed channel. **Func/anat detection** is by substring, `anat` checked before `func`. One row per func is appended to `master_2P.xlsx`.
- brainsss-dff's `fly_builder.py` is a 215-line-diff descendant of this file. Its moco writes `moco/functional_channel_N_moco.h5` instead of `stitched_brain_*` (see CLAUDE.md filename chain).
- **Latent bug in your repo:** in your `brainsss/utils.py:96` (and brainsss-dff's), the `global_resources=True` branch of `sbatch` emits `--cpus-per-task={},` with a stray comma. Every live call in `preprocess.py` passes `global_resources=False` (line 373), so it is not hit today [from code].

## 4. What brainsss-dff absorbed or replaced

"Same" means the brainsss-dff script is a descendant of the dataflow script. Your `YDPlayground` copies of these scripts match brainsss-dff (identical diff counts against dataflow) [from code].

| dataflow script(s) | brainsss-dff | Status |
|---|---|---|
| `main.py`, `main.sh` | `preprocess.py`/`.sh` (CLI flags, settings JSON); an old port sits in `scripts/to_delete/main.py` | **Replaced** |
| `loop.py`, `loop.sh` | `postprocess.py`/`.sh` | **Replaced** (different steps) |
| `dataflow.utils.sbatch/wait_for_job/Printlog` | `brainsss/utils.py` | **Absorbed, fixed**: separate `cpus` and real `--mem`, `begin`, `bigmem`, `mail` |
| `check_for_flag.py` | `check_for_flag.py` | Same (imports swapped) |
| `fly_builder.py` | `fly_builder.py` | Absorbed (215-line diff) |
| `fictrac_qc.py` | `fictrac_qc.py` | Absorbed; **`fps` comes from args and `expt_len` from the data length** (fixes the 30-min/50 fps hardcode) |
| `bleaching_qc.py`, `make_mean_brain.py` | same names | Absorbed (`make_mean_brain` takes `files` and `meanbrain_n_frames`) |
| `moco_partial.py` + `moco_stitcher.py` (+ `dataflow/moco.py`) | `motion_correction.py` | **Replaced**: one job, h5 output, `type_of_transform` arg (default SyN), stepsize 100/5 |
| `zscore.py` | `zscore.py` | Replaced (chunked h5; 116-line diff) |
| `smooth.py` (Gaussian σ=200 HPF) | `temporal_high_pass_filter.py` (same Gaussian); `butter_highpass.py` (0.01 Hz) | Replaced |
| — | `dff.py`, `blur.py`, `background_subtraction.py` | New in brainsss: dataflow had **no ΔF/F** |
| `mask.py` | — | **Not absorbed** |
| `clean_anat.py`, `align_anat.py`, `apply_transforms.py` | same names | Absorbed (`anatomy_channel_1_moc_mean.nii` input, `_2umiso` transform dirs, `anat-to-non_myr_mean` warp) |
| `sharpen_anat.py`, `avg_brains.py`, `build_meanbrain.py`, all MB-family meanbrain/FDA builders | — | **Not absorbed.** brainsss uses existing templates under `anat_templates/` |
| `apply_transforms_to_raw_data.py`, `20230117_warp_all_raw_data_to_FDA.py` | `raw_warp.py` | Replaced |
| `correlation.py`, `correlation_z_correction.py` | `correlation.py` | **Replaced**: fps arg, data-derived length, per-z timestamps, h5 input, **`grey_only`** option (restricts to `ConstantBackground` stimulus epochs via photodiode) |
| `final_9_*clustering.py`, `build_final_9_pooled_brain*.py` | `make_supervoxels.py` (per fly, 2000/slice), `supercluster.py`, `individual_clusters.py` | Partly: same Ward + `grid_to_graph` method, but per fly rather than pooled 9-fly superslices; no z-depth map |
| `bout_triggered.py` | `build_STA.py` / `tf_to_STA.py` (event times from a pickle) | Replaced in spirit: event-triggered averages, but from supplied event times rather than FicTrac bout detection [inferred] |
| `create_behavior_X_matrix*.py`, `neu_weighted_beh*.py`, `cluster_filters.py` | — | **Not absorbed.** No `master_X`, lagged-behaviour design or reverse-correlation filters in brainsss |
| `instantaneous_glm_unique*.py`, `shaul_temporal_glm*.py`, `glm.py` | — | **Not absorbed.** No `RidgeCV`/`LassoCV` in brainsss. `regress_noise.py` is dual-channel noise regression, not behaviour GLM |
| `bootstrap_map.py`, `final_9_*correlation.py` (pooled supervoxel r/p) | — | Not absorbed |
| `pca*.py`, `20221107_ICA.py`, `umap_.py`, `20230123_3d_hists_accel.py` | — | Not absorbed |
| `2022*_connectome_*.py` | — | Not absorbed |
| `fictrac` behaviour definitions | `brainsss/fictrac.py`: `smooth_and_interp_fictrac` (savgol, unit conversion to mm/s and deg/s), `interpolate_fictrac` (Gaussian σ=3, `my_speed`, `speed_all_3` computed correctly) | Absorbed partly; **no `W`/`walking` label in brainsss** |

## 5. Every function with the two-argument `np.sqrt` bug

`np.sqrt(a, b)` writes into `b` (`out=`) and returns `sqrt(a)`. So every row below computes **|Y|** and ignores Z [from code; numpy semantics confirmed locally by Yandan, see topography doc §5 item 10]. Port these only after rewriting them as `np.sqrt(Y**2 + Z**2)`. Then re-derive the `.2` threshold, which was tuned on |Y| (bigbadbrain `20231030 - calc walking thresh for topography paper.ipynb`) [inferred].

| File:line | Function | Variable | Consumed by |
|---|---|---|---|
| `create_behavior_X_matrix.py:94` | `Fictrac.make_walking_vector` | `YZ` → `W` | **`W` block (rows 1500–1999) of `master_X.npy`**, so the paper's walking filter (index 3) |
| `20221202_create_behavior_X_matrix_noYclip.py:94` | same | `W` | `W` block of `20221202_master_X_noYclip.npy` |
| `20231204_create_behavior_X_matrix_threshold_reviewer.py:94` | same | `W` | `W` block (file does not parse) |
| `create_behavior_X_matrix_acceleration.py:94` | same | `W` | computed, **unused** (no `W` behaviour) |
| `20230117_create_behavior_X_matrix_acceleration.py:94` | same | `W` | computed, unused |
| `neu_weighted_beh.py:123-124` | `Fictrac.interp_fictrac(z)` | `YZ`, `YZh` | unused |
| `neu_weighted_beh_single.py:123-124` | same | `YZ`, `YZh` | unused |
| `final_9_correlation.py:111-112` | `Fictrac.interp_fictrac(z)` (FicA) | `YZ`, `YZh` | not in `all_behaviors`, so unused |
| `20210322_final_9_correlation.py:111-112` | same | same | unused |
| `20210420_voxelres_correlation.py:111-112` | same | same | unused |
| `final_9_idv_correlation.py:111-112` | same | same | used **only if** `behavior_to_corr == 'YZ'` (line 165) |
| `bootstrap_map.py:158-159` | same | same | unused (`get_behavior_times` computes Y²+Z² correctly) |
| `bout_triggered.py:123-124` | same | same | unused (bouts use `Yh`) |
| `instantaneous_glm_unique.py:82` | `Fictrac.interp_fictrac()` (FicB) | `walking` | full model, walking-only, ypos/zpos/zneg leave-one-out models |
| `instantaneous_glm_unique_single.py:82` | same | `walking` | same, per fly |
| `instantaneous_glm_unique_reconstructed.py:84` | same | `walking` | same, PCA-reconstructed |
| `instantaneous_glm_unique_single_reconstructed.py:84` | same | `walking` | same |
| `instantaneous_glm_unique_state_subtraction.py:82` | same | `walking` | walking model whose prediction is **subtracted from Y**, so it contaminates every other score |
| `shaul_temporal_glm.py:95, 101` | `Fictrac.interp_fictrac(shift)` (FicC) | `walking`, `walking_s` | every model |
| `shaul_temporal_glm_singles.py:95, 101` | same | same | every model |

There are 20 files; none are in `dataflow/` or `deprecated/`. Non-hits: `correlation.py`, `correlation_z_correction.py` and `final_9_*` have the **correct** form commented out, and `20221107_ICA.py` calls `sqrt` with one argument [from code].

## 6. Gotchas: locomotion assumptions that must not carry into optomotor analysis

**Dataset identity**
1. FINAL9 (`fly_087…105`), 10-fly variants including fly_095, and positional deletes are hardcoded in every analysis `main`:
   - `np.delete(..., 3)` removes fly_095;
   - `np.delete(X, 0, axis=1)` removes fly_087.

   With different flies these silently remove the wrong one. `bootstrap_map` and `shaul_*` include fly_095 while everything else excludes it [from code].
2. Superslices, `cluster_labels.npy` and `20201220_warped_z_depth.nii` are dataset-wide artefacts built from these exact flies, in this order [from code]. Labels cannot be reused for new flies [inferred].

**Timing and rig**
3. 30-minute sessions, 3384 volumes, a 50 fps camera and no sync are hardcoded. Behaviour past 30 min becomes 0, and a different length breaks the `3384` reshapes [from code]. brainsss's `fictrac_qc`/`correlation` already take `fps` from args and length from data; keep that.
4. The ±5 s lag window at 20 ms (500 lags, centre 250) and z 9…39 are fixed [from code]. Your `tf_to_STA` uses −500/+1000 ms.
5. "Acceleration" in the X-matrix variants is a `diff` across **neural volumes** (~0.53 s), not camera frames [from code + inferred]. FicA's `Ya` uses the 10 ms grid. The two are not comparable.

**Behaviour definitions**
6. Only forward (`dRotLabY`) and yaw (`dRotLabZ`) are modelled. **There is no stimulus term** in any X matrix, GLM or correlation here [from code]. OMR turning is stimulus-locked, so behaviour filters and GLM weights will absorb visual responses. Add stimulus regressors (direction/velocity from `visual/` and the photodiode), or condition on epochs. brainsss's `correlation.py --grey_only` is the existing hook.
7. `Z_pos` = left turn and `Z_neg` = right turn only on her rig (§1.3). Sign depends on the FicTrac config and camera orientation [inferred]. Verify with a known stimulus direction before you call anything ipsi or contra.
8. `walking` and `W` are |forward| > 0.2 std (§5). Pure rotation, the OMR response, is classed as **not walking**. A corrected magnitude will change which timepoints count as walking, and the 0.2 cut-off was tuned on the bugged quantity.
9. Normalisation is inconsistent across files: raw rad/frame (X matrix, FicA, correlation), per-fly per-z std (FicB/FicC), or pooled-std (bootstrap) [from code]. `STD_BEH` thresholds are absolute raw values from her flies' distributions. Don't reuse them.
10. Some `_neg` labels are negated and others are not (§1.3) [from code]. Check the sign before you pool outputs from different scripts.

**Neural side**
11. The neural signal is z-scored after a Gaussian high-pass, with **no ΔF/F** [from code]. Filters are un-normalised sums over all timepoints, so their amplitude scales with recording length and number of flies [inferred].
12. Behaviour is aligned to each fly's original z through `20201220_warped_z_depth.nii` in the GLM and filter scripts, but **not** in FicA correlation scripts. `correlation.py` uses slice 25 for every z [from code]. Your pipeline warps first; decide explicitly how you handle slice timing.
13. The FFT "notch" in `cluster_filters` zeroes asymmetric bins 15–22 and 475–484 of a 500-lag filter [from code]. It targets something rig-specific, possibly a laser or scan artifact [inferred]. Don't apply it blindly.
14. GLM scores are in-sample `sqrt(R²)` with default `RidgeCV`. The `_unique` keys are the leave-one-out score, not a difference [from code]. Cross-validate if you port this.

**Infrastructure**
15. If you port any dataflow job, translate `mem=N` to `cpus=N` (plus an explicit `mem`) for brainsss's `sbatch`. Passing dataflow's numbers to brainsss's `mem` would request N GB instead of N cores' worth of memory [from code].

## 7. Open questions

1. Who wrote `master_X_corrected.npy` (2020-12-21) and `20220921/master_X_clipped.npy`? No producer exists at `HEAD`; check `git log -S master_X_clipped` and bigbadbrain notebooks.
2. Was the paper's `master_X.npy` built at a commit whose `make_walking_vector` already had the sqrt bug? The `W` filter (index 3) depends on it. The turn and forward filters do not.
3. What is the notch in `cluster_filters` (bins 15–22 of 500 at 20 ms → about 1.5–2.2 Hz [inferred]) removing, and is the same artifact present on the OMR rig?
4. How were `superslice_{z}.nii` and `20201220_warped_z_depth.nii` produced? No script here writes them. Candidates are bigbadbrain notebooks around 2020-11/12.
5. Which GLM variant fed `unique_glm_in_hemibrain.npy` (the connectome input): plain, state-subtraction, or reconstructed?
6. For OMR: what is the FicTrac fps and sign convention on your rig, and is the camera triggered by the scope? That decides whether the `timestamps + shift` interpolation is valid at all.
