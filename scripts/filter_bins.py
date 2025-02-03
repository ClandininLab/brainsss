import os
import sys
import brainsss.fictrac as fictrac
import numpy as np
import json
import brainsss
import h5py
import pickle
import gc


def main(args):
    fly_directory = args['fly_directory']
    fly= args['fly']
    dataset_path = args['dataset_path']
    save_directory = args['save_directory']
    timestamp_file = args['timestamp_file']
    # behavior = args['behavior']

    load_path = os.path.join(fly_directory, timestamp_file)
    event_times_path = os.path.join(dataset_path, 'later/event_times_split_dic.pkl')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    #######################
    ### BINS BINS BABYY ###
    #######################

    printlog("Beginning bin creation")
    
    behaviors = ['inc', 'dec', 'flat', 'total']
    
    #load timestamp data
    with h5py.File(load_path, 'r') as hf:
        ts = hf['data']
        dimst = np.shape(ts)
        printlog(f"Timestamp shape is {dimst}")
        
        #load event times
        with open(event_times_path, 'rb') as file:
            event_times_struct = pickle.load(file)
        printlog(f"Event times loaded from {event_times_path}")
        

        for behavior in behaviors:
            if f'filter_needs_{behavior}.h5' not in os.listdir(save_directory):
                fly_name= fly[4:7]
                printlog(f"Fly name is {fly_name} and behavior is {behavior}")
                starts_loom_ms = event_times_struct[fly_name][behavior]
                
                bin_start = -500; bin_end = 2000; bin_size = 100 #ms
                
                #if loom starts are outside of the neural data, remove them
                bool_starts=(starts_loom_ms>=(np.min(ts))) & (starts_loom_ms<=(np.max(ts)))
                starts_loom_ms=np.array(starts_loom_ms)
                starts_loom_ms=starts_loom_ms[bool_starts]
                
                bins_array=[]
                for loom in starts_loom_ms:
                #     print(loom)
                    start=loom+bin_start
                    end=loom+bin_end-bin_size
                #     edges=[start,end]
                    bins_array.append(start)
                    bins_array.append(end)
                # bins_test=np.vstack(bins_test)
                bins_array=np.array(bins_array)
                bins_shape=np.shape(bins_array)
                printlog(f"Bins shape is {bins_shape}")
                
                stepsize=100
                dims=np.shape(ts)
                steps = list(range(0,dims[-1],stepsize))
                steps.append(dims[-1])
                
                bin_idx = np.zeros(dims, dtype=int)
                
                for chunk_num in range(len(steps)):
                        if chunk_num + 1 <= len(steps)-1:
                            chunkstart = steps[chunk_num]
                            chunkend = steps[chunk_num + 1]
                            ts_chunk = ts[...,chunkstart:chunkend]
                            bin_idx[...,chunkstart:chunkend] = np.digitize(ts_chunk, bins_array) 
                bin_shape = [bin_start, bin_end]
            
                #save filter_needs
                filter_needs_file = os.path.join(save_directory, f'filter_needs_{behavior}.h5')
                with h5py.File(filter_needs_file, "w") as data_file:
                            data_file.create_dataset("bins", data=bin_idx)
                            data_file.create_dataset("loom_starts", data=starts_loom_ms)
                            data_file.create_dataset("bin_shape", data=bin_shape)
                
                printlog(f"Array for temp filter done. Data saved in {filter_needs_file}")
                # Delete variables to free up memory
                del ts, dimst, bins_array, starts_loom_ms, steps, bin_idx, bin_shape
                
                # Manually invoke the garbage collector
                gc.collect()
                
                
            else:
                printlog(f"Filter bins for {behavior} already exists. Skipping...")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

