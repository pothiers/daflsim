#! /usr/bin/env python3
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
from enum import Enum
import random
from collections import defaultdict
import functools
import json

import simpy

import actions 
import literate
import defaultCfg

from pprint import pprint
import networkx as nx


def stepTraceFunc(event):
    import inspect
    if isinstance(event,simpy.Process):
        xtra = 'Waiting for %s'%(event.target,)
        generatorName = event._generator.__name__
        #!generatorSignature = inspect.signature(event._generator)
        geninfo = inspect.getgeneratorstate(event._generator)
        print('TRACE %s: event.Process: gen=%s(locals=%s) (value=%s) %s'  
              % (event.env.now, generatorName, geninfo, event.value, xtra))


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
    

def print_summary(env, G):
    print('#'*55)
    print('Simulation done.')

    if hasattr(Dataq,'putcount'):
        qmap = dict() # qmap[name] = Dataq
        for dq in Dataq.instances:
            qmap[dq.name] = dq

        print('Dataq use summary:')
        print('  %15s  %5s %5s %s'%('Queue', 'Put',   'Max',  ''))
        print('  %15s  %5s %5s %s'%('Name' , 'Count', 'Used', 'Comment'))
        for name in sorted(qmap.keys()):
            print('  %15s: %5d %5d %s'
                  %(name,
                    qmap[name].putcount,
                    qmap[name].hiwater,
                    'WARNING: unused' if qmap[name].hiwater == 0 else ''
                ))
        print()
        

    archive = G.node['NSA']['sim']
    print('%d of %s get slots are allocated.' 
          % (len(archive.get_queue),archive.capacity))

    print('%d of %s put slots are allocated.' 
          % (len(archive.put_queue),archive.capacity))

    print('Queued %d items in NSA:'% len(archive.items))
    pprint(sorted(archive.items))
    #print('NSA contains %d items'% (archive.level))




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

def q_in(when, src, q, data):
    q.put(data)
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
        q_in(env.now, name, dataq, msg)
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


class Dataq(simpy.Store):
    '''Data Queue.'''
    instances = list()
    def __init__(self, env, name,  capacity=float('inf')):
        logging.debug('Creating dataq: %s'%name)
        self.env = env
        self.name = name
        self.hiwater = 0
        self.simType = 'q'
        self.putcount = 0
        super().__init__(env,capacity=capacity)
        Dataq.instances.append(self)


    
class DciInstrument():
    '''Generates data records, such as pictures. '''

    def __init__(self, env, name, host, cpu, count=5 ):
        self.env = env
        self.name = name
        self.host = host
        self.cpu = cpu
        self.count = count
        self.simType = 's'

        #! start_delay = next_cron(env.now,cfg['cron']['%s_%s'%(name,inport)])
        self. start_delay = 5 #!!! speed things up

        logging.debug('[DciInstrument] Initializing (%s)'%(self.name,))

    def generateData(self, out_pipe):
        '''Generates data records such as pictures, but could be any instrument 
        in the telescope. '''
        name = self.name
        logging.debug('Starting "%s" INSTRUMENT to generate %d files.'
                      %(name,self.count))
        for cid in range(self.count):
            yield self.env.timeout(1) #!!! config
            msg = '%s.%s.%03d.png' % (self.host,self.name, cid)
            out_pipe.put(msg)
            print('# %04d [%s]: Generated data: %s'
                  %(self.env.now, self.name, msg))

