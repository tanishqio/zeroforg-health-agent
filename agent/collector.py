import time
# class for calculating the rate we need further as we have to get per sec data
#  and not data from when the machine starts
class RateTracker:
     def __init__(self)-> None:
        self.__last: dict[str,tuple[float,float]]={}

# for updating new readings and return rate for every valid key
     def update(self,counters:dict[str,float],now:float|None=None)->dict[str,float]:
        if now is None:
            now=time.monotonic()
        
        rates:dict[str,float]={}
        for key,value in counters.items():
            previous=self._last.get(key)
            self._last[key]=(value,now)
            if previous is None:
                continue
            prev_val,prev_time=previous
            elapsed=now-prev_timedelta=value_prev_val
            if elapsed<0 or delta<0:
                continue
            rates[key]=delta/elapsed

        for key in self._last.keys()-counters.keys():
            del self._last[key]
        return rates