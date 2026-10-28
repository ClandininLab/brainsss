# Reference: `mc_glom_pipeline` (Minseung Choi) — FicTrac & alignment logic

Read-only survey of `../refs/mc_glom_pipeline`, scoped to the FicTrac and alignment
code only (glomerular-imaging pipeline; the moco / bleedthrough / glom-extraction
parts are out of scope here). Nothing in that repo was modified.

- **Origin:** `https://github.com/minseungchoi/mc_glom_pipeline.git`, branch `main`,
  at `83a8664` (2026-04-19, Minseung Choi) [from code: `git remote -v`, `git log`].
- **Size:** 308 KB, 19 tracked files. Python ≥3.9. Hard dependency on `mcregistration`
  (not installed locally — `import mcregistration` fails here) [from code: `setup.py`].
- Surveyed 2026-10-16.

Tags: **[from code]** = read directly in the file; **[inferred]** = my interpretation.

## TL;DR for the OMR use case

This repo is a **FicTrac launcher plus a raw-dump archiver**, nothing more. It runs the
FicTrac binary on saved ball video and copies the resulting `.dat` matrix verbatim into
a per-day HDF5. There is **no unit conversion, no smoothing, no velocity computation,
no resampling, and no frame-to-imaging-time alignment anywhere in it** [from code:
grep for `timestamp|epoch|resample|interp|velocity|smooth|sync|photodiode|voltage`
across all `*.py`/`*.yaml`/`*.md` returns no such logic]. All of that is delegated
downstream to `visanalysis` / `mcregistration`.

So: useful to me as a pattern for **invoking FicTrac offline and for the camera↔series
directory convention**, and useful as a **column-name reference**. Not a source for
alignment or kinematics code — see the closing list for what still has to come from
elsewhere.

---

## 1. Running FicTrac offline

**File:** `mc_glom_pipeline/fictrac.py` (183 lines, the whole module).
Docstring says it is ported from `glom_project/scripts/run_fictrac.py` [from code:9].

### Module-level constants (all hardcoded)

```python
FICTRAC_BINARY = os.path.expanduser('~/src/fictrac_tw/bin/fictrac')   # :18
VIDEO_FILENAME = 'cam_18384364.mp4'                                   # :19
CONFIG_FILENAME = 'config_L.txt'                                      # :20
```

`cam_18384364` is a camera serial number — one fixed camera. `fictrac_tw` is a local
fork/build of FicTrac, not upstream [inferred from the directory name].

### `discover_fictrac_series(camera_dir, date)` — :23

Walks `{camera_dir}/{date}/`, treats every subdirectory whose name parses as an `int`
as a series number, and sorts them into two lists:

- `ready` — has both `cam_18384364.mp4` and `config_L.txt`;
- `missing_config` — has the video but **no config**.

Directories with no video at all are skipped silently. Returns `([], [])` if the date
directory doesn't exist. The caller (`pipeline.py:651`) prints a warning for every
`missing_config` entry and **does not** create a config for it — those series are
simply dropped from the DAG [from code].

### Config file: **per-series, pre-existing, and destructively rewritten**

This is the part most worth knowing. The config is **not generated** and **not shared** —
`config_L.txt` must already sit in each series directory (presumably dropped there by
the acquisition rig or by hand [inferred]). `run_fictrac` then **edits it in place**
before each run, overwriting the file on disk:

**`_update_config(config_path, video_path)` — :86**

```python
for line in lines:
    stripped = line.strip()
    if stripped.startswith('src_fn'):
        out.append(f'src_fn           : {video_path}\n')
        src_fn_set = True
    elif stripped.startswith('do_display'):
        out.append('do_display       : n\n')
    elif stripped.startswith('sock_host') or stripped.startswith('sock_port'):
        continue
    elif stripped.startswith('c2a_cnrs_xy'):
        continue
    elif stripped.startswith('c2a_cnrs_yz'):
        out.append('c2a_cnrs_xz      : { 410, 161, 172, 156, 172, 478, 409, 470 }\n')
    elif stripped.startswith('c2a_r'):
        out.append('c2a_r            : { 1.491184, 0.569246, 0.568653 }\n')
    elif stripped.startswith('c2a_src'):
        out.append('c2a_src          : c2a_cnrs_xz\n')
    elif stripped.startswith('c2a_t'):
        out.append('c2a_t            : { -0.214502, 0.146568, 25.260717 }\n')
    else:
        out.append(line)

if not src_fn_set:
    out.append(f'src_fn           : {video_path}\n')
```

