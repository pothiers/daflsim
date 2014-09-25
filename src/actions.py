import random
import time

# Possible simulated actions that can be performed when moving from 
# one queue to another

def nop(in_msg, probFail = 0.00, name='NOP'):
    #!print('WARNING: simulating "nop" action')
    result = in_msg
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "%s" FAILED'%(name,))


def stb(in_msg, probFail = 0.00):
    result = in_msg
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "STB" FAILED')

def client(in_msg, probFail = 0.00):
    #! time.sleep(random.randint(10,30)/10.0)
    result = in_msg
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "CLIENT" FAILED')

def bundle(in_msg, probFail = 0.00):
    result = in_msg
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "BUNDLE" FAILED')

def unbundle(in_msg, probFail = 0.00):
    result = in_msg
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "UNBUNDLE" FAILED')

# Sometimes submit to archive (NSA), sometimes put on q8336
def submit_to_archive(in_msg, probFail = 0.00):
    result = in_msg
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "SUBMIT_TO_ARCHIVE" FAILED')

def resubmit(in_msg, probFail = 0.00):
    result = in_msg
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "RESUBMIT" FAILED')


    
