import os
import sys
import json
from time import sleep
import datetime
import brainsss.utils as brainsss

def main(args):

    logfile = args['logfile']
    imports_path = args['imports_path']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    width=120
    printlog(F"{'Checking build queue':.<{width}}")
    #printlog('Time: {}'.format(datetime.datetime.now()))

    queued_folders = []
    for item in os.listdir(imports_path):
        queued_folders.append(item)
    printlog(F"Found queued folders{str(queued_folders):.>{width-20}}")

    if len(queued_folders) == 0:
        printlog('No queued folders found. Raising SystemExit.')
        raise SystemExit
    else:
        brainsss.sort_nicely(queued_folders)
        folder_to_build = os.path.join(os.path.split(imports_path)[0], queued_folders[0])
        print(folder_to_build)
        printlog(F"Commencing processing of{folder_to_build:.>{width-24}}")
        printlog(f"{'>   '+str(queued_folders[0])+'   <':-^{width}}")

        #os.system('sbatch build_fly.sh {}'.format(folder_to_build))
        #os.remove(os.path.join(imports_path, queued_folders[0]))

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))