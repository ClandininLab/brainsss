# brezovec-topography — detailed map

Repo: `../refs/brezovec-topography` (bellabrez/brezovec_topography, 5 commits all on 2023-08-16). Code for Brezovec et al., *Mapping the neural dynamics of locomotion across the Drosophila brain*. Surveyed 2026-10-02. See [00-index.md](00-index.md) for how it relates to the other refs.

Tags: **[from code]** = read directly in the file; **[inferred]** = my interpretation.

## 0. Read this first

- **Most files are not runnable as committed** [from code]. Only `anatomical_alignment.py`, `correlation_analysis.py`, `instantaneous_glm_unique.py` and `create_meanbrain.py` have complete imports and a `__main__` entry point. The rest are excerpts that rely on names that are never defined:
  - `preprocessing_neural_data.py`, `supervoxel_creation.py`, `deconvolution.py`, `find_temporal_break_point.py` have no imports at all.
  - `supervoxel_creation.py` uses `fly_idx_delete`, which is never defined.
  - `deconvolution.py` uses `b_notch`, `a_notch` and `signal`, which are never defined.
  - `find_temporal_break_point.py` uses `cluster_dir`, which is never defined.
  - `linear_filters.py` uses `cluster_model_labels_all` and `n_clusters`, which are never defined, and never calls `load_z_depth_correction`.
  - `load_behavior_fictrac.py` calls `bbb.load_fictrac` but only imports `timing`.
  - `connectome_enriched_for_DNs.py` uses `beh`, which is never defined.
  - `connectome_identify_neural_network.py` uses `cell_ids_full_adj`, which is never defined.
  - Both `connectome_*` DN/network files contain `%matplotlib inline`, so they are notebook exports and will not parse as `.py`.
- **`cross_correlation_analysis.py` and `linear_filters.py` are byte-identical** (`cmp`) [from code]. Neither one computes a cross-correlation in the usual sense. Both build a neural-activity-weighted behaviour average (see §1.9).
- None of the files submit Slurm jobs. The `main(json.loads(sys.argv[1]))` scripts expect an external orchestrator, presumably `dataflow/sherlock_scripts/main.py` [inferred].

## 1. Scripts

### 1.1 `preprocessing_neural_data.py` (34 lines)
- **What:** library-style snippets for the preprocessing chain: a temporal mean brain, then ANTs **SyN** motion correction of each red-channel volume to that mean, then applying the red-channel transforms to the green channel, then a Gaussian high-pass filter, then a per-voxel z-score [from code].
- **In:** a 4D array `(x,y,z,t)`, plus single 3D volumes for moco. **Out:** arrays. Nothing is saved [from code].
- **Paper:** the Methods steps for motion correction, high-pass filtering and z-scoring [inferred]. In practice the real pipeline was `dataflow`/`brainsss` moco (`moco_partial`/`moco_stitcher`) [inferred].

### 1.2 `create_meanbrain.py` (288 lines)
- **What:** builds a population mean anatomy. Steps: clean each raw anatomy (blur, triangle-threshold mask, keep the largest connected blob, quantile-normalise); sharpen it (unsharp mask); affine-align every brain **and its X-mirror** to a seed brain and average (`affine_0`); repeat against `affine_0` (`affine_1`); SyN-align to the sharpened `affine_1` and average (`syn_0`) [from code]. The docstring says SyN is repeated twice more, but the code only does `syn_0` [from code].
- **In:** `20210126_alignment_package/raw_anats/*.nii` and the seed brain `seed/seed_fly91_clean_20200803.nii`. **Out:** `clean_anats/`, `sharp_anats/`, `affine_0/`, `affine_1/`, `syn_0/`, plus `affine_0.nii`, `affine_1.nii`, `affine_1_sharp.nii`, `syn_0.nii`, `syn_0_sharp.nii` in `main_dir` [from code].
- **Paper:** construction of the mirror-symmetric template, i.e. the "FDA" (functional Drosophila atlas) referenced in the connectome scripts [inferred].

### 1.3 `anatomical_alignment.py` (206 lines)
- **What:** a Slurm worker that registers one moving brain to one fixed brain with ANTs. It supports optional X/Z flips, low-res resampling, saving forward and inverse transforms, and a "mimic" brain that gets the same warp applied [from code].
- **In:** a JSON `args` dict (`fixed_path`, `moving_path`, the resolutions, `type_of_transform`, `grad_step`, `flow_sigma`, `total_sigma`, `syn_sampling`, `flip_X`, `flip_Z`, `low_res`, `very_low_res`, `save_warp_params`, and optionally `mimic_*`). **Out:** `{moving}[_m]-to-{fixed}[_lowres].nii` and the `..._fwdtransforms/` and `..._invtransforms/` directories [from code]. The mimic is warped but **never saved** [from code].
- **Paper:** individual fly → template and func → anat alignment [inferred].

