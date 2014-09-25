DES (Discrete Event Simulation) of data-flow from data-flow diagram (graphviz format). 

see doc/dataflow-simulation.org

Try:
    dfsim.py --loglevel=INFO --summarize end  --profile tests/graphviz-sample1.dot 
    dfsim.py --summarize NSA  tests/sdm-dci-dataflow.dot   
    dfsim.py --summarize NSA --summarize NOWHERE1 --profile tests/sdm-dci-dataflow.dot 

Quick test, execute:
    ./tests/smoke.sh


