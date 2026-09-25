# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`brainsss` is a Python wrapper around Slurm for preprocessing and analyzing whole-brain volumetric 2-photon imaging data from *Drosophila* on Stanford's Sherlock cluster. Nothing here runs meaningfully on a laptop — the pipeline scripts assume Slurm (`sbatch`/`sacct`), Linux-only `fcntl` locking, `/oak/stanford/groups/trc/...` data paths, and Sherlock module loads. Local work is limited to editing code and reading notebooks.

## Commands

Everything is launched from `scripts/` (the orchestrators use `$PWD` to locate `com/`, `logs/`, and `../users/`):

```shell
sbatch preprocess.sh --build_flies 20220307        # build flies from imports, then run enabled steps
sbatch preprocess.sh --moco --flies fly_006,fly_007
sbatch preprocess.sh -bg -rw -tsw --blur -hpf -dff --flies 240
sbatch postprocess.sh -post -f 240 -e OMR          # postprocess with an event label
sbatch postprocess.sh -fb -rts -tf --supervox -STA -f 240
sbatch motion_correction.sh <dir> <brain_master> [brain_mirror]   # standalone moco, no naming scheme
sbatch watcher.slurm                               # resubmits postprocess every 10 min if not running
```

Useful flags: `--flies` accepts a comma list with or without the `fly_` prefix; `-best`/`--best_flies` uses the hardcoded fly list in `preprocess.py`/`postprocess.py`; `--redo` forces recomputation; `-cc`/`--channel_change` switches the processed channel from 2 (default) to 1; `-d func|anat` restricts the directory type.

Install (on Sherlock): `ml python/3.6; pip install -e . --user`, plus `pyfiglet psutil lxml openpyxl opencv-python-headless antspyx==0.3.2`.

Tests: `pytest tests/` — the only test is an import smoke test (`tests/test_imports.py`), run from the repo root or `tests/`.

Monitoring a run: `scripts/logs/<YYYYmmdd-HHMMSS>.txt` is the combined log for one orchestrator invocation; `scripts/logs/mainlog.out` catches errors that occur before logging is set up; `scripts/com/<jobid>.out` is a worker's stdout, which is also how workers return values.

## Architecture

**Two-layer job model.** `preprocess.sh` / `postprocess.sh` are thin arg parsers that pack every flag into one JSON string and hand it to `preprocess.py` / `postprocess.py`. Those Python orchestrators run on a single core and do no computation — they only decide which steps to run, build an `args` dict per step, call `brainsss.sbatch(...)` to submit a worker script, and block on `brainsss.wait_for_job(...)`. Each worker in `scripts/` is a standalone `main(args)` invoked as `python3 <script>.py '<json>'` and unpacks its arguments by key.

**Return values travel through stdout.** `wait_for_job` polls `sacct` and, on completion, reads `com/<jobid>.out` and returns its contents as a string. `fly_builder.py` uses this to hand back the built `func:`/`anat:` paths, which `preprocess.py` parses line by line.

**Logging is shared and stolen.** All processes append to one logfile via `brainsss.Printlog(logfile).print_to_log` (flock-protected), and `sys.stderr` is redirected to the same file. Inside workers and orchestrators, **use `printlog(...)`, not `print(...)`** — `print` output goes to the `com/` file and is treated as the job's return value.

**Adding a pipeline step** means touching four places: a `--flag` case in the `.sh` parser, the flag in that script's `ARGS` JSON blob, a `settings.get(...)` default plus an `if args["FLAG"] != ""` override in the orchestrator, and an `if <step>:` block that submits the new worker with explicit `time`/`cpus`/`mem`.

**Settings.** `users/<sunetid>.json` holds `imports_path`, `dataset_path`, `scratch_path`, `later_path`, plus `"True"`/`"False"` strings toggling steps. The user is inferred from `scripts_path.split("/")[3]`, so the repo must live at `/home/users/<sunetid>/...` on Sherlock. Step toggles in the JSON only apply when the orchestrator runs in bulk mode (`--build_flies` for preprocess, `-post` for postprocess); otherwise only explicit CLI flags enable steps.

**Package vs. scripts.** `brainsss/` is the importable library — `utils.py` (Slurm submission, logging, timestamps/resolution parsing from Bruker XML, h5 chunked saving), `brain_utils.py` (STA construction, supervoxel↔full-res mapping, ANTs warping, butterworth filters, dF/F helpers), `alignment_utils.py` + `explosion_plot.py` (template brains, ROI atlas, explosion-plot rendering), `fictrac.py` (behavior traces), `visual.py` (photodiode/visual-stim metadata). `brainsss/__init__.py` star-imports all of them, so everything is reachable as `brainsss.<fn>`. Several of these functions hardcode `/oak/stanford/groups/trc/data/WBI_shared/anat_templates/...` paths.

## Data layout and filename chain

Per-fly directories under `dataset_path` follow `fly_NNN/{func_0,anat_0,warp,temp_filter,STA}/`, with `func_0/{imaging,fictrac,moco,playground}/`. Steps are chained by filename suffix, and each worker reconstructs the expected input name from `ch_num` — so renaming or reordering a step breaks downstream scripts:

```
functional_channel_{1,2}.nii
  → moco/functional_channel_N_moco.h5                       (motion_correction)
  → playground/..._moco.h5 (background-subtracted)           (background_subtraction)
  → ..._moco_warp.h5                                        (raw_warp, into template space)
  → ..._moco_warp_blurred.h5                                (blur)
  → ..._moco_warp_blurred_hpf.h5                            (butter_highpass)
  → ..._moco_warp_blurred_hpf_dff.h5                        (dff)
  → temp_filter/..._hpf_dff_filtered_{behavior}.h5          (temp_filter)
  → STA/stepsize_{N}_STA_{behavior}.h5                      (build_STA)
```

Postprocessing stages toward group analysis: `filter_bins` → `relative_ts` → `temp_filter` → `make_supervoxels` → `build_STA` / `tf_to_STA` → `later_transfer` (copies to `later_path`) → `regress_noise` / `supercluster` / `get_ind_vox` / `individual_clusters`. Cross-fly stages (`tf_to_STA`, `later_transfer`, `regress_noise`, `supercluster`, `individual_clusters`) read from `later_path` rather than per-fly directories, and large intermediates are staged through `scratch_path` to avoid hammering Oak.

The `--events` / `-e` flag is a suffix that selects an event-times pickle (`{event}_event_times_split_dic.pkl` vs. the unlabeled default) and disambiguates output filenames — used to run the same pipeline for different behavioral paradigms (e.g. OMR).

## Conventions and gotchas

- Python 3.6 syntax only (Sherlock module `py-*_py36`); the module string is duplicated at the top of both orchestrators.
- The `preprocess.py` / `postprocess.py` step blocks are inconsistently indented (some `if` bodies use 3-space `for` loops); match the surrounding block rather than reformatting.
- `sbatch(...)` defaults are per-call — memory-heavy workers pass explicit `mem='250GB'` and `cpus=32`. `nice=True` and `nodes=2` are set at the top of the orchestrators.
- Hardcoded fly lists live inline in the `BEST_FLIES` branch of both orchestrators.
- `notebooks/` is a chronological scratch/figure archive (`YYYYMMDD_topic.ipynb`), not library code — figure notebooks (`fig1_images`, `fig3_FINAL`, …) are the paper-facing consumers of the pipeline outputs.