### 1.4 `supervoxel_creation.py` (30 lines)
- **What:** for each of 49 z-slices, loads a "superslice" (one z-plane with all flies concatenated in time). It drops the fly at `fly_idx_delete`, which per the comment is fly_095, then runs Ward agglomerative clustering with 2D grid connectivity into 2000 supervoxels per slice [from code].
- **In:** `20201129_super_slices/superslice_{z}.nii`. **Out:** `final_9_cluster_labels_2000.npy`, with shape `(49, 32768)` [from code]. The downstream scripts load `cluster_labels.npy` instead, so the file name differs [from code].
- **Paper:** supervoxel definition, clustered jointly across flies so that supervoxel IDs match between flies [inferred].

### 1.5 `correlation_analysis.py` (227 lines)
- **What:** for one z-slice and one behaviour, takes the per-fly supervoxel mean signal, concatenates it across the 9 flies, and computes its Pearson r and p against the concatenated behaviour regressor [from code].
- **Behaviours available:** `Y`, `Z`, `Ya`, `Za` and their `_pos`/`_neg` rectified versions. Y = forward velocity (`dRotLabY`), Z = rotational velocity (`dRotLabZ`), and `a` = acceleration [from code].
- **In:** `args` with `logfile`, `save_directory`, `z` and `behavior_to_corr`, plus the superslices, `cluster_labels.npy`, the per-fly `imaging/` timestamps and `fictrac/`. **Out:** `rvalues_{beh}_z{z}.npy` and `pvalues_{beh}_z{z}.npy` [from code].
- **Paper:** whole-brain behaviour correlation maps for forward walking and turning [inferred].
- Unlike the GLM, it does **not** correct for z-depth: it samples behaviour at the timestamps of the current slice `z` [from code].

### 1.6 `instantaneous_glm_unique.py` (264 lines)
- **What:** for every supervoxel in every slice, fits `RidgeCV` models that predict the pooled neural signal from 4 instantaneous regressors: `Y_pos` (forward), `Z_pos` and `Z_neg` (rectified turning) and `walking` (binary). It fits the full model, each regressor alone, and each leave-one-out model, and stores `sqrt(R²)` [from code]. "Unique" contribution = full − leave-one-out is presumably computed later [inferred].
- For each fly, behaviour is sampled at the timestamps of the supervoxel's **original z-plane before warping**. That z is the median of `20201220_warped_z_depth.nii` over the supervoxel [from code].
- **In:** the same data as 1.5, plus `warp/20201220_warped_z_depth.nii`. **Out:** `20210208_inst_uniq_glm/Z{z}.pickle`, a dict of 9 score lists [from code].
- **Paper:** maps of unique variance explained per behaviour. `unique_glm_in_hemibrain.npy` in the connectome scripts is derived from this output [inferred].

### 1.7 `load_behavior_fictrac.py` (102 lines)
- **What:** the FicTrac `.dat` parser `load_fictrac`, plus a `Fictrac` class that Savitzky–Golay-smooths `dRotLabY` and `dRotLabZ` and builds an `interp1d` on a 50 fps camera clock [from code].
- **In:** a FicTrac directory. **Out:** a DataFrame and interpolation objects [from code].
- **Paper:** behaviour preprocessing [inferred]. This is the standalone version of the `Fictrac` class that is copy-pasted into 1.5, 1.6 and 1.9.

### 1.8 `deconvolution.py` (60 lines)
- **What:** builds a GCaMP6f kernel `a(1−e^{−x/b})·c·e^{−x/d}+e` with (1,4,−1,8,0) over 50 samples, negates it, pads it to 500 and turns it into a Toeplitz matrix. It then loads the `responses_*` files from 1.9, applies a notch filter (coefficients undefined in the file), deconvolves behaviours 0–2 by least squares, smooths with a σ=3 Gaussian and clamps 5 samples at each edge [from code].
- **In:** `20210316_neural_weighted_behavior/responses_*.npy`. **Out:** the in-memory `all_signals_deconv`, with shape `(62000, 3, 500)` after the swaps. Nothing is saved [from code].
- **Paper:** deconvolved temporal filters [inferred].

### 1.9 `linear_filters.py` ≡ `cross_correlation_analysis.py` (258 lines each)
- **What:**
  - **Step 1** builds a time-shifted behaviour design matrix for each fly, slice and behaviour (`Y_pos_plus`, `Z_pos_plus`, `Z_neg_plus`). Shifts run from −5000 to +4980 ms in 20 ms steps, giving 500 lags. It saves `master_X.npy` [from code].
  - **Step 2** loops over slices z = 9…39. For each supervoxel, it takes the dot product of the lagged behaviour matrix with the pooled neural vector, which gives a neural-activity-weighted behaviour average (a reverse-correlation filter). Each row of X is picked from the fly's original z [from code].
