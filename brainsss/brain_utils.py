import numpy as np
import ants
import scipy
import nibabel as nib
import os
import time
from scipy.signal import butter, filtfilt, freqz

def extract_traces(fictrac, stim_times, pre_window, post_window, val=None):
    traces = []
    for i in range(len(stim_times)):
        if val != None:
            trace = fictrac[val][stim_times[i]-pre_window:stim_times[i]+post_window]
        else:
            trace = fictrac[stim_times[i]-pre_window:stim_times[i]+post_window]
        if len(trace) == pre_window + post_window: # this handles fictrac that crashed or was aborted or some bullshit
            traces.append(trace)
    traces = np.asarray(traces)
    mean_trace = np.mean(traces,axis=0)
    sem_trace = scipy.stats.sem(traces,axis=0)
    return traces, mean_trace, sem_trace

def get_vals_for_analysis(tp_width_sec=0, trial_time_sec=0, before_stim_sec=0, pre_trial_window_sec=0, pre_trial_size_sec=0, post_trial_window_sec=0, post_trial_size_sec=0, thresh=0, fr=0):
        
    stim_end_sec = before_stim_sec + trial_time_sec
    
    stim_idx = int(before_stim_sec/tp_width_sec)
    stim_end_idx = int(stim_end_sec/tp_width_sec)
    pre_trial_window_idx = int(pre_trial_window_sec/tp_width_sec)

    # first val i use to make delta to compare change in vel
    first_val_end_idx = int(stim_idx - pre_trial_window_idx)
    first_val_start_idx = int(first_val_end_idx - (pre_trial_size_sec/tp_width_sec)) #only needed if you're averaging across a window, otherwise just start val is used

    # second val used to make delta
    second_val_start_idx = int(stim_idx + post_trial_size_sec/tp_width_sec)
    second_val_end_idx = int(second_val_start_idx + post_trial_window_sec/tp_width_sec)
    return stim_idx, stim_end_idx, pre_trial_window_idx, first_val_end_idx, first_val_start_idx, second_val_end_idx, second_val_start_idx

def butter_lowpass(cutoff, fs, order=5):
    return butter(order, cutoff, fs=fs, btype='low', analog=False)

def butter_lowpass_filter(data, cutoff, fs, order=5):
    b, a = butter_lowpass(cutoff, fs, order=order)
    y = filtfilt(b, a, data, method="gust")
    return y

def apply_butter_lowpass(behavior_traces, stim_idx, fr):
    # Filter requirements.
    order = 4
    fs = fr      # sample rate, Hz
    cutoff = 3  # desired cutoff frequency of the filter, Hz

    # Filter the data, and plot both the original and filtered signals.
    lpf_behavior = np.zeros((behavior_traces.shape[0], behavior_traces.shape[1] - stim_idx))

    for i in range(behavior_traces.shape[0]):
        lpf_behavior[i, :] = butter_lowpass_filter(behavior_traces[i,stim_idx:], cutoff, fs, order)

    return lpf_behavior

def get_speed_change(behavior, stim_idx, first_val_start_idx, first_val_end_idx, second_val_start_idx, second_val_end_idx):
    pre_tsi= first_val_start_idx-stim_idx
    pre_tei = first_val_end_idx-stim_idx
    post_tsi = second_val_start_idx-stim_idx
    post_tei = second_val_end_idx-stim_idx
    
    if first_val_start_idx!=first_val_end_idx:
        first_speed = np.mean(behavior[:,pre_tsi:pre_tei], axis = 1)
    else:
        first_val_start_idx = int(first_val_start_idx)
        first_speed = np.asarray(behavior[:,pre_tsi])

    if second_val_start_idx!=second_val_end_idx:
        second_speed = np.mean(behavior[:,post_tsi:post_tei], axis = 1)
    else: 
        second_speed = np.asarray(behavior[:,post_tsi])
    speed_change = second_speed-first_speed
    return speed_change

def get_trials(speed_change, thresh):
    decrease_trials = speed_change <-thresh
    decrease_idx = np.where(decrease_trials)
    increase_trials = speed_change>thresh
    increase_idx = np.where(increase_trials)
    flat_trials = np.logical_and(speed_change>-thresh, speed_change<thresh)
    flat_idx = np.where(flat_trials)
    return increase_trials, increase_idx, decrease_trials, decrease_idx, flat_trials, flat_idx

