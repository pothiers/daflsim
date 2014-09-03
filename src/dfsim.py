#! /usr/bin/env python
## @package pyexample
#  Documentation for this module. (for DOXYGEN)
#
#  More details.

'''\
Simulate data-flow from instruments to NSA (archive) .
'''

'''
Resources we might simulate usage for:
- CPU cycles
- RAM 
- disk space
- network bandwidth

Simulate modules on significant machines from all 5 sites:
  - KP 
  - TU 
  - CT
  - CP
  - LS
'''

import sys
import string
import argparse
import logging
import simpy
import random

import actions 

cfg = dict(
    queue_capacity   = 40, # max number of records in queue
    monitor_interval = 1, # seconds between checking queue
    cron = dict(
        # host_action_readPort = 'minute hour' ;first two fields in crontab
        # dtskp
        iclient_1235 = '35 *', 
        ibundle_1335 = '0 *',

        # dtstuc
        iclient_6135 = '35 *',  # guessed !!!
        ibundle_6235 = '0 *',   # guessed !!!
        
        # dsan3
        iunbundle_1435 = '*/10 *',
        iunbundle_2635 = '*/10 *',
        iunbundle_6435 = '*/5 *',
        iclient_1735   = '*/6 *',
        iclient_1934   = '* *',
        iclient_9435   = '*/5 *',
        ibundle_1535   = '*/10 *',
        submit_to_archive2_8335    = '*/2 *',
        resubmit_8336  = '0 10',  # 0 10 * * *
        
        # dsas3
        iunbundle_1635 = '*/10 *',
        iunbundle_3435 = '*/10 *',
        iunbundle_2435 = '*/10 *',
        iclient_9635   = '*/5 *',        
        )
)

monitor = None # !!!

# Minutes since start of hour
def minutesThisHour(nowSeconds):
    return(int((nowSeconds/60) % 60))

# Hours since start of day
def hoursThisDay(nowSeconds):
    return(int((nowSeconds/60) % (60*24)/60))

    
# Return number of seconds until a cron job using the spec containing 
# "<minute> <hour> * * *" would fire.
# APPROXIMATE: Only implements pieces of cron date/time matching we need.
def next_cron(nowSeconds, cronstr):
    '''
    nowSeconds:: seconds since start of simulation
    cronstr:: "minute hour"; either can be N or "*" or "*/<step>"
    '''
    def parseStep(str):
        n,*stepList = str.split('/')
        return(0 if (n == '*') else int(n),
               1 if (0 == len(stepList)) else int(stepList[0]))
    def remTime(nowTime, times, timeStep):
        if times == 0:
            # for "*/5 *"
            return(timeStep - (nowTime + times) % timeStep)
        else:
            # for "35 *"
            return(times - (nowTime % times))


        
    minute,hour = cronstr.split()

    nowMinutes = minutesThisHour(nowSeconds)
    minutes,minuteStep = parseStep(minute)
    delayMinutes = remTime(nowMinutes, minutes, minuteStep)

    nowHours = hoursThisDay(nowSeconds)
    hours,hourStep = parseStep(hour)
    delayHours = remTime(nowHours, hours, hourStep)

    return delayMinutes*60+ delayHours*60*60
    

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
    log = monitor.file if monitor else sys.stdout
    print('%s %s %d' % (path, value, timestamp), file=log)

class Monitor():
    def __init__(self, outfile):
        self.file = outfile
        
    def close(self):
        self.file.close()

def q_in(when, src, q, data=None):
    q.put(data or 'NA')
    #feed_graphite('dataq.%s'%q.name, len(q.items), when)          
    print('# %s -> %s'%(src, q.name))

