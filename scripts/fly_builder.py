import os
import sys
import json
import numpy as np
import pandas as pd
from time import strftime
from shutil import copyfile
from xml.etree import ElementTree as ET
from lxml import etree, objectify
from openpyxl import Workbook
from openpyxl import load_workbook
import brainsss
#import bigbadbrain as bbb
#import dataflow as flow

def main(args):
    ### Move folders from imports to fly dataset - need to restructure folders ###

    logfile = args['logfile']
    flagged_dir = args['flagged_dir']
    target_path = args['dataset_path']
    fly_dirs = args['fly_dirs']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
    #printlog('\nBuilding flies from directory {}'.format(flagged_dir))
    width = 120
    #printlog(F"\n{'#' * width}\n"
    #         F"{'   Building flies from directory ' + os.path.split(flagged_dir)[-1] + '   ':#^{width}}\n"
    #         F"{'#' * width}")

    # Assume this folder contains fly1 etc
    # This folder may (or may not) contain separate areas # False, now enforcing experiment subfolders
    # Each area will have a T and a Z
    # Avoid grabbing other weird xml files, reference folder etc.
    # Need to move into fly_X folder that reflects it's date

    # get fly folders in flagged directory and sort to ensure correct fly order
    likely_fly_folders = os.listdir(flagged_dir)
    brainsss.sort_nicely(likely_fly_folders)
    likely_fly_folders = [i for i in likely_fly_folders if 'fly' in i]
    printlog(F"Found fly folders{str(likely_fly_folders):.>{width-17}}")

    if fly_dirs is not None:
        likely_fly_folders = fly_dirs
        printlog(F"Continuing with only{str(likely_fly_folders):.>{width-20}}")

    for likely_fly_folder in likely_fly_folders:
        if 'fly' in likely_fly_folder:

            new_fly_number = get_new_fly_number(target_path)
            #printlog(f'\n*Building {likely_fly_folder} as fly number {new_fly_number}*')
            printlog(f"\n{'   Building '+likely_fly_folder+' as fly_'+ str(new_fly_number) + '   ':-^{width}}")

            # Define source fly directory
            source_fly = os.path.join(flagged_dir, likely_fly_folder)

            # Define destination fly directory
            #fly_time = get_fly_time(source_fly)
            new_fly_folder = 'fly_' + str(new_fly_number)

            destination_fly = os.path.join(target_path, new_fly_folder)
            os.mkdir(destination_fly)
            printlog(F'Created fly directory:{destination_fly:.>{width-22}}')

            # Copy fly data
            copy_fly(source_fly, destination_fly, printlog)

            # Add date to fly.json file
            add_date_to_fly(destination_fly)

            # Add json metadata to master dataset
            add_fly_to_xlsx(destination_fly)

def add_date_to_fly(destination_fly):
    ''' get date from xml file and add to fly.json'''

    ### Get date
    try: # Check if there are func folders
        # Get func folders
        func_folders = [os.path.join(destination_fly,x) for x in os.listdir(destination_fly) if 'func' in x]
        brainsss.sort_nicely(func_folders)
        func_folder = func_folders[0]
        # Get full xml file path
        xml_file = os.path.join(func_folder, 'imaging', 'functional.xml')
    except: # Use anatomy folder
        # Get anat folders
        anat_folders = [os.path.join(destination_fly,x) for x in os.listdir(destination_fly) if 'anat' in x]
        brainsss.sort_nicely(anat_folders)
        anat_folder = anat_folders[0]
        # Get full xml file path
        xml_file = os.path.join(anat_folder, 'imaging', 'anatomy.xml')
    # Extract datetime
    datetime_str,_,_ = get_datetime_from_xml(xml_file)
    # Get just date
    date = datetime_str.split('-')[0]
    time = datetime_str.split('-')[1]

    ### Add to fly.json
    json_file = os.path.join(destination_fly, 'fly.json')
    with open(json_file, 'r+') as f:
        metadata = json.load(f)
        metadata['date'] = str(date)
        metadata['time'] = str(time)
        f.seek(0)
        json.dump(metadata, f, indent=4)
        f.truncate()

