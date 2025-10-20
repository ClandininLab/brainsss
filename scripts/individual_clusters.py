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
    event = args['event']
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

    printlog("Beginning indivudal clusters")
 
    n_clusters=500
    
    total_path = os.path.join(later_path, f'{event}_event_times_split_dic.pkl')
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
        event_time_bins=[]
        for event in total_data_dict[str(fly_num)]['total'][:198]:
            seconds_before = 2
            ms_per_unit = 10

            units_to_subtract = (seconds_before * 1000) // ms_per_unit
            new_timepoint = event - units_to_subtract
            event_edges=[new_timepoint,event]
            event_time_bins.append(event_edges)
        event_time_bins=np.asarray(event_time_bins)
        
        time_bins = event_time_bins
        cluster_brains = {}
        range_r=np.arange(n_clusters)

        with h5py.File(file_path, 'r') as hf, h5py.File(ts_path, 'r') as tf:
            data_ds = hf['data']
            time_ds = tf['data']
            
            for cluster in range_r:
                printlog(f"Processing cluster {cluster}")
                
                mask = (giant_total_labels == cluster)
                x_idx, y_idx, z_idx = np.where(mask)
                n_voxels = len(x_idx)
                
                if n_voxels == 0:
                    continue
                    
                # Initialize dictionary for this cluster's bins
                cluster_data = {}
                for bin_idx in range(len(time_bins)):
                    cluster_data[bin_idx] = []
                
                for i, (x, y, z) in enumerate(zip(x_idx, y_idx, z_idx)):
                    voxel_times = time_ds[x, y, z, :]
                    voxel_data = data_ds[x, y, z, :]
                    
                    # For each time bin, find matching data
                    for bin_idx, (start_time, end_time) in enumerate(time_bins):
                        in_bin = (voxel_times >= start_time) & (voxel_times <= end_time)
                        
                        if np.any(in_bin):
                            matching_times = voxel_times[in_bin]
                            matching_data = voxel_data[in_bin]
                            
                            for t, d in zip(matching_times, matching_data):
                                cluster_data[bin_idx].append([x, y, z, t, d])
                
                # Convert to arrays and store
                cluster_brains[cluster] = {}
                for bin_idx in range(len(time_bins)):
                    if cluster_data[bin_idx]:
                        cluster_brains[cluster][bin_idx] = np.array(cluster_data[bin_idx])
        #                 print(f"Cluster {cluster}, Bin {bin_idx}: {len(cluster_data[bin_idx])} points")
                    else:
                        cluster_brains[cluster][bin_idx] = np.array([]).reshape(0, 5)
        
        # Access data:
        # cluster_brains[cluster_id][bin_index] gives you array with [x, y, z, time, value]
        cluster_averages = {}
        for cluster in cluster_brains:
            cluster_averages[cluster] = {}
            for bin_idx in cluster_brains[cluster]:
                data = cluster_brains[cluster][bin_idx]
                if len(data) > 0:
                    # data columns are [x, y, z, timestamp, data_value]
                    # Group by timestamp and average the data_values
                    unique_times = np.unique(data[:, 3])  # Get unique timestamps
                    averaged_data = []
                    
                    for time_point in unique_times:
                        # Find all spatial points at this timepoint
                        time_mask = data[:, 3] == time_point
                        spatial_values = data[time_mask, 4]  # Get all data_values at this time
                        avg_value = np.mean(spatial_values)
                        averaged_data.append([time_point, avg_value])
                    
                    cluster_averages[cluster][bin_idx] = np.array(averaged_data)
        #             print(f"Cluster {cluster}, Bin {bin_idx}: {len(averaged_data)} time points")
                else:
                    cluster_averages[cluster][bin_idx] = np.array([]).reshape(0, 2)
        save_file=os.path.join(later_path,f'{fly_num}_{event}_individual_clusters_ch_{ch_num}_dict.pkl')
        with h5py.File(save_file, "w") as data_file:
                    data_file.create_dataset("data", data=cluster_averages)
        printlog(f'Finished fly {fly_num} saved in {save_file}')
    
    
    
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