- **In:** fictrac, timestamps, superslices and labels. **Out:** `master_X.npy` and `responses_{z}.npy`, each with shape `(2000, 3·500)` [from code].
- **Bug:** step 2 indexes `X[original_z, i, :, :]`, but `X` at that point is the **last per-slice** matrix (z=48, shape `(9, 1500, 3384)`), not the stacked `Xs`. So the fly axis gets indexed by `original_z` [from code]. The published results must come from a different version [inferred].
- **Mismatch:** `deconvolution.py` reshapes the responses as **4** behaviours × 500, and `find_temporal_break_point.py` documents 4 behaviours (fwd, left, right, walking). This script builds 3, so the files the paper used came from a 4-behaviour variant [inferred].
- **Paper:** temporal filters of neural activity around behaviour [inferred].

### 1.10 `find_temporal_break_point.py` (50 lines)
- **What:** for each of 250 superclusters, combines the left- and right-turn filters with the matching contralateral cluster (`cluster+250`). It requires left and right to agree (r ≥ 0.5) and the peak to be ≥ 0.1, then finds where the derivative first exceeds 0.001 before the peak. That point is the "break point", meaning how far before behaviour the activity starts to ramp [from code].
- **In:** `{cluster_dir}/20230202_SC_temporal_filters.npy`, with shape `(501, 4, 500)`. **Out:** the in-memory lists `break_points` and `flipped` [from code].
- **Paper:** **Figure 3** (the header comment says so) [from code].

### 1.11 `adjacency_matrix.py` (274 lines)
- **What:** loads hemibrain synapse pickles and scales coordinates by the 0.38 µm voxel size. It bins synapses into a 0.38 µm grid, maps each grid voxel to an FDA supervoxel and counts pre→post synapses between supervoxels across 96 processes [from code]. The `adj_cal.calculate_adj` method and `calculate_cor_multiprocessing` are dead code: they never increment `place_holder`. The module-level `calculate_adj` is the one that runs [from code].
- **In:** the `hemibrain_all_neurons_*` pickles, `/home/data/supervoxels/20220701_supervoxel_labels_in_fda.npy` and `supervoxel_to_voxel.pickle`. **Out:** `adjacent_supervoxel.h5`, a `(4999, 4999)` matrix [from code].
- The `/home/data/...` path is not Sherlock-style, so this script was run on another machine [inferred]. A comment in 1.12 says "Feng removed the 0 entry", which fits Feng Chen, a coauthor, running it [inferred].
- **Paper:** supervoxel-level connectome adjacency [inferred].

### 1.12 `connectome_connectivity_across_distance_bins.py` (246 lines)
- **What:**
  - Loads the FDA, crops it to the hemibrain bounding box and loads 5000 full-volume supervoxels.
  - Picks the supervoxels with ipsi-turn correlation > 0.2. Bins the pairwise centroid distances (0–150 µm, 10 µm bins) and computes size-normalised mean synaptic connectivity per bin.
  - Builds a null by drawing an equal number of random pairs with synapses from the same distance bin (1000 bootstraps) [from code].
- **In:** the FDA template, `syn_transformed_to_FDA.nii`, `20220624_cluster_labels_flat.npy`, `20220624_{ipsi_turn,contra_turn,fwd}_corrs.npy` and `adjacent_supervoxel.h5`. **Out:** the in-memory `yes_connectivities` and `no_connectivities` [from code].
- **Bug:** centroids are scaled by `(2.6,2.6,5)[0]`, which is the scalar 2.6, so z distances are under-scaled by about 2× [from code].
- It imports `brainsss` but never uses it [from code].
- **Paper:** whether turn-correlated regions are more connected than chance at matched distance [inferred].

### 1.13 `connectome_enriched_for_DNs.py` (115 lines)
- **What:** queries neuPrint (`hemibrain:v1.2.1`) for descending neurons by the types `DNa/b/d/g/p/ES*`, `Giant_Fiber` and `MDN`. It averages their Dice overlap with a behaviour map and compares that against 10,000 random equal-size cell sets [from code].
- **In:** the synapse pickle, `synpervox.npy`, `all_neuron_dice.npy` and a neuPrint token (left blank). **Out:** the in-memory `mean_dn_dice` and `sample_means` [from code].
- **Paper:** DN enrichment in the behaviour-related regions [inferred].

### 1.14 `connectome_identify_neural_network.py` (218 lines)
- **What:** binarises the unique-GLM map for one behaviour (`beh = 1`, threshold 0.01). It grid-searches thresholds on fraction-of-synapses-in-mask and mean connectivity, scores each resulting cell set by Dice against the mask using the left half only (`[:75]`), then unions the networks with fewer than 50 cells and Dice > 0.25 [from code].
- **In:** `20220817_full_adj.npy`, `synpervox.npy`, the synapse pickle and `unique_glm_in_hemibrain.npy`. **Out:** the in-memory `cells`, a list of hemibrain body IDs [from code].
- **Paper:** identifying a candidate connectome network for a behaviour, likely turning [inferred].

