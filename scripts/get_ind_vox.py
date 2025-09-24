import os
import sys
import brainsss.fictrac as fictrac
import numpy as np
import json
import brainsss
import h5py
import ants
import gc
import pickle


def main(args):
    dataset_path = args['dataset_path']
    later_path = args['later_path']
    event = args['event']
    flies = args['fly_num']
    channel = args['ch_num']
    
    
    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ##################################
    ### making stuff for tom sighs ###
    ##################################

    printlog("Beginning indivdual vox getting")
    
    later_dir=os.path.join(later_path, 'temp_filter')
    
    supercluster_labels=np.load(os.path.join(later_dir, 'clustering', 'supercluster_labels_total_500.npy'))
    
    event_times_path = os.path.join(later_path, f'{event}_event_times_split_dic.pkl')
    with open(event_times_path, 'rb') as file:
        event_times_struct = pickle.load(file)
        f=list(event_times_struct.keys())[0]
        behaviors=list(event_times_struct[f].keys())
        printlog(f"Found behaviors: {behaviors}")
    
    fly_superclust_dict={'inc':{}, 'dec':{}, 'flat':{}, 'total':{}}
    # range_start=-2000; range_end=3000; steps=500
    intervals=np.asarray([[-600,0],[700,1300]])
    super_clust=500
    # n_steps = len(range(range_start, range_end, steps))

    for b in behaviors:
        for fn in flies:
            fly=f'fly_{fn}'
            temp_dir=os.path.join(dataset_path,fly,'temp_filter')
            for fx in os.listdir(temp_dir):
                if '500_' not in fx and f'_{b}_' in fx and event in fx and f'_{channel}_' in fx:
                    printlog(fly,fx)
                    file_need=(fx)
                    if file_need!=[]:
                        path=os.path.join(temp_dir,file_need)
                        with h5py.File(path, 'r') as hf:
                            brain = hf['brain']
                            ts = hf['time_stamps'][:]
                            dimsb = np.shape(brain)
                            dimst = np.shape(ts)
                            printlog(f"Brain shape is {dimsb}, time stamp shape is {dimst}")
                            temp=[]
                            for interval in intervals:
    #                             start=i
    #                             end = i + steps if i + steps < range_end else range_end
                                start=interval[0]; end=interval[1]
                                mask = (ts > start) & (ts < end)
                                result = np.where(mask, brain, np.nan)
                                temp.append(result)
                            temp=np.asarray(temp)
                            brain_w_ts=np.moveaxis(temp,0,-1)
                            five_shape=brain_w_ts.shape
                            printlog(five_shape)
                            brain_new=brain_w_ts
                            neural_activity= brain_new.reshape(-1, five_shape[-2], five_shape[-1])

                            behavior_superclusters = []
                            for cluster_num in range(super_clust):
                                labels= supercluster_labels
                                cluster_indicies= np.where(labels==cluster_num)[0]
                                mean_signal = np.mean(neural_activity[cluster_indicies,:], axis=0)
                                behavior_superclusters.append(mean_signal)
                            behavior_superclusters = np.asarray(behavior_superclusters)
                            printlog(behavior_superclusters.shape)
                            fly_superclust_dict[b][fn]=behavior_superclusters
                            del brain,neural_activity,behavior_superclusters,brain_new,ts,result,mask,labels,mean_signal
                            gc.collect()
                    else:
                        printlog(f'{fly} does not contribute to this behavior')
    file_path=os.path.join(later_dir, 'clustering', 'individual_fly_superclusters_2bin_total.pkl')
    with open(file_path, 'wb') as file:
            pickle.dump(fly_superclust_dict, file)

    printlog(f'Successfully saved to {file_path}')
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))
