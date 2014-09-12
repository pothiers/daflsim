#! /usr/bin/env python3
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
import literate

from pprint import pprint


cfg = dict( # MOVE TO DOTFILE!!!
    queue_capacity   = 40, # max number of records in queue
    monitor_interval = 5, # seconds between checking queue
    cron = dict(
        # action_inport
        stb_none      = '* *',
        unbundle_none = '* *',

        # host_action_readPort = 'minute hour' ;first two fields in crontab
        # dtskp
        client_1235 = '35 *', 
        bundle_1335 = '0 *',

        # dtstuc
        client_6135 = '35 *',  # guessed CRON !!!
        bundle_6235 = '0 *',   # guessed CRON !!!
        
        # dsan3
        unbundle_1435 = '*/10 *',
        unbundle_2635 = '*/10 *',
        unbundle_6435 = '*/5 *',
        client_1735   = '*/6 *',
        client_1934   = '* *',
        client_9435   = '*/5 *',
        bundle_1535   = '*/10 *',
        submit_to_archive2_8335    = '*/2 *',
        resubmit_8336  = '0 10',  # 0 10 * * *
        
        # dsas3
        unbundle_1635 = '*/10 *',
        unbundle_3435 = '*/10 *',
        unbundle_2435 = '*/10 *',
        client_9635   = '*/5 *',        
        client_2735   = '*/5 *',   # guessed CRON !!!
        bundle_2535   = '*/5 *',   # guessed CRON !!!

        # dtsct
        bundle_2335   = '*/5 *',   # guessed CRON !!!
        client_2135   = '*/5 *',   # guessed CRON !!!
        # dtscp
        bundle_3335   = '*/5 *',   # guessed CRON !!!
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
    

def print_summary(env):
    global q_list
    print('#'*55)
    print('Simulation done.')

    qmap = dict() # qmap[name] = Dataq
    for dq in q_list:
        qmap[dq.name] = dq
        
    print('Max size of queues during sim:')
    for name in sorted(qmap.keys()):
        print('  %15s: %d\t%s'
              %(name,
                qmap[name].hiwater,
                'WARNING: unused' if qmap[name].hiwater == 0 else ''
            ))
    print()
        

    archive = qmap['dsan3.NSA']
    print('%d of %d get slots are allocated.' 
          % (len(archive.get_queue),archive.capacity))

    print('%d of %d put slots are allocated.' 
          % (len(archive.put_queue),archive.capacity))

    print('Queued %d ITEMS:'% len(archive.items), sorted(archive.items))



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
    logging.debug('Starting "%s" CAMERA to generate %d pictures. Send to %s'
                  %(name,shots,dataq.name))
    for cid in range(shots):
        yield env.timeout(random.randint(1,7))
        msg = '%s.id%d.png' % (name, cid)
        q_in(env.now, name, dataq, data=msg)
        print('# %04d [%s]: Generated data: %s' %(env.now, name, msg))

# data PRODUCER  (generator)
def instrument(env, name, count=5):
    '''Generates data records such as pictures, but could be any instrument 
in the telescope. '''
    logging.debug('Starting "%s" INSTRUMENT to generate %d files.'
                  %(name,count))
    for cid in range(count):
        yield env.timeout(random.randint(1,7))
        msg = '%s.id%d.png' % (name, cid)
        print('# %04d [%s]: Generated data: %s' %(env.now, name, msg))
        return msg


q_list = list()
class Dataq(simpy.Store):
    '''Data Queue.'''
    global q_list
    def __init__(self, env, name, capacity=cfg['queue_capacity']):
        logging.debug('Creating dataq: %s'%name)
        self.env = env
        self.name = name
        self.hiwater = 0
        super().__init__(env,capacity=capacity)
        q_list.append(self)
    
# CONSUMER, PRODUCER
def dataAction(env, action, inp, outqList):
    name = action.__name__
    if isinstance(inp,Dataq):
        inport = inp.name[-4:]  #!!! Bad to count on naming scheme!
    else:
        inport = inp
    logging.debug('[dataAction] outqList=%s'%(outqList))
    logging.debug('[dataAction] Starting (%s) connecting %s to %s'
                  %(name, inport,','.join([q.name for q in outqList])))
    while True:
        #! start_delay = next_cron(env.now,cfg['cron']['%s_%s'%(name,inport)])
        start_delay = 5 #!!! speed things up
        logging.debug('[dataAction] delay %s seconds; %s %s'%(start_delay, env.now, name))
        yield env.timeout(start_delay)
        logging.debug('[dataAction] DONE delay')
        msg = 'NA'
        if isinstance(inp,Dataq):
            logging.debug('[dataAction] inq.get()')
            msg = yield inp.get()
            logging.debug('[dataAction] DONE inp.get()')
            print('# %s -> %s'%(inp.name, name))

        print('# %04d [%s]: Do action using record: %s' %(env.now, name, msg))
        #!yield env.timeout(random.randint(5,20))
        logging.debug('START %s'%(name))
        action(msg)
        logging.debug('END %s'%(name))
        for outq in outqList:
            q_in(env.now, name, outq, data=msg)
            logging.debug('%s submitted message to %s'%(name,outq.name))

def monitorQ(env, dataq, delay=cfg['monitor_interval']):
    log = monitor.file if monitor else sys.stdout
    while True:
        yield env.timeout(delay)
        dataq.hiwater = max(dataq.hiwater,len(dataq.items))
        feed_graphite('dataq.%s'%dataq.name, len(dataq.items), env.now) 
        logging.debug('# %04d [%s]: %s %d ITEMS'% (env.now,
                                                    'monitorQ',
                                                    dataq.name,
                                                    len(dataq.items))
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
    #                            ACTION               IN-Q   OUT-Q 
    env.process( dataAction(env, actions.client,     q1235, [q1335]) )
    env.process( dataAction(env, actions.bundle,     q1335, [q1435]) )
    env.process( dataAction(env, actions.unbundle,   q1435, [q1735]) )
    env.process( dataAction(env, actions.client,     q1735, [q8335,q1535]) )
    env.process( dataAction(env, actions.submit_to_archive2,
                                                      q8335, [q8336, nsa]) )
    #! env.process( dataAction(env, actions.resubmit, q8336, [q8335]) )
    env.process( dataAction(env, actions.bundle,     q1535, [q1635]) )
    env.process( dataAction(env, actions.unbundle,   q1635, [q9635]) )
    env.process( dataAction(env, actions.client,     q9635, [unk3]) )
                                                             
    env.process( dataAction(env, actions.client,     q6135, [q6235]) )    
    env.process( dataAction(env, actions.bundle,     q6235, [q6435]) )    
    env.process( dataAction(env, actions.unbundle,   q6435, [q1735]) )

    return nsa

# return target node
def downstreamMatch(G, startNode, targetNodeType, maxHop=4):
    if maxHop == 0:
        return(None)
    if G.node[startNode].get('type') == targetNodeType:
        return(startNode)
    else:
        for n in G.successors(startNode):
            return(downstreamMatch(G, n, targetNodeType, maxHop=maxHop-1))
            
def setupDataflowNetwork(env, dotfile):
    random.seed(42) # make it reproducible?
    nqLUT = dict() # nqLUT[node] = Dataq instance
    nsLUT = dict() # nsLUT[node] = Source event
    activeProcesses = 0

    G = literate.loadDataflow(dotfile,'sdm-data-flow.graphml')
    pprint(G.nodes(data=True))

    for n,d in G.nodes(data=True):
        if d.get('type') == 'q':
            host = 'dtskp' # STUB!!!
            q = Dataq(env,'%s.%s'%(host,n))
            nqLUT[n] = q
            activeProcesses += 1
            env.process( monitorQ(env, q) )
    for n,d in G.nodes(data=True):
        if d.get('type') == 's':
            prefix='DECam'
            qnode = downstreamMatch(G, n, 'q')
            activeProcesses += 1
            inst = instrument(env, prefix)
            nsLUT[n] = env.process(inst)
            
    for n,d in G.nodes(data=True):
        if d.get('type') == 'a':
            activeProcesses += 1
            func = eval('actions.'+d.get('action'))
            preds = [p for p in G.predecessors(n)
                     if ((G.node[p]['type'] == 'q') 
                         or (G.node[p]['type'] == 's') )]
            if len(preds) == 0:
                return None
            elif len([p for p in preds if G.node[p]['type'] == 'q']) > 1:
                raise RuntimeError(
                    'Action can only be connected to one queue. Got %d (%s)'%
                    (len(preds),n))
            else:
                if preds[0] in nqLUT:
                    inp = nqLUT[preds[0]]
                elif preds[0] in nsLUT:
                    inp = nsLUT[preds[0]]
                else:
                    raise RuntimeError(
                        'ACTION input must be a QUEUE. Got "%s" (node: "%s")'%
                        (G.node[preds[0]]['type'],preds[0]))

            action_event = env.process(
                dataAction(env, 
                           func, 
                           inp,
                           [nqLUT[sn] for sn in G.successors(n)
                            if (sn in nqLUT)]
                       ))
            if not isinstance(inp,Dataq):
                inp.callbacks.append(inp.trigger(action_event))

                                 
        if d.get('type') == 't':
            pass #!!!
        if d.get('type') == 'd':
            pass #!!!
    
    logging.debug('%d processes started'%(activeProcesses))
    logging.debug('Next event starts at: %s'%(env.peek()))
    return None # nsa

def simulate0():
    env = simpy.Environment()
    setup(env)

    print('event schedule queue = ',)
    pprint(env._queue)

    #!env.run(until=400)
    env.run(until=1e5)
    print_summary(env)

def simulate(dotfile):
    env = simpy.Environment()
    setupDataflowNetwork(env, dotfile)
    #!env.run(until=400)
    env.run(until=1e5)
    print_summary(env)

    

##############################################################################

def main():
    global monitor
    #!print('EXECUTING: %s\n\n' % (string.join(sys.argv)))
    parser = argparse.ArgumentParser(
        description='My shiny new python program',
        epilog='EXAMPLE: %(prog)s a b"'
        )
    parser.add_argument('--version', action='version',  version='1.1.0')
    parser.add_argument('infile', type=argparse.FileType('r'),
                        help='Graphviz (dot) file. Spec for dataflow network.')
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
    simulate(infile)
    monitor.close()

if __name__ == '__main__':
    main()

        
