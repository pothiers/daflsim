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


dotfile=sdm-dci-dataflow.dot
fg1=feed_graphite.out
testCommand dim1_1 "dfsim.py --profile $dotfile $fg1 2>&1" "^\#" n
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

