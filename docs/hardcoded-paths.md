# Hardcoded data paths in `scripts/` and `brainsss/`

These need fixing before the OMR flies move out of `/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20190101_walking_dataset/`. The rule is in `CLAUDE.md` → *Data rules*: no script hardcodes a dataset root, and `dataset_path` always comes from user settings, `fly.json` or a paths config.

Scanned on `YDPlayground` on 2026-10-02 by grepping `scripts/` and `brainsss/` for `/oak/`, `/scratch/`, `/home/users/` and `Brezovec`.

## 1. Must fix: the walking-dataset root is hardcoded

| Location | What | Fix |
|---|---|---|
| `brainsss/brain_utils.py:203` | `warp_STA_brain(STA_brain, fly, fixed, anat_to_mean_type)` sets `dataset_path = '.../Brezovec/2P_Imaging/20190101_walking_dataset'` and reads `<dataset_path>/<fly>/warp/func-to-anat_fwdtransforms_2umiso/` plus the anat-to-mean transforms from there. On the same line it also hardcodes `moving_resolution = (2.611, 2.611, 5)`. | Add a `dataset_path` parameter (or take the fly directory directly). Read `moving_resolution` from the fly's XML (`brainsss.get_resolution`) instead of the constant. |

No script in `scripts/` or `brainsss/` calls `warp_STA_brain`. The only callers are notebooks (see §4). That makes the fix safe, but nothing in the pipeline will catch it breaking.

## 2. Config, not code: update on the move

| Location | What |
|---|---|
| `users/yandanw.json:2-3` | `imports_path` and `dataset_path` point at `Brezovec/2P_Imaging/{imports,20190101_walking_dataset}`. Change these when the data moves. This is the sanctioned place for the path. |
| `users/brezovec.json:2-3` | Bella's own settings. Leave them alone. |

## 3. Other hardcoded data roots (not the walking dataset, but same class of problem)

| Location | Path | Note |
|---|---|---|
| `scripts/individual_clusters.py:51-52` | `/oak/.../Ilana/2P/data/fly_{n}/{dff,warp}` | Ilana's data. The script ignores `dataset_path` entirely. Fix this before using it for OMR. |
| `scripts/fly_builder.py:332` | `/oak/.../data/fictrac/<user>` | FicTrac import root, derived from the user name rather than from settings. |
| `scripts/fly_builder.py:256` | `/oak/.../WBI_shared/visual` | Shared visual-stim folder. |
| `scripts/fly_builder.py:660` | `/oak/.../WBI_shared/master_2P.xlsx` | Shared lab spreadsheet. |
| `scripts/quick_ashley_mean.py:28,35` | `/home/users/brezovec/...`, `/oak/.../Ashley2/imports/...` | One-off script, not called by the orchestrators. Candidate for deletion. |

Commented out or dead code (no action needed, but delete it rather than uncomment it):
- `scripts/fly_builder.py:322` contains a `#fictrac_folder = '.../Brezovec/2P_Imaging/imports/fictrac'` comment.
- `scripts/to_delete/` contains several `Brezovec/...` paths, e.g. `anat_moco.py:39` and `20220222_vol_moco.py:19`.

## 4. Shared templates (fine to keep, listed for completeness)

These point at `WBI_shared/anat_templates/`, a lab-wide location that does not move with your data:

- `brainsss/brain_utils.py:194` (`load_fda_meanbrain`)
- `brainsss/alignment_utils.py:11, 19, 27, 35`
- `brainsss/explosion_plot.py:13, 27`
- `scripts/preprocess.py:547`

They could move into a paths config later, but they are not blockers for the move.

## 5. Outside the scan scope

- **Notebooks:** 8 tracked notebooks in `notebooks/` contain `20190101_walking_dataset`. They will break after the move but are not pipeline code.
- **`user` inference:** `scripts/{pre,post}process.py:41-42` derive the user from `scripts_path.split("/")[3]`. This assumes the repo lives at `/home/users/<sunetid>/...`, and it is how `users/<sunetid>.json` is chosen.
