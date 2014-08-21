#! /usr/bin/env python
## @package pyexample
#  Documentation for this module. (for DOXYGEN)
#
#  More details.

'''\
Simulate data-flow from instruments to archive.
'''

'''
Resources we might simulate usage for:
- CPU cycles
- RAM 
- disk space
- network bandwidth
'''

import sys
import string
import argparse
import logging
import simpy
import random

cfg = dict(
    queue_capacity   = 40,  # max number of records in queue
)


def print_stats(msg, res):
    print('#'*55)
    print('### ', msg)
    print('%d of %d get slots are allocated.' 
          % (len(res.get_queue),res.capacity))
    print('Get Queued events:', res.get_queue)

    print('%d of %d put slots are allocated.' 
          % (len(res.put_queue),res.capacity))
    print('Put Queued events:', res.put_queue)

    Print('Queued %d ITEMS:'% len(res.items), res.items)
    print('#'*55)

# PRODUCER
def camera(env, name, dataq, shots=5):
    '''Generates data records such as pictures, but could be any instrument 
in the telescope. '''
    for cid in range(shots):
        yield env.timeout(random.randint(1,7))
        msg = '%s.id%d.t%d.png' % (name, cid, env.now)
        dataq.put(msg)
        print('%d: [%s] Generated data: %s' %(env.now, name, msg))
        #! print_stats('after yield',dataq)
        #! print('%d: [%s] saved data' %(env.now, name))
    print_stats('Cameras put to dataq',dataq)        

class Dataq(simpy.Store):
    '''Data Queue.'''
    def __init__(self, env, name, capacity=cfg['queue_capacity']):
        self.env = env
        self.name = name
        super().__init__(env,capacity=capacity)
    
# CONSUMER, PRODUCER
def dataAction(env, name, inq, outq):
    while True:
        msg = yield inq.get()
        print('%d: [%s] Do action against %s' %(env.now, name, msg))
        yield env.timeout(random.randint(5,20))
        outq.put(msg)

def setup(env):
    random.seed()

    q1235 = Dataq(env,'q1235')
    q1335 = Dataq(env,'q1335')
    q1435 = Dataq(env,'q1435')
    archive = Dataq(env,'archive')

    env.process(camera(env, 'DECam', q1235))
    env.process(camera(env, 'KPCam', q1235))

    # Simulate pop from In-Queue, do action, push to Out-Queue
    #                             ACTION      IN-Q   OUT-Q 
    env.process( dataAction(env, 'iclient',   q1235, q1335) )
    env.process( dataAction(env, 'ibundle',   q1335, q1435) )
    env.process( dataAction(env, 'iunbundle', q1435, archive) )
    return archive

def simulate():
    env = simpy.Environment()

    archive = setup(env)
    env.run()
    print_stats('Simulation done. ARCHIVE:',archive)            

    

##############################################################################

def main():
    print('EXECUTING: %s\n\n' % (string.join(sys.argv)))
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

    simulate()

if __name__ == '__main__':
    main()

        
