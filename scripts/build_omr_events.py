"""Build OMR event times for later postprocessing (-e OMR).

Runs on a login node (no Slurm). For each fly, takes the static-hold onsets of the
non-grey visual epochs, maps them from unix time onto imaging time through the
FicTrac strobe pulses recorded in photodiode.csv, splits them by the fly's turning
in the classification window, and merges {fly: {behavior: [onset_ms, ...]}} into
<later_path>/<event>_event_times_split_dic.pkl.

Usage (from scripts/):
    python3 build_omr_events.py --fly 001 --subject 1 --series 1 --event OMR \
                                [--fly 002 --subject 2 --series 2]
"""
import argparse
import os
import pickle
import re
import sys
import time

import h5py
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import brainsss

N_TRIALS = 264  # non-grey epochs in this OMR protocol
CLASSIFICATION_WINDOW_MS = (500, 1250)  # motion period (500–1000) + 250 ms, matching the old design’s coverage relative to motion offset
TURN_THRESHOLD = 50  # deg/s
SIGN = {0: -1, 180: +1}  # signed = mean dRotLabZ * SIGN[angle]; positive = syn-directional
MAX_RESIDUAL_MS = 5
FIRST_PULSE_MAX_MS = 1  # the extra strobe pulse at recording start sits at ~0 ms
BEHAVIORS = ['syn_turn_0', 'syn_turn_180', 'anti_turn_0', 'anti_turn_180', 'flat_0', 'flat_180', 'total']


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--fly', action='append', required=True, help='fly number, e.g. 001 or fly_001 (repeatable)')
    parser.add_argument('--subject', action='append', required=True, help='Subjects/<subject> in the visual hdf5 (one per --fly)')
    parser.add_argument('--series', action='append', required=True, type=int, help='epoch_runs/series_NNN (one per --fly)')
    parser.add_argument('--event', required=True, help='event label; output is <later_path>/<event>_event_times_split_dic.pkl')
    cli = parser.parse_args()
    if not (len(cli.fly) == len(cli.subject) == len(cli.series)):
        parser.error('--fly, --subject and --series must be given the same number of times')
    if cli.event.strip() == '':
        parser.error('--event must be non-empty (never write to event_times_split_dic.pkl)')

    ### Settings, located as the orchestrators do (repo must be at /home/users/<sunetid>/...)
    scripts_path = os.path.dirname(os.path.abspath(__file__))
    user = scripts_path.split('/')[3]
    settings = brainsss.load_user_settings(user, scripts_path)
    dataset_path = settings['dataset_path']
    later_path = settings['later_path']

    logfile = os.path.join(scripts_path, 'logs', time.strftime('%Y%m%d-%H%M%S') + '.txt')
    _printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    def printlog(message):
        _printlog(message)
        print(message)

    printlog('build_omr_events: user {}, dataset_path {}, later_path {}'.format(user, dataset_path, later_path))

    # Compute every fly before touching the pickle, so a failure leaves it unchanged
    results = {}
    for fly_arg, subject, series in zip(cli.fly, cli.subject, cli.series):
        fly = fly_arg.replace('fly_', '').zfill(3)
        func_dir = os.path.join(dataset_path, 'fly_' + fly, 'func_0')
        printlog('\n=== fly_{} (subject {}, series {:03d}) ==='.format(fly, subject, series))
        results[fly] = build_fly(func_dir, fly, subject, series, printlog)

    save_file = os.path.join(later_path, '{}_event_times_split_dic.pkl'.format(cli.event))
    assert os.path.basename(save_file) != 'event_times_split_dic.pkl'
    if os.path.exists(save_file):
        with open(save_file, 'rb') as f:
            event_times = pickle.load(f)
        printlog('\nMerging into existing {} (keys: {})'.format(save_file, sorted(event_times.keys())))
    else:
        event_times = {}
        printlog('\nCreating {}'.format(save_file))
    for fly, behaviors in results.items():
        event_times[fly] = behaviors
    tmp_file = save_file + '.tmp'
    with open(tmp_file, 'wb') as f:
        pickle.dump(event_times, f, protocol=4)  # readable by Sherlock's python 3.6
    os.replace(tmp_file, save_file)
    printlog('Wrote flies {}; file now has keys {}'.format(sorted(results.keys()), sorted(event_times.keys())))


