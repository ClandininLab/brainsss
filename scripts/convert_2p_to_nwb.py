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

def find_tseries_folder(base_folder):
    """
    Find the tseries folder which may have timestamp in name
    e.g., 'TSeries-12172018-1322-001' or just 'tseries'
    
    Looks in:
    1. base_folder/imaging/TSeries-XXX  (processed data)
    2. base_folder/TSeries-XXX           (raw imports)
    
    Returns the full path to the tseries folder, or None if not found
    """
    if not os.path.exists(base_folder):
        print(f"    base_folder does not exist: {base_folder}")
        return None
    
    # First try looking in imaging subfolder (processed data)
    imaging_folder = os.path.join(base_folder, 'imaging')
    if os.path.exists(imaging_folder):
        for item in os.listdir(imaging_folder):
            item_path = os.path.join(imaging_folder, item)
            if os.path.isdir(item_path):
                if item.startswith('TSeries') or item.lower() == 'tseries':
                    print(f"    Found TSeries in imaging/: {item}")
                    return item_path
    
    # If not found, look directly in base_folder (raw imports)
    for item in os.listdir(base_folder):
        item_path = os.path.join(base_folder, item)
        if os.path.isdir(item_path):
            if item.startswith('TSeries') or item.lower() == 'tseries':
                print(f"    Found TSeries directly: {item}")
                return item_path
    
    # If still not found, return None
    print(f"    No TSeries folder found in {base_folder}")
    return None

def find_nifti_files(tseries_folder):
    """
    Find nifti files in tseries folder
    Returns dict with channel_1 and channel_2 paths
    """
    nifti_files = {'channel_1': None, 'channel_2': None}
    
    if not os.path.exists(tseries_folder):
        return nifti_files
    
    for file in os.listdir(tseries_folder):
        if file.endswith('.nii.gz'):
            if 'channel_1' in file:
                nifti_files['channel_1'] = os.path.join(tseries_folder, file)
                print(f"      Found channel_1: {file}")
            elif 'channel_2' in file:
                nifti_files['channel_2'] = os.path.join(tseries_folder, file)
                print(f"      Found channel_2: {file}")
    
    return nifti_files

def find_xml_file(folder, xml_type='functional'):
    """
    Find XML file in folder
    xml_type: 'functional', 'anatomy', 'voltage_output', or 'voltage_recording'
    """
    if not os.path.exists(folder):
        return None
    
    for file in os.listdir(folder):
        if file.endswith('.xml'):
            if xml_type == 'functional' and 'Voltage' not in file:
                return os.path.join(folder, file)
            elif xml_type == 'anatomy' and 'Voltage' not in file:
                return os.path.join(folder, file)
            elif xml_type == 'voltage_output' and 'VoltageOutput' in file:
                return os.path.join(folder, file)
            elif xml_type == 'voltage_recording' and 'VoltageRecording' in file:
                return os.path.join(folder, file)
    
    return None

def find_hdf5_file(func_folder):
    """
    Find HDF5 file (visual stimulus) 
    Could be in func_0/, func_0/imaging/, or func_0/TSeries-XXX/
    """
    search_locations = [
        func_folder,  # func_0/
    ]
    
    # Check if there's an imaging subfolder
    imaging_folder = os.path.join(func_folder, 'imaging')
    if os.path.exists(imaging_folder):
        search_locations.append(imaging_folder)
    
    # Also check TSeries folder if it exists
    tseries = find_tseries_folder(func_folder)
    if tseries:
        search_locations.append(tseries)
    
    for location in search_locations:
        if os.path.exists(location):
            for file in os.listdir(location):
                if file.endswith('.hdf5') or file.endswith('.h5'):
                    print(f"      Found HDF5 in {os.path.basename(location)}: {file}")
                    return os.path.join(location, file)
    
    return None

