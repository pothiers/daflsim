see ~/org/sdm.org

DES (Discrete Event Simulation) of SDM data-flow.  Intended to span
from STB output (first queue) to /submit_to_archive2.pl/

Every node must be of one of the followings types:
- s:: Source
- q:: Queue
- a:: Action
- t:: Terminal
- d:: Database

Node attributes are stored in the dotfile (graphviz) nodes in the
"comment" property. Format is: "name1='value2' name2='value2' ..."
Possible attributes are:
- type::
- action::
- delay::
- duration::
- host::

If an ACTION is given, then "type='a'" is implied.