In plain words, per run it:
1. points `src_fn` at the absolute video path (appending the key if it was absent);
2. forces `do_display : n` (headless);
3. **deletes** `sock_host` / `sock_port` (no live socket output — offline batch mode);
4. **deletes** `c2a_cnrs_xy`, and rewrites the `c2a_cnrs_yz` line as `c2a_cnrs_xz` with
   8 hardcoded corner pixel coordinates;
5. forces the camera-to-animal transform to one fixed calibration: `c2a_src = c2a_cnrs_xz`,
   `c2a_r` (3 rotation params), `c2a_t` (3 translation params, all hardcoded above).

So the per-series file supplies the per-series bits (ball ROI, circumference, fps, …)
while the **camera↔animal geometry is overridden with a single shared calibration** —
i.e. one rig geometry assumed for every fly and every day [from code; the "one rig"
reading is inferred]. Note the asymmetry: the rewrite only fires on lines that already
exist (except `src_fn`), so a config lacking a `c2a_r` line never gets one.

**Caution if I reuse this:** the rewrite is in-place with no backup, and a second run
re-parses its own output. That is idempotent for these particular rules, but any
hand-tuning of the `c2a_*` lines is silently destroyed on every run.

### `run_fictrac(series_dir, fictrac_binary=None, printlog=print)` — :122

Order of operations [from code:146–182]:

1. Resolve `binary = fictrac_binary or FICTRAC_BINARY`, `video_path`, `config_path`.
2. `FileNotFoundError` if binary, video, or config is missing (checked in that order).
3. **Destructive cleanup** — deletes *every* `.dat` and `.log` file in the series dir:
   ```python
   for fn in os.listdir(series_dir):
       if fn.endswith('.dat') or fn.endswith('.log'):
           os.remove(os.path.join(series_dir, fn))
   ```
   No backup, no filename filter. This is what keeps `get_dat_file` unambiguous.
4. `_update_config(config_path, video_path)`.
5. Invoke:
   ```python
   result = subprocess.run(
       [binary, config_path],
       cwd=series_dir,
       capture_output=True,
       text=True,
   )
   ```
   **Config passed positionally**, not via a `-c` flag. `cwd=series_dir` is what makes
   FicTrac drop its outputs next to the video. No `-v`/verbosity, no overrides, no
   timeout, no environment tweaks.
6. `RuntimeError` on non-zero exit, with `result.stderr[:500]` appended.
7. `RuntimeError` if the run succeeded but no `.dat` matched.
8. Returns the `.dat` path.

### Output naming — `get_dat_file(series_dir)` — :70

FicTrac itself chooses the name; the code only discovers it:

```python
video_base = os.path.splitext(VIDEO_FILENAME)[0]
pattern = re.compile(fr'^{re.escape(video_base)}-\d{{8}}_\d{{6}}\.dat$')
```

i.e. `cam_18384364-YYYYMMDD_HHMMSS.dat` — a wall-clock stamp of **when FicTrac ran**,
not when the video was acquired [inferred]. Returns the first `os.listdir` match, which
is filesystem-order and therefore arbitrary if several ever coexist; step 3 above is
what normally guarantees exactly one.

### Video pre-processing

**None.** The raw `.mp4` is handed straight to FicTrac — no crop, resize, de-Bayer,
format conversion, frame-dropping, or ffmpeg pass anywhere in the repo [from code:
`fictrac.py` is the only module touching the video, and it only ever builds its path].

### Where it sits in the DAG

Skimmed `pipeline.py` only, as asked. Two tasks, both thin wrappers:

| Task | Priority | Deps | Executes | Complete when |
|---|---|---|---|---|
| `fictrac_{S}` | 15 | *none* | `run_fictrac(series_dir, fictrac_binary=pcfg.fictrac_binary, printlog=…)` | `get_dat_file(series_dir) is not None` |
| `attach_fictrac_{S}` | 16 | `fictrac_{S}`, `metadata_{S}` | `_attach_fictrac(h5_path, camera_dir, date, series_filter=[S])` under `h5_lock` | `'behavior' in group and 'fictrac_data' in group['behavior']` |

[from code: `pipeline.py:129–130, 389–448`]. Built in `build_day_tasks` at `:646–665`:
it calls `discover_fictrac_series`, makes a `fictrac_{S}` task for every `ready` series,
and makes the `attach_` task **only** if `S` is also a non-anatomical series in the
metadata TSV (`dag_series`, `:656`). So camera series with no matching functional
imaging row get tracked but never attached [from code].

