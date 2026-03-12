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
    clust_num = args['clust_num']
    redo=args['redo']
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
    super_clust = clust_num
    
    save_file_clusters = os.path.join(cluster_dir, f'superclust_clusters_{super_clust}_{event}.pkl')
    if not os.path.exists(save_file_clusters) or redo:
        
        behave_dict_path=os.path.join(temp_dir,f'behave_dict_total_{event}.pkl')
        giant_vox_labels = np.load(os.path.join(cluster_dir, 'cluster_labels_best_flies.npy'))
        full_res = brainsss.vox_to_full_res(behave_dict_path, giant_vox_labels, super_vox)
        fixed = brainsss.load_fda_meanbrain().numpy()
        
        printlog('clustering.........')
        giant_cluster_labels_path = os.path.join(cluster_dir, f'supercluster_labels_total_{super_clust}.npy')
        if not os.path.exists(giant_cluster_labels_path):
            total_dict_path=os.path.join(temp_dir,'behave_dict_total_10flies.pkl')
            full_res_total = brainsss.vox_to_full_res(total_dict_path, giant_vox_labels, super_vox)
            brain_total=full_res_total['total']
            brain_total=np.where(fixed[...,None]>0.1,brain_total, np.nan)
            brain_total=np.nan_to_num(brain_total)
            shape=np.shape(brain_total)

            connectivity = grid_to_graph(shape[0],shape[1],shape[2]).astype('float32')
            neural_activity_total= brain_total.reshape(-1, shape[-1])

            giant_cluster_labels= []
            cluster_model= AgglomerativeClustering(connectivity=connectivity,
                                                n_clusters=super_clust,
                                                memory=None,
                                                linkage='ward')

            cluster_model.fit(neural_activity_total)
            giant_cluster_labels = np.asarray(cluster_model.labels_)
            printlog(f'shape of cluster labels {np.shape(giant_cluster_labels)}')
            
            np.save(giant_cluster_labels_path, giant_cluster_labels)
            
            del brain_total, neural_activity_total, connectivity, cluster_model
            gc.collect()
        else:
            giant_cluster_labels = np.load(giant_cluster_labels_path)
        
        superclust_dict = {}
        for behavior in full_res:
            brain=full_res[behavior]
            neural_activity= brain.reshape(-1, np.shape(brain)[-1])

            behavior_superclusters = []
            for cluster_num in range(super_clust):
                labels= giant_cluster_labels
                cluster_indicies= np.where(labels==cluster_num)[0]
                mean_signal = np.mean(neural_activity[cluster_indicies,:], axis=0)
                behavior_superclusters.append(mean_signal)
            superclust_dict[behavior] = np.asarray(behavior_superclusters)
            
            
            # Clean up
            del brain, neural_activity
            gc.collect()
            printlog(f'done with {behavior} superclustering')
        
        
        
        printlog(f'Saving clusters to {save_file_clusters}')
        with open(save_file_clusters, 'wb') as file:
            pickle.dump(superclust_dict, file)
    else:        printlog(f"File {save_file_clusters} already exists, skipping superclustering")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

