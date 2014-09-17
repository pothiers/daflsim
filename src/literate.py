#! /usr/bin/env python
## @package pyexample
#  Documentation for this module. (for DOXYGEN)
#
#  More details.

'''\
<<Python script callable from command line.  Put description here.>>
'''

import sys
import string
import argparse
import logging

from pprint import pprint

# Graph stuff
import matplotlib.pyplot as plt
import networkx as nx

# These are GRAPHVIZ attribute names subverted for our own use!
clustProps='comment'
nodeProps='tooltip'

def onpick(event):
    thisline = event.artist
    xdata = thisline.get_xdata()
    ydata = thisline.get_ydata()
    ind = event.ind
    print('onpick points:', zip(xdata[ind], ydata[ind]))

def onmousedown(event):
    print('onmousedown event:', event)


# Map our node "type" to matplotlib marker codes
shape = dict(
    q = 's',
    a = 'o',
    s = 'v',
    t = '^',
    d = 'd'
    )

def drawDfGraph(G,figTitle='SDM Dataflow'):
    plt.ion()

    fig = plt.figure()
    pos = nx.graphviz_layout(G,prog='dot')
    for ntype in 'qastd':
        nodes = [n for n,d in G.nodes(data=True) 
                 if d.get('type') == ntype]
        nx.draw_networkx_nodes(G, pos=pos, nodelist=nodes,
                               node_shape=shape[ntype])

    nx.draw_networkx_edges(G,pos=pos)

    labels = dict([(k,v['label']) for (k,v) in G.nodes(data=True)])
    nx.draw_networkx_labels(G,pos=pos, labels=labels)
    #!f = plt.gcf()
    fig.suptitle(figTitle)    
    #f.canvas.mpl_connect('button_press_event',onmousedown)
    plt.show()
    return(fig)
    
def loadDataflow(dotfile, outgraphml='foo.graphml'):
    G = nx.read_dot(dotfile)
    allowedNodeTypes = set('qastd')
    #!pprint(G.nodes(data=True))
    #!print(G.node['q9435'])


    saveGraphDict = G.graph['graph']
    saveNodeDict = G.graph['node']
    saveEdgeDict = G.graph['edge']

    defaultNodeDict = dict(delay=0, duration=0, host='NA-host')
    defaultEdgeDict = dict(delay=0, host='NA-host', port='0000')
    G.graph = {} # containts DICT VALUES that are dict, bad for graphml
    if outgraphml != None:
        nx.write_graphml(G,outgraphml)

    for n,d in G.nodes_iter(data=True):
        dd = defaultNodeDict.copy()

        npd = eval('dict(%s)'%(d[nodeProps])) if nodeProps in d else dict()
        cpd = eval('dict(%s)'%(d[clustProps])) if clustProps in d else dict()
        #print('cpd=',cpd)
        #ud = eval('dict(%s)'%(d[nodeProps])) if nodeProps in d else dict()   
        ud = dict()
        #ud.update(cpd.copy())
        ud.update(npd.copy())

        # Determine TYPE from type specific attributs
        if ('action' in ud):
            ud['type'] = 'a'

        if 'type' not in ud:
            raise RuntimeError('Node %s (%s) does not have a type! (%s)'
                               %(n,d,dotfile))
        if ud['type'] not in allowedNodeTypes:
            raise RuntimeError('Node %s (%s, file: %s) has invalid type. Expecting one of: %s'
                               %(n,d,dotfile,','.join(allowedNodeTypes)))

            
        # Validate dotfile
        if 'host' not in ud:
            raise RuntimeError(
                'No "host" attribute found in node=%s %s ("%s")'
                %(n,d,dotfile))
        if 'type' not in ud:
            raise RuntimeError(
                'No "type" attribute found in node=%s %s ("%s")'
                %(n,d,dotfile))
        if (ud['type'] == 'a') and (ud.get('action') == None):
            raise RuntimeError('Node %s: type="a", but no ACTION ("%s")'
                               %(n,d,dotfile))

        dd.update(ud)
        d['type'] = 'a' if ('action' in ud) else dd['type']
        if d.get('type') == 'a':
            if ('action' not in dd):
                raise Exception('Node "%s" as type="a", but no "action" field'
                                %(n))
            d['action'] = dd['action']
        d['host'] = dd['host']

    return G

def drawDataflow(dotfile, outgraphml):
    G = loadDataflow(dotfile, outgraphml)
    fig = drawDfGraph(G)
    plt.show()
    return G,fig

##############################################################################

def main():
    print('EXECUTING: %s\n\n' % (string.join(sys.argv)))
    parser = argparse.ArgumentParser(
        description='My shiny new python program',
        epilog='EXAMPLE: %(prog)s a b"'
        )
    parser.add_argument('--version', action='version',  version='1.0.1')
    parser.add_argument('infile', type=argparse.FileType('r'),
                        help='Input dot (graphviz) file')
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

    myFunc(args.infile, args.outfile)

if __name__ == '__main__':
    main()
