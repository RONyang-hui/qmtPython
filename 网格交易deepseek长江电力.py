#encoding:gbk
import numpy as np

def init(ContextInfo):
    ContextInfo.tradestock = '600900.SH'  # 代码修正
    ContextInfo.set_universe([ContextInfo.tradestock])
    ContextInfo.accountid = '3556642'
    
    # 动态网格参数（基于20日ATR）
    hist_data = ContextInfo.get_history_data(20, '1d', ['high','low','close'])
    high_prices = [x for x in hist_data[ContextInfo.tradestock]['high'] if x > 0]
    low_prices = [x for x in hist_data[ContextInfo.tradestock]['low'] if x > 0]
    closes = [x for x in hist_data[ContextInfo.tradestock]['close'] if x > 0]
    
    # 计算ATR波动率
    atr = np.mean([max(abs(closes[i]-closes[i-1]), 
                  abs(high_prices[i]-low_prices[i])) 
                 for i in range(1, len(closes))])
    
    # 网格参数动态设定
    ContextInfo.grid_upper = max(high_prices[-20:]) if high_prices else 27.0  
    ContextInfo.grid_lower = min(low_prices[-20:]) if low_prices else 25.0    
    ContextInfo.grid_count = 10       
    ContextInfo.grid_step = max(0.1, round(atr * 0.5, 2))  # ATR动态步长
    
    # 资金管理参数优化
    ContextInfo.per_grid_ratio = 0.05  
    ContextInfo.max_risk_ratio = 0.07  
    ContextInfo.take_profit = 0.08     
    
    # 生成网格（价格向上下扩展1个步长）
    ContextInfo.grid_prices = np.round(
        np.arange(ContextInfo.grid_lower - ContextInfo.grid_step,
                 ContextInfo.grid_upper + ContextInfo.grid_step*2,
                 ContextInfo.grid_step), 2
    ).tolist()
    
    # 状态跟踪增强
    ContextInfo.grid_positions = dict.fromkeys(ContextInfo.grid_prices, 0)
    ContextInfo.grid_shares = dict.fromkeys(ContextInfo.grid_prices, 0)
    ContextInfo.grid_cost = {}  # 记录每格成本价
    ContextInfo.position = 0    
    ContextInfo.slippage = 0.003      
    ContextInfo.min_lots = 100        
    
    print(f"动态网格已更新：{ContextInfo.grid_prices}")

def handlebar(ContextInfo):
    try:
        # 趋势过滤（20/60均线）
        ma20 = np.mean(ContextInfo.get_history_data(20, '1d', 'close'))
        ma60 = np.mean(ContextInfo.get_history_data(60, '1d', 'close'))
        if ma20 < ma60:  
            print("趋势偏空，暂停交易")
            return
            
        current_price = get_current_price(ContextInfo)
        total_assets = get_total_assets(ContextInfo)
        available_cash = get_available_cash(ContextInfo)
        
        if check_risk_control(ContextInfo, current_price):
            return
            
        grid_value = total_assets * ContextInfo.per_grid_ratio
        
        for grid_price in ContextInfo.grid_prices:
            # 买入：价格跌破网格且现金充足
            if (current_price < grid_price) and (ContextInfo.last_price >= grid_price):
                if ContextInfo.grid_positions[grid_price] == 0 and available_cash >= grid_value:
                    buy_qty = calculate_lots(grid_value, current_price, ContextInfo)
                    if buy_qty > 0:
                        execute_order(ContextInfo, 'BUY', buy_qty, current_price)
                        update_position(ContextInfo, grid_price, buy_qty, current_price)
                        
            # 卖出：价格升破网格且持仓盈利>1%
            elif (current_price > grid_price) and (ContextInfo.last_price <= grid_price):
                if ContextInfo.grid_positions[grid_price] == 1:
                    cost = ContextInfo.grid_cost.get(grid_price, 0)
                    if cost > 0 and (current_price/cost -1) > 0.01:  # 至少1%盈利才卖出
                        sell_qty = ContextInfo.grid_shares[grid_price]
                        execute_order(ContextInfo, 'SELL', sell_qty, current_price)
                        update_position(ContextInfo, grid_price, -sell_qty, current_price)
        
        ContextInfo.last_price = current_price
        
    except Exception as e:
        print(f"执行异常: {str(e)}")

# 其余辅助函数保持与用户原代码相同，仅更新update_position()
def update_position(ContextInfo, grid_price, qty, price):
    ContextInfo.grid_positions[grid_price] = 1 if qty > 0 else 0
    ContextInfo.grid_shares[grid_price] += qty
    ContextInfo.position += qty
    if qty > 0:  # 记录买入成本（含滑点）
        ContextInfo.grid_cost[grid_price] = price * (1 + ContextInfo.slippage)
    else:         # 卖出时移除成本记录
        ContextInfo.grid_cost.pop(grid_price, None)