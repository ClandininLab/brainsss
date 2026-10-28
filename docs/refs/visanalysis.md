# Reference: `visanalysis` (ClandininLab) — imaging timebase & stimulus/behavior alignment

Read-only survey of `../refs/visanalysis`, scoped to the two things needed for whole-brain OMR
analysis: (1) how the imaging timebase is read from Bruker XML and written to HDF5, and (2) how
stimulus epochs, photodiode traces, and FicTrac behavior are timed and joined to it. Nothing in
that repo was modified.

- **Origin:** `https://github.com/ClandininLab/visanalysis.git`, branch `master`,
  at `ec4ade7` (2026-10-09, David Mac) [from code: `git remote -v`, `git log`].
- **Size:** 1.8 MB, 26 tracked files, ~7.5k lines of Python.
- Surveyed 2026-10-16.

Tags: **[from code]** = read directly in the file; **[verified]** = I ran it to confirm;
**[inferred]** = my interpretation.

## TL;DR — the answer to "where is the alignment code?"

It exists, and this is the repo that holds it. The design is **one shared seconds-timebase per
series, with everything re-zeroed to the start of that series' acquisition**:

| Signal | HDF5 location | Units / origin |
|---|---|---|
| Imaging volume times | `acquisition/time_points` | sec, 0 = series start |
| Per-z-slice frame times | `acquisition/frame_times` | sec, 0 = series start, shape `(t, z)` |
| Photodiode / frame monitor | `stimulus_timing/frame_monitor` + `time_vector` | sec, 0 = series start |
| Camera exposure onsets | `behavior/<cam>/exposure_onset` | sec, 0 = block start (40hr rig only) |
| FicTrac raw matrix | `behavior/fictrac_data` | FicTrac's own clock, **ms** |

Stimulus epochs are then *derived* from the photodiode trace (or from stimpack unix timestamps),
and the join to imaging is a **plain boolean window selection on that shared timebase — no
interpolation, no resampling** (`getEpochResponseMatrix`). Behavior is joined the same way, but
`getBehaviorData` returns per-epoch FicTrac chunks rather than anything resampled onto volumes.

**Three cautions up front**, each detailed below:
1. There are **three different `getStimulusTiming` implementations with two incompatible time
   origins** (seconds-from-series-start vs. absolute unix). Picking the wrong DataObject class
   silently produces garbage.
2. `getEpochResponseMatrix` zeroes its `time_vector` at **epoch start** (= `pre_time` before
   stim onset); `getBehaviorData` zeroes its timestamps at **stim onset**. Combining the two
   outputs naively offsets behavior from imaging by `pre_time`.
3. Minseung's header-writing convention (`dtype='S'`) **breaks** visanalysis's FicTrac readers.
   Verified empirically below — this is the concrete blocker between the two repos.

---

## 1. Imaging timebase

### Entry point: `attach_data.py` (29 lines, repo root)

A bare three-argument script, no argparse:

```python
experiment_filepath = sys.argv[1]
data_directory = sys.argv[2]
rigID = sys.argv[3]

if rigID == 'Bruker':
    from visanalysis.plugin import bruker
    plug = bruker.BrukerPlugin()
...
experiment_file_name = os.path.split(experiment_filepath)[-1].split('.')[0]
plug.attachData(experiment_file_name, experiment_filepath, data_directory)
```

[from code: `attach_data.py:8–27`]. Note `rigID` only dispatches `'Bruker'` and `'AODscope'` —
the `fortyhourfitness` / `twentyfourhourfitness` plugins are **not reachable from this script**;
they are driven by `rig_specific/move_and_attach_data.py` instead [from code]. `experiment_file_name`
is the HDF5 basename, which is also assumed to be the acquisition date in `YYYY-MM-DD` form
[inferred from its use in filename construction below].

### `BrukerPlugin.attachData` — `visanalysis/plugin/bruker.py:98`

Loops over every series in the HDF5 and, for each, reconstructs the Bruker directory basename
from the date and series number:

```python
file_basename = 'TSeries-' + experiment_file_name.replace('-', '') + '-' + ('00' + str(series_number))[-3:]
metadata_filepath = os.path.join(data_directory, file_basename)
if os.path.exists(metadata_filepath + '.xml'):
    v_rec_suffix = '_Cycle00001_VoltageRecording_001'
    voltage_basepath = os.path.join(data_directory, file_basename + v_rec_suffix)
    voltage_recording, time_vector, sample_rate = getVoltageRecording(voltage_basepath)
    frame_monitor = voltage_recording   # TODO: pick frame monitor(s) out by name
    response_timing = getAcquisitionTiming(metadata_filepath)
    metadata = getMetaData(metadata_filepath)
```

So the naming contract is `TSeries-YYYYMMDD-NNN.xml` plus
`TSeries-YYYYMMDD-NNN_Cycle00001_VoltageRecording_001.{xml,csv}` in `data_directory`
[from code:101–107]. **Hardcoded:** the `_Cycle00001_..._001` suffix (only cycle 1, only
recording 1), and the `('00' + str(n))[-3:]` zero-pad, which silently truncates for series
≥ 1000 [from code].

