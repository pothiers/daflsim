#! /usr/bin/env python
## @package pyexample
#  Turn a timeline queue log into NxM matrix.
#
#  N:: Number of queues
#  M:: Number of time steps

'''\
<<Python script callable from command line.  Put description here.>>
'''

import sys
import string
import argparse
import logging
import csv
from pprint import pprint

sample='''
dataq.dtskp.q1235 0 1
dataq.dtskp.q1335 0 1
dataq.dtskp.q1435 0 1
dataq.dtstuc.q6135 0 1
'''

## DOXYGEN documentation for a function.
#
# More details.
def toMatrix(incsv,outcsv):
    matrix = dict() # matrix[timestamp] = dict(path1=value1,path2=value2,...)
    paths = set()
    with incsv as csvfile:
        dialect = csv.Sniffer().sniff(sample,delimiters=' ')
        reader = csv.DictReader(incsv, dialect=dialect,
                                fieldnames=['path','value','timestamp'])
        for d in reader:
            paths.add(d['path'])
            matrix.setdefault(int(d['timestamp']),dict())
            matrix[int(d['timestamp'])][d['path']] = d['value']

    # Delete duplicates (keep both ends of run but remove middle)
    prev1Value,prev1Key,prev2Value,prev2Key = [None]*4
    t = sorted(matrix.keys(),reverse=True) # time (seconds)
    nukem = set()
    for i in range(2,len(t)):
        if matrix[t[i]] == matrix[t[i-1]] == matrix[t[i-2]]:
            nukem.add(t[i-1])
    for k in nukem:
        del matrix[k]

    # Print matrix
    print('time',',',end='', file=outcsv)        
    for p in sorted(paths):
        print(p,',',end='', file=outcsv)        
    print(file=outcsv)
    for k in sorted(matrix.keys()):
        print(k,',',end='', file=outcsv)
        for p in sorted(paths):
            print(matrix[k][p],',',end='', file=outcsv)
        print(file=outcsv)





##############################################################################

def main():
    parser = argparse.ArgumentParser(
        description='My shiny new python program',
        epilog='EXAMPLE: %(prog)s a b"'
        )
    parser.add_argument('--version', action='version',  version='1.0.1')
    parser.add_argument('infile', type=argparse.FileType('r'),
                        help='Input file')
    parser.add_argument('outfile', type=argparse.FileType('w'),
                        help='Output output'
                        )

    parser.add_argument('--loglevel',      help='Kind of diagnostic output',
                        choices=['CRTICAL', 'ERROR', 'WARNING',
                                 'INFO', 'DEBUG'],
                        default='WARNING',
                        )
    args = parser.parse_args()
    #!args.infile.close()
    #!args.infile = args.infile.name
    #!args.outfile.close()
    #!args.outfile = args.outfile.name

    #!print 'My args=',args
    #!print 'infile=',args.infile

    log_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(log_level, int):
        parser.error('Invalid log level: %s' % args.loglevel)
    logging.basicConfig(level=log_level,
                        format='%(levelname)s %(message)s',
                        datefmt='%m-%d %H:%M'
                        )
    logging.debug('Debug output is enabled in %s !!!', sys.argv[0])

    toMatrix(args.infile, args.outfile)

if __name__ == '__main__':
    main()