def copy_fly(source_fly, destination_fly, printlog):

    ''' There will be two types of folders in a fly folder.
    1) func_x folder
    2) anat_x folder
    For functional folders, need to copy fictrac and visual as well
    For anatomy folders, only copy folder. There will also be
    3) fly json data '''

    # look at every item in source fly folder
    for item in os.listdir(source_fly):
        ##print('Currently looking at item: {}'.format(item))
        ##sys.stdout.flush()

        # Handle folders
        if os.path.isdir(os.path.join(source_fly, item)):
            # Call this folder source expt folder
            source_expt_folder = os.path.join(source_fly, item)
            # Make the same folder in destination fly folder
            expt_folder = os.path.join(destination_fly, item)
            os.mkdir(expt_folder)
            ##print('Created directory: {}'.format(expt_folder))
            ##sys.stdout.flush()

            # Is this folder an anatomy or functional folder?
            if 'anat' in item:
                # If anatomy folder, just copy everything
                # Make imaging folder and copy
                imaging_destination = os.path.join(expt_folder, 'imaging')
                os.mkdir(imaging_destination)
                copy_bruker_data(source_expt_folder, imaging_destination, 'anat', printlog)
                ######################################################################
                print(f"anat:{expt_folder}") # IMPORTANT - FOR COMMUNICATING WITH MAIN
                ######################################################################
            elif 'func' in item:
                # Make imaging folder and copy
                imaging_destination = os.path.join(expt_folder, 'imaging')
                os.mkdir(imaging_destination)
                copy_bruker_data(source_expt_folder, imaging_destination, 'func', printlog)
                # Copt fictrac data based on timestamps
                copy_fictrac(expt_folder, printlog)
                # Copy visual data based on timestamps, and create visual.json
                copy_visual(expt_folder, printlog)

                ######################################################################
                print(f"func:{expt_folder}") # IMPORTANT - FOR COMMUNICATING WITH MAIN
                ######################################################################
                # REMOVED TRIGGERING

            else:
                printlog('Invalid directory in fly folder (skipping): {}'.format(item))

        # Copy fly.json file
        else:
            if item == 'fly.json':
                ##print('found fly json file')
                ##sys.stdout.flush()
                source_path = os.path.join(source_fly, item)
                target_path = os.path.join(destination_fly, item)
                ##print('Will copy from {} to {}'.format(source_path, target_path))
                ##sys.stdout.flush()
                copyfile(source_path, target_path)
            else:
                printlog('Invalid file in fly folder (skipping): {}'.format(item))
                ##sys.stdout.flush()

def copy_bruker_data(source, destination, folder_type, printlog):
    # Do not update destination - download all files into that destination
    for item in os.listdir(source):
        # Create full path to item
        source_item = os.path.join(source, item)

        # Check if item is a directory
        if os.path.isdir(source_item):
            # Do not update destination - download all files into that destination
            copy_bruker_data(source_item, destination, folder_type, printlog)

        # If the item is a file
        else:
            ### Change file names and filter various files
            # Don't copy these files
            if 'SingleImage' in item:
                continue
            # Rename functional file to functional_channel_x.nii
            if '.nii' in item and folder_type == 'func':
                # '_' is from channel numbers my tiff to nii adds
                item = 'functional_' + item.split('_')[1] + '_' + item.split('_')[2]
            # Rename anatomy file to anatomy_channel_x.nii
            if '.nii' in item and folder_type == 'anat':
                item = 'anatomy_' + item.split('_')[1] + '_' + item.split('_')[2]
            # Special copy for photodiode since it goes in visual folder
            if '.csv' in item:
                item = 'photodiode.csv'
                try:
                    visual_folder = os.path.join(os.path.split(destination)[0], 'visual')
                    os.mkdir(visual_folder)
                except:
                    pass
                target_item = os.path.join(os.path.split(destination)[0], 'visual', item)
                copyfile(source_item, target_item)
                continue
            # Rename to anatomy.xml if appropriate
            if '.xml' in item and folder_type == 'anat' and 'Voltage' not in item:
                item = 'anatomy.xml'
            # Rename to functional.xml if appropriate, copy immediately, then make scan.json
            if '.xml' in item and folder_type == 'func' and 'Voltage' not in item:
                item = 'functional.xml'
                target_item = os.path.join(destination, item)
                copy_file(source_item, target_item, printlog)
                # Create json file
                create_imaging_json(target_item, printlog)
                continue
            if '.xml' in item and 'VoltageOutput' in item:
                item = 'voltage_output.xml'
            # Special copy for expt.json
            if 'expt.json' in item:
                target_item = os.path.join(os.path.split(destination)[0], item)
                copyfile(source_item, target_item)
                continue

            # Actually copy the file
            target_item = os.path.join(destination, item)
            copy_file(source_item, target_item, printlog)