class DciAction():
    def __init__(self, env, action, cpu, nid):
        self.env = env
        self.action = action
        self.cpu = cpu
        self.name = self.action.__name__
        self.simType = 'a'
        self.nid = nid

        #! start_delay = next_cron(env.now,cfg['cron']['%s_%s'%(name,inport)])
        self. start_delay = 5 #!!! speed things up
        logging.debug('[DciAction] Initializing (%s)'%(self.name,))


    def generateAction(self, in_pipes, out_pipes):
        if len(in_pipes) > 1:
            logging.warning('More than 1 input to node: %s'%n)

        while True:
            # Get event for message pipe
            msgList = []
            for in_pipe in in_pipes:
                res = yield in_pipe.get()
                m = res[0] if isinstance(res,tuple) else res
                msgList.append(m)
            print('DBG: action=%s in-msgList=%s inPipes=%s outPipes=%s'
                  %(self.nid, msgList, in_pipes, out_pipes))
            msg = ','.join(msgList)
                
            logging.debug('[dataAction] delay %s seconds; %s@%s'
                          %(self.start_delay, self.nid, self.env.now ))
            yield self.env.timeout(self.start_delay)
            result = self.action(msg)
            logging.debug('END action "%s"; msg="%s", result="%s"'
                          %(self.nid, msg, result))
            for out_pipe in out_pipes:
                out_pipe.put(result)


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
        start_delay = 1 #!!! speed things up
        logging.debug('[dataAction] delay %s seconds; %s; %s'%(start_delay, env.now, name))
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
            q_in(env.now, name, outq, msg)
            logging.debug('%s submitted message to %s'%(name,outq.name))

def monitorQ(env, dataq, delay=1):
    log = monitor.file if monitor else sys.stdout
    while True:
        yield env.timeout(delay)
        dataq.hiwater = max(dataq.hiwater,len(dataq.items))
        feed_graphite('dataq.%s'%dataq.name, len(dataq.items), env.now) 
        #!logging.debug('# %04d [monitorQ]: %s %d ITEMS'
        #!              % (env.now, dataq.name, len(dataq.items)))
        
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
            
class SimType(Enum):
    generator = 1
    resource = 2

def setupDataflowNetwork(env, dotfile, draw=False, profile=False):
    random.seed(42) # make it reproducible?
    nqLUT = dict() # nqLUT[node] = Dataq instance
    nsLUT = dict() # nsLUT[node] = Source event
    createdProcesses = 0

    nodeLUT = dict() # nodeLUT[node] = simInstance
    simTypeLUT = dict( # LUT[nodeType] = simType
        s = SimType.generator,
        q = SimType.resource,
        a = SimType.generator,
        t = SimType.resource,
        d = SimType.resource
        )


    G = literate.loadDataflow(dotfile,'sdm-data-flow.graphml')
    print(nx.info(G))
    if draw:
        print('Displaying dataflow graph')
        fig = literate.drawDfGraph(G)
    print('Content of loaded graph:')
    pprint(G.nodes(data=True))

    cpuLUT = dict() # cpuLUT[hostname] = resource
    for n,d in G.nodes_iter(data=True):
        #simType = simTypeLUT[d.get('type')]
        cpu = cpuLUT.setdefault(d['host'], simpy.Resource(env))
        ntype = d.get('type')

        # Map node types to Simpy instances (not exhaustive)
        if ntype == 's':
            d['sim'] = DciInstrument(env,'DECam',d['host'], cpu) #!!!
        elif ntype == 'q':
            d['sim'] = Dataq(env,'%s.%s'%(d['host'],n))
        elif ntype == 'a':
            d['sim'] = DciAction(env, eval('actions.'+d['action']), cpu, n)
        elif ntype == 't':
            #!d['sim'] = simpy.Container(env)
            d['sim'] = Dataq(env,'%s.%s'%(d['host'],n))
        else:
            print('WARNING: No simulation for node of type:',ntype)
    
    if profile:
        addProfiling(G)

    # Create "link" elements of simulation based upon type of edge
    # Edge type is ordered character pair of black/white node type.
    edgeTypeCnt = defaultdict(int) # diag!!!
    for u,v,d in G.edges_iter(data=True):
        ud = G.node[u]	
        vd = G.node[v]	
        etype = ud['type'] + vd['type']
        edgeTypeCnt[etype] += 1 # diag!!!
        
        # Map edge types to Simpy "connection instances" (not exhaustive)
        if etype == 'sa':
            d['pipe'] = simpy.Store(env,capacity=1)
        elif etype == 'aa':
            d['pipe'] = simpy.Store(env,capacity=1)
        elif etype == 'qa':
            d['pipe'] = ud['sim']
        elif etype == 'at':
            d['pipe'] = simpy.Store(env,capacity=1)
        elif etype == 'aq':
            d['pipe'] = vd['sim']
        elif etype == 'sq':
            d['pipe'] = vd['sim']
        else:
            print('WARNING: No simulation for edge of type:',etype)
            
    print('edgeTypeCnt=',edgeTypeCnt)
        

    for n,d in G.nodes_iter(data=True):
        simType = simTypeLUT[d.get('type')]
        cpu = cpuLUT.setdefault(d['host'], simpy.Resource(env))

        if d.get('type') == 's':
            for u,v,di in G.out_edges(n,data=True):
                if 'pipe' not in di: 
                    continue

                env.process(d['sim'].generateData(di['pipe']))
                createdProcesses += 1
                print('Create DATA generator for %s. Pipe=%s'%(n,di['pipe']))
        elif d.get('type') == 'q':
            env.process( monitorQ(env, d['sim'] ))
            createdProcesses += 1
        elif d.get('type') == 'a':
            in_pipes = [d0['pipe']
                        for u0,v0,d0 in G.in_edges(n,data=True)
                        if ('pipe' in d0)]
            out_pipes = [d1['pipe'] 
                         for u,v,d1 in G.out_edges(n,data=True)
                         if ('pipe' in d1) ]
            env.process(d['sim'].generateAction(in_pipes, out_pipes))
            print('Create ACTION generator for %s. in=%s out=%s'
                  %(n,in_pipes, out_pipes))
            createdProcesses += 1
        elif d.get('type') == 't':
            pass
        elif d.get('type') == 'd':
            pass
        else:
            print('WARNING!!! Unexpected node type: "%s"'%(d.get('type')))

    print('Created %d processes'%(createdProcesses,))
    print('Content of sim annotated graph:')
    print('  NODES:')
    pprint(G.nodes(data=True))
    print('  EDGES:')
    pprint(G.edges(data=True))