Both are early/cheap by design — priority 15/16 vs. 20–60 for moco/registration/extract.
`attach_fictrac` depends on `metadata_{S}` because that task is what guarantees the
series group exists in the HDF5 [inferred]. Note the priority table in
`.agents/docs/pipeline-dag.md:17` says `attach_fictrac` is priority **45**, while the
code says **16** (`PRIORITY_ATTACH_FICTRAC = 16`) — the doc is stale [from code].

---

## 2. FicTrac I/O

**File:** `mc_glom_pipeline/process_imports.py`, function `_attach_fictrac` — :98.
This single function is the *entire* read path. There is no separate loader module.

### Matching `.dat` files to an imaging series

Purely **by directory name — no timestamp or duration matching at all**:

```python
series_numbers = series_filter or _get_series_numbers_from_h5(h5_path)
for sn in series_numbers:
    series_dir = os.path.join(fictrac_dir, date, str(sn))
    dat_files = glob.glob(os.path.join(series_dir, '*.dat'))
    if not dat_files:
        continue
    fictrac_path = dat_files[0]
```

The convention is that **the camera subdirectory number equals the imaging series
number** [from code]. Series numbers come from the HDF5 itself when no filter is given
(`_get_series_numbers_from_h5`, :53 — walks `Subjects`/`Flies` → `epoch_runs` →
`series_*` and parses the integer). `glob(...)[0]` is unordered, so a stray second
`.dat` would be picked arbitrarily; note this `glob('*.dat')` is **looser** than
`get_dat_file`'s regex, so it would also match a hand-renamed file.

### Which columns are read

**All of them. None are selected, dropped, or reordered.**

```python
df = pd.read_csv(fictrac_path, header=None)
data = df.values
```

Wrapped in `try/except Exception` → warn and `continue` on any read failure (:148).

The 25 column names are declared only as a **label list**, never used for selection:

```python
FICTRAC_HEADER = [
    "frame_count",
    "rel_vec_cam_x", "rel_vec_cam_y", "rel_vec_cam_z",
    "error",
    "rel_vec_world_x", "rel_vec_world_y", "rel_vec_world_z",
    "abs_vec_cam_x", "abs_vec_cam_y", "abs_vec_cam_z",
    "abs_vec_world_x", "abs_vec_world_y", "abs_vec_world_z",
    "integrated_xpos", "integrated_ypos", "integrated_heading",
    "direction", "speed",
    "integrated_x_movement", "integrated_y_movement",
    "timestamp",
    "sequence_number",
    "delta_ts",
    "timestamp_alt",
]
```

Reconciled against the actual column count by truncate-or-pad (:152–155):

```python
num_cols = data.shape[1]
header = FICTRAC_HEADER[:num_cols] if num_cols <= len(FICTRAC_HEADER) else (
    FICTRAC_HEADER + [f"col_{i}" for i in range(len(FICTRAC_HEADER), num_cols)]
)
```

**Caution:** this is a silent, position-based reconciliation. A column-count mismatch
produces confidently wrong names rather than an error. Upstream FicTrac v2 writes 23
columns; this list has 25 and inserts `delta_ts` / `timestamp_alt` near the end, which
suggests the `fictrac_tw` fork emits extra columns [inferred — I could not verify
against a real `.dat`, there is none in the repo]. **Verify column order against my own
`.dat` header before trusting these names for OMR.**

### Unit conversion, smoothing, velocity

