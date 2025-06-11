import os
import sys
import brainsss.fictrac as fictrac
import numpy as np
import json
import brainsss
import h5py
import ants
import shutil
import pickle

def main(args):
    later_dir = args['later_directory']
    cc = args['ch_num'] 
    event = args['event']
    flies = args['fly_num']
    dataset_path = args['dataset_path']
    scratch_dir = args['scratch_dir']
    
    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ##################################
    ### TRANSFERRING FILTERED DATA ###
    ##################################
    
    printlog("Beginning transfer of filtered data")
    if event != None:
        event_times_path = os.path.join(later_dir, f'{event}_event_times_split_dic.pkl')
    else:
        event_times_path = os.path.join(later_dir, 'event_times_split_dic.pkl')
    with open(event_times_path, 'rb') as file:
        event_times_struct = pickle.load(file)
        f=list(event_times_struct.keys())[0]
        behaviors=list(event_times_struct[f].keys())
    
    
    for behavior in behaviors:
        for fly in flies:
            fly_path = os.path.join(dataset_path, fly)
            files = os.listdir(os.path.join(fly_path, 'temp_filter'))
            if event == None:
                file = f"functional_channel_{cc}_moco_warp_blurred_hpf_dff_filtered_{behavior}.h5"
                new_file = f"{fly}_tf_{behavior}_{cc}.h5"
            else:
                file = f"functional_channel_{cc}_moco_warp_blurred_hpf_dff_filtered_{behavior}_{event}.h5"
                new_file = f"{fly}_tf_{behavior}_{cc}_{event}.h5"
            if file in files:
                source_path = os.path.join(fly_path, 'temp_filter', file)
                destination_path = os.path.join(scratch_dir, 'tf', new_file)
                with h5py.File(source_path, "r") as source:
                    fly_brain = source['brain']
                    fly_ts = source['time_stamps']
                    with h5py.File(destination_path, "w") as target:
                        target.create_dataset("brain", data=fly_brain)
                        target.create_dataset("time_stamps", data=fly_ts)

            else:
                printlog("Not there yet!")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