#!            preds = [p for p in G.predecessors(n)
#!                     if ((G.node[p]['type'] == 'q') 
#!                         or (G.node[p]['type'] == 's') )]
#!            if len(preds) == 0:
#!                return None
#!            elif len([p for p in preds if G.node[p]['type'] == 'q']) > 1:
#!                raise RuntimeError(
#!                  'Action can only be connected to one in queue. Got %d (%s)'%

    
    logging.debug('%d processes started'%(createdProcesses))
    logging.debug('Next event starts at: %s'%(env.peek()))
    return G
    # END setupDataflowNetwork()


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

    
def addProfiling(G):
    simpy.Container.instances = list()
    Dataq.instances = list()

    for n,d in G.nodes_iter(data=True):
        if 'sim' not in d:
            continue

        si = d['sim']
        setattr(si,'putcount', 0)
        print('DBG si=',si)

        if isinstance(si,DciAction):
            pass
        elif isinstance(si,Dataq):
            # Monkey patch PUT to count messages
            origPut = si.put
            def put(data):
                setattr(si,'putcount', 1 + getattr(si,'putcount',0))
                return origPut(data)
            si.put = put
            Dataq.instances.append(si)

        elif isinstance(si, simpy.Container):
            # Monkey patch PUT to count messages
            origPut = si.put
            def put(data):
                setattr(si,'putcount', 1 + getattr(si,'putcount',0))
                return origPut(data)
            si.put = put
            simpy.Container.instances.append(si)
        elif isinstance(si,DciInstrument):
            pass
        else:
            print('WARNING: not profiling %s; %s'%(n,d))



##############################################################################

def main():
    global monitor
    #!print('EXECUTING: %s\n\n' % (string.join(sys.argv)))
    parser = argparse.ArgumentParser(
        description='My shiny new python program',
        epilog='EXAMPLE: %(prog)s a b"'
        )
    parser.add_argument('--version', action='version',  version='1.1.0')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--cfg', 
                        help='Configuration file',
                        type=argparse.FileType('r') )
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

    cfg = defaultCfg.cfg if args.cfg is None else json.load(args.cfg)

    monitor = Monitor(args.monitor)

    #!simulate(infile)
    env = simpy.Environment()
    simpy.util.trace(env,stepTrace=stepTraceFunc)
    G = setupDataflowNetwork(env, args.infile, profile=args.profile)
    env.run(until=1e3)
    print_summary(env,G)

    monitor.close()

if __name__ == '__main__':
    main()

        
