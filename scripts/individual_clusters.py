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
    event = args['event']
    redo=args['redo']
    n_clusters = args['clust_num']
    total_path = args['event_times_path']

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
 
    n_clusters=n_clusters
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
        save_file=os.path.join(later_path,f'{fly_num}_individual_clusters_new_ch_{ch_num}_dict.pkl')
        if not os.path.exists(save_file) or redo:
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
                            # Define time window
                        if event_idx == 0:
                            # First event: get last 10 points before it
                            time_min = -np.inf
                        else:
                            # Subsequent events: start 2 seconds after previous event
                            seconds_after = 2
                            ms_per_unit = 10
                            units = (seconds_after * 1000) // ms_per_unit
                            time_min = events[event_idx - 1] + units

                        time_max = event_time
                        cluster_data = []
                        for voxel_idx in range(n_voxels):
                            voxel_times = voxel_times_cache[voxel_idx]
                            voxel_data = voxel_data_cache[voxel_idx]
                            
                            valid_indices = np.where((voxel_times >= time_min) & 
                                                    (voxel_times <= time_max))[0]
                            
                            if len(valid_indices) >= 10:
                                matching_data = voxel_data[valid_indices[-10:]]
                            elif len(valid_indices) > 0:
                                if event_idx % 10 == 0 and voxel_idx == 0:  # Reduce log spam
                                    printlog(f"Warning: Only {len(valid_indices)} timepoints before event {event_idx} for cluster {cluster}")
                                matching_data = voxel_data[valid_indices]
                                matching_data = np.pad(matching_data, (10 - len(matching_data), 0), 
                                                    constant_values=np.nan)
                            else:
                                matching_data = np.full(10, np.nan)
                                
                            cluster_data.append(matching_data)
                        cluster_brains[cluster][event_idx] = np.nanmean(cluster_data, axis=0)
            with open(save_file, 'wb') as file:
                pickle.dump(cluster_brains, file)
            printlog(f'Finished fly {fly_num} saved in {save_file}')
        else:
            printlog(f"File {save_file} already exists, skipping fly {fly_num}")    
    
    
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

