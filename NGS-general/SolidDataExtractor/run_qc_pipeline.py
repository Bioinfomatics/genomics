#!/bin/env python
#
#     run_pipeline.py: run pipeline script on file sets
#     Copyright (C) University of Manchester 2011 Peter Briggs
#
########################################################################
#
# run_pipeline.py
#
#########################################################################

"""run_pipeline.py

Implements a program to run a pipeline script or command on the
set of files in a specific directory.

Usage: python run_pipeline.py [OPTIONS] <script> <data_dir> [ <data_dir> ... ]

<script> must accept arguments based on the --input option, but defaults to
         a csfasta/qual file pair.
<data_dir> contains the input data for the script.
"""

#######################################################################
# Import modules that this module depends on
#######################################################################

import sys
import os
import time
import subprocess
import logging

#######################################################################
# Class definitions
#######################################################################

# Qstat: helper class for getting information from qstat
class Qstat:
    """Utility class for getting information from the qstat command.

    Provides basic functionality for getting information on running jobs
    from the GE 'qstat' command.
    """
    def __init__(self):
        pass

    def list(self,user=None):
        """Get list of job ids in the queue.
        """
        cmd = ['qstat']
        if user:
            cmd.extend(('-u',user))
        else:
            # Get current user name
            cmd.extend(('-u',os.getlogin()))
        # Run the qstat
        p = subprocess.Popen(cmd,stdout=subprocess.PIPE)
        p.wait()
        # Process the output: get job ids
        job_ids = []
        # Typical output is:
        # job-ID  prior   name       user         ...<snipped>...
        # ----------------------------------------...<snipped>...
        # 620848 -499.50000 qc       myname       ...<snipped>...
        # ...
        # i.e. 2 header lines then one line per job
        for line in p.stdout:
            try:
                if line.split()[0].isdigit():
                    job_ids.append(line.split()[0])
            except IndexError:
                pass
        return job_ids

    def njobs(self,user=None):
        """Return the number of jobs in the queue.
        """
        return len(self.list(user=user))

    def hasJob(self,job_id):
        """Check if the specified job id is in the queue.
        """
        return (job_id in self.list())

# QsubJob: container for a script run
class QsubJob:
    """Wrapper class for setting up, submitting and monitoring qsub scripts

    """
    def __init__(self,name,dirn,script,*args):
        """Create an instance of QsubJob.

        Arguments:
          name: name to give the running job (i.e. qsub -N)
          dirn: directory to run the script in (i.e. qsub -wd)
          script: script file to submit, either a full path, relative path to dirn, or
            must be on the user's PATH in the environment where GE jobs are executed
          args: arbitrary arguments to supply to the script when it is submitted via qsub
        """
        self.name = name
        self.working_dir = dirn
        self.script = script
        self.args = args
        self.job_id = None
        self.log = None
        self.submitted = False
        self.terminated = False
        self.finished = False
        self.home_dir = os.getcwd()
        self.qstat = Qstat()

    def start(self):
        """Submit the job to the GE queue
        """
        if not self.submitted and not self.finished:
            self.job_id = QsubScript(self.name,self.working_dir,self.script,*self.args)
            self.submitted = True
            self.log = self.name+'.o'+self.job_id
            # Wait for evidence that the job has started
            logging.debug("Waiting for job to start")
            while not self.qstat.hasJob(self.job_id) and not os.path.exists(self.log):
                time.sleep(5)
        logging.debug("Job %s started (%s)" % (self.job_id,time.asctime()))
        return self.job_id

    def terminate(self):
        """Terminate (qdel) a running job
        """
        if not self.isRunning():
            Qdeljob(self.job_id)
            self.terminated = True

    def resubmit(self):
        """Resubmit the job

        Terminates the job (if still running) and restarts"""
        # Terminate running job
        if self.isRunning():
            self.terminate()
            while self.isRunning():
                time.sleep(5)
        # Reset flags
        self.submitted = False
        self.terminated = False
        self.finished = False
        # Resubmit
        return self.start()

    def isRunning(self):
        """Check if job is still running
        """
        if not self.submitted:
            return False
        if not self.finished:
            if not self.qstat.hasJob(self.job_id):
                self.finished = True
        return not self.finished

#######################################################################
# Module Functions
#######################################################################

# RunScript: execute a script or command
def RunScript(script,csfasta,qual):
    """Run a script or command
    """
    cwd=os.path.dirname(csfasta)
    p = subprocess.Popen((script,csfasta,qual),cwd=cwd)
    print "Running..."
    p.wait()
    print "Finished"

