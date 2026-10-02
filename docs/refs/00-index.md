# Reference repos index

Index of the four read-only repos under `../refs/` (sibling of this repo). Surveyed 2026-10-02.
Tags: **[from code]** = checked directly in files / git metadata; **[inferred]** = judgement from names, imports, or structure.
Sizes are on-disk (`du -sh`), file counts exclude `.git/`.

## Summary

| Repo | Origin | Size | Files | Code type |
|---|---|---|---|---|
| `brainsss-dff` | ClandininLab/brainsss, branch `origin/dff` | 626 MB | 355 | preprocessing + analysis + job submission |
| `brezovec-bigbadbrain` | bellabrez/bigbadbrain | 2.2 GB (769 MB is `.git`) | 1174 | analysis + figures (notebooks), some job submission |
| `brezovec-dataflow` | bellabrez/dataflow | 2.4 MB | 178 | data transfer/conversion + Sherlock preprocessing + analysis + job submission |
| `brezovec-topography` | bellabrez/brezovec_topography | 272 KB | 16 | analysis (paper code), plus condensed preprocessing |

All origins from `git remote -v` [from code].

## brainsss-dff

**Not actually a separate Bella repo.** Its `.git` is a file pointing to `brainsss/.git/worktrees/brainsss-dff`, i.e. it is a git worktree of *this* repo, checked out detached at `e25e58b` ("why no work?", Ilana Zucker-Scharff, 2026-07-17) [from code]. That commit is on `origin/dff` and is **not** an ancestor of `YDPlayground` [from code]. Note: because it's a worktree, git operations in this repo (e.g. `git worktree prune`) can affect it.

- **Purpose:** the lab's Slurm wrapper for preprocessing/analysing whole-brain 2P data on Sherlock — same codebase as this repo, on the dF/F branch [from code: README, setup.py `name='brainsss'`].
- **Main folders** [from code]:
  - `brainsss/` (144 KB) — library: `utils`, `brain_utils`, `alignment_utils`, `explosion_plot`, `fictrac`, `visual`.
  - `scripts/` (524 KB, ~50 workers) — `preprocess.{sh,py}`, `postprocess.{sh,py}`, `watcher.slurm`, and per-step workers (moco, background_subtraction, raw_warp, blur, butter_highpass, dff, temp_filter, make_supervoxels, build_STA, tf_to_STA, regress_noise, supercluster, …).
  - `notebooks/` (529 MB, 249 files) — dated scratch/analysis notebooks, 2022–2025.
  - `demo_data/fly_001` (95 MB), `users/*.json` (incl. `yandanw.json`), `tests/test_imports.py`, `master_2P.xlsx`.
- **Code type:** preprocessing, postprocessing/analysis, job submission; notebooks hold exploratory figures [from code].
- **Diff vs. `YDPlayground`** [from code]: `brainsss/fictrac.py`, `brainsss/utils.py`, and most postprocess workers differ (`build_STA`, `filter_bins`, `get_ind_vox`, `individual_clusters`, `later_transfer`, `make_supervoxels`, `regress_noise`, `relative_ts`, `supercluster`, `temp_filter`, `tf_to_STA`, both orchestrators). Only in dff: `scripts/convert_2p_to_nwb.py`. Only in YDPlayground: `scripts/make_supervoxels_backup.py`.
- Also contains committed junk: `slurm-*.out`, `.DS_Store`, `__pycache__`, `.swp` [from code].

## brezovec-bigbadbrain

- **Purpose:** Bella's earlier (≈2019–2024) personal analysis library for whole-brain imaging: loading, motion correction, GLM, PCA, correlation, event-triggered averages, anatomy warping [from code: module names; dates from notebook names]. Likely the predecessor of brainsss's analysis layer [inferred].
- **Main folders** [from code]:
  - `bigbadbrain/` (88 KB, 12 modules) — `brain`, `loaders`, `motcorr`, `glm`, `pca`, `correlation`, `event_triggered`, `anatomy_warp`, `fictrac`, `visual`, `utils`.
  - `jupyter_notebooks/` (1.4 GB, ~1124 notebooks, 2019–2024) — the bulk of the repo; analysis and figure exploration.
  - `scripts/` (140 KB, 34 files) — GLM drivers (`glm_master*.py`, `visual_glm`, `behavior_glm`), CMTK warp triggers, `run_X_*.sh`; 3 files call `sbatch` [from code].
- **Code type:** mostly analysis + figure notebooks; small amount of job submission; preprocessing only via `motcorr.py` [from code].
- No README; `setup.py` declares no dependencies [from code].

## brezovec-dataflow

- **Purpose:** two things in one repo [inferred from layout]:
  1. `dataflow/` + `scripts/` (≈1.7k lines) — moving raw data off the Bruker/stim computers: raw→tiff ("ripper"), tiff→nii, FTP, transfer to Oak, email notification; includes Windows `.bat` launchers [from code], so it ran on the acquisition PC [inferred].
  2. `sherlock_scripts/` (828 KB, 83 entries, ≈15k lines of Python) — Bella's Sherlock pipeline before/alongside brainsss: `main.py`/`main.sh`, `fly_builder`, moco (`moco_partial`, `moco_stitcher`), meanbrain creation (many dated variants), `align_anat`, `apply_transforms`, `zscore`, `correlation`, GLMs (`instantaneous_glm_unique*`, `shaul_temporal_glm*`), clustering, PCA/ICA/UMAP, connectome analyses [from code].
