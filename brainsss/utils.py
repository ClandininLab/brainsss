import sys
import smtplib
import re
import os
import h5py
import math
import json
from email.mime.text import MIMEText
from time import time
from time import strftime
from time import sleep
from functools import wraps
import numpy as np
import nibabel as nib
from xml.etree import ElementTree as ET
import subprocess

# only imports on linux, which is fine since only needed for sherlock
try:
    import fcntl
except ImportError:
    pass

def get_json_data(file_path):
    with open(file_path) as f:  
        data = json.load(f)
    return data

class Logger_stderr_sherlock(object):
    '''
    for redirecting stderr to a central log file.
    note, locking did not work fir fcntl, but seems to work fine without it
    keep in mind it could be possible to get errors from not locking this
    but I haven't seen anything, and apparently linux is "atomic" or some shit...
    '''
    def __init__(self, logfile):
        self.logfile = logfile

    def write(self, message):
        with open(self.logfile, 'a+') as f:
            f.write(message)

    def flush(self):
        pass

class Printlog():
    '''
    for printing all processes into same log file on sherlock
    '''
    def __init__(self, logfile):
        self.logfile = logfile
    def print_to_log(self, message):
        with open(self.logfile, 'a+') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(message)
            f.write('\n')
            fcntl.flock(f, fcntl.LOCK_UN)

def sbatch(jobname, script, modules, args, logfile, time=1, mem=1, dep='', nice=False, silence_print=False, nodes=2, begin='now'):
    if dep != '':
        dep = '--dependency=afterok:{} --kill-on-invalid-dep=yes '.format(dep)
 
    command = f'ml {modules}; python3 {script} {json.dumps(json.dumps(args))}'

    if nice: # For lowering the priority of the job
        nice = 1000000

    if nodes == 1:
        node_cmd = '-w sh02-07n34 '
    else:
        node_cmd = ''

    sbatch_command = "sbatch -J {} -o ./com/%j.out -e {} -t {}:00:00 --nice={} --partition=trc {}--open-mode=append --cpus-per-task={} --begin={} --wrap='{}' {}".format(jobname, logfile, time, nice, node_cmd, mem, begin, command, dep)
    sbatch_response = subprocess.getoutput(sbatch_command)
    width = 120
    if not silence_print:
        Printlog(logfile=logfile).print_to_log(f"{sbatch_response}{jobname:.>{width-27}}")
    job_id = sbatch_response.split(' ')[-1].strip()
    return job_id

def get_job_status(job_id, logfile, should_print=False):
    printlog = getattr(Printlog(logfile=logfile), 'print_to_log')
    temp = subprocess.getoutput('sacct -n -P -j {} --noconvert --format=State,Elapsed,MaxRSS,NCPUS,JobName'.format(job_id))
    if temp == '': return None # is empty if the job is too new
    status = temp.split('\n')[0].split('|')[0]
    
    if should_print: 
        if status != 'PENDING':
            try:
                duration = temp.split('\n')[0].split('|')[1]
                jobname = temp.split('\n')[0].split('|')[4]
                num_cores = int(temp.split('\n')[0].split('|')[3])
                memory_used = float(temp.split('\n')[1].split('|')[2]) # in bytes
            except (IndexError, ValueError) as e:
                printlog(str(e))
                printlog(F"Failed to parse sacct subprocess: {temp}")
                return status
            core_memory = 7.77 * 1024 * 1024 * 1024 #GB to MB to KB to bytes

            if memory_used > 1024 ** 3:
                memory_to_print = f'{memory_used/1024 ** 3 :0.1f}' + 'GB'
            elif memory_used > 1024 ** 2:
                memory_to_print = f'{memory_used/1024 ** 2 :0.1f}' + 'MB'
            elif memory_used > 1024 ** 1:
                memory_to_print = f'{memory_used/1024 ** 1 :0.1f}' + 'KB'
            else:
                memory_to_print = f'{memory_used :0.1f}' + 'B'

            percent_mem = memory_used/(core_memory*num_cores)*100
            percent_mem = f"{percent_mem:0.1f}"

            width = 120
            pretty = '+' + '-' * (width-2) + '+'
            sep = ' | '
            printlog(F"{pretty}\n"
                     F"{'| SLURM | '+jobname+sep+job_id+sep+status+sep+duration+sep+str(num_cores)+' cores'+sep+memory_to_print+' (' + percent_mem + '%)':{width-1}}|\n"
                     F"{pretty}")
        else:
            printlog('Job {} Status: {}'.format(job_id, status))

    return status

def wait_for_job(job_id, logfile, com_path):
    printlog = getattr(Printlog(logfile=logfile), 'print_to_log')
    #printlog(f'Waiting for job {job_id}')
    while True:
        status = get_job_status(job_id, logfile)
        if status in ['COMPLETED', 'CANCELLED', 'TIMEOUT', 'FAILED', 'OUT_OF_MEMORY']:
            status = get_job_status(job_id, logfile, should_print=True)
            com_file = os.path.join(com_path, job_id + '.out')
            try:
                with open(com_file, 'r') as f:
                    output = f.read()
            except:
                output = None
            return output
        else:
            sleep(5)

