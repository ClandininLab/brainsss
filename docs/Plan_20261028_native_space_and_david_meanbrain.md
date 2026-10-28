# Plan 2026-10-28 — two routes for the 20261015 flies (fly_001, fly_002)

Context: the T4/T5-TNT line's anat→FDA SyN warp (template `20220301_luke_2_jfrc_affine_zflip_2umiso.nii`) is not usable. Two routes, run in parallel on separate branches off `YDPlayground`. Route A needs nothing from anyone; Route B waits on answers from David.

Background subtraction for fly_001 is verified (windows all in the black margins; spectra show the line-wise projector contamination removed). Moco for fly_001 is clean (sub-voxel jitter, ~8 µm slow z drift, no jumps). The residual 1.8 Hz comb in the bg spectra is the piezo z-sweep; it only becomes a temporal artifact after sub-volume rebinning in `temp_filter`/`tf_to_STA`, and the existing `regress_noise` (`-rn`, red-out-of-green regression per supervoxel) is the pipeline's fix for it, provided channel 1 has been run through postprocess too. Ilana's alternative is an `iirnotch(f0=1.8, Q=30)` on the 10 Hz STA (`notebooks/20250225_notch_filter.ipynb` on `dff`; never made it into a script).

## Shared first step — fix the postprocess path mismatch

`postprocess.py` still loads `fly_N/dff/` and `warp/timestamps_warp.h5` (≈ lines 191, 231, 267, 272) while preprocess writes everything to `func_0/playground/`. Point the default path at `func_0/playground/` before either route.

## Route A — native space (branch `native-space`)

### Claude Code brief

> Add a `--native` flag to `preprocess.sh`/`preprocess.py` and `postprocess.sh`/`postprocess.py` that runs the pipeline in native functional space, skipping the atlas warp.
> 1. Preprocess with `--native`: `blur` reads `func_0/playground/background_subtraction/functional_channel_{ch}_moco.h5` directly; outputs are named `..._moco_native_blurred.h5`, `..._moco_native_blurred_hpf.h5`, `..._moco_native_blurred_hpf_dff.h5` in `func_0/playground/`. `raw_warp` and `timestamp_warp` are not run.
> 2. Postprocess with `--native`: `filter_bins`, `relative_ts`, `temp_filter`, `make_supervoxels`, `build_STA` read the `_native_` dff file and use `func_0/imaging/timestamps.h5` (ms, shape t×z, from `brainsss.load_timestamps`) instead of `warp/timestamps_warp.h5`. Check every worker for hard-coded atlas dims (314×146×91 or 256×128×49) and use the array's own shape.
> 3. `make_supervoxels` must fit per-fly labels (no shared `cluster_labels_best_flies.npy`) and save them under the fly's `func_0/clustering/`.
> 4. Add a native-space `regress_noise` variant that takes one fly's channel-1 and channel-2 STA and calls `brainsss.dual_channel_remove_noise`, writing next to the STAs.
> 5. Do the shared path fix above.
> Constraints: do not touch `dff.py`'s F0 (CLAUDE.md); Python 3.6 syntax; no change to default (non-native) behaviour except the path fix. Finish with a per-file diff summary.

### Run on Sherlock (fly_001, then fly_002)

```bash
sbatch preprocess.sh  --native --blur -hpf -dff --flies 001
sbatch postprocess.sh --native -fb -rts -tf --supervox -STA -f 001 -e OMR        # channel 2
sbatch postprocess.sh --native -fb -rts -tf --supervox -STA -f 001 -e OMR -cc    # channel 1
# then the native regress_noise on the channel pair
```

Check after: the log says each behavior was regressed (not "Skipping ... missing data"); a periodogram of a few supervoxel STAs at fs = 10 Hz shows no 1.8 Hz line.