Then the write:

```python
stimulus_timing_group = epoch_run_group.require_group('stimulus_timing')
h5io.overwriteDataSet(stimulus_timing_group, 'frame_monitor', frame_monitor)
h5io.overwriteDataSet(stimulus_timing_group, 'time_vector', time_vector)
stimulus_timing_group.attrs['sample_rate'] = sample_rate

acquisition_group = epoch_run_group.require_group('acquisition')
h5io.overwriteDataSet(acquisition_group, 'time_points', response_timing['stack_times'])
if 'frame_times' in response_timing:
    h5io.overwriteDataSet(acquisition_group, 'frame_times', response_timing['frame_times'])
acquisition_group.attrs['sample_period'] = response_timing['sample_period']
for key in metadata:
    acquisition_group.attrs[key] = metadata[key]
```

[from code:122–133]. If the `.xml` is absent it prints a warning and **skips the series
silently** — no exception [from code:136–137].

### `getAcquisitionTiming(filepath)` — `bruker.py:310` ← **this is the timebase**

Parses the PrairieView `.xml` and reads the `relativeTime` attribute off each `<Frame>`:

```python
if root.find('Sequence').get('type') == 'TSeries ZSeries Element':
    # volumetric xyz time series
    num_t = len(root.findall('Sequence'))
    num_z = len(root.find('Sequence').findall('Frame'))
    frame_times = np.ndarray(shape=(num_t, num_z), dtype=float)
    frame_times[:] = np.nan
    for t_ind, t_step in enumerate(root.findall('Sequence')):
        for z_ind, z_step in enumerate(t_step.findall('Frame')):
            frame_times[t_ind, z_ind] = z_step.get('relativeTime')

    stack_times = frame_times[:, 0]
    sample_period = np.mean(np.diff(stack_times))

    response_timing = {'frame_times': frame_times,
                       'stack_times': stack_times,
                       'sample_period': sample_period}

elif root.find('Sequence').get('type') == 'TSeries Timed Element':
    # Single-plane, xy time series
    stack_times = []
    for frame in root.find('Sequence').findall('Frame'):
        stack_times.append(float(frame.get('relativeTime')))
    stack_times = np.array(stack_times)
    sample_period = np.mean(np.diff(stack_times))
    response_timing = {'stack_times': stack_times, 'sample_period': sample_period}
```

In plain words:

- **For a volume series** (`TSeries ZSeries Element`): each `<Sequence>` is one volume, each
  `<Frame>` inside it one z-plane. `frame_times` is the full `(n_volumes, n_z)` grid of
  per-plane times; `stack_times` is **column 0 — the time of the first z-plane of each
  volume** [from code:334]. So a volume's nominal time is its *bottom slice's* time, not its
  centre. Within-volume z-stagger is thrown away at this level but preserved in `frame_times`.
- **For a single plane** (`TSeries Timed Element`): one `<Sequence>`, each `<Frame>` is a
  timepoint.
- `sample_period` = `mean(diff(stack_times))` — a **nominal** uniform period, which is what
  all downstream epoch-window arithmetic actually uses. Real jitter is discarded [from code].

**Units and origin.** `relativeTime` is seconds, relative to the start of that series'
acquisition — so `time_points[0]` is ~0, not a wall-clock or unix time [inferred: the name plus
the fact that `stack_times` is used directly against photodiode `time_vector`, which is itself
`Time(ms)/1e3` from sample 0 of the voltage recording]. **Both clocks are zeroed at the start
of the same Bruker series, which is what makes the join work without any offset term.**

**Unhandled case:** `getAcquisitionTiming` has no `else` branch. A `ZSeries` (anatomical stack)
reaches it and raises `UnboundLocalError` on `response_timing` [from code:324–354]. By contrast
`getMetaData` *does* handle `ZSeries` (`t_dim=1`) and prints a warning for anything else
[from code:289–299]. So anatomical series must not be passed through `attachData`.

### `getVoltageRecording(filepath)` — `bruker.py:212`

Reads the paired voltage-recording `.xml` (for sample rate and channel names) plus `.csv` (for
the traces):

```python
rate_node = root.find('Experiment').find('Rate')
sample_rate = int(rate_node.text)

active_channels = []
for signal_node in list(root.find('Experiment').find('SignalList')):
    if signal_node.find('Enabled').text == 'true':
        active_channels.append(signal_node.find('Name').text)

data_frame = pd.read_csv(filepath + '.csv')
# if the last column's dtype differs from the first, the last line was truncated
if data_frame.dtypes.iloc[-1] != data_frame.dtypes.iloc[0]:
    data_frame = pd.read_csv(filepath + '.csv', skipfooter=1, engine='python')

time_vector = data_frame.get('Time(ms)').values / 1e3  # ->sec

frame_monitor = []
for ac in active_channels:
    frame_monitor.append(data_frame.get(' ' + ac).values)
frame_monitor = np.vstack(frame_monitor)
```

