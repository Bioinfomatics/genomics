#!/bin/env python
#
#     build_analysis_dir.py: build directory with links to primary data
#     Copyright (C) University of Manchester 2011 Peter Briggs
#
########################################################################
#
# build_analysis_dir.py
#
#########################################################################

"""build_analysis_dir.py
"""

#######################################################################
# Import modules that this module depends on
#######################################################################

import sys,os
import logging
import SolidDataExtractor

#######################################################################
# Class definitions
#######################################################################

class Experiment:
    """Class to define an experiment from a SOLiD run.
    """
    def __init__(self):
        """Create a new Experiment instance.
        """
        self.name = None
        self.type = None
        self.sample = None
        self.library = None

    def dirname(self):
        """Return directory name for experiment

        The directory name is the supplied name plus the experiment
        type joined by an underscore, unless no type was specified (in
        which case it is just the experiment name).
        """
        if self.type:
            return '_'.join((self.name,self.type))
        else:
            return self.name

    def describe(self):
        """Describe the experiment as a set of command line options
        """
        options = ["--name=%s" % self.name]
        if self.type:
            options.append("--type=%s" % self.type)
        if self.sample:
            sample = self.sample
        else:
            sample = '*'
        if self.library:
            library = self.library
        else:
            library = '*'
        options.append("--source=%s/%s" % (sample,library))
        return ' '.join(options)

#######################################################################
# Module functions
#######################################################################

def match(pattern,word):
    """Check if word matches pattern"""
    if not pattern or pattern == '*':
        # No pattern/wildcard, matches everything
        return True
    # Only simple patterns considered for now
    if pattern.endswith('*'):
        # Match the start
        return word.startswith(pattern[:-1])
    else:
        # Match the whole word exactly
        return (word == pattern)

def getLinkName(filen,sample,library):
    """Return the 'analysis' file name based on a source file name.
    
    The analysis file name is constructed as

    <instrument>_<datestamp>_<sample>_<library>.csfasta

    or

    <instrument>_<datestamp>_<sample>_<library>_QV.qual
    
    Arguments:
      filen: name of the source file
      sample: SolidSample object representing the parent sample
      library: SolidLibrary object representing the parent library

    Returns:
    Name for the analysis file.
    """
    # Construct new name
    link_filen_elements = [sample.parent_run.run_info.instrument,
                           sample.parent_run.run_info.datestamp,
                           sample.name,library.name]
    ext = os.path.splitext(filen)[1]
    if ext == ".qual":
        link_filen_elements.append("QV")
    link_filen = '_'.join(link_filen_elements) + ext
    return link_filen

# Filesystem wrappers

def mkdir(dirn):
    """Make a directory"""
    ##print "Making %s" % dirn
    if not os.path.isdir(dirn):
        os.mkdir(dirn)

def mklink(target,link_name):
    """Make a symbolic link"""
    ##print "Linking to %s from %s" % (target,link_name)
    os.symlink(target,link_name)

#######################################################################
# Main program
#######################################################################

