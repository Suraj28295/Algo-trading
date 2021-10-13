#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import oandapyV20 as oandapy
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.instruments as instruments
import json
import requests
import datetime
import pandas as pd
from collections import OrderedDict
from datetime import datetime, timedelta
from pandas import json_normalize
import logging 
import time
from os import path


class Algo_trade:

# Initialize variables    
    def __init__(self,environment,access_token,instrument,account_id,Start_date_time,granularity,logging_mode,quantity,database_location,inclusion_percentage,take_profit_percentage):
        self.access_token=access_token
        self.environment=environment
        self.instrument=instrument
        self.account_id=account_id
        self.Start_date_time=Start_date_time
        self.granularity=granularity
        self.logging=logging_mode
        self.quantity=quantity
        self.inclusion_percentage=inclusion_percentage
        self.take_profit_percentage=take_profit_percentage
        self.price_dict=dict()
        self.counter=1
        self.filename=database_location+self.instrument+".json"
        logging.basicConfig(filename="Oanda trades.log",format='%(asctime)s %(message)s',filemode='w')
        self.logger=logging.getLogger()
        if(self.logging=='INFORMATION' or self.logging=='Information' or self.logging=='information'):
            self.logger.setLevel(logging.INFO)
        if(self.logging=='DEBUG' or self.logging=='Debug' or self.logging=='debug'):
            self.logger.setLevel(logging.DEBUG)
        self.establish_connection()

# Connect to the Oanda server using credintials    
    def establish_connection(self,):
        try:
            self.oanda=oandapy.oandapyV20.API(environment=self.environment,
                                     access_token=self.access_token)
            self.logger.info("Connection Established..........")
        except ValueError:
            self.logger.error("Invalid Credintials...........")
            print("Invalid Credintials...........")

#Change Json into Dataframe for openig candle            
    def DataFrameFactory(self, colmap=None, conv=None):
        df=pd.DataFrame(self.OHLC_opening['candles'][0]['mid'],index=pd.DatetimeIndex([self.OHLC_opening['candles'][0]['time']]))
        df = df.apply(pd.to_numeric)
        return df

#Get High and Low for the Opening Candle
    def opening_High_low(self,):
        inst_param={ "from":self.Start_date_time ,  "granularity":self.granularity ,'count':1}
        r = instruments.InstrumentsCandles(instrument=self.instrument,params=inst_param)
        self.oanda.request(r)
        self.OHLC_opening=r.response
        df = dict()
        df.update({self.instrument: self.DataFrameFactory(self.OHLC_opening)})
        self.df_instrument=df
        self.opening_high=self.OHLC_opening['candles'][0].get('mid')['h']
        self.opening_low=self.OHLC_opening['candles'][0].get('mid')['l']


#Get the Trade list to later check if the instrument is present in the Traded list or not
    def get_tradelist(self):
        tradelist = trades.TradesList(self.account_id,)
        self.rv_tradelist = self.oanda.request(tradelist)
        trade_df=json_normalize(self.rv_tradelist['trades'])
        self.logger.info("TRADELIST:- \n\t\t"+json.dumps(self.rv_tradelist))
        
        return(self.rv_tradelist)

#Get the Current Pirce of a instrument    
    def current_price(self):
        self.param={'instruments':self.instrument}
        r=pricing.PricingInfo(accountID=self.account_id,params=self.param)
        self.rv_currentprice = self.oanda.request(r)
        curr_p={i:self.rv_currentprice['prices'][0][i]  for i in self.rv_currentprice['prices'][0] if (i in ['type', 'time', 'bids', 'asks', 'closeoutBid', 'closeoutAsk', 'status', 'tradeable', 'instrument'])}
        # price_dataframe[curr_p['time']]=curr_p

        # dict(filter(lambda curr_p: curr_p[0] not in ['type', 'time'], curr_p.items()))
        if(True):#self.rv_currentprice['prices'][0]['status']=='tradeable'
            self.counter=self.counter+1
            if(self.counter % 10 == 0):
#                 print(self.filename)
                 # Check if file exists
                if path.isfile(self.filename) is False:
                      with open(self.filename, 'w+') as f:
                        f.write('[]')            
                        f.close
                else:
                    print("File exist")

                # Read JSON file
                with open(self.filename) as fp:
                      listObj = json.load(fp)

                # Verify existing list
                print(listObj)

                listObj.append(curr_p)

                # Verify updated list
                print(listObj)

                with open(self.filename, 'w') as json_file:
                    json.dump(listObj, json_file, 
                                        indent=4,  
                                        separators=(',',': '))


