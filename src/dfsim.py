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
    queue_capacity   = 40, # max number of records in queue
    monitor_interval = 10, # seconds between checking queue
)

mon = None # !!!


def print_stats(msg, res):
    print('#'*55)
    print('### ', msg)
    print('%d of %d get slots are allocated.' 
          % (len(res.get_queue),res.capacity))
    #! print('Get Queued events: %s'%res.get_queue)

    print('%d of %d put slots are allocated.' 
          % (len(res.put_queue),res.capacity))

    print('Queued %d ITEMS:'% len(res.items), sorted(res.items))
    print('#'*55)


# Example plaintext feed to Graphite:
#   <metric path> <metric value> <metric timestamp>.
#   echo "local.random.diceroll 4 `date +%s`" | nc -q0 ${SERVER} ${PORT}
#   
#   timestamp:: Unix epoch (seconds since 1970-01-01 00:00:00 UTC)
#   value:: float
def feed_graphite(path, value, timestamp):
    log = mon.file if mon else sys.stdout
    print('%s %s %d' % (path, value, timestamp), file=log)

class Monitor():
    def __init__(self, outfile):
        self.file = outfile
        
    def close(self):
        self.file.close()

def q_in(when, src, q, data=None):
    q.put(data or 'NA')
    feed_graphite('dataq.%s'%q.name, len(q.items), when)          
    print('# %s -> %s'%(src, q.name))

# BROKEN; returns generator object instead of msg value
def q_out(when, dest, q):
    msg = yield q.get()
    print('# %s -> %s'%(q.name, dest))
    feed_graphite('dataq.%s'%q.name, len(q.items), when)          
    return msg


# PRODUCER (really the whole iSTB upto DciArchT)
def camera(env, name, dataq, shots=5):
    '''Generates data records such as pictures, but could be any instrument 
in the telescope. '''
    for cid in range(shots):
        yield env.timeout(random.randint(1,7))
        msg = '%s.id%d.png' % (name, cid)
        q_in(env.now, name, dataq, data=msg)

        print('# %04d [%s]: Generated data: %s' %(env.now, name, msg))
        #! print_stats('after yield',dataq)
        #! print('%d: [%s] saved data' %(env.now, name))
    #!print_stats('Cameras put to dataq',dataq)        

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
        #! msg = q_out(env.now, name, inq)
        print('# %s -> %s'%(inq.name, name))
        feed_graphite('dataq.%s'%inq.name, len(inq.items), env.now)          

        print('# %04d [%s]: Do action against: %s' %(env.now, name, msg))
        yield env.timeout(random.randint(5,20))
        if isinstance(outq,list):
            for dq in outq:
                #! dq.put(msg)
                q_in(env.now, name, dq, data=msg)
        else:
            #! outq.put(msg)
            q_in(env.now, name, outq, data=msg)

def monitorQ(env, dataq, delay=cfg['monitor_interval']):
    log = mon.file if mon else sys.stdout
    while True:
        yield env.timeout(delay)
        feed_graphite('dataq.%s'%dataq.name, len(dataq.items), env.now) 
        print('# %04d [%s]: %s %d ITEMS:'% (env.now,
                                           'monitorQ',
                                           dataq.name,
                                           len(dataq.items)),
              dataq.items
          )
        print('%4d %10s %3d'%(env.now,dataq.name,len(dataq.items)), file=log)
        
def setup(env):
    random.seed(42) # make it reproducible?

    q1235 = Dataq(env,'q1235')
    q1335 = Dataq(env,'q1335')
    q1435 = Dataq(env,'q1435')
    q1535 = Dataq(env,'q1535')
    q1735 = Dataq(env,'q1735')
    q8335 = Dataq(env,'q8335')
    q8336 = Dataq(env,'q8336')
    archive = Dataq(env,'archive')
    nsa = Dataq(env,'NSA')
    env.process( monitorQ(env, q1235) )
    env.process( monitorQ(env, nsa) )
    env.process( monitorQ(env, archive) )


    env.process(camera(env, 'DECam', q1235))
    env.process(camera(env, 'KPCam', q1235))

    # Simulate pop from In-Queue, do action, push to Out-Queue
    #                             ACTION      IN-Q   OUT-Q 
    env.process( dataAction(env, 'iclient',   q1235, q1335) )
    env.process( dataAction(env, 'ibundle',   q1335, q1435) )
    #! env.process( dataAction(env, 'iunbundle', q1435, archive) )
    env.process( dataAction(env, 'iunbundle', q1435, q1735) )
    #! env.process( dataAction(env, 'iclient',   q1735, [q8335,q1535]) )
    env.process( dataAction(env, 'iclient',   q1735, q8335) )
    #!env.process( dataAction(env, 'submit',    q8335, [q8336, nsa]) )
    env.process( dataAction(env, 'submit',    q8335, archive) )
    env.process( dataAction(env, 'resubmit',  q8336, q8335) )


    return archive

def simulate():
    env = simpy.Environment()

    archive = setup(env)
    env.run(until=400)
    print_stats('Simulation done. ARCHIVE:',archive)            

    

##############################################################################

def main():
    global mon
    #!print('EXECUTING: %s\n\n' % (string.join(sys.argv)))
    parser = argparse.ArgumentParser(
        description='My shiny new python program',
        epilog='EXAMPLE: %(prog)s a b"'
        )
    parser.add_argument('--version', action='version',  version='1.0.1')
    #!parser.add_argument('infile', type=argparse.FileType('r'),
    #!                    help='Input file')
    parser.add_argument('monitor', type=argparse.FileType('w'),
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

    mon = Monitor(args.monitor)
    simulate()
    mon.close()

if __name__ == '__main__':
    main()

        