def separate_traces(behavior_struct, value_struct):

    increase_total= {}
    increase_trial_num = 0
    decrease_total= {}
    decrease_trial_num = 0
    flat_total= {}
    flat_trial_num = 0

    stim_idx, stim_end_idx, pre_trial_window_idx, first_val_end_idx, first_val_start_idx, second_val_end_idx, second_val_start_idx = get_vals_for_analysis(**value_struct)

    for key in behavior_struct:
        traces = behavior_struct[key]
        lpf_behavior = apply_butter_lowpass(traces, stim_idx, value_struct["fr"])
        speed_change = get_speed_change(lpf_behavior, stim_idx, first_val_start_idx, first_val_end_idx, second_val_start_idx, second_val_end_idx)
        increase_trials,increase_idx, decrease_trials, decrease_idx, flat_trials, flat_idx = get_trials(speed_change, value_struct["thresh"])
        increase_traces = traces[increase_trials]
        increase_trial_num += np.shape(increase_traces)[0]
        increase_total[key]={}
        increase_total[key]['traces'] = increase_traces
        increase_total[key]['idx'] = increase_idx
        decrease_traces = traces[decrease_trials]
        decrease_trial_num += np.shape(decrease_traces)[0]
        decrease_total[key]={}
        decrease_total[key]['traces'] = decrease_traces
        decrease_total[key]['idx'] = decrease_idx
        flat_traces = traces[flat_trials]
        flat_trial_num += np.shape(flat_traces)[0]
        flat_total[key]={}
        flat_total[key]['traces'] = flat_traces
        flat_total[key]['idx'] = flat_idx

    print(f"Increase trial number: {increase_trial_num}")
    print(f"Decrease trial number: {decrease_trial_num}")
    print(f"Flat trial number: {flat_trial_num}")
    return increase_total, decrease_total, flat_total

def get_visually_evoked_turns(traces, mean_turn, start, stop, r_thresh, av_thresh, stim_times, expected_direction):
    ### this will flip the sign of the trace to get the correct av_thresh comparison
    if expected_direction == 'pos':
        flip = 1
    elif expected_direction == 'neg':
        flip = -1


    mean_trace = mean_turn[start:stop] * flip * -1
    
    ### calculate correlation of each turn to mean turn within a defined window
    rs = []
    for i in range(traces.shape[0]):
        rs.append(scipy.stats.pearsonr(mean_trace, traces[i,start:stop])[0])
    
    turns = []
    stim_evoked_turn_times = []
    for i in range(traces.shape[0]):
        if rs[i]>r_thresh:
            if max(traces[i,start:stop]*flip) > av_thresh:
                turns.append(traces[i,:])
                stim_evoked_turn_times.append(stim_times[i])
    turns = np.asarray(turns)
    return turns, stim_evoked_turn_times

def make_STA_brain(neural_signals, neural_timestamps, event_times_list, neural_bins):
    #### super voxel version
    
    STA_brain = []
    for z in range(49):
        all_bin_indicies = []
        for stim_idx in range(len(event_times_list)):
            stim_time = event_times_list[stim_idx]
            stim_centered_bins = neural_bins + stim_time
            bin_indicies = np.digitize(neural_timestamps[:,z] , stim_centered_bins)
            all_bin_indicies.append(bin_indicies)
        all_bin_indicies = np.asarray(all_bin_indicies)

        avg_neural_across_bins = []
        for bin_num in np.arange(1,len(neural_bins)):
            this_bin_sample_times = list(np.where(all_bin_indicies==bin_num)[1])
            average_neural_in_bin = np.mean(neural_signals[z,:,this_bin_sample_times],axis=0)
            avg_neural_across_bins.append(average_neural_in_bin)
        avg_neural_across_bins = np.asarray(avg_neural_across_bins)
        STA_brain.append(avg_neural_across_bins)
    STA_brain = np.asarray(STA_brain)
    return STA_brain

def STA_supervoxel_to_full_res(STA_brain, cluster_labels):
    n_clusters = STA_brain.shape[2]
    n_tp = STA_brain.shape[1]
    
    reformed_STA_brain = []
    for z in range(49):
        colored_by_betas = np.zeros((n_tp, 256*128))
        for cluster_num in range(n_clusters):
            cluster_indicies = np.where(cluster_labels[z,:]==cluster_num)[0]
            colored_by_betas[:,cluster_indicies] = STA_brain[z,:,cluster_num,np.newaxis]
        colored_by_betas = colored_by_betas.reshape(n_tp,256,128)
        reformed_STA_brain.append(colored_by_betas)
    return np.asarray(reformed_STA_brain)

