import os
import sys
import brainsss.fictrac as fictrac
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.image import grid_to_graph
import numpy as np
import json
import brainsss
import h5py
import ants
import psutil
import gc
import pickle

def main(args):
    later_path = args['later_path']
    temp_dir=args['temp_directory']
    cluster_dir = os.path.join(temp_dir, 'clustering')
    ch_num = args['ch_num']
    fly_nums = args['fly_num']

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ###########################
    ### INDIVIDUAL CLUSTERS ###
    ###########################

    printlog("Beginning individual clusters")
 
    n_clusters=500
    
    total_path = os.path.join(later_path, f'10flies_5sec_event_times_split_dic.pkl')
    with open(total_path, 'rb') as file:
        total_data_dict = pickle.load(file)
    
    for file in os.listdir(cluster_dir):
#     print(file)
        if f'_{n_clusters}' in file and 'labels' in file and 'total' in file:
            label_files=os.path.join(cluster_dir,file)
    giant_total_labels=np.load(label_files)
    
    giant_total_labels=giant_total_labels.reshape(314,146,91)
    for fly_num in fly_nums:
        printlog(f'Processing fly {fly_num}')
        dff_path = f'/oak/stanford/groups/trc/data/Ilana/2P/data/fly_{fly_num}/dff'
        warp_path = f'/oak/stanford/groups/trc/data/Ilana/2P/data/fly_{fly_num}/warp'
        for file in os.listdir(dff_path):
            if f'_{ch_num}_' in file:
                file_path=os.path.join(dff_path,file)
        for file in os.listdir(warp_path):
            if 'timestamps' in file:
                ts_path=os.path.join(warp_path,file)
        events=total_data_dict[str(fly_num)]['total']
        cluster_brains = {}
        range_r=np.arange(n_clusters)

        with h5py.File(file_path, 'r') as hf, h5py.File(ts_path, 'r') as tf:
            data_ds = hf['data']
            time_ds = tf['data']
            
            for cluster in range_r:
                # printlog(f"Processing cluster {cluster}")
                
                mask = (giant_total_labels == cluster)
                x_idx, y_idx, z_idx = np.where(mask)
                n_voxels = len(x_idx)
                
                if n_voxels == 0:
                    continue
                    
                voxel_data_cache = []
                voxel_times_cache = []

                for x, y, z in zip(x_idx, y_idx, z_idx):
                    voxel_data_cache.append(data_ds[x, y, z, :])
                    voxel_times_cache.append(time_ds[x, y, z, :])

                # Convert to numpy arrays for faster processing
                voxel_data_cache = np.array(voxel_data_cache)  # Shape: (n_voxels, timepoints)
                voxel_times_cache = np.array(voxel_times_cache) 
                cluster_brains[cluster] = {}
                for event_idx in range(np.shape(events)[0]):
                    event_time = events[event_idx]
                    
                    # Get 10 points AFTER the event (within 2 seconds)
                    if event_idx == np.shape(events)[0] - 1:  # FIXED: Last event
                        # Last event: can go up to 2 seconds after
                        seconds_after = 2
                        ms_per_unit = 10
                        units = (seconds_after * 1000) // ms_per_unit
                        time_max = event_time + units
                    else:
                        # For other events: stop at next event or 2 seconds, whichever comes first
                        seconds_after = 2
                        ms_per_unit = 10
                        units = (seconds_after * 1000) // ms_per_unit
                        time_max = min(events[event_idx + 1], event_time + units)

                    time_min = event_time
                    cluster_data = []
                    for voxel_idx in range(n_voxels):
                        voxel_times = voxel_times_cache[voxel_idx]
                        voxel_data = voxel_data_cache[voxel_idx]
                        
                        valid_indices = np.where((voxel_times >= time_min) & 
                                                (voxel_times <= time_max))[0]
                        
                        if len(valid_indices) >= 10:
                            matching_data = voxel_data[valid_indices[:5]]  # FIRST 5, not last 10
                        elif len(valid_indices) > 0:
                            matching_data = voxel_data[valid_indices]
                            matching_data = np.pad(matching_data, (0,5 - len(matching_data)), 
                                                constant_values=np.nan)  # Pad at END
                        else:
                            matching_data = np.full(10, np.nan)
                            
                        cluster_data.append(matching_data)
                    cluster_brains[cluster][event_idx] = np.nanmean(cluster_data, axis=0)
        save_file=os.path.join(later_path,f'{fly_num}_individual_clusters_ch_{ch_num}_after_dict.pkl')
        with open(save_file, 'wb') as file:
            pickle.dump(cluster_brains, file)
        printlog(f'Finished fly {fly_num} saved in {save_file}')
    
    
    
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