#Initiate Buy Trade
    def Buy_trade(self):
        data={
              "order": {
                "price": self.rv_currentprice['prices'][0]['bids'][0]['price'],
                "stopLossOnFill": {
                  "timeInForce": "GTC",
                  "price": str(round((self.df_instrument[self.instrument]['l']).item(),5))
                },
                  "takeProfitOnFill": {"price": str(round(float(self.rv_currentprice['prices'][0]['asks'][0]['price'])*(1+self.take_profit_percentage),5))},
                "timeInForce": "FOK",
                "instrument": self.instrument,
                "units": str(self.quantity),
                "type": "MARKET",
                "positionFill": "DEFAULT"
              }
            }
        r = orders.OrderCreate(self.account_id, data=data)
        self.oanda.request(r)
        trade_acknowledgment=r.response
        self.order_excecution_details = trade_acknowledgment['orderFillTransaction'].get('tradeOpened')
        print("Bought {0} quantity of {1} at {2}".format(self.order_excecution_details['units'],self.instrument,self.order_excecution_details['price']))
        self.logger.info("Bought {0} quantity of {1} at {2}".format(self.order_excecution_details['units'],self.instrument,self.order_excecution_details['price']))

#Initiate Sell Trade
    def sell_trade(self):
        data={
              "order": {
                "price": self.rv_currentprice['prices'][0]['asks'][0]['price'],
                "stopLossOnFill": {
                  "timeInForce": "GTC",
                  "price": str(round((self.df_instrument[self.instrument]['h']).item(),5))
                },
                "takeProfitOnFill": {"price": str(round(float(self.rv_currentprice['prices'][0]['bids'][0]['price'])*(1-self.take_profit_percentage),5))},
                "timeInForce": "FOK",
                "instrument": self.instrument,
                "units": str(-self.quantity),
                "type": "MARKET",
                "positionFill": "DEFAULT"
              }
            }
        r = orders.OrderCreate(self.account_id, data=data)
        self.oanda.request(r)
        trade_acknowledgment=r.response
#         print(trade_acknowledgment)
        self.order_excecution_details = trade_acknowledgment['orderFillTransaction'].get('tradeOpened')
        print("Short {0} quantity of {1} at {2}".format(self.order_excecution_details['units'],self.instrument,self.order_excecution_details['price']))
        self.logger.info("Bought {0} quantity of {1} at {2}".format(self.order_excecution_details['units'],self.instrument,self.order_excecution_details['price']))

# Initiate the trading loop        
    def take_trade(self,):
        while True:
            self.opening_High_low()
            self.get_tradelist()
            self.current_price()
# To check if the instrument exists in tradelist        
            ls=[i['instrument'] not in self.rv_currentprice['prices'][0]['instrument'] for i in self.rv_tradelist['trades']]
            tradeable = (self.rv_currentprice['prices'][0]['status']=='tradeable')
#If closeoutBid>Opening_High & closeoutBid< (1 % of Opening_High) & instrument not already in trading list & Instrument is tradeable
            if (float(self.rv_currentprice['prices'][0]['closeoutBid'])>self.df_instrument[self.instrument]['h'].item()) and           (float(self.rv_currentprice['prices'][0]['closeoutBid'])<(self.df_instrument[self.instrument]['h']*(1+self.inclusion_percentage)).item()) and (any(ls) or len(ls) == 0) and tradeable:
                self.Buy_trade()
#                 self.trail_SL_buy()
#If closeoutBid<Opening_Low & closeoutask> (1 % of Opening_Low) & instrument not already in trading list & Instrument is tradeable
            else:
                if (float(self.rv_currentprice['prices'][0]['closeoutAsk'])<self.df_instrument[self.instrument]['l'].item())  and (float(self.rv_currentprice['prices'][0]['closeoutAsk'])>(self.df_instrument[self.instrument]['l']*(1-self.inclusion_percentage)).item()) and (any(ls) or len(ls) == 0) and tradeable:
                    self.sell_trade()
#                      self.trail_SL_sell()
#If closeoutBid>Opening High & instrument not already in trading list            
                else:    
                    if(not any(ls) and tradeable):
                        print("Can not Buy : Instrument already in tradebook")
#                         time.sleep(5)
                    else:
                        if(not tradeable):
                            print("Instrument not Tradable")
                            self.logger.info("Instrument not Tradable")
                            print("The file containing data for "+self.instrument+" is -->\t"+self.filename)
                            break