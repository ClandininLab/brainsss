from setuptools import setup

setup(
    name='brainsss',
    version='0.0.1',
    long_description="""
    This package performs preprocessing and analysis of 
    volumetric neural data on sherlock. At its core, brainsss is a wrapper to 
    interface with Slurm via python. It can handle complex submission of batches of 
    jobs with job dependencies and makes it easy to pass variables between jobs. 
    It also has full logging of job progress, output, and errors.
    """,
    packages=['brainsss'],
    include_package_data=True,
    install_requires=[
        'pyfiglet',
        'psutil',
        'lxml',
        'openpyxl',
        'nibabel',
        'numpy',
        'pandas',
        'pytest'
    ],
)