# BROKEN; returns generator object instead of msg value
def q_out(when, dest, q):
    msg = yield q.get()
    print('# %s -> %s'%(q.name, dest))
    #feed_graphite('dataq.%s'%q.name, len(q.items), when)          
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
def dataAction(env, action, inq, outq):
    name = action.__name__
    inport = inq.name[-4:] #!!! Bad to count on naming scheme!
    while True:
        start_delay = next_cron(env.now,cfg['cron']['%s_%s'%(name,inport)])
        yield env.timeout(start_delay)
        print('start_delay=',start_delay)

        msg = yield inq.get()
        #! msg = q_out(env.now, name, inq)
        print('# %s -> %s'%(inq.name, name))
        #feed_graphite('dataq.%s'%inq.name, len(inq.items), env.now)          

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
    log = monitor.file if monitor else sys.stdout
    while True:
        yield env.timeout(delay)
        feed_graphite('dataq.%s'%dataq.name, len(dataq.items), env.now) 
        logging.debug('# %04d [%s]: %s %d ITEMS:'% (env.now,
                                                    'monitorQ',
                                                    dataq.name,
                                                    len(dataq.items)),
                      dataq.items
                  )
        
def setup(env):
    random.seed(42) # make it reproducible?

    q1235 = Dataq(env,'dtskp.q1235')
    q1335 = Dataq(env,'dtskp.q1335')
    q1435 = Dataq(env,'dtskp.q1435')

    q6135 = Dataq(env,'dtstuc.q6135')
    q6235 = Dataq(env,'dtstuc.q6235')
    q6435 = Dataq(env,'dtstuc.q6435')

    q1535 = Dataq(env,'dsan3.q1535')
    q1735 = Dataq(env,'dsan3.q1735')
    q8335 = Dataq(env,'dsan3.q8335')
    q8336 = Dataq(env,'dsan3.q8336')
    q9435 = Dataq(env,'dsan3.q9435')
    nsa   = Dataq(env,'dsan3.NSA')

    q1635 = Dataq(env,'dsas3.q1635')
    q2435 = Dataq(env,'dsas3.q2435')
    q2535 = Dataq(env,'dsas3.q2535')
    q2635 = Dataq(env,'dsas3.q2635')
    q2735 = Dataq(env,'dsas3.q2735')
    q3435 = Dataq(env,'dsas3.q3435')
    q9635 = Dataq(env,'dsas3.q9635')

    unk3 = Dataq(env,'dsas3.UNKNOWN')

    for q in [q1235, q1335, q1435, q6135, q6235, q6435, 
              q1535, q1735, q8335, q8336, q8336, nsa,
              q2535, q2635, q2735, q3435, q9635,]:
        env.process( monitorQ(env, q) )

    env.process(camera(env, 'DECam', q1235))
    env.process(camera(env, 'KPCam', q1235))
    env.process(camera(env, 'pipeline?', q6135))

    

    # Simulate pop from In-Queue, do action, push to Out-Queue
    #                            ACTION                      IN-Q   OUT-Q 
    env.process( dataAction(env, actions.iclient,            q1235, q1335) )
    env.process( dataAction(env, actions.ibundle,            q1335, q1435) )
    env.process( dataAction(env, actions.iunbundle,          q1435, q1735) )
    env.process( dataAction(env, actions.iclient,            q1735, [q8335,q1535]) )
    env.process( dataAction(env, actions.submit_to_archive2, q8335, [q8336, nsa]) )
    #! env.process( dataAction(env, actions.resubmit,        q8336, q8335) )
    env.process( dataAction(env, actions.ibundle,            q1535, q1635) )
    env.process( dataAction(env, actions.iunbundle,          q1635, q9635) )
    env.process( dataAction(env, actions.iclient,            q9635, unk3) )
                                                             
    env.process( dataAction(env, actions.iclient,            q6135, q6235) )    
    env.process( dataAction(env, actions.ibundle,            q6235, q6435) )    
    env.process( dataAction(env, actions.iunbundle,          q6435, q1735) )

    return nsa

def simulate():
    env = simpy.Environment()
    archive = setup(env)
    #!env.run(until=400)
    env.run(until=1e5)
    print_stats('Simulation done. NSA (archive):',archive)            

    

##############################################################################

def main():
    global monitor
    #!print('EXECUTING: %s\n\n' % (string.join(sys.argv)))
    parser = argparse.ArgumentParser(
        description='My shiny new python program',
        epilog='EXAMPLE: %(prog)s a b"'
        )
    parser.add_argument('--version', action='version',  version='1.1.0')
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

    monitor = Monitor(args.monitor)
    simulate()
    monitor.close()

if __name__ == '__main__':
    main()

        
