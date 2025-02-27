import os
import sys
import brainsss.fictrac as fictrac
from scipy.ndimage import gaussian_filter1d
import numpy as np
import json
import brainsss
import h5py
import ants
import psutil
import gc

def STA_supervoxel_to_full_res(STA_brain, cluster_labels):
    n_clusters = STA_brain.shape[2]
    n_tp = STA_brain.shape[1]
    brain_dims=[314,146]
    
    reformed_STA_brain = []
    for z in range(STA_brain.shape[0]):
        colored_by_betas = np.zeros((n_tp, brain_dims[0]*brain_dims[1]))
        for cluster_num in range(n_clusters):
            cluster_mask = cluster_labels[z,:]==cluster_num
#             print(cluster_indicies)
            colored_by_betas[:,cluster_mask] = STA_brain[z,:,cluster_num,np.newaxis]
        colored_by_betas = colored_by_betas.reshape(n_tp,brain_dims[0],brain_dims[1])
        reformed_STA_brain.append(colored_by_betas)
    return np.asarray(reformed_STA_brain)


def main(args):
    fly_directory = args['fly_directory']
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    ch_num = args['ch_num'] 
    
    steps=100

    cluster_dir = os.path.join(fly_directory, 'func_0','clustering')
    
    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ###########
    ### STA ###
    ###########

    printlog("Beginning STA")
    behaviors = ['inc', 'dec', 'flat', 'total']
    for behavior in behaviors:
    #load brain
        tf_load_path = os.path.join(load_directory, f"functional_channel_{ch_num}_moco_warp_blurred_hpf_dff_filtered_{behavior}.h5")
        save_file = os.path.join(save_directory, 'stepsize_'+str(steps)+ f'_STA_{behavior}.h5')
        if os.path.exists(save_file)==False:
            with h5py.File(tf_load_path, 'r') as hf:    
                ts = hf['time_stamps'][:]
                dimst = np.shape(ts)
            printlog(f"time stamp shape is {dimst}")
            label_name =''
            signal_name =''

            for x in sorted(os.listdir(cluster_dir)):
                if 'label' in x and ch_num in x and behavior in x:
                    label_name = x
                    load_file = os.path.join(cluster_dir, label_name)
                    cluster_labels = np.load(load_file)
                if 'signals' in x and ch_num in x and behavior in x:
                    signal_name = x
                    load_file = os.path.join(cluster_dir, signal_name)
                    all_signals = np.load(load_file)
                    
            printlog(label_name)
            printlog(signal_name)
            all_signals_new=np.moveaxis(all_signals,-1,1)
            printlog(str(np.shape(all_signals_new)))
            
            STA_brain = np.nan_to_num(all_signals_new)
            reformed_STA_brain = STA_supervoxel_to_full_res(STA_brain, cluster_labels)
            STA_brain = gaussian_filter1d(reformed_STA_brain,sigma=1,axis=1,truncate=1)
            STA_brain_temp=np.moveaxis(STA_brain,0,-1).astype('float32')
            STA_brain_final=np.moveaxis(STA_brain_temp,0,-1)
            range_start=-500; range_end=1900
            STA=[]  
            
            for i in range(range_start, range_end, steps):
                end = i + steps if i + steps < range_end else range_end
                mask = (ts > i) & (ts < end)
                result = np.mean(np.where(mask, STA_brain_final, np.nan), axis=-1)
                STA.append(result)
            STA=np.asarray(STA)
        
            with h5py.File(save_file, "w") as data_file:
                    data_file.create_dataset("data", data=STA.astype('float32'))
            
            printlog(f"STA for {behavior} done. Data saved in {save_file}")
            # Delete variables to free up memory
            del ts, dimst, label_name, signal_name, cluster_labels, all_signals, all_signals_new
            del STA_brain, reformed_STA_brain, STA_brain_temp, STA_brain_final, STA
            
            # Manually invoke the garbage collector
            gc.collect()
                    
            
        else:
            printlog(f'STA for {behavior} already exists. Skipping...')
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