def copy_file(source, target, printlog):
    #printlog('Transfering file {}'.format(target))
    to_print = ('/').join(target.split('/')[-4:])
    width = 120
    printlog(f'Transfering file{to_print:.>{width-16}}')
    ##sys.stdout.flush()
    copyfile(source, target)

def copy_visual(destination_region, printlog):
    width=120
    printlog(F"Copying visual stimulus data{'':.^{width-28}}")
    visual_folder = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/imports/visual'
    visual_destination = os.path.join(destination_region, 'visual')

    # Find time of experiment based on functional.xml
    true_ymd, true_total_seconds = get_expt_time(os.path.join(destination_region,'imaging'))

    # Find visual folder that has the closest datetime
    # First find all folders with correct date, and about the correct time
    folders = []
    for folder in os.listdir(visual_folder):
        test_ymd = folder.split('-')[1]
        test_time = folder.split('-')[2]
        test_hour = test_time[0:2]
        test_minute = test_time[2:4]
        test_second = test_time[4:6]
        test_total_seconds = int(test_hour) * 60 * 60 + \
                             int(test_minute) * 60 + \
                             int(test_second)

        if test_ymd == true_ymd:
            time_difference = np.abs(true_total_seconds - test_total_seconds)
            if time_difference < 3 * 60:
                folders.append([folder, test_total_seconds])
                printlog('Found reasonable visual folder: {}'.format(folder))

    #if more than 1 folder, use the oldest folder
    if len(folders) == 1:
        correct_folder = folders[0]
    #if no matching folder,
    elif len(folders) == 0:
        printlog(F"{'No matching visual folders found; continuing without visual data':.<{width}}")
        return
    else:
        printlog('Found more than 1 visual stimulus folder within 3min of expt. Picking oldest.')
        correct_folder = folders[0] # set default to first folder
        for folder in folders:
            # look at test_total_seconds entry. If larger, call this the correct folder.
            if folder[-1] > correct_folder[-1]:
                correct_folder = folder

    # now that we have the correct folder, copy it's contents
    printlog('Found correct visual stimulus folder: {}'.format(correct_folder[0]))
    try:
        os.mkdir(visual_destination)
    except:
        pass
        ##print('{} already exists'.format(visual_destination))
    source_folder = os.path.join(visual_folder, correct_folder[0])
    printlog('Copying from: {}'.format(source_folder))
    for file in os.listdir(source_folder):
        target_path = os.path.join(visual_destination, file)
        source_path = os.path.join(source_folder, file)
        ##print('Transfering from {} to {}'.format(source_path, target_path))
        ##sys.stdout.flush()
        copyfile(source_path, target_path)

    # Create visual.json metadata
    # Try block to prevent quiting if visual stimuli timing is wonky (likely went too long)
    try:
        unique_stimuli = brainsss.get_stimuli(visual_destination)
    except:
        unique_stimuli = 'brainsss.get_stimuli failed'
    with open(os.path.join(visual_destination, 'visual.json'), 'w') as f:
        json.dump(unique_stimuli, f, indent=4)