def print_progress_table(progress, logfile, start_time, print_header=False, print_footer=False):
    printlog = getattr(Printlog(logfile=logfile), 'print_to_log')

    fly_print, expt_print, total_vol, complete_vol = [], [], [], []
    for funcanat in progress:
        fly_print.append(funcanat.split('/')[-2])
        expt_print.append(funcanat.split('/')[-1])
        total_vol.append(progress[funcanat]['total_vol'])
        complete_vol.append(progress[funcanat]['complete_vol'])
        #printlog("{}, {}".format(progress[funcanat]['total_vol'], progress[funcanat]['complete_vol']))

    total_vol_sum = np.sum([int(x) for x in total_vol])
    complete_vol_sum = np.sum([int(x) for x in complete_vol])
    #printlog("{}, {}".format(total_vol_sum, complete_vol_sum))
    fraction_complete = complete_vol_sum/total_vol_sum
    num_columns = len(fly_print)
    column_width = int((120-20)/num_columns)
    if column_width < 9:
        column_width = 9

    if print_header:
        printlog((' '*9) + '+' + '+'.join([F"{'':-^{column_width}}"]*num_columns) + '+')
        printlog((' '*9) + '|' + '|'.join([F"{fly:^{column_width}}" for fly in fly_print]) + '|')
        printlog((' '*9) + '|' + '|'.join([F"{expt:^{column_width}}" for expt in expt_print]) + '|')
        printlog((' '*9) + '|' + '|'.join([F"{str(vol)+' vols':^{column_width}}" for vol in total_vol]) + '|')
        printlog('|ELAPSED ' + '+' + '+'.join([F"{'':-^{column_width}}"]*num_columns) + '+' + 'REMAININ|')

    def sec_to_hms(t):
        secs=F"{np.floor(t%60):02.0f}"
        mins=F"{np.floor((t/60)%60):02.0f}"
        hrs=F"{np.floor((t/3600)%60):02.0f}"
        return ':'.join([hrs, mins, secs])

    elapsed = time()-start_time
    elapsed_hms = sec_to_hms(elapsed)
    try:
        remaining = elapsed/fraction_complete - elapsed
    except ZeroDivisionError:
        remaining = 0
    remaining_hms = sec_to_hms(remaining)

    single_bars = []
    for funcanat in progress:
        bar_string = progress_bar(progress[funcanat]['complete_vol'], progress[funcanat]['total_vol'], column_width)
        single_bars.append(bar_string)
    fly_line = '|' + '|'.join(single_bars) + '|'
    #fly_line = '|' + '|'.join([F"{bar_string:^{column_width}}"]*num_columns) + '|'
    fly_line = '|' + elapsed_hms + fly_line + remaining_hms + '|'
    printlog(fly_line)

    if print_footer:
        printlog('|--------+' + '+'.join([F"{'':-^{column_width}}"]*num_columns) + '+--------|')
        #for funcanat in progress:
        #    printlog("{} {} {}".format(funcanat, progress[funcanat]['complete_vol'], progress[funcanat]['total_vol']))

def progress_bar(iteration, total, length, fill = '█'):
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    fraction = F"{str(iteration):^4}" + '/' + F"{str(total):^4}"
    bar_string = f"{bar}"
    return bar_string

def moco_progress(progress_tracker, logfile, com_path):
    ##############################################################################
    ### Printing a progress bar every min until all moco_partial jobs complete ###
    ##############################################################################
    printlog = getattr(Printlog(logfile=logfile), 'print_to_log')
    print_header = True
    start_time = time()
    while True:

        stati = []
        ###############################
        ### Get progress and status ###
        ###############################
        ### For each expt_dir, for each moco_partial job_id, get progress from slurm.out files, and status ###
        for funcanat in progress_tracker:
            complete_vol = 0
            for job_id in progress_tracker[funcanat]['job_ids']:
                # Read com file
                com_file = os.path.join(com_path, job_id + '.out')
                try:
                    with open(com_file, 'r') as f:
                        output = f.read()
                        #complete_vol_partial = int(max(re.findall(r'\d+', output)))
                        complete_vol_partial = max([int(x) for x in re.findall(r'\d+', output)])
                except:
                    complete_vol_partial = 0
                complete_vol += complete_vol_partial
            progress_tracker[funcanat]['complete_vol'] = complete_vol
            stati.append(get_job_status(job_id, logfile)) # Track status

        ############################
        ### Print progress table ###
        ############################
        print_progress_table(progress_tracker, logfile, start_time, print_header)
        print_header = False

        ###############################################
        ### Return if all jobs are done, else sleep ###
        ###############################################
        finished = ['COMPLETED', 'CANCELLED', 'TIMEOUT', 'FAILED', 'OUT_OF_MEMORY']
        if all([status in finished for status in stati]):
            print_progress_table(progress_tracker, logfile, start_time)
            print_progress_table(progress_tracker, logfile, start_time, print_footer=True) # print final 100% complete line
            return
        else:
            sleep(int(60*5))

def tryint(s):
    try:
        return int(s)
    except:
        return s

def alphanum_key(s):
    return [tryint(c) for c in re.split('([0-9]+)', s)]

def sort_nicely(x):
    x.sort(key=alphanum_key)

def get_resolution(xml_file):
    """ Gets the x,y,z resolution of a Bruker recording.

    Units of microns.

    Parameters
    ----------
    xml_file: string to full path of Bruker xml file.

    Returns
    -------
    x: float of x resolution
    y: float of y resolution
    z: float of z resolution """

    tree = ET.parse(xml_file)
    root = tree.getroot()
    statevalues = root.findall('PVStateShard')[0].findall('PVStateValue')
    for statevalue in statevalues:
        key = statevalue.get('key')
        if key == 'micronsPerPixel':
            indices = statevalue.findall('IndexedValue')
            for index in indices:
                axis = index.get('index')
                if axis == 'XAxis':
                    x = float(index.get('value'))
                elif axis == 'YAxis':
                    y = float(index.get('value'))
                elif axis == 'ZAxis':
                    z = float(index.get('value'))
                else:
                    print('Error')
    return x, y, z