**All absent.** Nothing is scaled, filtered, differentiated, or unwrapped. Whatever
units FicTrac emits (radians of ball rotation for the `*_vec_*` triples, radians for
`integrated_heading`, ball-radius units for `integrated_*_movement`) land in the HDF5
as-is [from code: `data = df.values` is the only transformation; unit identification is
inferred from FicTrac's own documented output, not from this repo]. `speed` and
`direction` are FicTrac's own columns, not computed here.

---

## 3. Attachment to HDF5

**File:** `mc_glom_pipeline/process_imports.py::_attach_fictrac` — :137–171.
**CLI:** `mc_glom_pipeline/cli/attach_fictrac.py` → `mcgp-attach-fictrac YYYYMMDD [--config P] [--fictrac-dir D]`.

### Target file

One HDF5 **per day**, not per fly:

```python
date_dashed = f'{date[:4]}-{date[4:6]}-{date[6:8]}'
h5_path = os.path.join(cfg.directories['datafiles'], f'{date_dashed}.hdf5')
```

[from code: `attach_fictrac.py:40–43`, same construction at `process_imports.py:204,250`].
This is a Stimpack/visanalysis datafile that already exists; the CLI exits 1 if it does
not. `process_imports` backs it up to `../RawDataFiles/{date}.hdf5` before touching it,
but only if that directory already exists and the backup is absent (:258–264).

### Group path

Via `metadata.py::_find_series_group(f, series_number)` — :27:

```
{Subjects|Flies}/{subject_id}/epoch_runs/series_{NNN:03d}
```

Both top-level names are tried, and every subject is scanned, returning the first match
or `None`. So series numbers are assumed globally unique within a day's file [inferred].

### What gets stored

```python
if 'behavior' not in group:
    group.create_group('behavior')
behavior = group['behavior']

if 'fictrac_data' in behavior:
    del behavior['fictrac_data']

dset = behavior.create_dataset('fictrac_data', data=data)
dset.attrs['fictrac_data_header'] = np.array(header, dtype='S')
```

| | |
|---|---|
| **Key** | `{Subjects\|Flies}/{subj}/epoch_runs/series_{NNN:03d}/behavior/fictrac_data` |
| **Shape** | `(n_frames, n_cols)` — exactly `pd.read_csv(...).values`, so `n_cols` is whatever the `.dat` had (~23–25) |
| **dtype** | float64 (pandas default for an all-numeric frame); `frame_count` / `sequence_number` are therefore stored as floats [inferred] |
| **Attribute** | `fictrac_data_header` on the dataset — fixed-length byte strings (`dtype='S'`), one per column; decode with `.astype(str)` on read |
| **Compression / chunking** | none |

No other FicTrac-derived keys are written. Nothing is written at the series-group or
file level by this function.

### Idempotency and concurrency

- Re-running deletes and recreates the dataset, so it is safely repeatable — but HDF5
  does not reclaim freed space, so repeated re-runs **grow the file** [inferred from
  standard h5py behaviour].
- File opened `'a'`. In the DAG path every call is wrapped in a `threading.Lock`
  (`h5_lock`) shared with the metadata tasks, and `check_complete` takes the same lock
  for its read [from code: `pipeline.py:414–440`]. The bulk `process_imports` path and
  the standalone CLI take no lock — they assume sole access [inferred].
- Counts attachments and logs either `"FicTrac: N series attached"` or
  `"FicTrac: no .dat files found in {fictrac_dir}/{date}/"` (:173–176).

### Call sites

1. **`process_imports(date, cfg, keep_import_dir=True)`** — :179, step (4) of four:
   copy `T*`/`Z*` series out of `imports/`, attach Bruker metadata via visanalysis,
   init series attributes (`include_in_analysis`, `anatomical_brain`, `series_notes`),
   then attach FicTrac for **all** series in the file.
2. **`attach_fictrac_{S}` DAG task** — per-series via `series_filter=[S]`.
3. **`mcgp-attach-fictrac` CLI** — all series for a date; note it loads `MCRConfig`
   directly, *not* `PipelineConfig`, so it never reads this repo's own `config.yaml`
   [from code: `attach_fictrac.py:18,39`]. It also imports `DataPaths` without using it.

---

## 4. Timing / alignment

**There is none in this repo.** No function maps FicTrac frames to imaging volume
times, and nothing references stimulus epochs, triggers, photodiode traces, or voltage
recordings [from code: exhaustive grep over all `*.py`/`*.yaml`/`*.md` for
`timestamp|frame_time|stim|epoch|resample|interp|velocity|smooth|sampling_rate|photodiode|sync|voltage`
— every hit is one of: the `FICTRAC_HEADER` names, the literal `epoch_runs` path
segment, log filenames, or BTS's unrelated `sampling_rate`].

Two things that look like timing but are not:

- **`bts.sampling_rate: 7.22` Hz** (`config.yaml:13`) is the imaging frame rate used
  *only* for bleedthrough-subtraction spectral QC (`bleedthrough.py:325,385`). It is
  never used to time-base behavior. Still a useful incidental datum: the glom rig runs
  at ~7.22 volumes/s [from code].
- **The `timestamp` / `delta_ts` / `timestamp_alt` columns** are preserved inside
  `fictrac_data`, so the camera's own clock survives into the HDF5 — but nothing reads
  or interprets them here.

**Alignment is delegated.** The mechanism is co-location, not computation: a separate
step writes the imaging time base into the *same* HDF5 series group —

```python
# process_imports.py:42–50
from visanalysis.plugin import bruker
plug = bruker.BrukerPlugin()
plug.attachData(experiment_name, h5_path, imaging_dir, series_numbers=None)
```

`BrukerPlugin.attachData` parses the Bruker XML and attaches imaging/stimulus metadata
(frame times, epoch parameters) under the same `epoch_runs/series_NNN` group [inferred —
`visanalysis` is not available locally, so I could not read what it writes]. On
`ImportError` it warns and skips, so the pipeline tolerates visanalysis being absent.

Net effect: this repo's contract is *"raw behavior matrix and imaging metadata live in
one series group; the analysis layer joins them."* Any frame↔volume interpolation lives
in `visanalysis` / `mcregistration` / Minseung's downstream analysis code, none of which
is in this repo.

---

## 5. Config — every FicTrac/behavior setting and hardcoded value

### `config.yaml` (19 lines, repo root) — the only FicTrac-relevant section

```yaml
fictrac:
  binary: /home/minseung/src/fictrac_tw/bin/fictrac
  video_filename: cam_18384364.mp4
  config_filename: config_L.txt
```

### `mc_glom_pipeline/config.py` — `PipelineConfig`

Layered on top of `mcregistration`'s `MCRConfig`: loads this repo's `config.yaml` for
pipeline-specific settings, and **delegates all directory resolution** to MCRConfig via
`PipelineConfig.directories → self.mcr.directories` (:96–98). Exposed FicTrac
properties (:80–93):

| Property | YAML key | Default in code |
|---|---|---|
| `fictrac_binary` | `fictrac.binary` | `~/src/fictrac_tw/bin/fictrac` (`expanduser`'d) |
| `fictrac_video_filename` | `fictrac.video_filename` | `cam_18384364.mp4` |
| `fictrac_config_filename` | `fictrac.config_filename` | `config_L.txt` |

### ⚠️ Two of those three config keys are dead

**`fictrac_video_filename` and `fictrac_config_filename` have no effect on behaviour.**
`fictrac.py` reads its own module constants `VIDEO_FILENAME` / `CONFIG_FILENAME` in all
four places that need them (:56–57, :78, :147–148), and neither `run_fictrac` nor
`discover_fictrac_series` accepts an override parameter. `pipeline.py` threads through
**only** `fictrac_binary` (`:659`); the one use of `pcfg.fictrac_config_filename` is
inside a warning *message string* (`:653`). So editing those YAML keys changes a log
line and nothing else [from code: verified by grepping every occurrence of all four
names]. If I port this, make them real parameters.

### Behavior-directory resolution

`cfg.directories['behavior']`, with the inline default `~/data/BrukerCamera` repeated in
**five** places — `process_imports.py:201`, `pipeline.py:392`, `:419`, `:648`,
`cli/attach_fictrac.py:50` (plus `transfer.py:106` for the oak pull). `mcgp-attach-fictrac`
can override it with `--fictrac-dir`. Layout assumed everywhere:

```
{behavior}/{YYYYMMDD}/{series_num}/cam_18384364.mp4
{behavior}/{YYYYMMDD}/{series_num}/config_L.txt
{behavior}/{YYYYMMDD}/{series_num}/cam_18384364-YYYYMMDD_HHMMSS.dat
{behavior}/{YYYYMMDD}/{series_num}/*.log
```

`transfer.py:102` pulls this tree from `{oak_base}/BrukerCamera` [from code].

### Full hardcoded-value inventory

| Value | Where | What it is |
|---|---|---|
| `~/src/fictrac_tw/bin/fictrac` | `fictrac.py:18` | binary default (overridable) |
| `/home/minseung/src/fictrac_tw/bin/fictrac` | `config.yaml:17` | binary, absolute, Minseung's home |
| `cam_18384364.mp4` | `fictrac.py:19` | camera serial / video name (**not** overridable) |
| `config_L.txt` | `fictrac.py:20` | per-series config name (**not** overridable) |
| `~/data/BrukerCamera` | ×5 inline defaults | behavior root fallback |
| `c2a_cnrs_xz : { 410, 161, 172, 156, 172, 478, 409, 470 }` | `fictrac.py:105` | 8 corner pixel coords, camera→animal |
| `c2a_r : { 1.491184, 0.569246, 0.568653 }` | `fictrac.py:107` | camera→animal rotation |
| `c2a_t : { -0.214502, 0.146568, 25.260717 }` | `fictrac.py:111` | camera→animal translation |
| `c2a_src : c2a_cnrs_xz` | `fictrac.py:109` | forces the xz corner source |
| `do_display : n` | `fictrac.py:99` | headless |
| 25-name `FICTRAC_HEADER` | `process_imports.py:116–130` | column labels |
| `-\d{8}_\d{6}\.dat` | `fictrac.py:79` | `.dat` name pattern |
| `7.22` Hz | `config.yaml:13`, `config.py:73`, `bleedthrough.py:325`, `pipeline.py:199` | imaging rate — **BTS QC only**, not behavior |
| `/run/media/minseung/data2/.../MC Imaging log - MvF exp.tsv` | `config.yaml:7` | metadata TSV, absolute local path |
| `/home/minseung/venv/visanalysis/bin/python` | `.agents/rules/AGENTS.md:51` | the venv the pipeline runs in |

### `.agents/` notes

- `.agents/rules/AGENTS.md` (51 lines, `trigger: always_on`, pulled in by a one-line
  `CLAUDE.md` that just does `@.agents/rules/AGENTS.md`) — module map, CLI list, and the
  per-day task DAG with priorities.
- `.agents/docs/pipeline-dag.md` (60 lines) — task table (type, priority, deps,
  execution), priority-scheduling rationale, per-task completeness checks, logging paths,
  and the metadata-TSV columns used. Neither file documents any FicTrac post-processing,
  units, or alignment — consistent with there being none.
- Two stale spots to not trust: `pipeline-dag.md:17` lists `attach_fictrac` at priority
  45 (code says 16), and `README.md:158` says "No separate config file needed" although
  `config.py` + `config.yaml` exist [from code].

---

## What I'd still need from `mcregistration` / `visanalysis`

> **Update 2026-10-16:** `visanalysis` has since been surveyed — see
> [visanalysis.md](visanalysis.md), whose closing section resolves items 1, 2, 3 and 5 below,
> answers 4 for the 40-hour rig only (the Bruker path writes no camera strobes and no unix
> anchor), and confirms 6 and 7 are in neither repo. It also documents a verified blocker: the
> `dtype='S'` header written at `process_imports.py:169` makes visanalysis's own FicTrac readers
> raise. Read the list below as the original question set, not as still-open.

Neither package is in `../refs/` and `mcregistration` is not importable here, so all of
the following is unverified and would have to be read from those sources:

1. **The imaging time base.** What `visanalysis.plugin.bruker.BrukerPlugin.attachData`
   actually writes into `epoch_runs/series_NNN` — the key holding per-volume frame
   times, its units (s vs. ms), and its origin (first frame vs. series trigger). This is
   the single most important missing piece.
2. **The frame↔volume join itself.** Whatever downstream code pairs `fictrac_data` rows
   with imaging volumes: nearest-neighbour vs. interpolation, which FicTrac column
   provides the clock (`timestamp` vs. `delta_ts` vs. `timestamp_alt`), and how the two
   clocks are zeroed against each other. Nothing in this repo does it.
3. **Stimulus epoch structure.** How `epoch_runs` / `epoch_parameters` encode trial
   onsets and stimulus parameters — needed to cut OMR epochs.
4. **Camera–imaging synchronisation.** Whether the ball camera is hardware-triggered off
   the scope (making frame counts commensurate) or free-running (making the timestamp
   columns load-bearing). This repo's number-matched directory convention implies they
   are started together, but nothing enforces or records it.
5. **FicTrac column count and order for the `fictrac_tw` fork** — to validate the 25-name
   header against a real `.dat`, and to confirm `rel_vec_*` units (radians/frame of ball
   rotation) and ball radius, before converting anything to mm/s or deg/s.
6. **`MCRConfig` / `DataPaths`** — the `directories` schema (`behavior`, `datafiles`,
   `bruker_raw`, `bts`) and `DataPaths.datafile()`, if I want to reuse the path-resolution
   layer rather than my own `users/<sunetid>.json`.
7. **Any kinematics the lab applies downstream** — smoothing kernel/window, velocity
   differentiation, and the stationary/moving threshold. Relevant to me because my dF/F
   F0 maps are behavior-state-matched (`dff_grey/F0_stationary`, `F0_moving`), and
   matching the lab's threshold definition would make results comparable. Not here.