- **Other folders:** `jupyter_notebooks/` (456 KB) — early (2019) FTP/XML/dataframe setup tests [from code].
- **Code type:** data ingestion, preprocessing, analysis, job submission (5 sherlock scripts call `sbatch`/`wait_for_job`) [from code]. No figure code to speak of [inferred].

## brezovec-topography

- **Purpose:** published code for Brezovec et al., *Mapping the neural dynamics of locomotion across the Drosophila brain* (Zenodo DOI in README) [from code]. README states it is not runnable outside their cluster [from code].
- **Main folders:** none — 15 flat `.py` files, ≈2.6k lines [from code]:
  - preprocessing (condensed): `preprocessing_neural_data.py` (ANTs SyN moco red→green, Gaussian high-pass), `create_meanbrain.py`, `anatomical_alignment.py`, `supervoxel_creation.py`, `load_behavior_fictrac.py`.
  - analysis: `correlation_analysis`, `cross_correlation_analysis`, `linear_filters`, `instantaneous_glm_unique`, `deconvolution`, `find_temporal_break_point` (Fig. 3), `adjacency_matrix`, `connectome_*` (neuprint queries).
- **Code type:** analysis, with a few preprocessing excerpts; no job submission (no `sbatch` calls) [from code]. Looks like cleaned-up copies extracted from `dataflow/sherlock_scripts` for publication [inferred].
- **Depends on the other repos:** imports `dataflow` (5 files), `bigbadbrain` (4 files), `brainsss` (1 file) [from code].

## Overlap

Function-name intersections (`def` names, library + scripts dirs) [from code]:

| Pair | Shared function names |
|---|---|
| topography ∩ brainsss-dff | `load_fictrac`, `load_timestamps`, `sec_to_hms`, `stderr_redirected`, `_redirect_stderr` (only 5 — little real overlap) |
| topography ∩ dataflow | ~20: `align_anat`, `avg_brains`, `clean_anat`, `sharpen_anat`, `build_X`, `build_timeshifted_behavior_matrix`, `create_clusters`, `get_cluster_averages`, `interp_fictrac`, `make_walking_vector`, `load_z_depth_correction`, `load_brain_slice`, … |
| brainsss-dff ∩ dataflow | ~45: whole Slurm/logging layer (`sbatch`, `wait_for_job`, `get_job_status`, `print_to_log`, `progress_bar`), fly building (`copy_fly`, `copy_bruker_data`, `copy_fictrac`, `add_fly_to_xlsx`, `get_new_fly_number`), XML parsing (`load_xml`, `get_resolution`, `get_datetime_from_xml`), moco (`motion_correction`, `align_volume`, `save_motCorr_brain`) |
| brainsss-dff ∩ bigbadbrain | ~17: `motion_correction`, `align_volume`, `get_resolution`, `interpolate_fictrac`, `smooth_and_interp_fictrac`, `load_photodiode`, `pd_csv_to_h5py`, `sort_nicely` |
| dataflow ∩ bigbadbrain | ~16: moco helpers, `load_numpy_brain`, `send_email`, `timing` |

Same-named scripts in `brainsss-dff/scripts` and `dataflow/sherlock_scripts` [from code]: `align_anat`, `apply_transforms`, `bleaching_qc`, `check_for_flag`, `clean_anat`, `correlation`, `fictrac_qc`, `fly_builder`, `make_mean_brain`, `zscore`. These have diverged (e.g. `fly_builder.py` diff is ~300 lines; brainsss's version has the `bigbadbrain`/`dataflow` imports commented out).

Caveats: shared names ≠ identical code. Spot check: `load_fictrac` in topography vs. brainsss-dff differs [from code]. Topography's high-pass is a Gaussian-smoothing subtraction (`sigma=200`), whereas brainsss uses a Butterworth filter (`butter_highpass`) — same step, different method [from code].

**Lineage** [inferred]: `bigbadbrain` (analysis lib) → `dataflow/sherlock_scripts` (Slurm pipeline, borrowing bbb helpers) → `brainsss` (pipeline consolidated into a package, lab-wide) ; `topography` = paper-ready extract of the dataflow/bbb analyses.

## Where to look for…

- Slurm orchestration / logging: this repo, or `brainsss-dff/brainsss/utils.py` for the `dff` branch version.
- Paper-method reference (GLM, filters, correlation, meanbrain): `brezovec-topography` first, then `dataflow/sherlock_scripts` for the full versions.
- Old figure notebooks: `brezovec-bigbadbrain/jupyter_notebooks` (dated filenames).
- Acquisition-side data transfer: `brezovec-dataflow/dataflow`.