def build_fly(func_dir, fly, subject, series, printlog):
    visual_dir = os.path.join(func_dir, 'visual')
    fictrac_dir = os.path.join(func_dir, 'fictrac')

    ### Stimulus: static-hold onsets (unix s) and directions
    onsets_unix, angles = load_trials(visual_dir, subject, series)
    printlog('Non-grey trials: {}'.format(len(onsets_unix)))
    assert len(onsets_unix) == N_TRIALS, 'expected {} trials, found {}'.format(N_TRIALS, len(onsets_unix))

    ### Clock mapping: strobe pulses (imaging ms) <-> jackfish frames (unix s)
    pulse_ms = load_strobe_pulses(os.path.join(visual_dir, 'photodiode.csv'))
    frame_mono, frame_unix = load_jackfish(os.path.join(fictrac_dir, 'jackfish_timestamps.txt'))
    n_frames = len(frame_unix)
    if pulse_ms[0] < FIRST_PULSE_MAX_MS:
        printlog('Dropping first strobe pulse at {:.2f} ms'.format(pulse_ms[0]))
        pulse_ms = pulse_ms[1:]
    # Off-by-one at the end is tolerated; the max-residual check below is the real validation
    if len(pulse_ms) == n_frames:
        printlog('Pulse/frame match: {} pulses == {} frames, using all'.format(len(pulse_ms), n_frames))
    elif len(pulse_ms) == n_frames - 1:
        printlog('Pulse/frame match: {} pulses == {} frames - 1, dropping last jackfish frame'.format(len(pulse_ms), n_frames))
        frame_mono, frame_unix = frame_mono[:-1], frame_unix[:-1]
    elif len(pulse_ms) == n_frames + 1:
        printlog('Pulse/frame match: {} pulses == {} frames + 1, dropping last strobe pulse'.format(len(pulse_ms), n_frames))
        pulse_ms = pulse_ms[:-1]
    else:
        raise Exception('Strobe pulses ({}) do not match jackfish frames ({}) within one'.format(len(pulse_ms), n_frames))

    # Fit relative to the first frame for conditioning; unix = a + b * t_ms
    b, a_rel = np.polyfit(pulse_ms, frame_unix - frame_unix[0], 1)
    a = frame_unix[0] + a_rel
    residual_ms = (frame_unix - frame_unix[0] - (a_rel + b * pulse_ms)) * 1000
    max_residual = np.max(np.abs(residual_ms))
    printlog('Strobe fit: slope - 1 = {:.1f} ppm, max residual = {:.3f} ms'.format((b * 1000 - 1) * 1e6, max_residual))
    if max_residual > MAX_RESIDUAL_MS:
        raise Exception('Strobe fit max residual {:.3f} ms > {} ms'.format(max_residual, MAX_RESIDUAL_MS))

    onsets_ms = (onsets_unix - a) / b
    assert onsets_ms.min() >= pulse_ms[0] and onsets_ms.max() <= pulse_ms[-1], \
        'trial onsets [{:.0f}, {:.0f}] ms outside strobe span [{:.0f}, {:.0f}] ms'.format(
            onsets_ms.min(), onsets_ms.max(), pulse_ms[0], pulse_ms[-1])

    ### Behavior: dRotLabZ in deg/s at each frame's strobe time
    fps = 1 / np.median(np.diff(frame_mono))
    printlog('Jackfish fps: {:.2f}'.format(fps))
    fictrac_raw = brainsss.load_fictrac(fictrac_dir, file='fictrac.dat')
    if len(fictrac_raw) != n_frames:
        raise Exception('fictrac.dat has {} frames, jackfish has {}'.format(len(fictrac_raw), n_frames))
    rot_z = np.asarray(fictrac_raw['dRotLabZ'], dtype=float) * 180 / np.pi * fps  # rad/frame -> deg/s
    rot_z = rot_z[:len(pulse_ms)]  # frames without a matched pulse have no imaging time

    signed = np.zeros(len(onsets_ms))
    for i, (onset, angle) in enumerate(zip(onsets_ms, angles)):
        in_window = (pulse_ms >= onset + CLASSIFICATION_WINDOW_MS[0]) & (pulse_ms <= onset + CLASSIFICATION_WINDOW_MS[1])
        if not in_window.any():
            raise Exception('no FicTrac frames in classification window of trial at {:.0f} ms'.format(onset))
        signed[i] = np.mean(rot_z[in_window]) * SIGN[angle]

    behaviors = {name: [] for name in BEHAVIORS}
    for onset, angle, value in zip(onsets_ms, angles, signed):
        if value >= TURN_THRESHOLD:
            behaviors['syn_turn_{}'.format(angle)].append(float(onset))
        elif value <= -TURN_THRESHOLD:
            behaviors['anti_turn_{}'.format(angle)].append(float(onset))
        else:
            behaviors['flat_{}'.format(angle)].append(float(onset))
        behaviors['total'].append(float(onset))
    behaviors = {name: sorted(times) for name, times in behaviors.items()}

    counts = {name: len(behaviors[name]) for name in BEHAVIORS}
    printlog('Counts: ' + ', '.join('{} {}'.format(name, counts[name]) for name in BEHAVIORS))

    qc_file = os.path.join(visual_dir, 'omr_events_qc_{}.png'.format(fly))
    plot_qc(qc_file, fly, signed, counts, pulse_ms, residual_ms)
    printlog('QC figure: {}'.format(qc_file))
    return behaviors