Points worth knowing [from code:219–247]:
- `sample_rate` is `int(...)` of the XML `<Rate>` — Hz, truncated.
- **`Time(ms)` is divided by 1e3 → the stored `time_vector` is in SECONDS.** Same origin as
  `relativeTime` (both start at 0 at series start).
- Column lookup is `' ' + channel_name` — a **hardcoded leading space**, matching PrairieView's
  CSV header spacing. A rig whose CSV lacks that space yields `None` → `np.vstack` fails.
- The truncated-last-line heuristic is a dtype comparison, so it only fires when the partial
  line makes the last column non-numeric [from code:237–238].
- **All enabled channels go in as `frame_monitor`** — the `# TODO: pick frame monitor(s) out of
  voltage recording traces based on name` at `bruker.py:109` is unresolved, so channel
  *identity* is lost at write time and recovered downstream only by positional heuristics
  ("take the last two"). This is the weakest link in the Bruker path [from code].

### Readers

- **`ImagingDataObject.getResponseTiming()`** — `imaging_data.py:288`: returns
  `{'time_vector': acquisition/time_points, 'sample_period': acquisition.attrs['sample_period']}`,
  both documented `# sec` [from code:300–308].
- **`ImagingDataObject.getVolumeFrameOffsets()`** — `imaging_data.py:311`: per-z-slice temporal
  offset within a volume, computed **once from volume 0 only**:
  ```python
  frame_offsets = np.zeros(frame_times.shape[1])
  for frame_ind in range(0, frame_times.shape[1]):
      # offsets are consitent for every single volume, so we only need to do this calculation once
      frame_offsets[frame_ind] = frame_times[0, frame_ind] - frame_times[0, 0]
  ```
  This is the hook for z-stagger correction — **it is computed but never used anywhere in the
  repo** except being called for its own sake in `examples/plotting_responses.py:26`
  [from code: grep for `getVolumeFrameOffsets`]. If OMR analysis cares about within-volume
  z-timing (and for a slow volume rate it should), applying this offset is on me.
- **`getAcquisitionMetadata()`** — `imaging_data.py:237`: all the `PVStateShard` attrs,
  including `image_dims` as `[x, y, z, t, c]` [from code: `bruker.py:301`]. Note every XML
  value is stored as the **raw string** from the attribute — `getMetaData` never casts, so
  e.g. `framePeriod` comes back as `str` [from code:264–281].

---

## 2. Stimulus timing

### `ImagingDataObject.getStimulusTiming()` — `imaging_data.py:329` (the photodiode path)

Logic, in order [from code:329–542]:

1. Load `frame_monitor`, `time_vector`, `sample_rate` from `stimulus_timing`.
2. **If more than two channels, keep the LAST two** — positional, because channel names were
   never stored:
   ```python
   if len(frame_monitor_channels) > 2:
       frame_monitor_channels = frame_monitor_channels[-2:]
   ```
3. `minimum_epoch_separation = 0.9 * (pre_time + tail_time) * sample_rate` — the gap, in
   datapoints, that separates one epoch's frame flips from the next. **Requires `pre_time` and
   `tail_time` to be scalar run parameters**, and assumes the inter-stimulus interval is at
   least 90% of their sum.
4. Per channel: 4th-order Butterworth low-pass, then shift/scale the trace onto `[0, 1]`:
   ```python
   b, a = signal.butter(4, 10 * self.command_frame_rate, btype="low", fs=sample_rate)
   frame_monitor = signal.filtfilt(b, a, frame_monitor)
   frame_monitor = frame_monitor - np.min(frame_monitor)
   frame_monitor = frame_monitor / np.max(frame_monitor)
   ```
   Normalization is **whole-trace min/max**, so a single voltage spike or baseline drift
   rescales everything and moves the effective threshold [inferred].
5. Threshold crossings in both directions give frame flips:
   ```python
   V_orig = frame_monitor[0:-2]; V_shift = frame_monitor[1:-1]
   ups   = np.where(np.logical_and(V_orig <  self.threshold, V_shift >= self.threshold))[0] + 1
   downs = np.where(np.logical_and(V_orig >= self.threshold, V_shift <  self.threshold))[0] + 1
   frame_times = np.sort(np.append(ups, downs))
   ```
6. **Epoch boundaries are gaps in the flip train**:
   ```python
   stimulus_start_frames = np.append(0, np.where(np.diff(frame_times) > minimum_epoch_separation)[0] + 1)
   stimulus_end_frames   = np.append(np.where(np.diff(frame_times) > minimum_epoch_separation)[0], len(frame_times) - 1)
   stimulus_start_times  = frame_times[stimulus_start_frames] / sample_rate  # datapoints -> sec
   stimulus_end_times    = frame_times[stimulus_end_frames] / sample_rate
   ```
   Note index 0 is **always** a stimulus start and the last flip **always** an end — so the
   function returns at least one "epoch" even from pure noise [from code].
