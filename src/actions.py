import random
import time

# Possible simulated actions that can be performed when moving from 
# one queue to another

def nop(record, probFail = 0.00):
    print('WARNING: simulating "nop" action')
    result = record
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "NOP" FAILED')


def stb(record, probFail = 0.00):
    result = record
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "STB" FAILED')

def client(record, probFail = 0.00):
    #! time.sleep(random.randint(10,30)/10.0)
    result = record
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "CLIENT" FAILED')

def bundle(record, probFail = 0.00):
    result = record
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "BUNDLE" FAILED')

def unbundle(record, probFail = 0.00):
    result = record
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "UNBUNDLE" FAILED')

# Sometimes submit to archive (NSA), sometimes put on q8336
def submit_to_archive(record, probFail = 0.00):
    result = record
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "SUBMIT_TO_ARCHIVE" FAILED')

def resubmit(record, probFail = 0.00):
    result = record
    if random.random() >= probFail:
        return result
    else:
        raise RuntimeError('Execution of action "RESUBMIT" FAILED')


    
