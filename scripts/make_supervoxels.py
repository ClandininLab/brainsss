import os
import sys
import json
import numpy as np
import h5py
import time
import brainsss
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.image import grid_to_graph

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

	func_path = args['func_path']
	logfile = args['logfile']
	brain_file = args['brain_file']
	ch_num = args['ch_num']
	printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
	n_clusters = 2000

	### LOAD BRAIN ###

	brain_path = os.path.join(func_path, brain_file)
	with h5py.File(brain_path, 'r+') as h5_file:
		brain = np.nan_to_num(h5_file.get("data")[:].astype('float32'))
	printlog('brain shape: {}'.format(brain.shape))
	printlog('load duration: {} sec'.format(time.time()-t0))

	### MAKE CLUSTER DIRECTORY ###

	cluster_dir = os.path.join(func_path, 'clustering')
	if not os.path.exists(cluster_dir):
		os.mkdir(cluster_dir)

	### FIT CLUSTERS ###
	printlog('fitting clusters')
	shape= np.shape(brain)
	connectivity = grid_to_graph(shape[0],shape[1])
	cluster_labels = []
	for z in range(shape[-2]): #THIS SHOULD NOT BE HARD CODED
		neural_activity = brain[:,:,z,:].reshape(-1, shape[3])
		cluster_model = AgglomerativeClustering(n_clusters=n_clusters,
									memory=cluster_dir,
									linkage='ward',
									connectivity=connectivity)
		cluster_model.fit(neural_activity)
		cluster_labels.append(cluster_model.labels_)
	cluster_labels = np.asarray(cluster_labels)
	save_file = os.path.join(cluster_dir, 'cluster_labels_{}.npy'.format(ch_num))
	np.save(save_file,cluster_labels)

	### GET CLUSTER AVERAGE SIGNAL ###

	printlog('getting cluster averages')
	all_signals = []
	for z in range(shape[-2]):
		neural_activity = brain[:,:,z,:].reshape(-1, shape[3])
		signals = []
		for cluster_num in range(n_clusters):
			cluster_indicies = np.where(cluster_labels[z,:]==cluster_num)[0]
			mean_signal = np.mean(neural_activity[cluster_indicies,:], axis=0)
			signals.append(mean_signal)
		signals = np.asarray(signals)
		all_signals.append(signals)
	all_signals = np.asarray(all_signals)
	save_file = os.path.join(cluster_dir, 'cluster_signals_{}.npy'.format(ch_num))
	np.save(save_file, all_signals)
	printlog('Clustering done bitches')
	printlog(f'Saved in {cluster_dir}')

if __name__ == '__main__':
	main(json.loads(sys.argv[1]))