# QsubScript: submit a command to the cluster
def QsubScript(name,working_dir,script,*args):
    """Submit a script or command to the cluster via 'qsub'
    """
    # 
    logging.debug("QsubScript: submitting job")
    logging.debug("QsubScript: name       :%s" % name)
    logging.debug("QsubScript: working_dir: %s" % working_dir)
    logging.debug("QsubScript: script     : %s" % script)
    logging.debug("QsubScript: args       : %s" % str(args))
    # Build command to be submitted
    cmd_args = [script]
    cmd_args.extend(args)
    cmd = ' '.join(cmd_args)
    # Build qsub command to submit it
    qsub = ['qsub','-b','y','-V','-N',name]
    if not working_dir:
        qsub.append('-cwd')
    else:
        qsub.extend(('-wd',working_dir))
    qsub.append(cmd)
    logging.debug("QsubScript: qsub command: %s" % qsub)
    # Run the qsub job in the current directory
    # This shouldn't be significant
    cwd = os.getcwd()
    logging.debug("QsubScript: executing in %s" % cwd)
    p = subprocess.Popen(qsub,cwd=cwd,stdout=subprocess.PIPE)
    p.wait()
    # Capture the job id from the output
    job_id = None
    for line in p.stdout:
        if line.startswith('Your job'):
            job_id = line.split()[2]
    logging.debug("QsubScript: done - job id = %s" % job_id)
    # Return the job id
    return job_id

# QdelJob: delete a job from the queue
def QdelJob(job_id):
    """Remove a job from the GE queue using 'qdel'
    """
    logging.debug("QdelJob: deleting job")
    qdel=('qdel',job_id)
    p = subprocess.Popen(qdel)
    p.wait()

# QstatJobs: get number of jobs user has already in queue
def QstatJobs(user=None):
    """Get the number of jobs a user has in the queue
    """
    return Qstat().njobs()

# RunPipeline: execute script for multiple sets of files
def RunPipeline(script,run_data,working_dir=None,max_concurrent_jobs=4):
    """Execute script for multiple sets of files

    Given a script and a list of input file sets, script will be
    submitted to the cluster once for each set of files. No more
    than max_concurrent_jobs will be running for the user at any
    time.

    Arguments:
      script: name (including path) for pipeline script.
      run_data: a list consisting of tuples of files which will be
        supplied to the script as arguments.
      working_dir: specific directory to run the jobs in (optional).
      max_concurrent_jobs: the maximum number of jobs that the runner
        will submit to the cluster at any particular time (optional).
    """ 
    # Setup job name
    job_name = os.path.splitext(os.path.basename(script))[0]
    # Queue monitoring helper
    qstat = Qstat()
    # For each set of files, run the pipeline script
    running_jobs = []
    for data in run_data:
        # Update running jobs
        running_jobs = UpdateRunningJobs(running_jobs)
        # Check if queue is "full"
        while qstat.njobs() >= max_concurrent_jobs:
            # Wait a while before checking again
            logging.debug("Waiting for free space in queue...")
            time.sleep(poll_interval)
        # Submit more jobs
        logging.info("Submitting job: %s %s %s" % (script,data,working_dir))
        job = QsubJob(job_name,working_dir,script,*data)
        job_id = job.start()
        logging.info("Job id = %s" % job.job_id)
        logging.info("Log file = %s" % job.log)
        running_jobs.append(job)
    # All jobs submitted - wait for running jobs to finish
    logging.debug("All jobs submitted, waiting for running jobs to complete...")
    while len(running_jobs) > 0:
        running_jobs = UpdateRunningJobs(running_jobs)
        time.sleep(poll_interval)
    # Running jobs also completed
    return

def UpdateRunningJobs(running_jobs):
    """Return updated list of job ids which are still running in the queue

    Takes a list of job ids and returns a list of those which are still
    running on the cluster.
    """
    # Check if any jobs have finished
    unfinished_jobs = []
    for job in running_jobs:
        if not job.isRunning():
            # Job no longer in the queue
            logging.info("Job %s has completed (%s)" % (job.job_id,time.asctime()))
        else:
            # Still running
            unfinished_jobs.append(job)
    return unfinished_jobs

def GetSolidDataFiles(dirn):
    """Return list of csfasta/qual file pairs in target directory
    """
    # Gather data files
    logging.debug("Collecting csfasta/qual file pairs in %s" % dirn)
    data_files = []
    all_files = os.listdir(data_dir)
    all_files.sort()

    # Look for csfasta and matching qual files
    for filen in all_files:
        logging.debug("Examining file %s" % filen)
        root = os.path.splitext(filen)[0]
        ext = os.path.splitext(filen)[1]
        if ext == ".qual":
            qual = filen
            # Match csfasta names which don't have "_QV" in them
            try:
                i = root.rindex('_QV')
                csfasta = root[:i]+root[i+3:]+".csfasta"
            except IndexError:
                # QV not in name, try to match whole name
                csfasta = root+".csfasta"
            if os.path.exists(os.path.join(data_dir,csfasta)):
                data_files.append((csfasta,qual))
            else:
                logging.critical("Unable to get csfasta for %s" % filen)
    # Done - return file pairs
    return data_files

