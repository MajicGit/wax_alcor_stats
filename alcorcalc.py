import requests
import time 

targets = ["majicwallet1","majicwallet2"]
tokens = ["TOCIUM","EFS","TLM","AOGG"]
actions_per_query = 1000 #If running into trouble, dropping this number might make sense 



api_index = 0  #Index to keep track of what API we last queried -- having this as a global variable is probably easiest even if not pretty... 
normal_api_list = ["https://api.wax.alohaeos.com","http://api.waxsweden.org","http://wax.pink.gg","http://api-wax-mainnet.wecan.dev","http://waxapi.ledgerwise.io","http://wax-api.eosiomadrid.io"] #Need to reduce actions_per_query for this

def try_api_request(request:str,endpoints = normal_api_list):
    """ Just a function that iterates through wax endpoints, finding one where we aren't being rate limited. Should decently well deal with the case where they are all occupied and we need to use wait a bit"""
    global api_index
    backoff_factor = 0
    while True: 
        for _ in range(0,len(endpoints)): #Try out all endpoints before we start worrying about backoffs 
            api_index = (api_index) % len(endpoints)
            current_api = endpoints[api_index]
            api_index = (api_index + 1) % len(endpoints) #Increment in case of failure. 
            full_req = current_api + request  #get the full request
            try:
                r = requests.get(full_req,timeout=5)
            except (requests.ConnectionError, requests.HTTPError,requests.ReadTimeout,requests.Timeout,requests.ConnectionError):
                #print("Request raised an unexpected error. Moving on to next endpoint but that may not be the problem...")
                continue
            try:
                data = r.json()
            except ValueError:
                #print("Encountered JSON Error", r.text)
                #print(full_req)   
                continue
            try:
                if data["code"] == 404:
                    #print("404 error")
                    #print(full_req)
                    continue 
            except:
                # print("No code, good.")
                pass
            try:
                if data['executed'] != True:
                    #if data['message'] == 'Rate limit':
                    #    print("Rate limiting, will try a different API endpoint")
                    #    print(full_req)   
                    #else: 
                    #   print("Unknown error in query, continuing but please analyse this closer...")
                    #   print(full_req, r)
                    continue 
            except:
                pass 
            if not "actions" in data:
                continue 
            api_index = (api_index - 1) % len(endpoints) #The request was succesfull, so let's keep using that API.
            return data 
        #At this point we hit all of the APIs unsucesfully. Time to sleep for a bit. 
        print("We tried all API endpoints and all are rate limiting us. Time to sleep!")
        if backoff_factor > 10:
            print("API really doesn't like us today. Giving up...")
            return -1 
        backoff_factor += 1 
        time.sleep(10*backoff_factor)



#Index all the alcor market pairs, so we know what tokens are involved in them 
id_pairs = {} 
r = requests.get("https://wax.alcor.exchange/api/markets")
markets = r.json()
for pair in markets:
    base_token = pair["base_token"]["symbol"]["name"]
    quote_token = pair["quote_token"]["symbol"]["name"]
    id = pair["id"]
    id_pairs[id] = (base_token,quote_token)

#For all wax accounts we want to look at:
for target in targets:
    #Get the entire history of the account on alcor market 
    r = requests.get(f"https://wax.alcor.exchange/api/account/{target}/deals")
    market_trades = r.json()
    timestamp = ""
    response = ""

    #Get the entire history of the account on wax to find all alcorswap transactions:
    all_actions = [] 
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    timestamp_second = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    while True: 
        try:
            endpoints=[normal_api_list[0]]
            resp = try_api_request(f"/v2/history/get_actions?limit={actions_per_query}&account={target}&before={timestamp_second}")['actions']
            changed = False 
            for action in resp:
                if action["@timestamp"] < timestamp:
                    timestamp_second = timestamp 
                    timestamp = action["@timestamp"]
                    changed = True 
                if action not in all_actions:
                    changed = True 
                    all_actions.append(action)
            if not changed : #Last query gave us no new transactions. So indiciates we are at the end.
                break  
        except Exception as e:
            print(e)
            print("This shouldn't have happened...")
            time.sleep(10)
    print(len(all_actions), " many transactions found for address: ",target)

    #For all transactions this person did with alcorammswap, we gather the pairs involved in that. 
    alcor_trx_ids = {}
    for action in all_actions:
        if action['act']['name'] == 'transfer' and action['act']['authorization'][0]['actor'] in [target,"alcorammswap"]  and action['act']['data']['to'] in [target,"alcorammswap"]:
            if action["trx_id"] not in alcor_trx_ids:
                alcor_trx_ids[action["trx_id"]] = [] 
            alcor_trx_ids[action["trx_id"]].append(action["act"]["data"]["symbol"]) 

    #For the tokens that interest us:
    for token in tokens: 
        #Keep track of sold (in wax, in token) and bought (in wax, in token) for this token. 
        sold = [0.0,0.0]
        bought = [0.0,0.0]

        #First go through the alcor trades 
        for trade in market_trades:
            pair = id_pairs[trade["market"]]
            #Get the pair for the trade 
            if token not in pair:
                continue 
            if (trade["type"] != "sellmatch" and trade["type"]!="buymatch"):
                print(trade)
                #No idea what else could be in here ... 
                break 
            #Figure out if we are selling or buying the token 
            is_sell = (trade["type"] == "sellmatch" and token == pair[0]) or (trade["type"] == "buymatch" and token == pair[1]) 
            price = trade["unit_price"]
            amount = trade["bid"]
            if pair[0] != "WAX":
                #A bit primitive, but ignores any types that we don't support. 
                print(pair)
                print(trade)
                print("Not supported")
                break 
            #Get the price in wax of this sell 
            wax_price = price * amount 
            if is_sell:
                sold[0] += wax_price
                sold[1] += amount
            else:
                bought[0] += wax_price
                bought[1] += amount            



        #Now gather all the swap data 
        for action in all_actions: 
            if action["trx_id"] not in alcor_trx_ids:
                continue 
            pair = alcor_trx_ids[action["trx_id"]]
            if len(pair) != 2 or token not in pair or "WAX" not in pair:
                #Either not a trade involving our token, or a trade to some other currency. Tool doesn't support those so we ignore it. 
                continue 
            if action['act']['name'] == 'transfer' and action['act']['authorization'][0]['actor']  == target and action['act']['data']['to'] == "alcorammswap":
                if action['act']['data']['symbol']==token:
                    sold[1] += action['act']['data']['amount']
                if action['act']['data']['symbol']=="WAX":
                    bought[0] += action['act']['data']['amount']

            if action['act']['name'] == 'transfer' and action['act']['authorization'][0]['actor']  == "alcorammswap" and action['act']['data']['to'] == target:
                if action['act']['data']['symbol']==token:
                    bought[1] += action['act']['data']['amount']
                if action['act']['data']['symbol']=="WAX":
                    sold[0] += action['act']['data']['amount']
                    
        print(f"Stats for WAX-{token} trades on alcor for {target}")
        print(f"Bought (value in wax): {bought[0]}")
        print(f"Sold (value in wax): {sold[0]}")
        print(f"Bought (value in {token}): {bought[1]}")
        print(f"Sold (value in {token}): {sold[1]}")