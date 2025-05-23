import time
import sys
import os
import re
import json
import datetime
import pyfiglet
import textwrap
import brainsss.utils as brainsss
import argparse

def main(args):

    dataset_path = args.dataset_path
    scripts_path = args.PWD
    com_path = os.path.join(scripts_path, 'com')


    modules = 'gcc/6.3.0 python/3.6 py-numpy/1.14.3_py36 py-pandas/0.23.0_py36 viz py-scikit-learn/0.19.1_py36 antspy/0.2.2'

    #########################
    ### Setup preferences ###
    #########################

    width = 120 # width of print log
    flies = ['fly_001'] # set to None, or a list of fly dirs in dataset_path
    nodes = 2 # 1 or 2
    nice = True # true to lower priority of jobs. ie, other users jobs go first

    #####################
    ### Setup logging ###
    #####################

    logfile = './logs/' + time.strftime("%Y%m%d-%H%M%S") + '.txt'
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
    sys.stderr = brainsss.Logger_stderr_sherlock(logfile)

    ###################
    ### Setup paths ###
    ###################

    #CHANGE THESE PATHS
    # scripts_path = "/home/users/brezovec/projects/brainsss/scripts"
    # com_path = "/home/users/brezovec/projects/brainsss/scripts/com"

    # #change this path to your oak directory, something like /oak/stanford/groups/trc/data/Brezovec/data
    # dataset_path = "/home/users/brezovec/projects/brainsss/demo_data"

    ###################
    ### Print Title ###
    ###################

    title = pyfiglet.figlet_format("Yandan", font="cyberlarge" ) #28 #shimrod
    title_shifted = ('\n').join([' '*28+line for line in title.split('\n')][:-2])
    printlog(title_shifted)
    day_now = datetime.datetime.now().strftime("%B %d, %Y")
    time_now = datetime.datetime.now().strftime("%I:%M:%S %p")
    printlog(F"{day_now+' | '+time_now:^{width}}")
    printlog("")

    printlog("Dataset path: {}".format(dataset_path))
    printlog("Scripts path: {}".format(scripts_path))

    ### toy practice###
    printlog(f"\n{'   hi this is a toy   ':=^{width}}")
    job_ids = []
    a = 5
    b = 10
    args = {'logfile': logfile, 'dataset_path': dataset_path}
    script = '20220222_vol_moco.py'
    job_id = brainsss.sbatch(jobname='moco',
                         script=os.path.join(scripts_path, script),
                         modules=modules,
                         args=args,
                         logfile=logfile, time=96, mem=4, nice=nice, nodes=nodes)
    job_ids.append(job_id)

    for job_id in job_ids:
        brainsss.wait_for_job(job_id, logfile, com_path)
        

    ############
    ### Done ###
    ############

    time.sleep(3) # to allow any final printing
    day_now = datetime.datetime.now().strftime("%B %d, %Y")
    time_now = datetime.datetime.now().strftime("%I:%M:%S %p")
    printlog("="*width)
    printlog(F"{day_now+' | '+time_now:^{width}}")

if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    # this is the present working directory where the script was run
    parser.add_argument("PWD") 

    # you must provide the dataset path on the command line
    # If you do not, throw an exception
    parser.add_argument("dataset_path", default="MISSING", nargs='?') 
    args = parser.parse_args()
    try:
        message = "{}\n{}\n{}\n{}".format("Aborted! You probably forgot to provide a fly directory.",
        "This argument is required and must be listed on the command line directly after the name of the shell file.",
        "It must be a full path to the directory.",
        "See readme for how to structure your fly directory.")
        assert (args.dataset_path != "MISSING"), message
    except Exception as e:
        print (e)

    main(args)