def copy_fictrac(destination_region, printlog):
    fictrac_folder = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/imports/fictrac'
    fictrac_destination = os.path.join(destination_region, 'fictrac')

    # Find time of experiment based on functional.xml
    true_ymd, true_total_seconds = get_expt_time(os.path.join(destination_region,'imaging'))
    printlog(f'true_ymd: {true_ymd}; true_total_seconds: {true_total_seconds}')

    # Find .dat file of 1) correct-ish time, 2) correct-ish size
    datetime_correct = None
    for file in os.listdir(fictrac_folder):

        # must be .dat file
        if '.dat' not in file:
            continue

        # Get datetime from file name
        datetime = file.split('-')[1][:-4]
        test_ymd = datetime.split('_')[0]
        test_time = datetime.split('_')[1]
        test_hour = test_time[0:2]
        test_minute = test_time[2:4]
        test_second = test_time[4:6]
        test_total_seconds = int(test_hour) * 60 * 60 + \
                             int(test_minute) * 60 + \
                             int(test_second)

        # Year/month/day must be exact
        if true_ymd != test_ymd:
            continue
        printlog('Found file from same day: {}'.format(file))

        # Time must be within 10min
        time_difference = np.abs(true_total_seconds - test_total_seconds)
        if time_difference > 10 * 60:
            continue
        printlog('Found fictrac file that matches time.')

        # Must be correct size
        fp = os.path.join(fictrac_folder, file)
        file_size = os.path.getsize(fp)
        if file_size > 30000000: #30MB
            width = 120
            printlog(F"Found correct .dat file{file:.>{width-23}}")
            datetime_correct = datetime
            break

    if datetime_correct is None:
        width = 120
        printlog(F"{'   No fictrac data found --- continuing without fictrac data   ':*^{width}}")
        return

    # Collect all fictrac files with correct datetime
    correct_time_files = [file for file in os.listdir(fictrac_folder) if datetime_correct in file]

    # correct_time_files = []
    # for file in os.listdir(fictrac_folder):
    #     if datetime_correct in file:
    #         correct_time_files.append(file)


    #printlog('Found these files with correct times: {}'.format(correct_time_files))
    ##sys.stdout.flush()

    # Now transfer these 4 files to the fly
    os.mkdir(fictrac_destination)
    for file in correct_time_files:
        target_path = os.path.join(fictrac_destination, file)
        source_path = os.path.join(fictrac_folder, file)
        to_print = ('/').join(target_path.split('/')[-4:])
        printlog(f'Transfering file{to_print:.>{width-16}}')
        #printlog('Transfering {}'.format(target_path))
        ##sys.stdout.flush()
        copyfile(source_path, target_path)

    ### Create empty xml file.
    # Update this later
    root = etree.Element('root')
    fictrac = objectify.Element('fictrac')
    root.append(fictrac)
    objectify.deannotate(root)
    etree.cleanup_namespaces(root)
    tree = etree.ElementTree(fictrac)
    with open(os.path.join(fictrac_destination, 'fictrac.xml'), 'wb') as file:
        tree.write(file, pretty_print=True)

def create_imaging_json(xml_source_file, printlog):

    # Make empty dict
    source_data = {}

    # Get datetime
    try:
        datetime_str, _, _ = get_datetime_from_xml(xml_source_file)
    except:
        printlog('No xml or cannot read.')
        ##sys.stdout.flush()
        return
    date = datetime_str.split('-')[0]
    time = datetime_str.split('-')[1]
    source_data['date'] = str(date)
    source_data['time'] = str(time)

    # Get rest of data
    tree = objectify.parse(xml_source_file)
    source = tree.getroot()
    statevalues = source.findall('PVStateShard')[0].findall('PVStateValue')
    for statevalue in statevalues:
        key = statevalue.get('key')
        if key == 'micronsPerPixel':
            indices = statevalue.findall('IndexedValue')
            for index in indices:
                axis = index.get('index')
                if axis == 'XAxis':
                    source_data['x_voxel_size'] = float(index.get('value'))
                elif axis == 'YAxis':
                    source_data['y_voxel_size'] = float(index.get('value'))
                elif axis == 'ZAxis':
                    source_data['z_voxel_size'] = float(index.get('value'))
        if key == 'laserPower':
            # I think this is the maximum power if set to vary by z depth - WRONG
            indices = statevalue.findall('IndexedValue')
            laser_power_overall = int(float(indices[0].get('value')))
            source_data['laser_power'] = laser_power_overall
        if key == 'pmtGain':
            indices = statevalue.findall('IndexedValue')
            for index in indices:
                index_num = index.get('index')
                if index_num == '0':
                    source_data['PMT_red'] = int(float(index.get('value')))
                if index_num == '1':
                    source_data['PMT_green'] = int(float(index.get('value')))
        if key == 'pixelsPerLine':
            source_data['x_dim'] = int(float(statevalue.get('value')))
        if key == 'linesPerFrame':
            source_data['y_dim'] = int(float(statevalue.get('value')))
    sequence = source.findall('Sequence')[0]
    last_frame = sequence.findall('Frame')[-1]
    source_data['z_dim'] = int(last_frame.get('index'))

    # Need this try block since sometimes first 1 or 2 frames don't have laser info...
    # try:
    #     # Get laser power of first and last frames
    #     last_frame = sequence.findall('Frame')[-1]
    #     source_data['laser_power'] = int(last_frame.findall('PVStateShard')[0].findall('PVStateValue')[1].findall('IndexedValue')[0].get('value'))
    #     #first_frame = sequence.findall('Frame')[0]
    #     #source_data['laser_power_min'] = int(first_frame.findall('PVStateShard')[0].findall('PVStateValue')[1].findall('IndexedValue')[0].get('value'))
    # except:
    #     source_data['laser_power_min'] = laser_power_overall
    #     source_data['laser_power_max'] = laser_power_overall
    #     #printlog('Used overall laser power.')
    #     # try:
    #     #     first_frame = sequence.findall('Frame')[2]
    #     #     source_data['laser_power_min'] = int(first_frame.findall('PVStateShard')[0].findall('PVStateValue')[1].findall('IndexedValue')[0].get('value'))
    #     #     printlog('Took min laser data from frame 3, not frame 1, due to bruker metadata error.')
    #     # # Apparently sometimes the metadata will only include the
    #     # # laser value at the very beginning
    #     # except:
    #     #     source_data['laser_power_min'] = laser_power_overall
    #     #     source_data['laser_power_max'] = laser_power_overall
    #     #     printlog('Used overall laser power.')

    # Save data
    with open(os.path.join(os.path.split(xml_source_file)[0], 'scan.json'), 'w') as f:
        json.dump(source_data, f, indent=4)