def load_fda_meanbrain():
    fixed_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/20220301_luke_2_jfrc_affine_zflip_2umiso.nii"#luke.nii"
    fixed_resolution = (2,2,2)
    fixed = np.asarray(nib.load(fixed_path).get_fdata().squeeze(), dtype='float32')
    fixed = ants.from_numpy(fixed)
    fixed.set_spacing(fixed_resolution)
    return fixed

def warp_STA_brain(STA_brain, fly, fixed, anat_to_mean_type):
    n_tp = STA_brain.shape[1]
    dataset_path = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20190101_walking_dataset'
    moving_resolution = (2.611, 2.611, 5)
    ###########################
    ### Organize Transforms ###
    ###########################
    warp_directory = os.path.join(dataset_path, fly, 'warp')
    warp_sub_dir = 'func-to-anat_fwdtransforms_2umiso'
    affine_file = os.listdir(os.path.join(warp_directory, warp_sub_dir))[0]
    affine_path = os.path.join(warp_directory, warp_sub_dir, affine_file)
    if anat_to_mean_type == 'myr':
        warp_sub_dir = 'anat-to-meanbrain_fwdtransforms_2umiso'
    elif anat_to_mean_type == 'non_myr':
        warp_sub_dir = 'anat-to-non_myr_mean_fwdtransforms_2umiso'
    else:
        print('invalid anat_to_mean_type')
        return
    syn_files = os.listdir(os.path.join(warp_directory, warp_sub_dir))
    syn_linear_path = os.path.join(warp_directory, warp_sub_dir, [x for x in syn_files if '.mat' in x][0])
    syn_nonlinear_path = os.path.join(warp_directory, warp_sub_dir, [x for x in syn_files if '.nii.gz' in x][0])
    ####transforms = [affine_path, syn_linear_path, syn_nonlinear_path]
    transforms = [syn_nonlinear_path, syn_linear_path, affine_path] ### INVERTED ORDER ON 20220503!!!!
    #ANTS DOCS ARE SHIT. THIS IS PROBABLY CORRECT, AT LEAST IT NOW WORKS FOR THE FLY(134) THAT WAS FAILING


    ### Warp timeponts
    warps = []
    for tp in range(n_tp):
        to_warp = np.rollaxis(STA_brain[:,tp,:,:],0,3)
        moving = ants.from_numpy(to_warp)
        moving.set_spacing(moving_resolution)
        ########################
        ### Apply Transforms ###
        ########################
        moco = ants.apply_transforms(fixed, moving, transforms)
        warped = moco.numpy()
        warps.append(warped)

    return warps

def extract_roi_signal_traces(roi_ids, roi_masks, all_warps, condition, hemi, signal_type):
    t0 = time.time()
    roi_time_avgs = []
    for roi in roi_ids[hemi]:
        mask = roi_masks[roi]
        masked_data = all_warps[condition][:,:,:,::-1]*mask[np.newaxis,:,:,:] #note z-flip
        if signal_type == 'max':
            roi_time_avg = np.max(masked_data,axis=(1,2,3))
        elif signal_type == 'mean':
            roi_time_avg = np.mean(masked_data,axis=(1,2,3))
        roi_time_avgs.append(roi_time_avg)
    print(time.time()-t0)
    return np.asarray(roi_time_avgs)

def apply_ants_trans(array, moving_resolution, fixed, transforms):
    if array.ndim>3:
        warpst=[]
        for i in range(np.shape(array)[-1]):
            moving = ants.from_numpy(array[...,i])
            moving.set_spacing(moving_resolution)
            moco = ants.apply_transforms(fixed, moving, transforms)
            warped = moco.numpy()
            warpst.append(warped)
    else:
        moving = ants.from_numpy(array)
        moving.set_spacing(moving_resolution)
        moco = ants.apply_transforms(fixed, moving, transforms, interpolator='nearestNeighbor')
        warpst = moco.numpy()
    return warpst