7. Dropped-frame detection: any inter-flip interval differing from `ideal_frame_len =
   sample_rate / command_frame_rate` by more than `frame_slop` datapoints is called a drop and
   excluded from the measured frame-rate estimate.
8. Returns **one channel's dict**: `{'stimulus_start_times', 'stimulus_end_times',
   'dropped_frame_times', 'frame_rate'}`, selected by `self.timing_channel_ind`
   [from code:542].

**Units:** `stimulus_start_times` / `stimulus_end_times` are **seconds from series start** —
same origin as `acquisition/time_points`. That is the whole basis of the join.

### The two alternative `getStimulusTiming` implementations

This is the biggest trap in the repo. Three classes, two incompatible time origins:

| Class | File | Timing source | Time origin |
|---|---|---|---|
| `ImagingDataObject` | `imaging_data.py:329` | photodiode threshold crossings | **sec from series start** |
| `TwentyFourHourDataObject` | `twentyfourhourfitness.py:86` | stimpack trial **unix** timestamps | **absolute unix sec** |
| `FortyHourDataObject` | `fortyhourfitness.py:908` | `find_peaks` on square photodiodes; falls back to the 24hr unix path when `use_square_photodiodes=False` | sec from block start, or unix |

`TwentyFourHourDataObject.getStimulusTiming` takes no photodiode at all:

```python
if h5io.getTrialStartUnixTime(epoch.attrs) is not None:
    epoch_unix_time = h5io.getTrialStartUnixTime(epoch.attrs)
else:  # older VP data
    epoch_unix_time = dateutil.parser.parse(date + ' ' + epoch_time).astimezone(timezone.utc).timestamp()
stim_start_time = epoch_unix_time + pre_time
...
stim_end_time = epoch_end_unix_time - tail_time
stim_start_time_more_accurate = stim_end_time - stim_time
stim_start_times.append(stim_start_time_more_accurate)
# MC: epoch_time and epoch_unix_time are recorded before load_stim, so could be early by a few ms.
#     so use stim_end_time - stim_time instead
```

[from code: `twentyfourhourfitness.py:109–143`]. Two things: the start time is back-computed as
`stim_end_time - stim_time` because the recorded start is early by a few ms (the `# MC:`
comment is Minseung's — **this is the path his rig uses** [inferred]); and the returned times
are **absolute unix seconds**. Feeding those into `getEpochResponseMatrix`, which compares them
against `acquisition/time_points` (seconds from series start), would select zero frames for
every trial. Any rig mixing stimpack unix epoch times with Bruker `relativeTime` acquisition
times needs an explicit `t0` offset that `ImagingDataObject` does not provide.

The 40-hour rig solves exactly that, storing the anchor explicitly:

```python
attrs['daq_t0_unix'] = float('nan') if plan.t0_unix is None else float(plan.t0_unix)
attrs['daq_t0_unix_spread_s'] = ...
attrs['daq_t0_unix_source'] = 'strobe_block_anchor'
attrs['daq_time_offset'] = float(lo / sample_rate)
```

[from code: `fortyhourfitness.py:455–464`]. The anchors are `(trial time − camera edge time)` at
each block's start and end, and their spread is validated against
`max(T0_SPREAD_MAX_S=0.5, 0.5 × trial period)` [from code: `daq_ensemble.py:103–104, 1241–1252`].
**Nothing equivalent is written by the Bruker plugin** — there is no unix anchor in the Bruker
path at all.

The 40hr detector is also materially better than the base one and worth copying if I touch
photodiodes: it clamps the low-pass below Nyquist, adds a high-pass to kill baseline drift, and
uses `find_peaks` with a minimum distance and prominence instead of bare threshold crossings:

```python
b, a = signal.butter(4, min(10*command_frame_rate, sample_rate/2-1), btype='low', fs=sample_rate)
frame_monitor = signal.filtfilt(b, a, frame_monitor)
sos = signal.butter(2, 0.01, 'highpass', fs=sample_rate, output='sos')
frame_monitor = signal.sosfiltfilt(sos, frame_monitor) if highpass_zero_phase else signal.sosfilt(sos, frame_monitor)
...
min_peak_distance = int(np.floor(ideal_frame_len * 1.8))
ups, peak_params = signal.find_peaks(frame_monitor, height=threshold, distance=min_peak_distance, prominence=0.04, rel_height=0.5)
downs = ups + ideal_frame_len_samples   # downs are *assumed*, not detected
```

[from code: `fortyhourfitness.py:746–771`]. Its own docstring explains why `highpass_zero_phase`
is off by default: the causal filter leaves a "~16 s transient" that can bridge
`minimum_epoch_separation` and merge adjacent epochs, but the zero-phase version "is not a
strict improvement on every channel" [from code:719–723]. Note `downs` are *synthesized* by
adding one ideal frame length, not measured.

### Camera / behavior timing: `getBehaviorTiming` — `imaging_data.py:544`

Two paths, in preference order:

1. **Preferred — hardware strobes.** Every subgroup of `behavior/` that is a Group (other than
   `log_lines`) is treated as a camera:
   ```python
   cam_timing["frame_time"]    = cam_group.get("exposure_onset")[:]   # sec
   cam_timing["exposure_time"] = cam_group.attrs["exposure_time"]     # sec
   cam_timing["frame_rate"]    = cam_group.attrs["frame_rate"]        # Hz
   ```
   These come from the DAQ, re-zeroed with the **same integer offset** as the photodiode trace —
   which is the explicit guarantee of the 40hr write path:
   ```python
   # daq_ensemble.py:934
   exposure_onset = (onset_abs - lo) / sample_rate
   # fortyhourfitness.py:524 — the audit that proves it
   assert cam_group.attrs['daq_sample_offset'] == attrs['daq_sample_offset']
   ```
   [from code]. This is the only place in the lab's code where behavior and stimulus timing are
   provably on one clock.

2. **Fallback — FicTrac's own clock.** When there is no FicTrac camera group (or
   `use_camera_timestamps=True`):
   ```python
   fictrac_header = behavior_group["fictrac_data"].attrs["fictrac_data_header"]
   frame_time = behavior_group["fictrac_data"][:, np.where(fictrac_header == "timestamp")[0][0]] / 1000
   frame_rate = 1 / np.mean(np.diff(frame_time))
   ```
   **→ The `timestamp` column is in MILLISECONDS** — `/1000` is the only unit conversion applied
   to FicTrac data anywhere in either repo [from code:583–588]. Its origin is FicTrac's own
   clock, *not* the imaging clock, and nothing here reconciles the two. The branch condition is
   also inverted relative to its comment: with `use_camera_timestamps=True` the loop at :565
   `continue`s past the FicTrac camera group, so the flag means "prefer FicTrac's own
   timestamps over the strobes" [from code:565–582].

### The behavior↔stimulus join: `getBehaviorData` — `imaging_data.py:598`

This is the real alignment routine. It takes `stimulus_timing` as an argument and walks a single
monotonic pointer through the FicTrac timestamps, cutting one chunk per epoch.

```python
stim_start_times = stimulus_timing["stimulus_start_times"]  # from photodiodes
stim_end_times   = stimulus_timing["stimulus_end_times"]    # from photodiodes

# trim both to the shorter of (strobes, .dat lines)
n_fictrac_valid_frames = min(len(fictrac_timestamps), len(fictrac_data))
fictrac_timestamps = fictrac_timestamps[:n_fictrac_valid_frames]
fictrac_data = fictrac_data[:n_fictrac_valid_frames]
```

Then per epoch `e` [from code:688–771]:

```python
# advance pointer to this stim's end
while ts_pointer < len(fictrac_timestamps) and fictrac_timestamps[ts_pointer] <= current_stim_end_time:
    ts_pointer += 1
current_stim_end_fictrac_index = ts_pointer - 1
# ... and on to the next stim's start
epoch_fictrac_data = fictrac_data.iloc[prev_stim_end_fictrac_index:next_stim_start_fictrac_index].copy()

epoch_fictrac_data["integrated_xpos"] -= epoch_fictrac_data["integrated_xpos"][epoch_start_frame_num]
epoch_fictrac_data["integrated_ypos"] -= epoch_fictrac_data["integrated_ypos"][epoch_start_frame_num]
epoch_fictrac_data["integrated_heading"] = np.unwrap(epoch_fictrac_data["integrated_heading"])
epoch_fictrac_data["integrated_heading"] -= epoch_fictrac_data["integrated_heading"][epoch_start_frame_num]
epoch_fictrac_data["integrated_heading"] = (np.mod((epoch_fictrac_data["integrated_heading"] + np.pi), np.pi * 2) - np.pi)

epoch_fictrac_timestamps = np.copy(fictrac_timestamps[prev_stim_end_fictrac_index:next_stim_start_fictrac_index])
epoch_fictrac_timestamps -= current_stim_start_time
fictrac_data_for_epoch.append({"timestamps": epoch_fictrac_timestamps, "data": epoch_fictrac_data})
```

In plain words:
- The window is **previous stim end → next stim start**, so each chunk brackets the stimulus
  with its surrounding ITI (tail of the previous trial + this trial's pre_time + stim + its
  tail). Epoch −1's boundary comes from `stim_start_times[0] - epoch_params[0]["pre_time"]`;
  the final epoch's tail from `current_stim_end_time + epoch_params[e]['tail_time']`.
- **`integrated_xpos` / `ypos` / `heading` are re-zeroed per epoch**, and heading is unwrapped
  before subtraction then re-wrapped to `[-π, π]`. So positions are relative, headings absolute
  in radians [inferred: `np.pi` arithmetic implies radians].
- **Timestamps are re-zeroed to stim onset** (`-= current_stim_start_time`), so they run
  negative through the pre-period.
- In closed loop (`loco_pos_closed_loop`), the zero point instead comes from the stimpack log's
  `set_pos_0` frame numbers, asserted 1:1 with epochs [from code:645–658].
