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
    
    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    #######################
    ### SUPERCLUSTERING ###
    #######################

    printlog("Beginning superclustering")
 
    super_vox = 2000
    super_clust = 50000
    
    behave_dict_path=os.path.join(temp_dir,f'behave_dict_total_{event}.pkl')
    with open(behave_dict_path, 'rb') as file:
        behave_dict_total = pickle.load(file)
        behaviors=list(behave_dict_total.keys())
        printlog(f'behaviors are {list(behave_dict_total.keys())}')
    
    giant_cluster_labels = np.load(os.path.join(cluster_dir, 'cluster_labels_best_flies.npy'))
    supervox_dict_total=brainsss.make_supervox_dict(behave_dict_total, behaviors, super_vox,giant_cluster_labels)

    full_res={}
    for behave in supervox_dict_total:
        supervox_brain=np.moveaxis(supervox_dict_total[behave],-1,-2)
        full_res_brain=brainsss.supervoxel_to_full_res(supervox_brain, giant_cluster_labels, super_vox)
        full_res_brain=np.moveaxis(full_res_brain, 0,-1)
        full_res_brain=np.moveaxis(full_res_brain, 0,-1)
        full_res[behave]=np.asarray(full_res_brain)
        

    printlog('clustering.........')
    superclust_labels_dict={}
    superclust_dict = {}
    for behavior in full_res:
        brain=full_res[behavior]
        shape=np.shape(brain)
        
        connectivity = grid_to_graph(shape[0],shape[1],shape[2]).astype('float32')
        neural_activity= brain.reshape(-1, shape[-1])
        
        cluster_labels= []
        cluster_model= AgglomerativeClustering(connectivity=connectivity,
                                               n_clusters=super_clust,
                                               memory=None,
                                               linkage='ward')
        
        cluster_model.fit(neural_activity)
        cluster_labels = np.asarray(cluster_model.labels_)
        printlog(f'shape of cluster labels {np.shape(cluster_labels)}')
        superclust_labels_dict[behavior]=cluster_labels
        printlog(f'done with {behavior} trial labels')

        behavior_superclusters = []
        for cluster_num in range(super_clust):
            labels= superclust_labels_dict[behavior]
            cluster_indicies= np.where(labels==cluster_num)[0]
            mean_signal = np.mean(neural_activity[cluster_indicies,:], axis=0)
            behavior_superclusters.append(mean_signal)
        superclust_dict[behavior] = np.asarray(behavior_superclusters)
        
        
         # Clean up
        del brain, neural_activity, connectivity, cluster_model
        gc.collect()
        printlog(f'done with {behavior} superclustering')
    
    save_file_labels = os.path.join(cluster_dir, f'superclust_labels_{super_clust}_{event}.pkl')
    save_file_clusters = os.path.join(cluster_dir, f'superclust_clusters_{super_clust}_{event}.pkl')
    
    printlog(f'Saving labels to {save_file_labels}')
    with open(save_file_labels, 'wb') as file:
        pickle.dump(superclust_labels_dict, file)
    
    printlog(f'Saving labels to {save_file_clusters}')
    with open(save_file_clusters, 'wb') as file:
        pickle.dump(superclust_dict, file)
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

