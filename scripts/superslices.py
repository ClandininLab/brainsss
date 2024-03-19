import os
import sys
import json
import numpy as np
import h5py
import time
import brainsss
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.image import grid_to_graph
import nibabel as nib

def warn(*args, **kwargs):
    pass
import warnings
warnings.warn = warn
'''
Suppressing this warning from AgglomerativeClustering:
UserWarning: Persisting input arguments took 1.06s to run.
If this happens often in your code, it can cause performance problems
(results will be correct in all cases).
The reason for this is probably some large input arguments for a wrapped
 function (e.g. large strings).
THIS IS A JOBLIB ISSUE. If you can, kindly provide the joblib's team with an
 example so that they can fix the problem.
  **kwargs)
 '''

def main(args):

    dataset_path = args['dataset_path']
    fly_dirs = args['fly_dirs']#.split(',')
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
    n_clusters = 2000
    z_dim = 36

    ###############################
    ### MAKE SUPERFLY DIRECTORY ###
    ###############################
    printlog(str(fly_dirs))

    day = time.strftime("%Y%m%d")
    superfly_dir = os.path.join(dataset_path,F'{day}_superfly')
    if not os.path.exists(superfly_dir):
        os.mkdir(superfly_dir)

    slices_dir = os.path.join(superfly_dir, 'superslices')
    if not os.path.exists(slices_dir):
        os.mkdir(slices_dir)

    ####################################################
    ### each z-slice will be clustered independently ###
    ####################################################
    cluster_labels_all = []
    signals_all = []
    for z in range(z_dim):
        printlog(F'z: {z}')

        ###################
        ### LOAD BRAINS ###
        ###################
        brain_superslice = []
        for fly in fly_dirs:
            brain_path = os.path.join(dataset_path, fly, 'func_0', 'brain_in_FDA.nii')
            brain = np.nan_to_num(np.asarray(nib.load(brain_path).get_data().squeeze(), dtype='float32'))
            brain_superslice.append(brain[:,:,z,:])

        dims = {'x': brain.shape[0],
                'y': brain.shape[1],
                't': int(brain.shape[3]*len(fly_dirs))}

        brain_superslice = np.asarray(brain_superslice) ### will be shape nfly,x,y,t
        brain_superslice = np.moveaxis(brain_superslice,0,2) ###x,y,n,t

        ####################
        ### FIT CLUSTERS ###
        ####################
        connectivity = grid_to_graph(dims['x'],dims['y'])
        brain_superslice = brain_superslice.reshape(-1, dims['t'])
        cluster_model = AgglomerativeClustering(n_clusters=n_clusters,
                                    memory=slices_dir,
                                    linkage='ward',
                                    connectivity=connectivity)
        cluster_model.fit(brain_superslice)
        cluster_labels = np.asarray(cluster_model.labels_)
        cluster_labels_all.append(cluster_labels)

        ##################################
        ### GET CLUSTER AVERAGE SIGNAL ###
        ##################################
        signals = []
        for cluster_num in range(n_clusters):
            cluster_indicies = np.where(cluster_labels==cluster_num)[0]
            mean_signal = np.mean(brain_superslice[cluster_indicies,:], axis=0)
            signals.append(mean_signal)
        signals = np.asarray(signals)
        signals_all.append(signals)

    ############
    ### SAVE ###
    ############

    cluster_labels_all = np.asarray(cluster_labels_all)
    save_file = os.path.join(slices_dir, 'cluster_labels.npy')

    signals_all = np.asarray(signals_all)
    save_file = os.path.join(slices_dir, 'cluster_signals.npy')

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))