def load_trials(visual_dir, subject, series):
    """Static-hold onset (unix s) and angle (0/180) of every non-grey epoch."""
    hdf5_files = [f for f in os.listdir(visual_dir) if f.endswith('.hdf5')]
    if len(hdf5_files) != 1:
        raise Exception('expected exactly one .hdf5 in {}, found {}'.format(visual_dir, hdf5_files))
    onsets, angles = [], []
    with h5py.File(os.path.join(visual_dir, hdf5_files[0]), 'r') as hf:
        series_group = hf['Subjects'][str(subject)]['epoch_runs']['series_{:03d}'.format(series)]
        epochs = series_group['epochs']
        for epoch_id in sorted(epochs.keys()):
            epoch = epochs[epoch_id]
            if to_bool(get_param(epoch, series_group, 'is_block_grey', default=False)):
                continue
            end = float(get_param(epoch, series_group, 'epoch_end_unix_time'))
            tail = float(get_param(epoch, series_group, 'tail_time'))
            stim = float(get_param(epoch, series_group, 'stim_time'))
            angle = int(round(float(get_param(epoch, series_group, 'angle'))))
            if angle not in SIGN:
                raise Exception('{}: unexpected angle {}'.format(epoch_id, angle))
            onsets.append(end - tail - stim)
            angles.append(angle)
    return np.asarray(onsets), angles


_MISSING = object()


def get_param(epoch, series_group, name, default=_MISSING):
    """Look for a parameter on the epoch, its parameter subgroups, then the run parameters."""
    places = [epoch]
    for sub in ('convenience_parameters', 'epoch_parameters'):
        if sub in epoch:
            places.append(epoch[sub])
    places.append(series_group)
    if 'run_parameters' in series_group:
        places.append(series_group['run_parameters'])
    for place in places:
        if name in place.attrs:
            return place.attrs[name]
    if default is _MISSING:
        raise KeyError('{} not found for {}'.format(name, epoch.name))
    return default


def to_bool(value):
    if isinstance(value, bytes):
        value = value.decode()
    if isinstance(value, str):
        return value.strip().lower() == 'true'
    return bool(value)


def load_strobe_pulses(photodiode_file):
    """Imaging times (ms) of the rising edges of the FT Strobe column."""
    df = pd.read_csv(photodiode_file)
    df.columns = [c.strip() for c in df.columns]
    t = df['Time(ms)'].values.astype(float)
    strobe = df['FT Strobe'].values.astype(float)
    threshold = (strobe.min() + strobe.max()) / 2
    high = strobe > threshold
    # A strobe already high at the first sample counts as a pulse at t[0]
    rising = np.flatnonzero(high & ~np.concatenate([[False], high[:-1]]))
    return t[rising]


def load_jackfish(timestamps_file):
    """Monotonic and unix seconds per frame (columns: frame, monotonic s, unix s)."""
    rows = []
    with open(timestamps_file, 'r') as f:
        for line in f:
            fields = re.split(r'[,\s]+', line.strip())
            try:
                rows.append([float(x) for x in fields[:3]])
            except ValueError:
                continue  # header
    rows = np.asarray(rows)
    return rows[:, 1], rows[:, 2]


def plot_qc(qc_file, fly, signed, counts, pulse_ms, residual_ms):
    fig, (ax_hist, ax_res) = plt.subplots(2, 1, figsize=(10, 7))

    ax_hist.hist(signed, bins=60, color='#4a6fa5', edgecolor='white', linewidth=0.5)
    for x in (-TURN_THRESHOLD, TURN_THRESHOLD):
        ax_hist.axvline(x, color='#333333', linestyle='--', linewidth=1)
    ax_hist.set_xlabel('signed dRotLabZ in classification window (deg/s; + = syn)')
    ax_hist.set_ylabel('trials')
    ax_hist.set_title('fly_{} OMR trials (n = {})'.format(fly, counts['total']))
    text = '\n'.join('{}: {}'.format(name, counts[name]) for name in BEHAVIORS)
    ax_hist.text(1.02, 1.0, text, transform=ax_hist.transAxes, ha='left', va='top', fontsize=8, family='monospace')

    ax_res.plot(pulse_ms / 1000, residual_ms, '.', color='#4a6fa5', markersize=1, rasterized=True)
    ax_res.axhline(0, color='#999999', linewidth=0.5)
    ax_res.set_xlabel('imaging time (s)')
    ax_res.set_ylabel('strobe fit residual (ms)')
    ax_res.set_title('unix vs strobe linear fit, max |residual| = {:.3f} ms'.format(np.max(np.abs(residual_ms))))

    for ax in (ax_hist, ax_res):
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    fig.tight_layout(rect=(0, 0, 0.82, 1))
    fig.savefig(qc_file, dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
