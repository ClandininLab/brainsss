import time
import sys
import os
import re
import json
import datetime
import pyfiglet
import textwrap
import brainsss
import argparse

def main(args):

    modules = 'gcc/6.3.0 python/3.6 py-numpy/1.14.3_py36 py-pandas/0.23.0_py36 viz py-scikit-learn/0.19.1_py36 antspy/0.2.2'

    #########################
    ### Setup preferences ###
    #########################

    width = 120 # width of print log
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

    scripts_path = args.PWD
    com_path = os.path.join(scripts_path, 'com')
    user = scripts_path.split('/')[3]

    '''
    is user == "example":
        imports_path: directory where brukerbridge dumps data. This path is only used if build_flies = True
        dataset_path: directory where files to be processed are
        ... in progress
    '''
    if user == "brezovec":
        imports_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/imports/build_queue"
        dataset_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20190101_walking_dataset"
        build_flies = False # If false, you must provide a list of fly_dirs in dataset_path to process
        fly_dirs = ['fly_123']#None#['fly_111'] # Set to None, or a list of fly dirs in dataset_path


    ###################
    ### Print Title ###
    ###################

    title = pyfiglet.figlet_format("Brainsss", font="cyberlarge" ) #28 #shimrod
    title_shifted = ('\n').join([' '*28+line for line in title.split('\n')][:-2])
    printlog(title_shifted)
    day_now = datetime.datetime.now().strftime("%B %d, %Y")
    time_now = datetime.datetime.now().strftime("%I:%M:%S %p")
    printlog(F"{day_now+' | '+time_now:^{width}}")
    printlog("")

    #printlog("Dataset path: {}".format(dataset_path))
    printlog("Scripts path: {}".format(scripts_path))
    printlog("User: {}".format(user))

    if build_flies:

        ######################
        ### CHECK FOR FLAG ###
        ######################

        printlog(f"\n{'   CHECK FOR FLAG   ':=^{width}}")
        args = {'logfile': logfile, 'imports_path': imports_path}
        script = 'check_for_flag.py'
        job_id = brainsss.sbatch(jobname='flagchk',
                             script=os.path.join(scripts_path, script),
                             modules=modules,
                             args=args,
                             logfile=logfile, time=1, mem=1, nice=nice, nodes=nodes)
        flagged_dir = brainsss.wait_for_job(job_id, logfile, com_path)

        ###################
        ### Build flies ###
        ###################

        printlog(f"\n{'   BUILD FLIES   ':=^{width}}")
        args = {'logfile': logfile, 'flagged_dir': flagged_dir.strip('\n'), 'dataset_path': dataset_path, 'fly_dirs': fly_dirs}
        script = 'fly_builder.py'
        job_id = brainsss.sbatch(jobname='bldfly',
                             script=os.path.join(scripts_path, script),
                             modules=modules,
                             args=args,
                             logfile=logfile, time=1, mem=1, nice=nice, nodes=nodes)
        func_and_anats = brainsss.wait_for_job(job_id, logfile, com_path)
        func_and_anats = func_and_anats.split('\n')[:-1]
        funcs = [x.split(':')[1] for x in func_and_anats if 'func:' in x] # will be full paths to fly/expt
        anats = [x.split(':')[1] for x in func_and_anats if 'anat:' in x]

    else:
        funcs = []
        anats = []
        for fly_dir in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly_dir)
            funcs.extend([os.path.join(fly_directory, x) for x in os.listdir(fly_directory) if 'func' in x])
            anats.extend([os.path.join(fly_directory, x) for x in os.listdir(fly_directory) if 'anat' in x])

    brainsss.sort_nicely(funcs)
    brainsss.sort_nicely(anats)
    funcanats = funcs + anats
    dirtypes = ['func']*len(funcs) + ['anat']*len(anats)

    # ##################
    # ### Fictrac QC ###
    # ##################

    # printlog(f"\n{'   FICTRAC QC   ':=^{width}}")
    # job_ids = []
    # for func in funcs:
    #     directory = os.path.join(func, 'fictrac')
    #     if os.path.exists(directory):
    #         args = {'logfile': logfile, 'directory': directory, 'fps': 100}
    #         script = 'fictrac_qc.py'
    #         job_id = brainsss.sbatch(jobname='fictracqc',
    #                              script=os.path.join(scripts_path, script),
    #                              modules=modules,
    #                              args=args,
    #                              logfile=logfile, time=1, mem=1, nice=nice, nodes=nodes)
    #         job_ids.append(job_id)
    # for job_id in job_ids:
    #     brainsss.wait_for_job(job_id, logfile, com_path)

    # ####################
    # ### Bleaching QC ###
    # ####################

    # printlog(f"\n{'   BLEACHING QC   ':=^{width}}")
    # #job_ids = []
    # for funcanat, dirtype in zip(funcanats, dirtypes):
    #     directory = os.path.join(funcanat, 'imaging')
    #     args = {'logfile': logfile, 'directory': directory, 'dirtype': dirtype}
    #     script = 'bleaching_qc.py'
    #     job_id = brainsss.sbatch(jobname='bleachqc',
    #                          script=os.path.join(scripts_path, script),
    #                          modules=modules,
    #                          args=args,
    #                          logfile=logfile, time=1, mem=2, nice=nice, nodes=nodes)
    #     brainsss.wait_for_job(job_id, logfile, com_path)

    # ###################################
    # ### Create temporal mean brains ###
    # ###################################

    # printlog(f"\n{'   MEAN BRAINS   ':=^{width}}")
    # for funcanat, dirtype in zip(funcanats, dirtypes):
    #     directory = os.path.join(funcanat, 'imaging')

    #     if dirtype == 'func':
    #         files = ['functional_channel_1.nii', 'functional_channel_2.nii']
    #     if dirtype == 'anat':
    #         files = ['anatomy_channel_1.nii', 'anatomy_channel_2.nii']

    #     args = {'logfile': logfile, 'directory': directory, 'files': files}
    #     script = 'make_mean_brain.py'
    #     job_id = brainsss.sbatch(jobname='meanbrn',
    #                          script=os.path.join(scripts_path, script),
    #                          modules=modules,
    #                          args=args,
    #                          logfile=logfile, time=1, mem=2, nice=nice, nodes=nodes)
    #     brainsss.wait_for_job(job_id, logfile, com_path)

    #########################
    ### Motion Correction ###
    #########################

    printlog(f"\n{'   MOTION CORRECT   ':=^{width}}")
    for funcanat, dirtype in zip(funcanats, dirtypes):

        directory = os.path.join(funcanat, 'imaging')
        if dirtype == 'func':
            brain_master = 'functional_channel_1.nii'
            brain_mirror = 'functional_channel_2.nii'
        if dirtype == 'anat':
            brain_master = 'anatomy_channel_1.nii'
            brain_mirror = 'anatomy_channel_2.nii'

        args = {'logfile': logfile,
                'directory': directory,
                'brain_master': brain_master,
                'brain_mirror': brain_mirror,
                'scantype': dirtype}

        script = 'motion_correction.py'
        job_id = brainsss.sbatch(jobname='moco',
                             script=os.path.join(scripts_path, script),
                             modules=modules,
                             args=args,
                             logfile=logfile, time=96, mem=4, nice=nice, nodes=nodes)
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
    # parser.add_argument("dataset_path", default="MISSING", nargs='?') 
    args = parser.parse_args()
    # try:
    #     message = "{}\n{}\n{}\n{}".format("Aborted! You probably forgot to provide a fly directory.",
    #     "This argument is required and must be listed on the command line directly after the name of the shell file.",
    #     "It must be a full path to the directory.",
    #     "See readme for how to structure your fly directory.")
    #     assert (args.dataset_path != "MISSING"), message
    # except Exception as e:
    #     print (e)

    main(args)