Note: σ = 2 blur is now in 2.6 µm native pixels, not 2 µm atlas voxels (Bella's ordering).

## Route B — David's meanbrain + bridge (branch `david-meanbrain`)

David's `atlases` folder has been copied (2026-10-28) to
`/oak/stanford/groups/trc/data/Yandan/2P_Imaging/anat_templates/david_atlases/`. It holds
`luke.nii`, `luke_funcres_256x128x49.nii`, `JRC2018_FEMALE_2um_iso.nii.gz`, `JRC2018_FEMALE_38um_iso_16bit.nii`,
`jfrc_2018_rois_improve_reorient_transformed.nii`, and the meanbrain
`YS300YS500_subvolume41_meanbrain/template_syn2_channel_1_centred.nii` (452 MB). No transforms directory is in it.

### Headers (read 2026-10-28)

| file | shape | voxel (µm) | axcodes |
|---|---|---|---|
| `template_syn2_channel_1_centred.nii` | 1024 × 480 × 241 | 0.653, 0.653, 1.0 | R, I, A |
| `luke.nii` (FDA anat) | 1024 × 512 × 256 | 0.65, 0.65, 1.0 | R, I, A |
| fly_001 `anatomy_channel_1_moc_mean_clean.nii` | 1024 × 512 × 241 | header unset (1,1,1); real res from Bruker XML via `res_anat` | R, A, S (identity affine written by brainsss) |

Conclusions: David's template is built on luke's convention (same voxel size, same affine, near-identical grid; "subvolume41" = slight crop), and it's channel 1 (tdTomato), the right channel for the anat moving image. So the z-flip setting that works for luke works for this template (currently `flip_X = flip_Z = False`), and the orientation uncertainty is gone. If the template was constructed from brains already aligned to luke, template→luke is close to identity and a single affine (computable locally from these two files) is the whole bridge. `align_anat.py` discards NIfTI orientation on load, so only the array layout matters, and it matches.

### Remaining questions for David

1. Does a `template_syn2 → luke` (or → JRC2018) transform exist, and where? If not: was the template built from brains already in luke space?
2. Genotype the meanbrain was built from (predicts whether the dim-tdTomato intensity profile will match).

### Claude Code brief

> In `preprocess.py` the a2a block hard-codes `fixed_path` to `20220301_luke_2_jfrc_affine_zflip_2umiso.nii`. Make the template configurable: read `a2a_template`, `a2a_template_resolution`, `a2a_flip_X`, `a2a_flip_Z` from `users/<sunetid>.json`, defaulting to current values.
> Add `scripts/make_2um_template.py`: resample a full-res template (here `david_atlases/.../template_syn2_channel_1_centred.nii`, 0.653×0.653×1.0 µm) to 2 µm iso with `ants.resample_image(..., (2,2,2), use_voxels=False)` and save it as `<name>_2umiso.nii` next to it, so a2a can stay on its existing `iso_2um_*` path and memory footprint.
> Add an optional bridge: if `a2a_bridge_dir` is set in the user JSON (an ANTs fwdtransforms directory from the template to FDA), `raw_warp.py` and `timestamp_warp.py` apply fly→template then template→FDA in one `ants.apply_transforms` call (ANTs applies the transformlist last-to-first — get the order right and add a comment). Also add `scripts/make_bridge.py` that computes template→`luke.nii` (Affine, then SyN) at 2 µm iso and saves the fwdtransforms in the same layout `align_anat.py` uses, for when David has no transform to hand over.
> Add `scripts/check_a2a.py`: Affine-only fly→template on `anatomy_channel_1_moc_mean_clean.nii`, saving an overlay PNG (template grey, warped anat red) at three z-planes, to judge alignment and masking before SyN.
> Check `clean_anat`'s triangle threshold on fly_001's clean anat — with dim tdTomato it may eat brain edge or keep cuticle; if so add an optional hand-mask path (`a2a_mask`) applied to the moving image.
> Constraints: Python 3.6; no behaviour change when the new keys are absent.

### Run

1. `make_2um_template.py` on David's template; `check_a2a.py` on fly_001 → look at the overlay; fix mask if needed.
2. `preprocess.sh --a2a --flies 001` with the new template → overlay again.
3. Bridge: David's if it exists, else `make_bridge.py` (and overlay the warped template on `luke.nii` to judge it).
4. `-rw -tsw --blur -hpf -dff`, then the standard postprocess (channel 2 and `-cc`), `-lt`, `-rn`.

## Order

Route A first (results this week, outputs stay valid as per-fly results). Route B once David answers. If the bridge works, the new flies rejoin the standard cross-fly pipeline; if not, Route B still gives a consistent space across the new-line flies only.
