#!/bin/bash
# AUTHORS:    S. Pothier
# PURPOSE:    Wrapper for smoke test
# EXAMPLE:
#   loadenv dq
#   $PHOME/test/smoke.sh
#

file=$0
dir=`dirname $file`
origdir=`pwd`
cd $dir
dir=`pwd`
cd ../src
srcdir=`pwd`
cd $dir

PATH=$srcdir:$dir:$PATH

source smoke-lib.sh
return_code=0
SMOKEOUT="README-smoke-results.txt"

echo ""
echo "Starting tests in \"$dir\" ..."
echo ""
echo ""


########################################
## Very simple graph
##
testCommand dim2_0 "dfsim.py graphviz-sample1.dot" "^\#" n
testCommand dim2_1 "dfsim.py --summarize end --profile graphviz-sample1.dot" "^\#" n

########################################
## A real DCI graph
##
dcidot=sdm-dci-dataflow.dot
testCommand dim1_0 "dfsim.py $dcidot 2>&1" "^\#" n

fg1=feed_graphite.out
#!testCommand dim1_1 "dfsim.py --end 10000 --summarize NSA --profile $dcidot --graphite $fg1 2>&1" "^\#" n
testCommand dim1_1 "dfsim.py --end 10000 --summarize NSA --profile $dcidot 2>&1" "^\#" n
# Order varies
#!testOutput out $fg1 '^\#' n


###########################################
#! echo "WARNING: ignoring remainder of tests"
#! exit $return_code
###########################################


##############################################################################

rm $SMOKEOUT 2>/dev/null
if [ $return_code -eq 0 ]; then
  echo ""
  echo "ALL smoke tests PASSED ($SMOKEOUT created)"
  echo "All tests passed on " `date` > $SMOKEOUT
else
  echo "Smoke FAILED (no $SMOKEOUT produced)"
fi


# Don't move or remove! 
cd $origdir
exit $return_code