def load_xml_metadata(xml_file):
    """
    Extract metadata from Bruker XML file
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
        print(f"      Warning: No .dat file found in {fictrac_folder}")
        return None
    
    dat_file = os.path.join(fictrac_folder, dat_files[0])
    
    # Load FicTrac data
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
        print(f"      Warning: Could not load FicTrac data: {e}")
        return None

def load_visual_stimulus(hdf5_file):
    """
    Load visual stimulus data from HDF5 file
    """
    if not hdf5_file or not os.path.exists(hdf5_file):
        return None
    
    try:
        with h5py.File(hdf5_file, 'r') as f:
            stimulus_data = {}
            
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
        print(f"      Warning: Could not load stimulus data: {e}")
        return None
    
def convert_fly_to_nwb(fly_folder, output_file):
    """
    Convert a complete fly dataset to NWB format
    Works with raw imports (no JSON files required)
    
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
    
    # Extract date from parent folder name (e.g., 20240403__queue__)
    parent_folder = os.path.basename(os.path.dirname(fly_folder))
    date_match = parent_folder[:8] if len(parent_folder) >= 8 else 'unknown'
    fly_name = os.path.basename(fly_folder)
    
    print(f"Date from folder: {date_match}")
    print(f"Fly name: {fly_name}")
    
    # Find functional folders
    func_folders = sorted([os.path.join(fly_folder, x) for x in os.listdir(fly_folder) if 'func' in x])
    
    if not func_folders:
        print("Error: No functional folders found!")
        return
    
    print(f"Found {len(func_folders)} functional folder(s)")
    
    # Load metadata from first functional scan's XML
    func_0 = func_folders[0]
    imaging_folder_0 = os.path.join(func_0, 'imaging')
    tseries_0 = find_tseries_folder(imaging_folder_0)
    
    func_xml = None
    if tseries_0:
        func_xml = find_xml_file(tseries_0, 'functional')
        print(f"Found XML: {func_xml if func_xml else 'None'}")
    
    if func_xml and os.path.exists(func_xml):
        scan_metadata = load_xml_metadata(func_xml)
        session_start_time = scan_metadata.get('session_start_time', datetime.now(tzlocal()))
    else:
        print("Warning: No functional.xml found, using current time")
        scan_metadata = {}
        session_start_time = datetime.now(tzlocal())
    
    # Create NWB file with minimal metadata
    print("Creating NWB file...")
    
    nwbfile = NWBFile(
        session_description=f"Two-photon imaging of Drosophila brain",
        identifier=f"{fly_name}_{date_match}",
        session_start_time=session_start_time,
        experimenter=['Unknown'],
        lab='Clandinin Lab',
        institution='Stanford University',
        experiment_description=f"Two-photon calcium imaging session",
        session_id=fly_name,
    )
    
    # Add subject information
    nwbfile.subject = Subject(
        subject_id=fly_name,
        age='unknown',
        description=f'Fly from {date_match}',
        species='Drosophila melanogaster',
        sex='U',  # Unknown
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
    
    # Create imaging plane with BOTH optical channels
    imaging_plane = nwbfile.create_imaging_plane(
        name='ImagingPlane',
        optical_channel=[optical_channel_green, optical_channel_red],  # Pass as list
        description=f"Multiplane imaging with 49 z-planes",
        device=device,
        excitation_lambda=920.0,  # Typical 2P excitation for GCaMP
        imaging_rate=scan_metadata.get('framerate', 1.0),
        indicator='GCaMP6f',
        location='brain',
        grid_spacing=[
            scan_metadata.get('x_voxel_size', 1.0),
            scan_metadata.get('y_voxel_size', 1.0),
            scan_metadata.get('z_voxel_size', 1.0)
        ],
        grid_spacing_unit='micrometers',
        reference_frame='Drosophila brain'
    )
    
    # Process anatomical scans
    print("\nProcessing anatomical scans...")
    anat_folders = sorted([os.path.join(fly_folder, x) for x in os.listdir(fly_folder) if 'anat' in x])
    
    if anat_folders:
        print(f"Found {len(anat_folders)} anatomical folder(s)")
    else:
        print("No anatomical folders found")
    
    for anat_idx, anat_folder in enumerate(anat_folders):
        imaging_folder = os.path.join(anat_folder, 'imaging')
        
        # Find the tseries folder (may have timestamp in name)
        tseries_folder = find_tseries_folder(imaging_folder)
        
        if tseries_folder is None:
            print(f"  Warning: No tseries folder found for {anat_folder}")
            continue
        
        print(f"  Found tseries folder: {os.path.basename(tseries_folder)}")
        
        # Find nifti files
        nifti_files = find_nifti_files(tseries_folder)
        
        # Load red channel (TdTomato)
        if nifti_files['channel_1']:
            print(f"  Loading anatomical scan {anat_idx} (red channel)...")
            img = nib.load(nifti_files['channel_1'])
            data = img.get_fdata().astype(np.float32)
            
            anat_series_red = TwoPhotonSeries(
                name=f'AnatomicalSeries_TdTomato_{anat_idx}',
                data=data,
                imaging_plane=imaging_plane,
                unit='normalized amplitude',
                format='raw',
                description=f'Anatomical scan {anat_idx} - TdTomato channel (red)',
                comments=f'Shape: {data.shape}, used for motion correction',
                rate=1.0,
            )
            nwbfile.add_acquisition(anat_series_red)
            print(f"    Added red channel: shape {data.shape}, size {data.nbytes / 1e9:.2f} GB")
        else:
            print(f"  No channel_1 nifti found")
        
        # Load green channel (GCaMP) if exists
        if nifti_files['channel_2']:
            print(f"  Loading anatomical scan {anat_idx} (green channel)...")
            img = nib.load(nifti_files['channel_2'])
            data = img.get_fdata().astype(np.float32)
            
            anat_series_green = TwoPhotonSeries(
                name=f'AnatomicalSeries_GCaMP_{anat_idx}',
                data=data,
                imaging_plane=imaging_plane,
                unit='normalized amplitude',
                format='raw',
                description=f'Anatomical scan {anat_idx} - GCaMP6f channel (green)',
                rate=1.0,
            )
            nwbfile.add_acquisition(anat_series_green)
            print(f"    Added green channel: shape {data.shape}")
    
    # Process functional scans
    print("\nProcessing functional scans...")
    
    for func_idx, func_folder in enumerate(func_folders):
        print(f"\n  Processing {os.path.basename(func_folder)}...")
        
        imaging_folder = os.path.join(func_folder, 'imaging')
        
        # Find the tseries folder (may have timestamp in name)
        tseries_folder = find_tseries_folder(imaging_folder)
        
        if tseries_folder is None:
            print(f"  Warning: No tseries folder found for {func_folder}")
            continue
            
        print(f"  Found tseries folder: {os.path.basename(tseries_folder)}")
        
        # Find nifti files
        nifti_files = find_nifti_files(tseries_folder)
        
        # Try to get scan metadata from XML
        func_xml = find_xml_file(tseries_folder, 'functional')
        scan_meta = {}
        
        if func_xml:
            try:
                xml_meta = load_xml_metadata(func_xml)
                scan_meta = xml_meta
                print(f"  Loaded metadata from XML")
            except Exception as e:
                print(f"  Warning: Could not load XML metadata: {e}")
        
        # Load functional red channel (TdTomato)
        if nifti_files['channel_1']:
            print(f"    Loading functional red channel...")
            img = nib.load(nifti_files['channel_1'])
            data = img.get_fdata().astype(np.float32)
            
            func_series_red = TwoPhotonSeries(
                name=f'FunctionalSeries_TdTomato_{func_idx}',
                data=data,
                imaging_plane=imaging_plane,
                unit='normalized amplitude',
                format='raw',
                description=f'Functional scan {func_idx} - TdTomato channel',
                comments=f'Laser power: {scan_meta.get("laser_power", "unknown")} mW, '
                        f'PMT gain: {scan_meta.get("PMT_red", "unknown")}',
                rate=scan_meta.get('framerate', 1.0),
            )
            nwbfile.add_acquisition(func_series_red)
            print(f"      Red channel: shape {data.shape}, size {data.nbytes / 1e9:.2f} GB")
        else:
            print(f"    No channel_1 nifti found")
        
        # Load functional green channel (GCaMP)
        if nifti_files['channel_2']:
            print(f"    Loading functional green channel...")
            img = nib.load(nifti_files['channel_2'])
            data = img.get_fdata().astype(np.float32)
            
            func_series_green = TwoPhotonSeries(
                name=f'FunctionalSeries_GCaMP_{func_idx}',
                data=data,
                imaging_plane=imaging_plane,
                unit='normalized amplitude',
                format='raw',
                description=f'Functional scan {func_idx} - GCaMP6f channel',
                comments=f'Laser power: {scan_meta.get("laser_power", "unknown")} mW, '
                        f'PMT gain: {scan_meta.get("PMT_green", "unknown")}',
                rate=scan_meta.get('framerate', 1.0),
            )
            nwbfile.add_acquisition(func_series_green)
            print(f"      Green channel: shape {data.shape}, size {data.nbytes / 1e9:.2f} GB")
        else:
            print(f"    No channel_2 nifti found")
        
        # Load visual stimulus data (HDF5 can be in multiple locations)
        print(f"    Looking for visual stimulus data...")
        hdf5_file = find_hdf5_file(func_folder)
        
        if hdf5_file:
            print(f"    Found stimulus file: {os.path.basename(hdf5_file)}")
            stimulus_data = load_visual_stimulus(hdf5_file)
            if stimulus_data:
                for key, value in stimulus_data.items():
                    if isinstance(value, np.ndarray) and value.ndim == 1:
                        try:
                            ts = TimeSeries(
                                name=f'Stimulus_{func_idx}_{key.replace("/", "_")}',
                                data=value,
                                unit='a.u.',
                                description=f'Visual stimulus parameter: {key}'
                            )
                            nwbfile.add_stimulus(ts)
                        except Exception as e:
                            pass  # Skip problematic stimulus data
                print(f"      Added stimulus data with {len(stimulus_data)} fields")
        else:
            print(f"    No HDF5 stimulus file found")
        
        # Load voltage recording data (CSV in tseries folder)
        voltage_csv = None
        if os.path.exists(tseries_folder):
            for file in os.listdir(tseries_folder):
                if 'VoltageRecording' in file and file.endswith('.csv'):
                    voltage_csv = os.path.join(tseries_folder, file)
                    break
        
        if voltage_csv:
            try:
                df = pd.read_csv(voltage_csv)
                voltage_series = TimeSeries(
                    name=f'VoltageRecording_{func_idx}',
                    data=df.values,
                    unit='volts',
                    description='Voltage recordings (photodiode)',
                    comments=f'Columns: {df.columns.tolist()}'
                )
                nwbfile.add_acquisition(voltage_series)
                print(f"      Added voltage recording data: shape {df.shape}")
            except Exception as e:
                print(f"      Warning: Could not load voltage data: {e}")
        
        # Load FicTrac behavioral data
        fictrac_folder = os.path.join(func_folder, 'fictrac')
        if os.path.exists(fictrac_folder):
            print(f"    Loading FicTrac behavioral data...")
            
            fictrac_data = load_fictrac_data(fictrac_folder)
            
            if fictrac_data:
                # Create behavioral processing module
                behavior_module = nwbfile.create_processing_module(
                    name=f'behavior_{func_idx}',
                    description=f'Behavioral data from FicTrac for functional scan {func_idx}'
                )
                
                # Add position data
                position_series = SpatialSeries(
                    name='Position',
                    data=np.column_stack([
                        fictrac_data['position_x'],
                        fictrac_data['position_y']
                    ]),
                    reference_frame='lab coordinates',
                    unit='arbitrary',
                    timestamps=fictrac_data['timestamps'],
                    description='Integrated position of fly on ball'
                )
                position = Position(spatial_series=position_series)
                behavior_module.add(position)
                
                # Add heading direction
                heading_series = SpatialSeries(
                    name='Heading',
                    data=fictrac_data['heading'],
                    reference_frame='lab coordinates',
                    unit='radians',
                    timestamps=fictrac_data['timestamps'],
                    description='Integrated heading angle'
                )
                compass = CompassDirection(spatial_series=heading_series)
                behavior_module.add(compass)
                
                # Add velocity as TimeSeries
                velocity_series = TimeSeries(
                    name='Velocity',
                    data=fictrac_data['velocity'],
                    unit='arbitrary units/s',
                    timestamps=fictrac_data['timestamps'],
                    description='Animal movement speed'
                )
                behavior_module.add(velocity_series)
                
                # Add rotational velocities
                for rotation_name in ['delta_rot_lab_side', 'delta_rot_lab_forward', 'delta_rot_lab_turn']:
                    rot_series = TimeSeries(
                        name=rotation_name,
                        data=fictrac_data[rotation_name],
                        unit='radians/frame',
                        timestamps=fictrac_data['timestamps'],
                        description=f'Rotational velocity: {rotation_name}'
                    )
                    behavior_module.add(rot_series)
                
                print(f"      Added FicTrac data: {len(fictrac_data['timestamps'])} timepoints")
        else:
            print(f"    No FicTrac folder found")
    
    # Write NWB file with compression
    print(f"\nWriting NWB file to {output_file}...")
    print("This may take several minutes for large files...")
    
    with NWBHDF5IO(output_file, 'w') as io:
        io.write(nwbfile)
    
    # Validate
    print("\nValidating NWB file...")
    try:
        from pynwb import validate
        with NWBHDF5IO(output_file, 'r') as io:
            nwbfile_in = io.read()
            results = validate(nwbfile_in)
            if results:
                print("Validation warnings:")
                for r in results:
                    print(f"  - {r}")
            else:
                print("Validation passed!")
    except Exception as e:
        print(f"Validation error: {e}")
    
    # Print file size
    file_size = os.path.getsize(output_file) / (1024**3)
    print(f"\nOutput file size: {file_size:.2f} GB")
    print(f"{'='*80}\n")

def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_2p_to_nwb.py <fly_folder> <output_file>")
        print("Example: python convert_2p_to_nwb.py /path/to/fly_001 /path/to/output/fly_001.nwb")
        sys.exit(1)
    
    fly_folder = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(fly_folder):
        print(f"Error: Fly folder does not exist: {fly_folder}")
        sys.exit(1)
    
    convert_fly_to_nwb(fly_folder, output_file)

if __name__ == '__main__':
    main()