def get_expt_time(directory):
    ''' Finds time of experiment based on functional.xml '''
    xml_file = os.path.join(directory, 'functional.xml')
    _, _, datetime_dict = get_datetime_from_xml(xml_file)
    true_ymd = datetime_dict['year'] + datetime_dict['month'] + datetime_dict['day']
    true_total_seconds = int(datetime_dict['hour']) * 60 * 60 + \
                         int(datetime_dict['minute']) * 60 + \
                         int(datetime_dict['second'])

    ##print('dict: {}'.format(datetime_dict))
    ##print('true_ymd: {}'.format(true_ymd))
    ##print('true_total_seconds: {}'.format(true_total_seconds))
    ##sys.stdout.flush()
    return true_ymd, true_total_seconds

def get_fly_time(fly_folder):
    # need to read all xml files and pick oldest time
    # find all xml files
    xml_files = []
    xml_files = get_xml_files(fly_folder, xml_files)

    ##print('found xml files: {}'.format(xml_files))
    ##sys.stdout.flush()
    datetimes_str = []
    datetimes_int = []
    for xml_file in xml_files:
        datetime_str, datetime_int, _ = get_datetime_from_xml(xml_file)
        datetimes_str.append(datetime_str)
        datetimes_int.append(datetime_int)

    # Now pick the oldest datetime
    datetimes_int = np.asarray(datetimes_int)
    ##print('Found datetimes: {}'.format(datetimes_str))
    ##sys.stdout.flush()
    index_min = np.argmin(datetimes_int)
    datetime = datetimes_str[index_min]
    ##print('Found oldest datetime: {}'.format(datetime))
    ##sys.stdout.flush()
    return datetime

def get_xml_files(fly_folder, xml_files):
    # Look at items in fly folder
    for item in os.listdir(fly_folder):
        full_path = os.path.join(fly_folder, item)
        if os.path.isdir(full_path):
            xml_files = get_xml_files(full_path, xml_files)
        else:
            if '.xml' in item and \
            '_Cycle' not in item and \
            'fly.xml' not in item and \
            'scan.xml' not in item and \
            'expt.xml' not in item:
                xml_files.append(full_path)
                ##print('Found xml file: {}'.format(full_path))
                ##sys.stdout.flush()
    return xml_files

def get_datetime_from_xml(xml_file):
    ##print('Getting datetime from {}'.format(xml_file))
    ##sys.stdout.flush()
    tree = ET.parse(xml_file)
    root = tree.getroot()
    datetime = root.get('date')
    # will look like "4/2/2019 4:16:03 PM" to start

    # Get dates
    date = datetime.split(' ')[0]
    month = date.split('/')[0]
    day = date.split('/')[1]
    year = date.split('/')[2]

    # Get times
    time = datetime.split(' ')[1]
    hour = time.split(':')[0]
    minute = time.split(':')[1]
    second = time.split(':')[2]

    # Convert from 12 to 24 hour time
    am_pm = datetime.split(' ')[-1]
    if am_pm == 'AM' and hour == '12':
        hour = str(00)
    elif am_pm == 'AM':
        pass
    elif am_pm == 'PM' and hour == '12':
        pass
    else:
        hour = str(int(hour) + 12)

    # Add zeros if needed
    if len(month) == 1:
        month = '0' + month
    if len(day) == 1:
        day = '0' + day
    if len(hour) == 1:
        hour = '0' + hour

    # Combine
    datetime_str = year + month + day + '-' + hour + minute + second
    datetime_int = int(year + month + day + hour + minute + second)
    datetime_dict = {'year': year,
                     'month': month,
                     'day': day,
                     'hour': hour,
                     'minute': minute,
                     'second': second}

    return datetime_str, datetime_int, datetime_dict

