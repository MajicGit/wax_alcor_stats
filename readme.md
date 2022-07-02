# Alcor transaction stats

This tool enables you to see aggregate statistics on all wax-token swaps you have done on alcor. 
To use it just replace targets and tokens with desired values and run it. 

Ignores all swaps that are between two tokens where neither is wax. E.g. even if you are tracking TLM and TOCIUM, if you do a swap from TOCIUM to TLM this will ignore it and not count it to the stats.

Requires: python and some patience if you have a large number of transactions. 

No guarantees on correctness. In particular, there is some weirdness where sometimes certain transactions are missed. The majority of them should be correct thought.

Thanks to Bottlecap for his help in this!