- **Still no resampling onto the imaging timebase.** The output is ragged per-epoch FicTrac
  chunks. Behavior and imaging end up commensurable only because both are expressed relative to
  the same photodiode `stimulus_start_times` — and even then with different zero points (see
  below).

### The imaging join: `getEpochResponseMatrix` — `imaging_data.py:850`

```python
def get_image_inds(epoch_index):
    '''find indices of image (volume) that fall within epoch given by [epoch_index] '''
    image_inds = np.where(
        np.logical_and(
            response_timing["time_vector"] < epoch_end_times[epoch_index],
            response_timing["time_vector"] >= epoch_start_times[epoch_index],
        )
    )[0]
    return image_inds
```

with windows padded out from the photodiode stim times by the per-trial pre/tail times:

```python
epoch_start_times = stimulus_timing["stimulus_start_times"][:no_trials] - np.array(self.getEpochParameters('pre_time'))[:no_trials]
epoch_end_times   = stimulus_timing["stimulus_end_times"] + np.array(self.getEpochParameters('tail_time'))[:no_trials]
epoch_time = (pre_time + stim_time + tail_time)                      # sec, per trial
epoch_frames = np.array([int(x) for x in epoch_time / response_timing["sample_period"]])
pre_frames   = np.array([int(x) for x in pre_time / response_timing["sample_period"]])
max_epoch_frames = np.max(epoch_frames)
time_vector = np.arange(0, max_epoch_frames) * response_timing["sample_period"]  # sec
```

[from code:881–903]. So:

- The join is **a boolean mask on the shared seconds timebase**. No interpolation, no nearest-
  neighbour, no sub-frame correction. Volumes are assigned whole to the epoch containing their
  `stack_times` value (= first-z-plane time).
- `time_vector` is **nominal** — `arange * sample_period`, not the actual volume times — and
  **starts at 0 = epoch start, i.e. `pre_time` before stim onset.** Contrast
  `getBehaviorData`, whose timestamps are 0 = **stim onset**. ⚠️ **Joining the two outputs
  requires shifting one by `pre_time`.**
- dF/F baseline is the mean of the first `pre_frames` frames of each epoch, per ROI:
  ```python
  baseline = np.mean(epoch_raw_resp[:, 0:pre_frames[epoch_index]], axis=1, keepdims=True)
  dff_resp = (epoch_raw_resp - baseline) / baseline
  ```
  Per-trial, per-ROI, no grey-period anchoring — **not** the F0 convention this project uses
  (`dff_grey/F0_stationary`, `F0_moving`), so do not reuse it [from code:874–879].
- Trials with no frames, or fewer frames than `epoch_frames[idx]`, are **skipped and left as
  NaN** with a `warnings.warn` [from code:908–914]. Ragged epochs are NaN-padded to the longest.
- `int()` truncation of frame counts means the window can be up to one volume short [inferred].

### `examples/` — what the analysis layer actually demonstrates

Both examples stop at ROI responses. `examples/plotting_responses.py` builds an
`ImagingDataObject`, pulls `getRoiResponses('set_2')` (which internally calls
`getEpochResponseMatrix`), and plots `epoch_response` shape `(rois, trials, time)` against
`time_vector`; `examples/mask_responses.py` shows the mask → `aligned/` path
[from code]. Both hardcode `mhturner`'s local paths.

**Neither example touches behavior.** More to the point: `getBehaviorData` and
`getBehaviorTiming` have **no callers anywhere in the repo** — only `getBehaviorTiming`'s single
internal call from `getBehaviorData` [from code: grep for both names]. So the behavior→imaging
join is library capability with no worked example and no in-repo consumer; I will be writing
that final step myself.

---

## 3. Hard-coded assumptions, thresholds, and units

### `ImagingDataObject.__init__` defaults — `imaging_data.py:53–63`

```python
self.timing_channel_ind = 0   # which photodiode channel defines stim timing
self.threshold = (0.6,)       # photodiode threshold, normalized to 0-1
self.frame_slop = (20,)       # datapoints +/- ideal frame duration
self.command_frame_rate = 120 # Hz, expected monitor frame rate
```

Overridable only via the `cfg_dict=` constructor kwarg, which loops `setattr` over the dict
[from code:62–63]. **Nothing in `rig_specific/` supplies a `cfg_dict`** — the configs' `attach`
key feeds `attachData`, not `ImagingDataObject` [from code: `configs/_README_config_format.md`].
So in practice these four values are the defaults unless set by hand in a notebook.

The trailing commas making `threshold` and `frame_slop` **1-tuples rather than floats** are
deliberate, not a typo — `fortyhourfitness.py:719–721` documents it: "find_peaks reads a
1-tuple `height` as 'minimum only' and the frame_slop comparison broadcasts, so normalizing
them to scalars would silently change existing results." In the base `getStimulusTiming` the
comparisons broadcast harmlessly; in the 40hr detector the tuple is load-bearing. **Passing a
scalar `threshold` via `cfg_dict` changes `find_peaks` semantics** [from code].