if __name__ == "__main__":
    print "%s [--dry-run] EXPERIMENT [EXPERIMENT ...] <solid_run_dir>" % \
        os.path.basename(sys.argv[0])
    print ""
    print "Build analysis directory structure for one or more 'experiments'"
    print "and populate with links to the primary data in <solid_run_dir>."
    print ""
    print "Options:"
    print "    --dry-run: report the operations that would be performed"
    print ""
    print "Defining experiments:"
    print ""
    print "Each experiment is defined with a group of options (must be supplied"
    print "in this order for each):"
    print ""
    print "    --name=<name> [--type=<expt_type>] --source=<sample>/<library>"
    print "                                      [--source=... ]"
    print ""
    print "    <name> is an identifier (typically the user's initials) used"
    print "        for the analysis directory e.g. 'PB'"
    print "    <expt_type> is e.g. 'reseq', 'ChIP-seq', 'RNAseq', 'miRNA'..."
    print "    <sample>/<library> specify the names for primary data files"
    print "        e.g. 'PB_JB_pool/PB*'"
    print ""
    print "    Example:"
    print "        --name=PB --type=ChIP-seq --source=PB_JB_pool/PB*"
    print ""
    print "    Both <sample> and <library> can include a trailing wildcard"
    print "    character (i.e. *) to match multiple names. */* will match all"
    print "    primary data files. Multiple --sources can be declared for"
    print "    each experiment."
    print ""
    print "For each experiment defined on the command line, a subdirectory"
    print "called '<name>_<expt_type>' (e.g. 'PB_ChIP-seq' - if no <expt_type>"
    print "was supplied then just the name is used) will be made, and links to"
    print "each of the primary data files."

    # List of experiment definitions
    expts = []
    # Dry run flag
    dry_run = False
    # Process command line
    if len(sys.argv) < 2:
        # Insuffient arguments
        sys.exit(1)
    solid_run_dir = None
    for arg in sys.argv[1:]:
        # Check
        if solid_run_dir is not None:
            # Still processing arguments after directory
            # name was read
            print "ERROR: additional argument after SOLiD run directory"
            sys.exit(1)
        # Process command line arguments
        if arg.startswith('--name='):
            expts.append(Experiment())
            expt = expts[-1]
            expt.name = arg.split('=')[1]
        elif arg.startswith('--type='):
            try:
                expt = expts[-1]
            except IndexError:
                print "No experiment defined for --type!"
                sys.exit(1)
            if not expt.type:
                expt.type = arg.split('=')[1]
            else:
                print "Type already defined for experiment!"
                sys.exit(1)
        elif arg.startswith('--source='):
            try:
                expt = expts[-1]
            except IndexError:
                print "No experiment defined for --source!"
                sys.exit(1)
            if expt.sample:
                # Duplicate the previous experiment
                expts.append(Experiment())
                expt_copy = expts[-1]
                expt_copy.name = expt.name
                expt_copy.type = expt.type
                expt = expt_copy
            # Extract sample and library
            source = arg.split('=')[1]
            try:
                i = source.index('/')
                expt.sample = source.split('/')[0]
                expt.library = source.split('/')[1]
            except ValueError:
                expt.sample = source
        elif arg == '--dry-run':
            dry_run = True
        elif arg == '--debug':
            logging.getLogger().setLevel(logging.DEBUG)
        elif not arg.startswith('--'):
            # Assume this is the last argument (source directory)
            solid_run_dir = arg
        else:
            # Unrecognised argument
            print "Unrecognised argument: %s" % arg
            sys.exit(1)
            
    # Check there's something to do
    if not solid_run_dir:
        print "No SOLiD run directory specified, nothing to do"
        sys.exit(1)
    if not os.path.isdir(solid_run_dir):
        print "ERROR directory '%s' not found" % solid_run_dir
    if not len(expts):
        print "No experiments defined, nothing to do"
        sys.exit(1)
    
    # Report
    print "%d experiments defined:" % len(expts)
    for expt in expts:
        print "\tName   : %s" % expt.name
        print "\tType   : %s" % expt.type
        print "\tSample : %s" % expt.sample
        print "\tLibrary: %s" % expt.library
        print "\tOptions: %s" % expt.describe()
        print ""

    # Get the run information
    print "Acquiring run information:"
    solid_runs = []
    for solid_dir in (solid_run_dir,solid_run_dir+"_2"):
        print "\t%s..." % solid_dir,
        run = SolidDataExtractor.SolidRun(solid_dir)
        if not run:
            print "FAILED: unable to get run data for %s" % solid_dir
        else:
            solid_runs.append(run)
            print "ok"
    if not len(solid_runs):
        print "No run data found!"
        sys.exit(1)

    # For each experiment, make a directory
    for expt in expts:
        expt_dir = expt.dirname()
        print "\nExperiment: %s" % expt_dir
        if not dry_run:
            mkdir(expt_dir)
        # Locate the primary data
        for run in solid_runs:
            for sample in run.samples:
                if match(expt.sample,sample.name):
                    # Found the sample
                    for library in sample.libraries:
                        if match(expt.library,library.name):
                            # Found a matching library
                            print "Located sample and library: %s/%s" % \
                                (sample.name,library.name)
                            # Look up primary data
                            print "Primary data:"
                            ln_csfasta = getLinkName(library.csfasta,
                                                     sample,library)
                            ln_qual = getLinkName(library.qual,
                                                  sample,library)
                            print "\t%s" % ln_csfasta
                            print "\t%s" % ln_qual
                            if not dry_run:
                                # Make symbolic links
                                mklink(library.csfasta,
                                       os.path.join(expt_dir,ln_csfasta))
                                mklink(library.qual,
                                       os.path.join(expt_dir,ln_qual))
                        else:
                            # Library didn't match
                            logging.debug("%s/%s: library didn't match pattern" %
                                          (sample.name,library.name))
                else:
                    # Sample didn't match
                    logging.debug("%s: ignoring sample" % sample.name)