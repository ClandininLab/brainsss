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
import pickle

def main(args):
    later_path = args['later_path']
    temp_dir=args['temp_directory']
    event = args['event']
    redo=args['redo']
    event_times_path = args['event_times_path']
    
    
    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ################################################
    ### DUAL CHANNEL REMOVE NOISE VIA REGRESSION ###
    ################################################

    printlog("Beginning regression noise removal")
    step_size=100
    if event != None:
        save_file = os.path.join(temp_dir, f'behave_dict_total_{event}.pkl')
    else:
        save_file = os.path.join(temp_dir, 'behave_dict_total.pkl')
    with open(event_times_path, 'rb') as file:
        event_times_struct = pickle.load(file)
        f=list(event_times_struct.keys())[0]
        behaviors=list(event_times_struct[f].keys())
        printlog(f"Found behaviors: {behaviors}")
    
    if not os.path.exists(save_file) or redo:
        # Load STAs for each behavior and channel
        behave_dict_g = brainsss.make_multi_behave_dict(behaviors,temp_dir,step_size,event,2, printlog)
        behave_dict_r = brainsss.make_multi_behave_dict(behaviors,temp_dir,step_size,event,1, printlog)
        
        # Remove noise from each behavior using dual channel regression
        behave_dict_total={}
        for behave in behaviors:
            printlog(behave)
            arr_g=behave_dict_g[behave]
            arr_r=behave_dict_r[behave]
            if arr_g == [] or arr_r == []:
                printlog(f"Skipping behavior {behave} due to missing data.")
            else:
                total_behave=brainsss.dual_channel_remove_noise(arr_r, arr_g, printlog)
                behave_dict_total[behave]=total_behave
            
        # Save the results to pickle file
        if behave_dict_total == {}:
            printlog("No behaviors were processed. Exiting without saving.")
            return
        else:
            printlog(f'Saving dict to {save_file}')
            with open(save_file, 'wb') as file:
                pickle.dump(behave_dict_total, file)
            
        # to open: 
        # with open('behave_dict_total_event.pkl', 'rb') as file:
            # loaded_dict = pickle.load(file)

            printlog(f'Successfully saved {len(behave_dict_total)} behaviors to pickle')
    else:
        printlog(f"File {save_file} already exists, skipping regression noise removal")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