def warp_raw(data, steps, fixed, func_path):
    moving_resolution = (2.611, 2.611, 5)
    ###########################
    ### Organize Transforms ###
    ###########################
    warp_directory = os.path.join(func_path,'warp')
    warp_sub_dir = 'func-to-anat_fwdtransforms_2umiso'
    affine_file = os.listdir(os.path.join(warp_directory, warp_sub_dir))[0]
    affine_path = os.path.join(warp_directory, warp_sub_dir, affine_file)
    warp_sub_dir = 'anat-to-meanbrain_fwdtransforms_2umiso'
    syn_files = os.listdir(os.path.join(warp_directory, warp_sub_dir))
    syn_linear_path = os.path.join(warp_directory, warp_sub_dir, [x for x in syn_files if '.mat' in x][0])
    syn_nonlinear_path = os.path.join(warp_directory, warp_sub_dir, [x for x in syn_files if '.nii.gz' in x][0])
    ####transforms = [affine_path, syn_linear_path, syn_nonlinear_path]
    transforms = [syn_nonlinear_path, syn_linear_path, affine_path] ### INVERTED ORDER ON 20220503!!!!
    #ANTS DOCS ARE SHIT. THIS IS PROBABLY CORRECT, AT LEAST IT NOW WORKS FOR THE FLY(134) THAT WAS FAILING

    
    if np.array(data).ndim==4: #if warping brain
        warp_dims=[314, 146, 91, np.shape(data)[-1]]#this probs shouldn't be hard coded but idk what else to do here
        warps = np.zeros(warp_dims)
        ### Warp timeponts
    #     with h5py.File(save_dir, 'w') as f:
    #             dset = f.create_dataset('warps', warp_dims, dtype='float16', chunks=True)         

        for chunk_num in range(len(steps)):
    #                 t0 = time()
            if chunk_num + 1 <= len(steps)-1:
                print(chunk_num)
                chunkstart = steps[chunk_num]
                chunkend = steps[chunk_num + 1]
                chunk = np.array(data[:,:,:,chunkstart:chunkend]).astype(np.float)
                warps_chunk = apply_ants_trans(chunk, moving_resolution, fixed, transforms)
    #             print(np.shape(warps_chunk))
                warps_chunk = np.moveaxis(np.array(warps_chunk),0,-1)
                warps[..., chunkstart:chunkend] = np.nan_to_num(warps_chunk)
    #                     print(F"vol: {chunkstart} to {chunkend} time: {time()-t0}")
    else: #if warping timestamps
        data = np.array(data).astype(np.float)
        warps = apply_ants_trans(data, moving_resolution, fixed, transforms)
    return warps

def load_roi_hemi_ids():

    roi_ids = {}

    roi_ids['right'] = {
    6: 'PB',
    26: 'FB',
    23: 'EB',
    4: 'NO',
    54: 'BU_L',
    56: 'LAL_L',
    76: 'PVLP_L',
    ####################
    60: 'VES_L', 
    85: 'EPA_L',
    80: 'GOR_L',
    58: 'AMMC_L',
    ####################
    70: 'AL_L',
    64: 'MB_PED_L',
    65: 'MB_VL_L',
    66: 'MB_ML_L',
    81: 'MB_CA_L',
    75: 'AVLP_L',
    77: 'IVLP_L',
    57: 'CAN_L',
    67: 'FLA_L',
    50: 'PRW',
    9: 'SAD',
    49: 'GNG', 
    ####################
    72: 'SLP_L',   
    74: 'SMP_L',
    78: 'PLP_L',
    55: 'LH_L',
    83: 'IPS_L',
    82: 'SPS_L',
    63: 'CRE_L',
    84: 'SCL_L',  
    59: 'ICL_L',
    62: 'ATL_L',
    61: 'IB_L',
    73: 'SIP_L',
    ###################
    71: 'MED_L',
    53: 'LO_L',
    69: 'LP_L',
    79: 'AOTU_L' 
    }

    roi_ids['left'] = {
    6: 'PB',
    26: 'FB',
    23: 'EB',
    4: 'NO',
    5: 'BU_R',
    8: 'LAL_R',
    31: 'PVLP_R',
    ##################
    13: 'VES_R',  
    40: 'EPA_R',
    35: 'GOR_R',
    11: 'AMMC_R',
    ##################
    24: 'AL_R',
    17: 'MB_PED_R',
    18: 'MB_VL_R',
    19: 'MB_ML_R',
    36: 'MB_CA_R',
    30: 'AVLP_R',
    32: 'IVLP_R',
    10: 'CAN_R',
    20: 'FLA_R',
    50: 'PRW',
    9: 'SAD',
    49: 'GNG',
    ###################    
    27: 'SLP_R',
    29: 'SMP_R',
    33: 'PLP_R',
    7: 'LH_R',
    38: 'IPS_R',
    37: 'SPS_R',
    16: 'CRE_R',
    39: 'SCL_R',
    12: 'ICL_R',
    15: 'ATL_R',
    14: 'IB_R',
    28: 'SIP_R',
    ###################
    25: 'MED_R',
    3: 'LO_R',
    22: 'LP_R',
    34: 'AOTU_R'
    }

    ##################
    ### ROI LABELS ###
    ##################
    names = []
    for name in roi_ids['left'].values():
        if '_R' in name:
            names.append(name[:-2])
        else:
            names.append(name)

    return roi_ids, names