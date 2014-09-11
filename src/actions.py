import random
import time

# Possible simulated actions that can be performed when moving from 
# one queue to another

def nop(record, probFail = 0.00):
    print('WARNING: simulating "nop" action')
    #!logging.debug('WARNING: using hardcoded random range for ACTION')
    time.sleep(random.randint(5,20))

    return random.random() >= probFail

def stb(record, probFail = 0.00):
    return random.random() >= probFail

def client(record, probFail = 0.00):
    #! time.sleep(random.randint(10,30)/10.0)
    return random.random() >= probFail

def bundle(record, probFail = 0.00):
    return random.random() >= probFail

def unbundle(record, probFail = 0.00):
    return random.random() >= probFail

# Sometimes submit to archive (NSA), sometimes put on q8336
def submit_to_archive(record, probFail = 0.00):
    return random.random() >= probFail

def resubmit(record, probFail = 0.00):
    return random.random() >= probFail

    