### 1.15 `README.md`
Paper citation and the Zenodo DOI. It states that the code is not runnable outside their cluster [from code].

## 2. Function table

Duplicated helper classes are listed once with every file they appear in. "Consts" lists the hardcoded values inside each function. Script-level constants are covered in §5. All entries are [from code].

| Function | File(s) | Inputs | Outputs | Hardcoded constants |
|---|---|---|---|---|
| `make_temporal_mean` | preprocessing_neural_data | brain (x,y,z,t) | mean over t | — |
| `motion_correct_single_volume` | preprocessing_neural_data | meanbrain, red vol | ANTs reg dict | `type_of_transform='SyN'` |
| `apply_transforms_from_red_to_green_channel` | preprocessing_neural_data | meanbrain, reg dict, green vol | warped green | uses `fwdtransforms` |
| `high_pass_filter` | preprocessing_neural_data | brain (x,y,z,t) | brain − gaussian + mean | `sigma=200` vols, `truncate=1` (≈106 s at ~1.88 Hz [inferred]) |
| `z_score` | preprocessing_neural_data | brain (x,y,z,t) | per-voxel z-score over the whole session | axis 3; **no F0/ΔF/F** |
| `create_clusters` | supervoxel_creation | superslice, n_clusters | fitted `AgglomerativeClustering` | reshape `(-1, 3384*9)`, `grid_to_graph(256,128)`, `linkage='ward'`, cache dir `.../20201129_super_slices` |
| `fit_eq` | deconvolution | x,a,b,c,d,e | kernel | called with (1,4,−1,8,0), x = 0..49 |
| `load_fictrac` | load_behavior_fictrac (+`@bbb.timing`) | directory, file | DataFrame (23 named cols) | raises if `max(speed) > 10` |
| `Fictrac.__init__` | load_behavior_fictrac, correlation_analysis, instantaneous_glm_unique, linear_filters/cross_corr | fly_dir, timestamps | — | uses `bbb.load_fictrac(fly_dir/'fictrac')` |
| `Fictrac.make_interp_object` | same 4 files | behaviour col | `(smoothed, interp)` in load_behavior/linear_filters; **interp only** in correlation/GLM | `fps=50`, `expt_len=30 min`, savgol(25, 3), `bounds_error=False` |
| `Fictrac.pull_from_interp_object` | same 4 files | interp, timepoints | values, NaN→0 | — |
| `Fictrac.interp_fictrac` | load_behavior, linear_filters | — | `Y`, `Z` (smoothed 50 Hz) and `Yi`, `Zi` | behaviours `dRotLabY`→Y, `dRotLabZ`→Z |
| `Fictrac.interp_fictrac(z)` | correlation_analysis | z | Y, Z, `_pos`/`_neg`, `h` (10 ms), `a` (accel), `YZ`, `YZh` | 10 ms grid; accel savgol(25,3); not std-normalised (commented out) |
| `Fictrac.interp_fictrac()` | instantaneous_glm_unique | — | per-z lists of std-normalised Y, Z, `_pos`/`_neg`, `walking` | 49 z; `walking = YZ > .2`; length 3384 |
| `Fictrac.make_walking_vector` | linear_filters/cross_corr | — | `W`, `Wi` (nearest interp) | threshold `.2` on std-normalised YZ; 50 fps, 30 min |
| `Fly.__init__` | correlation, GLM, linear_filters/cross_corr | fly_name, fly_idx | — | `dataset_path/fly/func_0` |
| `Fly.load_timestamps` | same | — | `[t,z]` ms | `bbb.load_timestamps(func_0/imaging)` |
| `Fly.load_fictrac` | same | — | `Fictrac` | — |
| `Fly.load_brain_slice` | same | — | `brain[:,:,:,fly_idx]` | depends on the superslice fly order |
| `Fly.load_anatomy` | same (never called) | — | anat in template | `warp/anat-to-meanbrain.nii` |
| `Fly.load_z_depth_correction` | GLM, linear_filters/cross_corr | — | z-map volume | `warp/20201220_warped_z_depth.nii` |
| `Fly.get_cluster_averages` | same 3 | labels, n_clusters | `(n_clusters, 3384)` means | reshape `(-1, 3384)` |
| `Fly.get_cluster_id` | same 3 (never called) | x, y | cluster id | `x*128 + y` (slice width 128) |
| `build_timeshifted_behavior_matrix` | linear_filters/cross_corr | shifts, fly, z, behaviour | shifts, list of lagged traces | substring tests on `'Y'`, `'Z'`, `'pos'`, `'neg'` |
| `build_X` | linear_filters/cross_corr | shifts, behaviours, z | `(9, n_beh·500, 3384)` | reshape `(-1, 3384)` |
| `main(args)` | anatomical_alignment | JSON dict | `.nii` + transforms | low-res `(256,128,49)`, very low `(128,64,49)`; Brezovec site-packages path |
| `main(args)` | correlation_analysis | `logfile`, `save_directory`, `z`, `behavior_to_corr` | r/p `.npy` | 9 flies, drop idx 3, 2000 clusters, paths §5 |
| `main(args)` | instantaneous_glm_unique | `logfile` | `Z{z}.pickle` | 9 flies, 49 z, 2000 clusters, `RidgeCV()` defaults |
| `main(args)` | linear_filters/cross_corr | `logfile` | `master_X`, `responses_{z}` | lags −5000:5000:20 ms; z 9..39; `30456 = 9·3384` |
| `main()` | create_meanbrain | — | template `.nii` files | res `(0.65,0.65,1)` µm; seed fly91 |
| `avg_brains` | create_meanbrain | in dir, out dir, name | mean `.nii` | array `(n, 1024, 512, 256)` |
| `align_anat` | create_meanbrain | fixed, moving, out, transform, res, mirror | `.nii` | mirror = flip X |
| `clean_anat` | create_meanbrain | in_file, save_dir | `*_clean.nii` | gaussian σ=10, triangle/2, `n_quantiles=500` |
| `sharpen_anat` | create_meanbrain | in_file, save_dir | `*_sharp.nii` | rescale .3–.7, unsharp r=3 amt=7, bg < .31, 500 quantiles |
| `sec_to_hms` | anatomical_alignment | seconds | `"HH:MM:SS"` | — |
| `stderr_redirected` / `_redirect_stderr` | anatomical_alignment, create_meanbrain | target (devnull) | context manager | — |
| `connectome.__init__` | adjacency_matrix | load_data, data_dir | synapse/neuron dicts | 3 pickle names; × `SEM_voxel_size=0.38` |
| `connectome.multiprocessing_help_func_2` | adjacency_matrix | x/y/z sets, i, dict | set intersections | — |
| `connectome.create_set_list_1d` (+ inner `multiprocessing_help_func_1`) | adjacency_matrix | data, bins | list of index sets | `cpu=96` (unused) |
| `connectome.create_grid` | adjacency_matrix | x0,y0,z0 | grid edges | called with 0.38 ×3 |
| `connectome.grid_data` | adjacency_matrix | — | `(nx,ny,nz)` sets | one process per x-bin |
| `adj_cal.__init__` | adjacency_matrix | kwargs | body-id set | — |
| `adj_cal.processing_voxel` | adjacency_matrix | — | per-voxel [inputs; outputs] | `prepost` 0/1 |
| `adj_cal.preprocessing_for_adj` | adjacency_matrix | — | input/output arrays, grid idx | — |
| `adj_cal.calculate_adj` / `adj_cal.handle_output` | adjacency_matrix | cpu, name | h5 (all zeros, dead path) | `cpu=96` |
| `calculate_cor_multiprocessing` | adjacency_matrix | queues, data | zeros (dead) | — |
| `calculate_adj` (module) | adjacency_matrix | cpu, name | `adjacent_supervoxel.h5` | `n_voxel=4999`, `cpu=96` |
| `handle_output` (module) | adjacency_matrix | name, dset, size, queue | h5 writer | — |
| `calculate_help_multiprocessing` | adjacency_matrix | queues, maps | per-supervoxel row | offsets (312,30,58), bounds (700,591,392) |
| `load_FDA` | connectome_connectivity_across_distance_bins | — | FDA, FDA_lowres | `anat_templates/20220301_luke_2_jfrc_affine.nii`, .38 µm → (2.6,2.6,5) |
| `load_synapses_in_FDA` | same | — | array | `/oak/.../Yukun/syn_transformed_to_FDA.nii` |
| `get_hemibrain_bounding_box` | same | synapse array | start/stop dicts | spacing .76 → (2.6,2.6,5) |
| `calc_dice` | connectome_identify_neural_network | mask, neurons | Dice | — |

