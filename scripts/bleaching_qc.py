import numpy as np
import sys
import os
import json
import matplotlib.pyplot as plt
from skimage.filters import threshold_triangle
import psutil
import dataflow as flow
import nibabel as nib

def main(args):

    logfile = args['logfile']
    directory = args['directory'] # directory will be a full path to either an anat/imaging folder or a func/imaging folder
    dirtype = args['dirtype']
    width = 120
    printlog = getattr(flow.Printlog(logfile=logfile), 'print_to_log')

    #################
    ### Load Data ###
    #################

    if dirtype == 'func':
        files = ['functional_channel_1', 'functional_channel_2']
    elif dirtype == 'anat':
        files = ['anatomy_channel_1', 'anatomy_channel_2']
    data_mean = {}
    for file in files:
        full_file = os.path.join(directory, file + '.nii')
        if os.path.exists(full_file):
            brain = np.asarray(nib.load(full_file).get_data(), dtype='uint16')
            data_mean[file] = np.mean(brain,axis=(0,1,2))
        else:
            printlog(F"Not found (skipping){file:.>{width-20}}")

    ##############################
    ### Output Bleaching Curve ###
    ##############################

    plt.rcParams.update({'font.size': 24})
    fig = plt.figure(figsize=(10,10))
    signal_loss = {}
    for file in data_mean:
        xs = np.arange(len(data_mean[file]))
        color='k'
        if file[-1] == '1': color='red'
        if file[-1] == '2': color='green'
        plt.plot(data_mean[file],color=color,label=file)
        linear_fit = np.polyfit(xs, data_mean[file], 1)
        plt.plot(np.poly1d(linear_fit)(xs),color='k',linewidth=3,linestyle='--')
        signal_loss[file] = linear_fit[0]*len(data_mean[file])/linear_fit[1]*-100
    plt.xlabel('Frame Num')
    plt.ylabel('Avg signal')
    loss_string = ''
    for file in data_mean:
        loss_string = loss_string + file + ' lost' + F'{int(signal_loss[file])}' +'%\n'
    plt.title(loss_string, ha='center', va='bottom')
    # plt.text(0.5,0.9,
    #          loss_string,
    #          horizontalalignment='center',
    #          verticalalignment='center',
    #          transform=plt.gca().transAxes)

    save_file = os.path.join(directory, 'bleaching.png')
    plt.savefig(save_file,dpi=300,bbox_inches='tight')

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))