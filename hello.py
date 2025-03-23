#encoding:gbk
'''
本策略事先设定好交易的股票篮子，然后根据指数的CCI指标来判断超买和超卖
当有超买和超卖发生时，交易事先设定好的股票篮子
'''
import pandas as pd
import numpy as np
import talib

def init(ContextInfo):
	print('hello.init!')
	
def handlebar(ContextInfo):
	print('hello.hadlebar!')