`deconvolution.py`, `find_temporal_break_point.py` and `connectome_enriched_for_DNs.py` define no functions apart from `fit_eq` [from code].

## 3. Name collisions with `refs/brainsss-dff`

Exact function-name matches only. All observations are [from code] unless tagged otherwise.

| Name | topography | brainsss-dff | Difference |
|---|---|---|---|
| `load_fictrac` | `load_behavior_fictrac.py` | `brainsss/fictrac.py` | Body is identical. topography adds `@bbb.timing` (prints the function name and duration to stdout, which brainsss would treat as job output); dff only adds a to-do docstring. Both raise on speed > 10. The topography analysis scripts actually call `bbb.load_fictrac`, which is identical to dff's. |
| `load_timestamps` (as `Fly.load_timestamps`) | wrapper method calling `bbb.load_timestamps` | `brainsss/utils.py` function | `bbb.load_timestamps` and dff's `load_timestamps` are identical (h5 cache, falling back to Bruker XML; returns `[t,z]` in ms). Only the wrapper differs. |
| `sec_to_hms` | `anatomical_alignment.py` | `scripts/align_anat.py`, `apply_transforms.py`, `motion_correction.py`, nested in `utils.py` | Identical. |
| `stderr_redirected` / `_redirect_stderr` | `anatomical_alignment.py`, `create_meanbrain.py` | `scripts/align_anat.py`, `apply_transforms.py` | Identical apart from whitespace. |
| `main` | `anatomical_alignment.py` ↔ `scripts/align_anat.py` | — | Same script lineage. dff logs via `brainsss.Printlog` instead of `dataflow.Printlog`, imports `ants` directly with no Brezovec `sys.path` hack, adds the `iso_2um_fixed`/`iso_2um_moving` resampling options with a `_2umiso` suffix, and stops saving `warpedmovout` (that save is commented out). The topography version **does** save the warped brain. Other `main`s share only the name. |
| `__init__` | class constructors | class constructors | Name only. |

