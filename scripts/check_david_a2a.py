"""Standalone check: does a fly's clean anatomy register to David's meanbrain?

Not part of the preprocess/postprocess pipeline. Takes the template and the fly's
anatomy_channel_1_moc_mean_clean.nii, sets voxel spacing on both (fly from its Bruker
.xml, template from its NIfTI header), resamples both to 2 um isotropic, optionally
flips the fly in z, then runs ANTs Affine followed by SyN (fly -> template).

Writes to the output directory:
    template_2um.nii                 template resampled to 2 um iso (reference for viewing)
    fly_to_template_affine.nii       fly after the Affine stage, in template space
    fly_to_template_syn.nii          fly after the SyN stage, in template space
    overlay_affine.png / overlay_syn.png
                                     red = fly, green = template, at three z-planes

Usage (from scripts/, or via check_david_a2a.sbatch):
    python3 check_david_a2a.py <template.nii> <anatomy_channel_1_moc_mean_clean.nii> <out_dir> [--flip-z]
"""
import argparse
import glob
import os
import sys
from time import time

import numpy as np
import nibabel as nib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import ants

import brainsss

ISO_SPACING = (2, 2, 2)  # um
Z_FRACTIONS = (0.25, 0.5, 0.75)  # z-planes shown in the overlays, as fractions of template depth


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('template_path', help="template NIfTI (David's meanbrain)")
    parser.add_argument('anat_path', help='fly clean anat NIfTI (anatomy_channel_1_moc_mean_clean.nii)')
    parser.add_argument('out_dir', help='output directory (created if missing)')
    parser.add_argument('--flip-z', action='store_true', help='flip the fly (moving) image in z before registering')
    cli = parser.parse_args()

    if not os.path.exists(cli.out_dir):
        os.makedirs(cli.out_dir)

    ### Fly resolution from the Bruker xml next to the anat
    xml_file = find_anat_xml(cli.anat_path)
    fly_res = brainsss.get_resolution(xml_file)
    log('Fly xml: {}'.format(xml_file))
    log('Fly pixel size (x, y, z) um: {}'.format(fly_res))

    ### Template resolution from its NIfTI header
    template_nii = nib.load(cli.template_path)
    template_res = tuple(float(v) for v in template_nii.header.get_zooms()[:3])
    log('Template: {}'.format(cli.template_path))
    log('Template voxel size (x, y, z) from header: {}'.format(template_res))

    ### Load, set spacing, resample to 2 um iso
    fixed = np.asarray(template_nii.get_data().squeeze(), dtype='float32')
    log('Template shape: {}'.format(fixed.shape))
    fixed = ants.from_numpy(fixed)
    fixed.set_spacing(template_res)
    fixed = ants.resample_image(fixed, ISO_SPACING, use_voxels=False)
    log('Template 2um iso shape: {}'.format(fixed.shape))

    moving = np.asarray(nib.load(cli.anat_path).get_data().squeeze(), dtype='float32')
    log('Fly shape: {}'.format(moving.shape))
    if cli.flip_z:
        moving = moving[:, :, ::-1]
        log('Flipped fly in z')
    moving = ants.from_numpy(moving)
    moving.set_spacing(fly_res)
    moving = ants.resample_image(moving, ISO_SPACING, use_voxels=False)
    log('Fly 2um iso shape: {}'.format(moving.shape))

    ants.image_write(fixed, os.path.join(cli.out_dir, 'template_2um.nii'))

    ### Affine
    t0 = time()
    affine = ants.registration(fixed, moving, type_of_transform='Affine')
    log('Affine done | {}'.format(sec_to_hms(time() - t0)))
    save_stage(affine['warpedmovout'], fixed, 'affine', cli.out_dir)

    ### SyN, initialized from the affine
    t0 = time()
    syn = ants.registration(fixed, moving, type_of_transform='SyN', initial_transform=affine['fwdtransforms'][0])
    log('SyN done | {}'.format(sec_to_hms(time() - t0)))
    save_stage(syn['warpedmovout'], fixed, 'syn', cli.out_dir)

    log('Done. Outputs in {}'.format(cli.out_dir))


def find_anat_xml(anat_path):
    """ The Bruker xml for an anat: next to the file, or in the sibling imaging/ folder
    (the clean anat lives in anat_0/moco/, the xml in anat_0/imaging/anatomy.xml). """
    anat_dir = os.path.dirname(os.path.abspath(anat_path))
    for directory in [anat_dir, os.path.join(os.path.dirname(anat_dir), 'imaging')]:
        named = os.path.join(directory, 'anatomy.xml')
        if os.path.exists(named):
            return named
        candidates = [f for f in sorted(glob.glob(os.path.join(directory, '*.xml'))) if 'Voltage' not in f]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            sys.exit('Multiple xml files in {}, cannot pick one: {}'.format(directory, candidates))
    sys.exit('No Bruker xml found next to {} or in ../imaging/'.format(anat_path))


def save_stage(warped, fixed, stage, out_dir):
    nii_file = os.path.join(out_dir, 'fly_to_template_{}.nii'.format(stage))
    ants.image_write(warped, nii_file)
    log('Saved {}'.format(nii_file))
    png_file = os.path.join(out_dir, 'overlay_{}.png'.format(stage))
    save_overlay(fixed.numpy(), warped.numpy(), stage, png_file)
    log('Saved {}'.format(png_file))


def save_overlay(template, fly, stage, png_file):
    """ Red = fly, green = template, at Z_FRACTIONS of the template depth. """
    template = normalize(template)
    fly = normalize(fly)
    z_planes = [int(round(f * (template.shape[2] - 1))) for f in Z_FRACTIONS]

    fig, axes = plt.subplots(1, len(z_planes), figsize=(6 * len(z_planes), 4))
    for ax, z in zip(axes, z_planes):
        rgb = np.zeros(template.shape[:2] + (3,), dtype='float32')
        rgb[..., 0] = fly[:, :, z]
        rgb[..., 1] = template[:, :, z]
        ax.imshow(np.transpose(rgb, (1, 0, 2)))  # x horizontal, y vertical
        ax.set_title('{} | z = {} ({} um)'.format(stage, z, z * ISO_SPACING[2]))
        ax.axis('off')
    fig.suptitle('red = fly, green = template')
    fig.tight_layout()
    fig.savefig(png_file, dpi=150, bbox_inches='tight')
    plt.close(fig)


def normalize(brain):
    brain = np.nan_to_num(brain.astype('float32'))
    lo, hi = np.percentile(brain, [1, 99])
    if hi <= lo:
        return np.zeros_like(brain)
    return np.clip((brain - lo) / (hi - lo), 0, 1)


def log(message):
    print(message, flush=True)


def sec_to_hms(t):
    secs = '{:02.0f}'.format(np.floor(t % 60))
    mins = '{:02.0f}'.format(np.floor((t / 60) % 60))
    hrs = '{:02.0f}'.format(np.floor((t / 3600) % 60))
    return ':'.join([hrs, mins, secs])


if __name__ == '__main__':
    main()
