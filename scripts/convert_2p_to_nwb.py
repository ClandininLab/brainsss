#!/usr/bin/env python3
"""
Convert 2-photon Drosophila imaging data to NWB format
Handles imaging, fictrac, and visual stimulus data
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import nibabel as nib
import h5py
from datetime import datetime
from dateutil.tz import tzlocal
from xml.etree import ElementTree as ET
from pynwb import NWBFile, NWBHDF5IO
from pynwb.file import Subject
from pynwb.ophys import TwoPhotonSeries, OpticalChannel, ImagingPlane
from pynwb.device import Device
from pynwb.image import ImageSeries
from pynwb.behavior import Position, SpatialSeries, CompassDirection, BehavioralTimeSeries
from pynwb.base import TimeSeries

def load_json(file):
    """Load JSON file"""
    with open(file, 'r') as f:
        data = json.load(f)
    return data

def load_xml_metadata(xml_file):
    """
    Extract metadata from Bruker XML file
    Based on create_imaging_json from your script
    """
    metadata = {}
    
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Get datetime
    datetime_str = root.get('date')
    metadata['datetime_raw'] = datetime_str
    
    # Parse datetime (format: "4/2/2019 4:16:03 PM")
    date_part = datetime_str.split(' ')[0]
    time_part = datetime_str.split(' ')[1]
    am_pm = datetime_str.split(' ')[-1]
    
    month, day, year = date_part.split('/')
    hour, minute, second = time_part.split(':')
    
    # Convert to 24-hour
    hour = int(hour)
    if am_pm == 'PM' and hour != 12:
        hour += 12
    elif am_pm == 'AM' and hour == 12:
        hour = 0
    
    metadata['session_start_time'] = datetime(
        int(year), int(month), int(day),
        hour, int(minute), int(second),
        tzinfo=tzlocal()
    )
    
    # Get imaging parameters
    statevalues = root.findall('.//PVStateValue')
    for statevalue in statevalues:
        key = statevalue.get('key')
        
        if key == 'micronsPerPixel':
            indices = statevalue.findall('IndexedValue')
            for index in indices:
                axis = index.get('index')
                value = float(index.get('value'))
                if axis == 'XAxis':
                    metadata['x_voxel_size'] = value
                elif axis == 'YAxis':
                    metadata['y_voxel_size'] = value
                elif axis == 'ZAxis':
                    metadata['z_voxel_size'] = value
                    
        elif key == 'laserPower':
            indices = statevalue.findall('IndexedValue')
            if indices:
                metadata['laser_power'] = float(indices[0].get('value'))
                
        elif key == 'pmtGain':
            indices = statevalue.findall('IndexedValue')
            for index in indices:
                index_num = index.get('index')
                if index_num == '0':
                    metadata['PMT_red'] = float(index.get('value'))
                elif index_num == '1':
                    metadata['PMT_green'] = float(index.get('value'))
                    
        elif key == 'pixelsPerLine':
            metadata['x_dim'] = int(float(statevalue.get('value')))
            
        elif key == 'linesPerFrame':
            metadata['y_dim'] = int(float(statevalue.get('value')))
    
    # Get number of z planes from last frame
    sequence = root.findall('Sequence')
    if sequence:
        frames = sequence[0].findall('Frame')
        if frames:
            last_frame = frames[-1]
            metadata['z_dim'] = int(last_frame.get('index')) + 1  # +1 because 0-indexed
    
    # Get frame rate
    if 'PVStateShard' in str(ET.tostring(root)):
        try:
            framerate_elem = root.findall('.//PVStateValue[@key="frameRate"]')
            if framerate_elem:
                metadata['framerate'] = float(framerate_elem[0].get('value'))
        except:
            pass
    
    return metadata

def load_fictrac_data(fictrac_folder):
    """
    Load FicTrac data from .dat file
    Returns dict with behavioral data
    """
    # Find .dat file
    dat_files = [f for f in os.listdir(fictrac_folder) if f.endswith('.dat')]
    
    if not dat_files:
        print(f"Warning: No .dat file found in {fictrac_folder}")
        return None
    
    dat_file = os.path.join(fictrac_folder, dat_files[0])
    
    # Load FicTrac data
    # Column names based on FicTrac output format
    column_names = [
        'frame', 'delta_rot_cam_right', 'delta_rot_cam_down', 'delta_rot_cam_forward',
        'delta_rot_error', 'delta_rot_lab_side', 'delta_rot_lab_forward', 'delta_rot_lab_turn',
        'abs_rot_cam_right', 'abs_rot_cam_down', 'abs_rot_cam_forward',
        'abs_rot_lab_side', 'abs_rot_lab_forward', 'abs_rot_lab_turn',
        'integrated_lab_x', 'integrated_lab_y', 'integrated_lab_heading',
        'animal_movement_direction_lab', 'animal_movement_speed', 'integrated_forward_movement',
        'integrated_side_movement', 'timestamp', 'seq_num', 'delta_timestamp', 'alt_timestamp'
    ]
    
    try:
        df = pd.read_csv(dat_file, names=column_names, skipinitialspace=True)
        
        fictrac_data = {
            'timestamps': df['timestamp'].values,
            'frame_count': df['frame'].values,
            'heading': df['integrated_lab_heading'].values,
            'position_x': df['integrated_lab_x'].values,
            'position_y': df['integrated_lab_y'].values,
            'velocity': df['animal_movement_speed'].values,
            'forward_movement': df['integrated_forward_movement'].values,
            'side_movement': df['integrated_side_movement'].values,
            'delta_rot_lab_side': df['delta_rot_lab_side'].values,
            'delta_rot_lab_forward': df['delta_rot_lab_forward'].values,
            'delta_rot_lab_turn': df['delta_rot_lab_turn'].values,
        }
        
        return fictrac_data
        
    except Exception as e:
        print(f"Warning: Could not load FicTrac data: {e}")
        return None

def load_visual_stimulus(visual_folder):
    """
    Load visual stimulus data from HDF5 file
    """
    hdf5_files = [f for f in os.listdir(visual_folder) if f.endswith('.hdf5')]
    
    if not hdf5_files:
        print(f"Warning: No .hdf5 file found in {visual_folder}")
        return None
    
    hdf5_file = os.path.join(visual_folder, hdf5_files[0])
    
    try:
        with h5py.File(hdf5_file, 'r') as f:
            stimulus_data = {}
            
            # Extract all datasets - customize based on your HDF5 structure
            def extract_datasets(group, path=''):
                for key in group.keys():
                    item = group[key]
                    current_path = f"{path}/{key}" if path else key
                    
                    if isinstance(item, h5py.Dataset):
                        stimulus_data[current_path] = item[()]
                    elif isinstance(item, h5py.Group):
                        extract_datasets(item, current_path)
            
            extract_datasets(f)
        
        return stimulus_data
        
    except Exception as e:
        print(f"Warning: Could not load stimulus data: {e}")
        return None

def load_photodiode_data(visual_folder):
    """
    Load photodiode data from CSV file
    """
    csv_file = os.path.join(visual_folder, 'photodiode.csv')
    
    if not os.path.exists(csv_file):
        print(f"Warning: No photodiode.csv found in {visual_folder}")
        return None
    
    try:
        # Load photodiode data
        # Adjust column names based on your actual CSV structure
        df = pd.read_csv(csv_file)
        
        photodiode_data = {
            'data': df.values,
            'column_names': df.columns.tolist()
        }
        
        return photodiode_data
        
    except Exception as e:
        print(f"Warning: Could not load photodiode data: {e}")
        return None

def convert_fly_to_nwb(fly_folder, output_file):
    """
    Convert a complete fly dataset to NWB format
    
    Parameters:
    -----------
    fly_folder : str
        Path to fly_XXX folder containing anat_X and func_X folders
    output_file : str
        Path to output NWB file
    """
    
    print(f"\n{'='*80}")
    print(f"Converting {os.path.basename(fly_folder)} to NWB format")
    print(f"{'='*80}\n")
    
    # Load fly metadata
    fly_json = os.path.join(fly_folder, 'fly.json')
    if os.path.exists(fly_json):
        fly_metadata = load_json(fly_json)
    else:
        fly_metadata = {}
        print("Warning: No fly.json found")
    
    # Find functional folders (use first one for main metadata)
    func_folders = sorted([os.path.join(fly_folder, x) for x in os.listdir(fly_folder) if 'func' in x])
    
    if not func_folders:
        print("Error: No functional folders found!")
        return
    
    # Load metadata from first functional scan
    func_0 = func_folders[0]
    
    # Load experiment metadata
    expt_json = os.path.join(func_0, 'expt.json')
    if os.path.exists(expt_json):
        expt_metadata = load_json(expt_json)
    else:
        expt_metadata = {}
        print("Warning: No expt.json found")
    
    # Load scan metadata from XML
    func_xml = os.path.join(func_0, 'imaging', 'functional.xml')
    if os.path.exists(func_xml):
        scan_metadata = load_xml_metadata(func_xml)
    else:
        scan_metadata = {'session_start_time': datetime.now(tzlocal())}
        print("Warning: No functional.xml found")
    
    # Create NWB file
    print("Creating NWB file...")
    
    nwbfile = NWBFile(
        session_description=f"Two-photon imaging of Drosophila brain. "
                          f"Area: {expt_metadata.get('brain_area', 'unknown')}. "
                          f"{expt_metadata.get('notes', '')}",
        identifier=f"{os.path.basename(fly_folder)}_{fly_metadata.get('date', 'unknown')}",
        session_start_time=scan_metadata.get('session_start_time', datetime.now(tzlocal())),
        experimenter=[expt_metadata.get('experimenter', 'Unknown')],
        lab='Clandinin Lab',
        institution='Stanford University',
        experiment_description=f"Two-photon calcium imaging with visual stimulation. "
                              f"Genotype: {fly_metadata.get('genotype', 'unknown')}",
        session_id=os.path.basename(fly_folder),
    )
    
    # Add subject information
    nwbfile.subject = Subject(
        subject_id=os.path.basename(fly_folder),
        age=fly_metadata.get('age', 'unknown'),
        description=f"Circadian: {fly_metadata.get('circadian_on', 'unknown')} to "
                   f"{fly_metadata.get('circadian_off', 'unknown')}. "
                   f"Temp: {fly_metadata.get('temp', 'unknown')}. "
                   f"{fly_metadata.get('notes', '')}",
        species='Drosophila melanogaster',
        sex=fly_metadata.get('gender', 'U'),
        genotype=fly_metadata.get('genotype', 'unknown')
    )
    
    # Create device
    device = nwbfile.create_device(
        name='BrukerTwoPhoton',
        description='Bruker two-photon microscope',
        manufacturer='Bruker'
    )
    
    # Create optical channels
    optical_channel_red = OpticalChannel(
        name='TdTomato',
        description='Red channel - TdTomato structural marker',
        emission_lambda=581.0  # TdTomato peak emission
    )
    
    optical_channel_green = OpticalChannel(
        name='GCaMP6f',
        description='Green channel - GCaMP6f calcium indicator',
        emission_lambda=510.0  # GCaMP6f peak emission
    )
    
    # Create imaging plane
    imaging_plane = nwbfile.create_imaging_plane(
        name='ImagingPlane',
        optical_channel=optical_channel_green,  # Primary channel
        description=f"Multiplane imaging with 49 z-planes. "
                   f"Brain area: {expt_metadata.get('brain_area', 'unknown')}",
        device=device,
        excitation_lambda=920.0,  # Typical 2P excitation for GCaMP
        imaging_rate=scan_metadata.get('framerate', 1.0),
        indicator='GCaMP6f',
        location=expt_metadata.get('brain_area', 'unknown'),
        grid_spacing=[
            scan_metadata.get('x_voxel_size', 1.0),
            scan_metadata.get('y_voxel_size', 1.0),
            scan_metadata.get('z_voxel_size', 1.0)
        ],
        grid_spacing_unit='micrometers',
        reference_frame='Drosophila brain'
    )
    
    # Add additional optical channel for red
    imaging_plane.add_optical_channel(optical_channel_red)
    
    # Process anatomical scans
    print("\nProcessing anatomical scans...")
    anat_folders = sorted([os.path.join(fly_folder, x) for x in os.listdir(fly_folder) if 'anat' in x])
    
    for anat_idx, anat_folder in enumerate(anat_folders):
        imaging_folder = os.path.join(anat_folder, 'imaging')
        
        # Load red channel (TdTomato)
        red_nii = os.path.join(imaging_folder, 'anatomy_channel_1.nii.gz')