The following are not name matches but do the same step differently. They matter if you compare results:
- **High-pass:** topography subtracts a Gaussian (σ=200 vols) and adds back the mean. dff `butter_highpass.py` uses a Butterworth filter (order 2, cutoff 0.01 Hz, `fs=1.8`) through `filtfilt`. dff `temporal_high_pass_filter.py` still has the Gaussian σ=200 version.
- **Normalisation:** topography z-scores each voxel over the session. dff `dff.py` computes `hpf / (lpf − min(lpf))`, so F0 is the low-pass component offset by its global minimum. dff `zscore.py` is a chunked equivalent of topography's `z_score`.
- **Supervoxels:** the same Ward + `grid_to_graph` method with 2000 clusters per slice. topography clusters **all flies concatenated** at a 256×128 slice; dff `make_supervoxels.py` clusters **per fly** on `..._filtered_{behavior}.h5` using its own slice shape. dff `supervoxel_to_full_res` hardcodes `[314,146]`, so the IDs and dimensions are not interchangeable.
- **Fictrac interpolation:** dff `fictrac.smooth_and_interp_fictrac` takes the same savgol(25,3) on a 50 fps grid but passes `fps`, `expt_len` and `resolution` as arguments, and can convert to mm/s or deg/s. topography hardcodes them and keeps raw FicTrac units (rad/frame).

## 4. Dependencies on dataflow, bigbadbrain and brainsss

| Package | Imported by | What is actually used |
|---|---|---|
| `dataflow` (as `flow`) | anatomical_alignment, correlation_analysis, instantaneous_glm_unique, linear_filters, cross_correlation_analysis | Only `flow.Printlog(logfile).print_to_log`, a flock-protected append. It is equivalent to `brainsss.Printlog` [from code: `dataflow/utils.py:136`]. |
| `bigbadbrain` (as `bbb`) | correlation_analysis, instantaneous_glm_unique, linear_filters, cross_correlation_analysis, load_behavior_fictrac (`timing`); deconvolution uses `bbb` without importing it | `bbb.load_timestamps`, `bbb.load_fictrac`, `bbb.sort_nicely` and `bbb.utils.timing`. The first two are identical to the brainsss-dff versions. |
| `brainsss` | connectome_connectivity_across_distance_bins | Imported but **never used**. |

All of these are swappable with brainsss: `brainsss.Printlog`, `brainsss.load_timestamps`, `brainsss.load_fictrac` and `brainsss.sort_nicely` (the last appears in the dff∩bbb list in 00-index) [inferred from the identical bodies].