def GetFastqFiles(dirn):
    """Return list of fastq files in target directory
    """
    # Gather data files
    logging.debug("Collecting fastq files in %s" % dirn)
    data_files = []
    all_files = os.listdir(data_dir)
    all_files.sort()

    # Look for csfasta and matching qual files
    for filen in all_files:
        logging.debug("Examining file %s" % filen)
        root = os.path.splitext(filen)[0]
        ext = os.path.splitext(filen)[1]
        if ext == ".fastq": data_files.append((filen,))
    # Done - return file list
    return data_files

#######################################################################
# Main program
#######################################################################

if __name__ == "__main__":
    # Initialise
    max_concurrent_jobs = 4
    poll_interval = 30
    max_total_jobs = 0
    logging_level = logging.INFO
    script = None
    data_dirs = []
    input_type = "solid"

    # Deal with command line
    if len(sys.argv) < 3:
        print "Usage: %s [OPTIONS] <script> <dir> [<dir> ...]" % \
            os.path.basename(sys.argv[0])
        print ""
        print "<script> : pipeline script file to execute"
        print "<dir>    : one or more directories holding SOLiD data"
        print "           By default, <script> will be executed for each"
        print "           csfasta/qual file pair in dir, using:"
        print "             <script> <csfasta> <qual>"
        print "           Use --input option to run e.g."
        print "             <script> <fastq> etc"
        print ""
        print "Options:"
        print "  --limit=<n>: queue no more than <n> jobs at one time"
        print "               (default %s)" % max_concurrent_jobs
        print "  --test=<n> : submit no more than <n> jobs in total"
        print "  --debug    : print debugging output while running"
        print "  --input=<type> : specify type of input for script"
        print "               Can be one of:"
        print "               solid = csfasta/qual file pair (default)"
        print "               fastq = fastq file"
        print
        sys.exit()

    # Collect command line options
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            # Set maximum number of jobs to queue at one time
            max_concurrent_jobs = int(arg.split('=')[1])
        elif arg.startswith("--debug"):
            # Set logging level to output debugging info
            logging_level = logging.DEBUG
        elif arg.startswith("--test="):
            # Run in test mode: limit the number of jobs
            # submitted
            max_total_jobs = int(arg.split('=')[1])
        elif arg.startswith("--input="):
            # Specify input type
            input_type = arg.split('=')[1]
        elif arg.startswith("--") and len(data_dirs) > 0:
            # Some option appeared after we started collecting
            # directories
            logging.error("Unexpected argument encountered: %s" % arg)
            sys.exit(1)
        else:
            if script is None:
                # Script name
                print "Script: %s" % arg
                if os.path.isabs(arg):
                    # Absolute path
                    if os.path.isfile(arg):
                        script = arg
                    else:
                        script = None
                else:
                    # Try relative to pwd
                    script = os.path.normpath(os.path.join(os.getcwd(),arg))
                    if not os.path.isfile(script):
                        # Try relative to directory for script
                        script = os.path.abspath(os.path.normpath(
                                os.path.join(os.path.dirname(sys.argv[0]),arg)))
                        if not os.path.isfile(script):
                            script = None
                if script is None:
                    logging.error("Script file not found: %s" % script)
                    sys.exit(1)
                print "Full path for script: %s" % script
            else:
                # Data directory
                print "Directory: %s" % arg
                dirn = os.path.abspath(arg)
                if not os.path.isdir(dirn):
                    logging.error("Not a directory: %s" % dirn)
                    sys.exit(1)
                data_dirs.append(dirn)

    # Set logging format and level
    logging.basicConfig(format='%(levelname)8s %(message)s')
    logging.getLogger().setLevel(logging_level)

    # Iterate over data directories
    for data_dir in data_dirs:

        print "Running %s on data in %s" % (script,data_dir)
        if input_type == "solid":
            run_data = GetSolidDataFiles(data_dir)
        elif input_type == "fastq":
            run_data = GetFastqFiles(data_dir)

        # Check there's something to run on
        if len(run_data) == 0:
            logging.error("No data files collected for %s" % data_dir)
            continue

        # Test mode: limit the total number of jobs that will be
        # submitted
        if max_total_jobs > 0:
            run_data = run_data[:max_total_jobs]

        # Run the pipeline
        RunPipeline(script,run_data,working_dir=data_dir,
                    max_concurrent_jobs=max_concurrent_jobs)

    # Finished
    print "All pipelines finished"
