import os
import sys
import numpy as np
import json
import brainsss
import h5py
import gc
import pickle

def load_STA(STA_path):
    # same cleanup as brainsss.make_multi_behave_dict; (steps, x, y, z) -> (x, y, z, steps)
    with h5py.File(STA_path, 'r') as sf:
        brain = sf['data'][:]
    brain[np.isnan(brain)] = 0
    brain[np.isinf(brain)] = 4
    return np.moveaxis(brain, 0, -1)

def main(args):
    later_path = args['later_path']
    STA_dir = args['STA_directory']
    event = args['event']


    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    #########################################################
    ### DUAL CHANNEL REMOVE NOISE VIA REGRESSION, ONE FLY ###
    #########################################################

    printlog(f"Beginning native regression noise removal in {STA_dir}")
    step_size=100
    if event != None:
        event_times_path = os.path.join(later_path, f'{event}_event_times_split_dic.pkl')
        event_suffix = f'_{event}'
    else:
        event_times_path = os.path.join(later_path, 'event_times_split_dic.pkl')
        event_suffix = ''
    with open(event_times_path, 'rb') as file:
        event_times_struct = pickle.load(file)
        f=list(event_times_struct.keys())[0]
        behaviors=list(event_times_struct[f].keys())
        printlog(f"Found behaviors: {behaviors}")

    # build_STA --native writes stepsize_{N}_STA_{ch}_native_{behavior}{_event}.h5 for each channel
    n_done = 0
    for behave in behaviors:
        printlog(behave)
        green_path = os.path.join(STA_dir, f'stepsize_{step_size}_STA_2_native_{behave}{event_suffix}.h5')
        red_path = os.path.join(STA_dir, f'stepsize_{step_size}_STA_1_native_{behave}{event_suffix}.h5')
        if not os.path.exists(green_path) or not os.path.exists(red_path):
            printlog(f"Skipping behavior {behave} due to missing data.")
            continue
        arr_g = load_STA(green_path)
        arr_r = load_STA(red_path)
        printlog(f'green shape: {np.shape(arr_g)}, red shape: {np.shape(arr_r)}')
        if np.shape(arr_g) != np.shape(arr_r):
            printlog(f"Skipping behavior {behave}: channel shapes differ.")
            continue

        total_behave=brainsss.dual_channel_remove_noise(arr_r, arr_g, printlog)

        # save in build_STA's (steps, x, y, z) layout, next to the STAs
        save_file = os.path.join(STA_dir, f'stepsize_{step_size}_STA_regressed_native_{behave}{event_suffix}.h5')
        with h5py.File(save_file, "w") as data_file:
            data_file.create_dataset("data", data=np.moveaxis(total_behave, -1, 0).astype('float32'))
        printlog(f"Regressed {behave}. Data saved in {save_file}")
        n_done += 1

        del arr_g, arr_r, total_behave
        gc.collect()

    printlog(f'Successfully regressed {n_done} of {len(behaviors)} behaviors')
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))