**Hardcoded dataset path (a move risk, not a dependency on Bella's data).** `brainsss/brain_utils.py:203` (`warp_STA_brain`) hardcodes `dataset_path = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20190101_walking_dataset'`. It reads each fly's `warp/func-to-anat_fwdtransforms_2umiso/` transforms from there and assumes `moving_resolution = (2.611, 2.611, 5)`. brainsss-dff has the same line [from code].

This works today, because the OMR flies are stored in that folder (`users/yandanw.json` points there too) [from code]. The risk is the upcoming move of the flies to your own user directory: after the move this function will look in the old location. Before then, change it to take the per-fly `dataset_path` from settings. See `docs/hardcoded-paths.md`.

Third-party packages: `ants` (antspy), `nibabel`, `sklearn`, `scipy`, `numpy`, `pandas`, `h5py`/`tables`, `umap` (imported by the GLM but unused), `psutil`, and for the connectome scripts `neuprint`, `networkx`, `fa2`, `nxviz`, `bokeh`/`holoviews`/`hvplot` [from code].

## 5. Gotchas: locomotion-specific choices that must not carry over to OMR

**Dataset identity**
1. The fly list `fly_087, 089, 094, 097, 098, 099, 100, 101, 105` and `dataset_path = .../Brezovec/2P_Imaging/20190101_walking_dataset` are hardcoded in every analysis `main` [from code].
2. `fly_idx_delete = 3` removes fly_095 **by its position** in the superslice [from code]. With a different fly set this silently deletes the wrong fly.
3. All paths are in Brezovec's Oak directory, and the code loads ants from `/home/users/brezovec/.local/...` [from code].

**Acquisition geometry and timing**
4. Every fly is assumed to have exactly **3384 volumes** over a **30-minute** session (`expt_len = 1000*30*60`), with 49 z-slices and 256×128 slices [from code]. 3384 / 1800 s works out to about 1.88 Hz [inferred].
5. Behaviour beyond 30 min is NaN, which `nan_to_num` turns into **0** without any warning [from code]. A longer OMR session would get zero-padded behaviour; a shorter one would break the reshapes.
6. The FicTrac camera is assumed to run at **50 fps** and to start at t=0 together with imaging; no sync signal is used [from code]. Check what the OMR rig's camera rate and trigger actually are.

**Behaviour definitions**
7. Only `dRotLabY` (forward) and `dRotLabZ` (turning) are used. There are **no stimulus regressors** [from code]. In OMR, turning is driven by the stimulus, so a turning correlation or GLM map will mix motor and visual-motion responses. Add stimulus direction and velocity regressors, or analyse within stimulus epochs.
8. The rectified `Z_pos`/`Z_neg` are labelled as left/right turns, and the break-point script calls behaviours 1 and 2 left_turn and right_turn [from code]. Which sign means left depends on the FicTrac config and the camera's mirroring [inferred]. Recheck it on your rig before reusing "ipsi" or "contra".
9. The "walking" threshold `.2` is applied to std-normalised velocity [from code]. It is tuned to a spontaneous-walking dataset; flies in an OMR paradigm may walk with a different velocity distribution.
10. **Bug:** `np.sqrt(np.power(Y,2), np.power(Z,2))` passes the second array as the `out=` argument, so `YZ` = |Y| and "walking" = |forward velocity| > 0.2 rather than speed > 0.2 [from code]. Yandan confirmed this by running it locally with `Y = [0.0, 0.0]` and `Z = [1.0, 5.0]`, which is pure rotation: `np.sqrt(Y**2, Z**2)` printed `[0. 0.]`, while `np.sqrt(Y**2 + Z**2)` printed `[1. 5.]`. The same bug is in the dataflow scripts that likely produced the paper's results (see §6). This affects `YZ`, `YZh`, `walking` and `W`. If you rebuild these, use `np.sqrt(Y**2 + Z**2)`, and remember that the published "walking" regressor ignores pure rotation [inferred]. Pure rotation is exactly what OMR evokes.
11. FicTrac values stay in raw units (rad/frame); the GLM normalises by per-fly std, but correlation does not [from code].
12. FicTrac is smoothed with savgol window 25 (0.5 s at 50 fps). `load_fictrac` throws out the **whole fly** if speed ever exceeds 10 [from code].

**Neural preprocessing**
13. The neural signal is a per-voxel **z-score**, not ΔF/F, after Gaussian high-pass σ=200 volumes [from code]. Your pipeline produces ΔF/F with a Butterworth high-pass at 0.01 Hz. Effect sizes (r, R², filter amplitudes) are not comparable across the two without re-running.
14. The GCaMP6f kernel parameters (rise 4, decay 8 samples, so the 20 ms grid gives 80/160 ms [inferred]) are indicator-specific [from code]. Use your indicator's kinetics.
15. The notch filter in deconvolution has undefined coefficients [from code]. It may target a laser or scan artifact specific to that rig [inferred; bigbadbrain has a notebook "reflecting on laser temporal artifact"].

**Clustering, z-correction and windows**
16. The supervoxels are fit on the **9 flies concatenated** [from code], so the labels in `cluster_labels.npy` only make sense for that exact fly set and order.
17. Behaviour is sampled at each supervoxel's **original z-plane timing** via `20201220_warped_z_depth.nii` [from code]. A pipeline that warps to the template without such a map loses up to one volume period (about 0.5 s) of alignment [inferred]. Note that `correlation_analysis` skips this correction.
18. The filter and STA analyses only cover z = 9…39, dropping 9 slices at each edge [from code].
19. Filter windows are ±5 s at 20 ms with the centre at index 250 [from code]. Your `tf_to_STA` uses −500/+1000 ms (commit `24c1c28`), so the two are not directly comparable.
20. The break-point thresholds (r 0.5, peak 0.1, derivative 0.001, skip the first 20 samples) and the hemisphere pairing `cluster+250` assume a 500-supercluster, left/right-ordered layout [from code].

**Connectome scripts**
21. The behaviour-map threshold is `.01`, the Dice score cuts at `[:75]` (the midline in that cropped space), correlation selection uses `> .2`, distance bins are 0–150 µm in 10 µm steps, and `n_voxel = 4999` / `n_clusters = 5000` [from code]. All of these are tied to the FDA crop and that clustering.
22. **Bug:** centroid scaling `(2.6,2.6,5)[0]` makes all axes scale by 2.6 µm [from code].

## 6. Scan: two-argument `np.sqrt` (walking-speed bug)

Scanned 2026-10-02. The scan covered every `.py` file and every notebook code cell in the four refs and in `brainsss/scripts/`, 928 files in all. It matched parentheses across line breaks and flagged any `np.sqrt(…)` call with a top-level comma. A follow-up scan of this repo's `brainsss/` and `notebooks/` (75 files) also found nothing [from code].

| Location | Hits | Files |
|---|---|---|
| `brainsss-dff` | 0 | 0 |
| this repo (`scripts/`, `brainsss/`, `notebooks/`) | 0 | 0 |
| `brezovec-topography` | 5 | 4: `instantaneous_glm_unique.py:81`, `correlation_analysis.py:117-118`, `linear_filters.py:96`, `cross_correlation_analysis.py:96` |
| `brezovec-dataflow` | 30 | 20, all in `sherlock_scripts/` |
| `brezovec-bigbadbrain` | 155 | 69 notebooks |

- Every hit is the same Y/Z speed pattern copied between files (`Y`/`Z`, `Yh`/`Zh`, `Y[z]`/`Z[z]`, std-normalised, `Y_s`/`Z_s`, `behavior_super[...]`). There are no unrelated two-argument uses [from code].
- **dataflow hits** include the likely paper-version scripts: `instantaneous_glm_unique{,_reconstructed,_single,_single_reconstructed,_state_subtraction}.py`, `neu_weighted_beh{,_single}.py`, `create_behavior_X_matrix*.py` (including `20231204_..._threshold_reviewer.py`), `final_9_correlation.py`, `20210322_final_9_correlation.py`, `final_9_idv_correlation.py`, `20210420_voxelres_correlation.py`, `bout_triggered.py`, `bootstrap_map.py` and `shaul_temporal_glm{,_singles}.py` [from code].
- **bigbadbrain** includes `20231030 - calc walking thresh for topography paper.ipynb`. So the 0.2 threshold was probably tuned on |forward velocity|, not speed [inferred].
- **brainsss is clean.** In both brainsss-dff and this repo, `brainsss/fictrac.py:97` (`my_speed`: `np.sqrt(dx*dx + dy*dy)` on `dRotLabX`/`dRotLabY`) and `:105` (`speed_all_3`) compute the magnitude correctly. Note that `my_speed` combines sideways and forward motion (X and Y), not forward and turning (Y and Z) [from code].

## 7. Open questions

1. Where are the **actually used** versions of the linear-filter and 4-behaviour scripts? `linear_filters.py` has the `X`/`Xs` bug and only 3 behaviours, but the outputs it fed have 4. The candidates are `dataflow/sherlock_scripts/neu_weighted_beh*.py` (the save dir is `20210316_neural_weighted_behavior`, which matches `20210318_neu_weighted_beh.py`) [inferred].
2. Where is the "unique" score (full − LOO) and its significance test computed? Does `unique_glm_in_hemibrain.npy` come from `instantaneous_glm_unique_reconstructed.py` in dataflow?
3. What are `b_notch`/`a_notch`: what frequency, and why?
4. ~~Is the `np.sqrt(a, b)` bug present in the paper-version GLM, meaning the published "walking" regressor really is |forward| > 0.2?~~ **Closed:** yes. The bug is in every dataflow GLM, filter and correlation variant and in the walking-threshold notebook (§6). The published "walking" regressor is very likely |forward| > 0.2 [inferred: these are the most likely paper versions, but which one actually ran isn't confirmed].
5. How were the superslices (`20201129_super_slices`) built? There is no code here for concatenating flies or for the z-depth map `20201220_warped_z_depth.nii`.
6. How were the 500 superclusters behind `20230202_SC_temporal_filters.npy` built and ordered so that `+250` gives the contralateral partner?
7. Which FDA template version did the paper use? Candidates are `syn_0` from `create_meanbrain.py`, `20220301_luke_2_jfrc_affine.nii`, or the `anat_templates` copies that brainsss loads.
8. For the OMR work: is the imaging volume rate still about 1.8 Hz, the session 30 min, and the camera 50 fps? And how is stimulus timing (photodiode, `brainsss/visual.py`) going to enter the regressors?
