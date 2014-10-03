Data flow diagram simulator
===========================

The *DAta FLow SIMulator* - DAFLSIM ("daffle sim") simulates the flow
of data given a data-flow diagram.

It requires Python 3.4.

You provide a dataflow-diagram (in `graphviz
<http://www.graphviz.org/>`_ format) The diagram must be annotated with a few special values in the graphviz "tooltip" attribute.  The *daflsim* program reads the diagram and runs a Descrete Event Simulation on it. 

Try these examples:

    dfsim.py --summarize end  --profile tests/graphviz-sample1.dot 
    dfsim.py --summarize NSA  tests/sdm-dci-dataflow.dot   
    dfsim.py --summarize NSA --summarize NOWHERE1 --profile tests/sdm-dci-dataflow.dot 


Quick test, execute:

    ./tests/smoke.sh



