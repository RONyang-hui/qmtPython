#encoding:gbk

import numpy as np
import pandas as pd

def init(ContextInfo):
    # 根据近期价格波动调整网格参数
    ContextInfo.tradestock = '000333.SZ'
    ContextInfo.set_universe([ContextInfo.tradestock])
    ContextInfo.accountid = '8883556642'
    
    # 调整后的网格参数（示例值，需根据实际行情调整）
    ContextInfo.grid_upper = 75.0    # 网格上限（近期观测最高价）
    ContextInfo.grid_lower = 55.0    # 网格下限（近期观测最低价）
    ContextInfo.grid_count = 20      # 网格数量（更密集的网格）
    ContextInfo.per_grid_ratio = 0.05  # 单网格资金比例（总资金5%）

    # 生成等比网格（可选，当前保持线性网格）
    price_range = ContextInfo.grid_upper - ContextInfo.grid_lower
    ContextInfo.grid_step = price_range / ContextInfo.grid_count
    ContextInfo.grid_prices = [round(ContextInfo.grid_lower + i*ContextInfo.grid_step, 2) 
                              for i in range(ContextInfo.grid_count + 1)]
    
    # 初始化网格状态
    ContextInfo.grid_positions = [0] * (ContextInfo.grid_count + 1)
    ContextInfo.grid_shares = [0] * (ContextInfo.grid_count + 1)
    ContextInfo.last_price = 0
    
    # 添加风控参数
    ContextInfo.min_trade_amount = 5000    # 最小交易金额
    ContextInfo.slippage = 0.005           # 滑点率0.5%
    
    print("优化后的网格交易策略")
    print(f"价格区间: {ContextInfo.grid_lower}-{ContextInfo.grid_upper}")
    print(f"网格间距: {ContextInfo.grid_step:.2f}")
    print(f"网格节点: {ContextInfo.grid_prices}")

def handlebar(ContextInfo):
    try:
        current_price = get_current_price(ContextInfo.tradestock, ContextInfo)
        if ContextInfo.last_price == 0:
            ContextInfo.last_price = current_price
            return
        
        # 获取可用资金（非总资产）
        available_cash = get_available_cash(ContextInfo.accountid, 'STOCK')
        total_assets = get_total_assets(ContextInfo.accountid, 'STOCK')
        
        # 动态计算单网格金额（基于总资产的固定比例）
        per_grid_value = total_assets * ContextInfo.per_grid_ratio
        
        for i in range(len(ContextInfo.grid_prices)):
            grid_price = ContextInfo.grid_prices[i]
            
            # 价格下穿买入条件
            if ContextInfo.last_price >= grid_price and current_price < grid_price:
                if ContextInfo.grid_positions[i] == 0 and per_grid_value >= ContextInfo.min_trade_amount:
                    # 计算实际买入金额（考虑可用资金限制）
                    actual_invest = min(per_grid_value, available_cash)
                    
                    # 计算买入数量（考虑滑点）
                    buy_price = current_price * (1 + ContextInfo.slippage)
                    shares = int(actual_invest / buy_price)
                    shares = (shares // 100) * 100  # 整手交易
                    
                    if shares > 0:
                        order_shares(ContextInfo.tradestock, shares, ContextInfo, ContextInfo.accountid)
                        ContextInfo.grid_shares[i] = shares
                        ContextInfo.grid_positions[i] = 1
                        available_cash -= shares * buy_price  # 更新可用资金
                        print(f"买入信号 @ {grid_price} 买入{shares}股")
            
            # 价格上穿卖出条件
            elif ContextInfo.last_price <= grid_price and current_price > grid_price:
                if ContextInfo.grid_positions[i] == 1 and ContextInfo.grid_shares[i] > 0:
                    # 计算实际卖出数量（考虑滑点）
                    sell_price = current_price * (1 - ContextInfo.slippage)
                    order_shares(ContextInfo.tradestock, -ContextInfo.grid_shares[i], ContextInfo, ContextInfo.accountid)
                    print(f"卖出信号 @ {grid_price} 卖出{ContextInfo.grid_shares[i]}股")
                    ContextInfo.grid_positions[i] = 0
                    ContextInfo.grid_shares[i] = 0
        
        ContextInfo.last_price = current_price

    except Exception as e:
        print(f"执行异常: {str(e)}")

# 获取可用资金
def get_available_cash(accountid, datatype):
    result = 0
    resultlist = get_trade_detail_data(accountid, datatype, "ACCOUNT")
    for obj in resultlist:
        result = obj.m_dAvailable  # 可用资金
    return result

# 获取总资产（现金+持仓市值）
def get_total_assets(accountid, datatype):
    cash = get_available_cash(accountid, datatype)
    position_value = get_position_value(accountid, ContextInfo.tradestock)
    return cash + position_value

# 获取当前价格（带异常处理）
def get_current_price(stockcode, ContextInfo):
    try:
        price_data = ContextInfo.get_history_data(2, '1d', 'close')
        return price_data[stockcode][-1] if stockcode in price_data else 0
    except:
        return 0

# 获取持仓数量
def get_position_quantity(accountid, stockcode):
    try:
        position_data = get_trade_detail_data(accountid, "STOCK", "POSITION")
        for pos in position_data:
            if pos.m_strInstrumentID == stockcode:
                return pos.m_nVolume
        return 0
    except:
        return 0