| Value | Where | Risk |
|---|---|---|
| `0.6` photodiode threshold | `imaging_data.py:56` | applied *after* whole-trace min/max normalization, so sensitive to spikes and drift |
| `20` datapoints frame slop | `imaging_data.py:59` | rate-dependent: 20 samples is a different tolerance at 10 kHz than at 1 kHz |
| `120` Hz command frame rate | `imaging_data.py:60` | sets `ideal_frame_len`; wrong value corrupts dropped-frame detection |
| `10 * command_frame_rate` = 1200 Hz low-pass | `imaging_data.py:360` | **no Nyquist clamp → raises for `sample_rate ≤ 2400 Hz`.** 40hr version clamps with `min(..., sample_rate/2-1)` |
| `0.9 * (pre_time + tail_time)` epoch separation | `imaging_data.py:347` | requires scalar pre/tail; fails on multi-valued ensemble protocols |
| `0.01` Hz high-pass, `prominence=0.04`, `distance = 1.8 × ideal_frame_len` | `fortyhourfitness.py:749–764` | 40hr detector only |
| "last two" / "last three" photodiode channels | `imaging_data.py:339`, `fortyhourfitness.py:921` | positional, because the Bruker writer discards channel names |
| `_Cycle00001_VoltageRecording_001` | `bruker.py:105` | only cycle 1, recording 1 |
| `' ' + channel_name` CSV column | `bruker.py:244` | hardcoded leading space |
| `('00' + str(n))[-3:]` series pad | `bruker.py:101` | truncates for series ≥ 1000 |
| `GAP_ABS_MIN_S=0.25`, `SURPLUS_MAX=2`, `MIN_BLOCK_S=5.0`, `MIN_BLOCK_PULSES=100`, `T0_SPREAD_MAX_S=0.5`, … | `daq_ensemble.py:78–104` | 40hr ensemble segmentation; all overridable via `thresholds=` |

### Units summary

| Quantity | Unit | Converted where |
|---|---|---|
| Bruker `relativeTime` | sec | used as-is (`bruker.py:332`) |
| PrairieView `Time(ms)` | ms → **sec** | `/ 1e3` (`bruker.py:240`) |
| `sample_rate` | Hz (int) | `bruker.py:222` |
| photodiode flip indices | datapoints → **sec** | `/ sample_rate` (`imaging_data.py:393`) |
| `exposure_onset` | DAQ samples → **sec**, re-zeroed to block | `(onset_abs - lo) / sample_rate` (`daq_ensemble.py:934`) |
| FicTrac `timestamp` | **ms** → sec | `/ 1000` (`imaging_data.py:587`) |
| stimpack trial times | **absolute unix sec** | `twentyfourhourfitness.py:109–115` |
| `integrated_heading` | radians | `np.unwrap` / `np.mod(±π)` (`imaging_data.py:766–768`) |

### HDF5 schema tolerance — `util/h5io.py`

Worth knowing because both the glom pipeline and my own code must navigate it. Stimpack renamed
things, so every accessor resolves names rather than assuming [from code:16–30]:

```python
SERIES_PARENT_GROUP_NAMES  = ('epoch_runs', 'series')
SUBJECT_PARENT_GROUP_NAMES = ('Subjects', 'Flies')
TRIAL_PARENT_GROUP_NAMES   = ('epochs', 'trials')
TRIAL_START_ATTR_NAMES     = ('epoch_unix_time', 'trial_unix_time')
TRIAL_END_ATTR_NAMES       = ('epoch_end_unix_time', 'trial_end_unix_time')
```

`find_series` is a **substring** match, which is why it works under either parent:

```python
def find_series(name, obj, sn):
    target_group_name = 'series_{}'.format(str(sn).zfill(3))
    if target_group_name in name:
        return obj
```

[from code:210–213]. Substring + `zfill(3)` means `series_001` also matches a hypothetical
`series_0012`; fine in practice, fragile in principle [inferred].

---

## 4. How this closes the gaps in `minseung_mc_glom_pipeline.md`

Those notes listed 7 things needed from `mcregistration`/`visanalysis`. visanalysis answers
five of them outright:

| Gap (from the glom notes) | Status |
|---|---|
| **1. The imaging time base** — what key, units, origin | ✅ **Answered.** `acquisition/time_points` = Bruker `relativeTime` of each volume's **first z-plane**, in **seconds from series start**; `acquisition/frame_times` is the full `(t, z)` grid; `acquisition.attrs['sample_period']` is the nominal mean period. `bruker.py:310–354`, written at `bruker.py:128–131`. |
| **2. The frame↔volume join** | ✅ **Answered, and simpler than expected.** `getEpochResponseMatrix` (`imaging_data.py:850`) does a boolean window select, no interpolation. Behavior is cut per-epoch by `getBehaviorData` (`imaging_data.py:598`). The two meet only via shared photodiode `stimulus_start_times`. Clock question answered: **`timestamp`, in ms** (`imaging_data.py:587`). ⚠️ Different zero points — imaging `time_vector` starts at epoch start, behavior timestamps at stim onset. |
| **3. Stimulus epoch structure** | ✅ **Answered.** `{epochs\|trials}/{epoch\|trial}_NNN` with `{epoch\|trial}_unix_time` / `_end_unix_time` attrs; per-trial `pre_time`/`stim_time`/`tail_time` via `getEpochParameters`. Epoch *onsets* come from the photodiode, not these attrs, except in the 24hr/unix path. `h5io.py:21–30`, `twentyfourhourfitness.py:86–148`. |
| **4. Camera–imaging synchronisation** | ⚠️ **Answered for the 40hr rig, open for Bruker.** The 40hr rig records camera strobes on the same DAQ as the photodiode and re-zeroes both with one offset (`daq_ensemble.py:907–949`, asserted at `fortyhourfitness.py:524`), plus a `daq_t0_unix` anchor. **The Bruker plugin writes no camera strobes and no unix anchor** — so for my rig this is still unresolved, and FicTrac's ms clock is all there is. |
| **5. FicTrac column count/order for `fictrac_tw`** | ✅ **Resolved.** `fortyhourfitness.py:33–40` defines `FICTRAC_DATA_HEADER` with **exactly the same 25 names in the same order** as Minseung's list. So 25 columns is the lab convention for this fork, and my earlier caution can be downgraded. One wrinkle: `twentyfourhourfitness.py:47–54` has a **26th name, `sync`**, appended. Three variants exist in the lab (23 upstream / 25 / 26) — still worth a one-time check against my own `.dat`. Units unaffected: nothing converts them. |
| **6. `MCRConfig` / `DataPaths`** | ❌ **Not here.** `mcregistration` is a separate package, still absent. |
| **7. Downstream kinematics / stationary-moving threshold** | ❌ **Not here either.** `getBehaviorData` re-zeroes positions and unwraps heading, and that is the whole of it — no smoothing, no velocity, no speed threshold. The lab's stationary/moving definition lives in neither repo. |

### ⚠️ The one concrete blocker between the two repos — verified

Minseung's writer and visanalysis's reader disagree on the header's string type.
`process_imports.py:169` writes **fixed-length bytes**:

```python
dset.attrs['fictrac_data_header'] = np.array(header, dtype='S')
```

visanalysis's readers compare against Python `str`:

```python
# imaging_data.py:583-586
np.where(fictrac_header == "timestamp")[0][0]
# imaging_data.py:632-637
pd.DataFrame(behavior_group["fictrac_data"][:], columns=header).astype({"frame_count": int, ...})
```

I ran both writers through h5py 3.9 / numpy 1.26 to check [verified]:

| Writer | Read-back dtype | `np.where(h == "timestamp")` | `DataFrame(...).astype({"frame_count": int})` |
|---|---|---|---|
| `np.array(header, dtype='S')` — **Minseung** | `|S11` (bytes) | `[]` → **`IndexError`** | columns are `b'frame_count'` → **`KeyError`** |
| `header` as a plain list of `str` — **visanalysis** (`fortyhourfitness.py:591`, `twentyfourhourfitness.py:66`) | `object` (str) | `[1]` ✅ | ✅ |

So **`getBehaviorTiming` raises `IndexError` and `getBehaviorData` raises `KeyError` on HDF5
files written by `mc_glom_pipeline`.** Fix either side — write the header as a list of `str`, or
decode with `h.astype(str)` on read. Cheap to fix, but it fails at the exact function I need.

### Also worth flagging before building on this

- **`getBehaviorData`'s header-mismatch guard is dead code.** It computes `n_headers_to_use`
  and prints a warning, then ignores it and calls `pd.DataFrame(..., columns=header)` anyway,
  which raises on a length mismatch [from code: `imaging_data.py:626–634`]. Given the 25-vs-26
  header variance in the lab, this will bite.
- **`epoch_start_frame_num` is a positional index used as a pandas label.**
  `epoch_fictrac_data` is indexed by `frame_count`, but it is subscripted with
  `current_stim_start_fictrac_index`, a position into `fictrac_timestamps`
  [from code: `imaging_data.py:760–767`]. These coincide only if `frame_count` equals the row
  position — i.e. 0-based and perfectly contiguous. FicTrac frame counts are typically 1-based,
  and the 40hr plugin stores a `frame_count_contiguous` flag precisely because contiguity is
  not guaranteed [from code: `fortyhourfitness.py:600–601`]. **Check this before trusting
  per-epoch re-zeroing.**
- **Z-stagger is available but unused.** `getVolumeFrameOffsets()` gives per-slice offsets
  within a volume and nothing applies them. For whole-brain volumes at a few Hz this is a real
  within-volume timing error on OMR latencies — worth applying myself.
- **The Bruker path discards photodiode channel identity** (`bruker.py:109–110` TODO), leaving
  only positional "last two" heuristics. If I attach my own data, store channel names.
- **`getAcquisitionTiming` raises on anatomical `ZSeries`** (no `else` branch,
  `bruker.py:324–354`), so `attachData` must only see T-series.
