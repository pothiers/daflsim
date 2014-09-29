# Calculate stuff from CRON string

# Minutes since start of hour
def minutesThisHour(nowSeconds):
    return(int((nowSeconds/60) % 60))

# Hours since start of day
def hoursThisDay(nowSeconds):
    return(int((nowSeconds/60) % (60*24)/60))

    
# Return number of seconds until a cron job using the spec containing 
# "<minute> <hour> * * *" would fire.
# If only one (space delimited) field is given, its for MINUTE. Assume hour=*
# APPROXIMATE: Only implements pieces of cron date/time matching we need.
def next_time(nowSeconds, cronstr, factor=60):
    '''
    nowSeconds:: seconds since start of simulation
    cronstr:: "minute hour"; either can be N or "*" or "*/<step>"
              HOUR is optional (defaults to "*")
    '''
    def parseStep(str):
        n,*stepList = str.split('/')
        return(0 if (n == '*') else int(n),
               1 if (0 == len(stepList)) else int(stepList[0]))

    def remTime(nowTime, times, timeStep):
        'Return remaining time units from nowTime until "times/timeStep"'
        if times == 0:
            # for "*/5"
            return(timeStep - (nowTime + times) % timeStep)
        else:
            # for "35"
            return(times - (nowTime % times))


        
    parts = cronstr.split()
    if len(parts) > 1:
        minute,hour = parts
    else:
        minute = parts[0]
        hour='*'

    nowMinutes = minutesThisHour(nowSeconds)
    minutes,minuteStep = parseStep(minute)
    delayMinutes = remTime(nowMinutes, minutes, minuteStep)

    nowHours = hoursThisDay(nowSeconds)
    hours,hourStep = parseStep(hour)
    delayHours = remTime(nowHours, hours, hourStep)

    if hour == '*':
        return delayMinutes*60
    else:
        return delayMinutes*60 + delayHours*60*60