def get_new_fly_number(target_path):
    oldest_fly = 0
    for current_fly_folder in os.listdir(target_path):
        if current_fly_folder.startswith('fly'):
            fly_num = current_fly_folder.split('_')[-1]
            if int(fly_num) > oldest_fly:
                oldest_fly = int(fly_num)
    new_fly_number = oldest_fly + 1
    return str(new_fly_number).zfill(3)

# OLDER VERSION:
# def get_new_fly_number(target_path):
#     oldest_fly = 0
#     for current_fly_folder in os.listdir(target_path):
#         if 'fly' in current_fly_folder and current_fly_folder[-3] == '_':
#             last_2_chars = current_fly_folder[-2:]
#             if int(last_2_chars) > oldest_fly:
#                 oldest_fly = int(last_2_chars)
#     current_fly_number = oldest_fly + 1
#     return current_fly_number

def load_json(file):
    with open(file, 'r') as f:
        data = json.load(f)
    return data

def load_xml(file):
    tree = objectify.parse(file)
    root = tree.getroot()
    return root

def add_times_to_jsons(destination_fly):
    ''' Deprecated '''
    # Do for each func_x folder
    func_folders = [os.path.join(destination_fly,x) for x in os.listdir(destination_fly) if 'func' in x]
    for func_folder in func_folders:
        pass

def add_fly_to_xlsx(fly_folder):

    # Load xlsx
    xlsx_path = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20190101_walking_dataset/master_2P.xlsx'
    wb = load_workbook(filename=xlsx_path, read_only=False)
    ws = wb.active

    # If no fly.json, just skip (atleast one fly in empty for some reason)
    try:
        fly_file = os.path.join(fly_folder, 'fly.json')
        fly_data = load_json(fly_file)
    except:
        return

    expt_folders = []
    expt_folders = [os.path.join(fly_folder,x) for x in os.listdir(fly_folder) if 'func' in x]
    brainsss.sort_nicely(expt_folders)
    for expt_folder in expt_folders:

        expt_file = os.path.join(expt_folder, 'expt.json')
        expt_data = load_json(expt_file)

        # Occasionally a fly may not have an imaging folder (if only fictrac was recorded for example)
        try:
            scan_file = os.path.join(expt_folder, 'imaging', 'scan.json')
            scan_data = load_json(scan_file)
            scan_data['x_voxel_size'] = '{:.1f}'.format(scan_data['x_voxel_size'])
            scan_data['y_voxel_size'] = '{:.1f}'.format(scan_data['y_voxel_size'])
            scan_data['z_voxel_size'] = '{:.1f}'.format(scan_data['z_voxel_size'])
        except:
            scan_data['laser_power'] = None
            scan_data['PMT_green'] = None
            scan_data['PMT_red'] = None
            scan_data['x_dim'] = None
            scan_data['y_dim'] = None
            scan_data['z_dim'] = None
            scan_data['x_voxel_size'] = None
            scan_data['y_voxel_size'] = None
            scan_data['z_voxel_size'] = None

        visual_file = os.path.join(expt_folder, 'visual', 'visual.json')
        try:
            visual_data = load_json(visual_file)
            visual_input = visual_data[0]['name'] + ' ({})'.format(len(visual_data))
        except:
            visual_input = None

        # Get fly_id
        fly_folder = os.path.split(os.path.split(expt_folder)[0])[-1]
        fly_id = fly_folder.split('_')[-1]

        # Get expt_id
        expt_id = expt_folder.split('_')[-1]

        # Append the new row
        new_row = []
        new_row = [int(fly_id),
                   int(expt_id),
                   fly_data['date'],
                   expt_data['brain_area'],
                   fly_data['genotype'],
                   visual_input,
                   None,
                   fly_data['notes'],
                   expt_data['notes'],
                   expt_data['time'],
                   fly_data['circadian_on'],
                   fly_data['circadian_off'],
                   fly_data['gender'],
                   fly_data['age'],
                   fly_data['temp'],
                   scan_data['laser_power'],
                   scan_data['PMT_green'],
                   scan_data['PMT_red'],
                   scan_data['x_dim'],
                   scan_data['y_dim'],
                   scan_data['z_dim'],
                   scan_data['x_voxel_size'],
                   scan_data['y_voxel_size'],
                   scan_data['z_voxel_size']]

        ws.append(new_row)

    # Save the file
    wb.save(xlsx_path)

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))
