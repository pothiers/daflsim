#! /usr/bin/env python3
'''\
Simulate data-flow from instruments to NSA (archive) .
'''

'''Resources we might simulate usage for:
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

> !!! For decam images there's a .hdr file generated on dtsct1 that flows
> independently (dci) from the complete file (dts) but they both have to
> have arrived on dsas3 or dsan3 before they can be ingested.
** Ok. I need to modify for that.  Simpy supports "all-of" and
   "any-of" so I don't anticipate trouble - just some more work.

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
import cron

from pprint import pprint
import networkx as nx

cfg = defaultCfg.cfg
monitor = None # !!!

def stepTraceFunc(event):
    import inspect
    if isinstance(event,simpy.Process):
        xtra = 'Waiting for %s'%(event.target,)
        generatorName = event._generator.__name__
        #!generatorSignature = inspect.signature(event._generator)
        geninfo = inspect.getgeneratorstate(event._generator)
        print('TRACE %s: event.Process: gen=%s(locals=%s) (value=%s) %s'  
              % (event.env.now, generatorName, geninfo, event.value, xtra))


def print_summary(env, G, summarizeNodes=[]):
    print('#'*55)
    print('Simulation done at time: %d.'%(env.now))
    print('Next event starts at: %s'%(env.peek()))

    # print profile if we collected data
    if G.graph.get('profileCollected',False):
        qmap = dict() # qmap[name] = Dataq
        #!for dq in Dataq.instances:
        for n,d in G.nodes_iter(data=True):
            if ('sim' in d) and isinstance(d['sim'],Dataq):
                instance = d['sim']
                if not hasattr(instance,'putcount'):
                    setattr(instance,'putcount',0)
                if not hasattr(instance,'hiwater'):
                    setattr(instance,'hiwater',0)

                qmap[d['sim'].name] = d['sim']

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

        siList = simpy.Store.instances
        siList.sort(key=lambda x: x.edge)
        if len(siList) > 0:
            print('Store use summary (%d):'%len(siList))
            for si in siList:
                print('\t Edge %s: putcount=%d'
                      %(si.edge,
                        getattr(si, 'putcount',-1)
                    ))

    
    for nid in summarizeNodes:
        dq = G.node[nid]['sim']
        #!print('%d of %s get slots are allocated.' 
        #!      % (len(dq.get_queue),dq.capacity))
        #!
        #!print('%d of %s put slots are allocated.' 
        #!      % (len(dq.put_queue),dq.capacity))

        #print('NSA contains %d items'% (dq.level))
        print('\nSummary of node "%s":'%nid)
        print('  Queued %d total items' % (len(dq.items),))
        #!print('  Queued %d total items:\n\t%s'
        #!      % (len(dq.items),
        #!         '\n\t'.join(sorted(dq.items))))
        print('  Contains %d unique items:' 
              % (len(set(dq.items))))
        print('\n\t%s'%(', '.join(sorted(set(dq.items)))))




# Example plaintext feed to Graphite:
#   <metric path> <metric value> <metric timestamp>.
#   echo "local.random.diceroll 4 `date +%s`" | nc -q0 ${SERVER} ${PORT}
#   
#   timestamp:: Unix epoch (seconds since 1970-01-01 00:00:00 UTC)
#   value:: float
def feed_graphite(path, value, timestamp):
    if not monitor:
        return
    log = monitor.file 
    print('%s %s %d' % (path, value, timestamp), file=log)

class Monitor():
    def __init__(self, outfile):
        self.file = outfile
        
    def close(self):
        if self.file:
            self.file.close()

class Dataq(simpy.Store):
    '''Data Queue.'''
    instances = list()
    def __init__(self, env, name,  capacity=float('inf')):
        logging.debug('Creating dataq: %s'%name)
        self.env = env
        self.name = name
        self.simType = 'q'
        super().__init__(env,capacity=capacity)
        Dataq.instances.append(self)


    
class DciInstrument():
    '''Generates data records, such as pictures. '''

    def __init__(self, env, name, host, cpu, count=5):
        global cfg
        self.env = env
        self.name = name
        self.host = host
        self.cpu = cpu
        self.count = count
        self.simType = 's'

        self. start_delay = cfg['image_delay']

        logging.debug('[DciInstrument] Initializing (%s)'%(self.name,))

    def generateData(self, out_pipes):
        '''Generates data records such as pictures, but could be any instrument 
        in the telescope. '''
        name = self.name
        logging.debug('Starting "%s" INSTRUMENT to generate %d files.'
                      %(name,self.count))
        for cid in range(self.count):
            yield self.env.timeout(self.start_delay)
            msg = '%s.%s.%03d.png' % (self.host,self.name, cid)
            for out_pipe in out_pipes:
                out_pipe.put(msg)
            logging.info('# t=%04d [%s]: Generated data: %s'
                  %(self.env.now, self.name, msg))

class DciAction():
    def __init__(self, env, action, cpu, nid, G):
        global cfg
        self.env = env
        self.action = action
        self.cpu = cpu
        #!self.name = self.action.__name__
        self.simType = 'a'
        self.nid = nid
        self.start_delay = cfg['action_delay'] #  use CRON data!!!
        #!print('DBG-1',G.node[nid])
        self. cronStr = G.node[nid]['cron'] if 'cron' in G.node[nid] else '* *'



    def generateAction(self, in_pipes, out_pipes):
        logging.debug('Starting action generator for "%s"'
                      %(self.nid))

        if len(in_pipes) > 1:
            logging.warning(
                'More than 1 input to node "%s". Getting msg from all.'
                %(self.nid))


        while True:
            next_time = cron.next_time(self.env.now,self.cronStr)
            #!print('DBG-1: (now=%s) generate next data for node=%s at %s (%s)'
            #!      %(self.env.now, self.nid, next_time, self.cronStr))
            yield self.env.timeout(next_time)

            # Get event for message pipe
            msgList = []
            for in_pipe in in_pipes:
                logging.debug('Action (%s) get from %s'%(self.nid,in_pipe))
                res = yield in_pipe.get()
                m = res[0] if isinstance(res,tuple) else res
                msgList.append(m)
            msg = ','.join(msgList)
                
            logging.debug('[t:%d] DELAY action "%s" for %d seconds'
                          %(self.env.now,  self.nid, self.start_delay))
            yield self.env.timeout(self.start_delay)
            result = self.action(msg)
            logging.debug('[t:%d] END action "%s"; msg="%s", result="%s"'
                          %(self.env.now, self.nid, msg, result))
            for out_pipe in out_pipes:
                out_pipe.put(result)



def monitorQ(env, dataq, delay=1):
    if not monitor:
        return
    log = monitor.file
    while True:
        yield env.timeout(delay)
        feed_graphite('dataq.%s'%dataq.name, len(dataq.items), env.now) 


def printGraphSummary(G):
    logging.info('Graph summary:')
    logging.info(nx.info(G))

    nodeTypeCnt = defaultdict(int) # diag!!!
    for n,d in G.nodes_iter(data=True):
        ntype = d.get('type')
        nodeTypeCnt[ntype] += 1 # diag!!!
        in_pipes = [d0['pipe']
                    for u,v,d0 in G.in_edges(n,data=True)
                    if ('pipe' in d0)]
        out_pipes = [d1['pipe'] 
                     for u,v,d1 in G.out_edges(n,data=True)
                     if ('pipe' in d1) ]
        logging.info('Node %8s: num in,out-pipes=(%d,%d)'
                     %(n,len(in_pipes),len(out_pipes)))

    edgeTypeCnt = defaultdict(int) # diag!!!
    for u,v,d in G.edges_iter(data=True):
        etype = G.node[u]['type'] + G.node[v]['type']
        edgeTypeCnt[etype] += 1 # diag!!!

    logging.info('nodeTypeCnt: %s' 
          % ', '.join(['%s=%d'%(k,v) for (k,v) in nodeTypeCnt.items()]))

    logging.info('edgeTypeCnt: %s' 
          % ', '.join(['%s=%d'%(k,v) for (k,v) in edgeTypeCnt.items()]))


def setupDataflowNetwork(env, dotfile, draw=False, profile=False):
    random.seed(42) # make it reproducible?
    nqLUT = dict() # nqLUT[node] = Dataq instance
    nsLUT = dict() # nsLUT[node] = Source event
    createdProcesses = 0

    nodeLUT = dict() # nodeLUT[node] = simInstance

    G = literate.loadDataflow(dotfile,'sdm-data-flow.graphml')
    if draw:
        print('Displaying dataflow graph')
        fig = literate.drawDfGraph(G)
    #! print('Content of loaded graph:')
    #! pprint(G.nodes(data=True))

    ##
    ## Stuff sim instances into graph NODES
    ##
    cpuLUT = dict() # cpuLUT[hostname] = resource
    noNodeSimCnt = defaultdict(int) # dict[ntype] = count
    for n,d in G.nodes_iter(data=True):
        cpu = cpuLUT.setdefault(d['host'], simpy.Resource(env))
        ntype = d.get('type')

        # Map node types to Simpy instances (not exhaustive)
        if ntype == 's':
            d['sim'] = DciInstrument(env,d['source'],d['host'], cpu) #!!!
        elif ntype == 'q':
            d['sim'] = Dataq(env,'%s.%s'%(d['host'],n))
        elif ntype == 'a':
            if hasattr(actions,d['action']):
                func = eval('actions.'+d['action']) 
            else:
                func = functools.partial(actions.nop,name=d['action'])
            d['sim'] = DciAction(env, func, cpu, n, G)
        elif ntype == 't':
            #!d['sim'] = simpy.Container(env)
            d['sim'] = Dataq(env,'%s.%s'%(d['host'],n))
        else:
            noNodeSimCnt[ntype] += 1

    #!if len(noNodeSimCnt) > 0:
    #!    print('WARNING: No simulation for some nodes.  (type=count): %s'
    #!          %(', '.join(['%s=%d'%(k,v) for k,v in noNodeSimCnt.items()])))
    
    if profile:
        addProfiling(G)

    ##
    ## Stuff sim instances into graph EDGES
    ##
    # Create "link" elements of simulation based upon type of edge
    # Edge type is ordered character pair of black/white node type.
    for u,v,d in G.edges_iter(data=True):
        ud = G.node[u]	
        vd = G.node[v]	
        etype = ud['type'] + vd['type']
        
        # Map edge types to Simpy "connection instances" (not exhaustive)
        noEdgeSimCnt = defaultdict(int) # dict[ntype] = count
        if etype == 'sa':
            d['pipe'] = simpy.Store(env,capacity=1)
            if not hasattr(simpy.Store,'instances'):
                simpy.Store.instances = []
            simpy.Store.instances.append(d['pipe'])
            d['pipe'].edge=(u,v)
        elif etype == 'aa':
            d['pipe'] = simpy.Store(env,capacity=1)
            if not hasattr(simpy.Store,'instances'):
                simpy.Store.instances = []
            simpy.Store.instances.append(d['pipe'])
            d['pipe'].edge=(u,v)
        elif etype == 'qa':
            d['pipe'] = ud['sim']
        elif etype == 'at':
            d['pipe'] = vd['sim']
        elif etype == 'aq':
            d['pipe'] = vd['sim']
        elif etype == 'sq':
            d['pipe'] = vd['sim']
        else:
            noEdgeSimCnt[etype] += 1

    #!if len(noEdgeSimCnt) > 0:
    #!    print('WARNING: No simulation for some edges.  (type=count): %s'
    #!          %(', '.join(['%s=%d'%(k,v) for k,v in noEdgeSimCnt.items()])))
        
            
    
    ##
    ## Create simulation processes
    ##
    for n,d in G.nodes_iter(data=True):
        cpu = cpuLUT.setdefault(d['host'], simpy.Resource(env))

        if d.get('type') == 's':
            out_pipes = [d1['pipe'] 
                         for u,v,d1 in G.out_edges(n,data=True)
                         if ('pipe' in d1) ]

            env.process(d['sim'].generateData(out_pipes))
            createdProcesses += 1
            logging.info('Create DATA generator for %s. Out=%s'
                  %(n,out_pipes))

        elif d.get('type') == 'q':
            if monitor:
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
            logging.info('Create ACTION generator for %s. in=%s out=%s'
                  %(n,
                    [r.__class__.__name__ for r in in_pipes], 
                    [r.__class__.__name__ for r in out_pipes]))
            createdProcesses += 1
        elif d.get('type') == 't':
            pass
        elif d.get('type') == 'd':
            pass
        else:
            print('WARNING!!! Unexpected node type: "%s"'%(d.get('type')))

    logging.info('Created %d processes'%(createdProcesses,))
    #!print('Content of sim annotated graph:')
    #!print('  NODES:')
    #!pprint(G.nodes(data=True))
    #!print('  EDGES:')
    #!pprint(G.edges(data=True))

    logging.debug('%d processes started'%(createdProcesses))
    logging.debug('Next event starts at: %s'%(env.peek()))
    
    return G
    # END setupDataflowNetwork()


    
def addProfiling(G):
    simpy.Container.instances = list()
    Dataq.instances = list()
    

    # Monkey patch PUT to count messages
    if not hasattr(Dataq,'monkey'):
        origDataqPut = Dataq.put
        def putDataqWithCount(self,data):
            instance = self
            setattr(instance,'putcount', 1 + getattr(instance,'putcount',0))
            res = origDataqPut(self,data)
            instance.hiwater = max(getattr(instance,'hiwater',0),
                                   len(instance.items))
            return res
        Dataq.put = putDataqWithCount
        setattr(Dataq,'monkey',True)

    if not hasattr(simpy.Store,'monkey'):
        origStorePut = simpy.Store.put
        def putStoreWithCount(self,data):
            instance = self
            setattr(instance,'putcount', 1 + getattr(instance,'putcount',0))
            logging.debug('Set simpy.Store %s pcount=%d'
                          %(instance, getattr(instance,'putcount',-1)))
            return origStorePut(self,data)
        simpy.Store.put = putStoreWithCount
        setattr(simpy.Store,'monkey',True)


    for n,d in G.nodes_iter(data=True):
        if 'sim' not in d:
            continue

        si = d['sim']
        if isinstance(si,DciAction):
            pass
        elif isinstance(si,Dataq):
            Dataq.instances.append(si)
        elif isinstance(si, simpy.Store):
            simpy.Store.instances.append(si)
        elif isinstance(si,DciInstrument):
            pass
    #!print('Dataq.instances = ',Dataq.instances)

    G.graph['profileCollected'] = True
    # END addProfiling



##############################################################################

def main():
    global monitor
    global cfg
    default_end = 1e3
    #!print('EXECUTING: %s\n\n' % (string.join(sys.argv)))
    parser = argparse.ArgumentParser(
        description='My shiny new python program',
        epilog='EXAMPLE: %(prog)s a b"'
        )
    parser.add_argument('--version', action='version',  version='1.1.0')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--end', 
                        help='Time (seconds) to end simulation [default=%s]'
                        %(default_end),
                        type = int,
                        default = default_end,)
    parser.add_argument('--summarize', 
                        default=[],                        
                        action='append')
    parser.add_argument('--cfg', 
                        help='Configuration file',
                        type=argparse.FileType('r') )
    parser.add_argument('infile', type=argparse.FileType('r'),
                        help='Graphviz (dot) file. Spec for dataflow network.')
    parser.add_argument('--graphite', type=argparse.FileType('w'),
                        help='Output for GRAPHITE plotter'
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

    if args.cfg:
        cfg = json.load(args.cfg)
    
    if args.graphite:
        monitor = Monitor(args.graphite)

    env = simpy.Environment()
    G = setupDataflowNetwork(env, args.infile, profile=args.profile)
    
    if args.loglevel == 'DEBUG':
        printGraphSummary(G)


    env.run(until=args.end)
    print_summary(env,G, summarizeNodes=args.summarize)

    if args.graphite:
        monitor.close()

if __name__ == '__main__':
    main()

        
