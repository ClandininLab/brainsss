import time
import sys
import os
import re
import json
import textwrap
import brainsss
import argparse

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
brainsss.print_title(logfile, width)
scripts_path = '/home/users/brezovec/projects/brainsss/scripts'
com_path = os.path.join(scripts_path, 'com')

###########################
### Run make mean brain ###
###########################

directory = '/oak/stanford/groups/trc/data/Ashley2/imports/20210802/fly3_20s-014/'
files = ['MOCO_ch2.h5']

args = {'logfile': logfile, 'directory': directory, 'files': files}
script = 'make_mean_brain.py'
job_id = brainsss.sbatch(jobname='meanbrn',
                     script=os.path.join(scripts_path, script),
                     modules=modules,
                     args=args,
                     logfile=logfile, time=5, mem=18, nice=nice, nodes=nodes, global_resources=True)
brainsss.wait_for_job(job_id, logfile, com_path)