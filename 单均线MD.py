#encoding:gbk
import numpy as np
import pandas as pd

def init(ContextInfo):
    ContextInfo.tradestock = '000333.SZ'
    ContextInfo.set_universe([ContextInfo.tradestock])
    ContextInfo.accountid = '8883556642'
    
    ContextInfo.MA_period = 20
    ContextInfo.VOL_MA_period = 10
    ContextInfo.risk_ratio = 0.95
    
    ContextInfo.position = 0
    print(f"初始化完成：{ContextInfo.tradestock}，均线周期：{ContextInfo.MA_period}")

def handlebar(ContextInfo):
    try:
        symbol = ContextInfo.tradestock
        
        # 获取实时tick数据（返回字典结构）
        tick_data = ContextInfo.get_full_tick([symbol])
        if not tick_data or symbol not in tick_data:
            print("实时行情获取失败，跳过本轮")
            return
            
        tick = tick_data[symbol]  # 获取标的的tick字典
        
        # 从字典中提取字段（确保键名正确）
        current_price = tick.get('last_price', None)
        bid_price = tick.get('bid1', None)
        ask_price = tick.get('ask1', None)
        current_volume = tick.get('volume', 0)  # 当日累计成交量
        
        # 检查关键数据是否存在
        if None in [current_price, bid_price, ask_price]:
            print(f"行情数据不完整：最新价{current_price} 买一价{bid_price} 卖一价{ask_price}")
            return
        
        # 获取历史数据（合并获取减少API调用）
        n_bars = max(ContextInfo.MA_period, ContextInfo.VOL_MA_period) + 1
        his_data = ContextInfo.get_history_data(n_bars, '1d', ['close', 'volume'])
        
        # 数据校验
        if symbol not in his_data or len(his_data[symbol]['close']) < n_bars:
            print(f"历史数据不足，需求{n_bars}根，实际{len(his_data.get(symbol,{}).get('close',[]))}根")
            return
        
        # 提取历史数据
        close_prices = his_data[symbol]['close']
        volumes = his_data[symbol]['volume']
        
        # 计算技术指标
        MA20 = pd.Series(close_prices).rolling(ContextInfo.MA_period).mean().values
        VOL_MA10 = pd.Series(volumes).rolling(ContextInfo.VOL_MA_period).mean().values
        
        # 获取账户信息
        account_info = get_trade_detail_data(ContextInfo.accountid, "STOCK", "ACCOUNT")
        if not account_info:
            print("获取账户信息失败")
            return
            
        cash = account_info[0].m_dBalance
        position_obj = get_position(ContextInfo.accountid, symbol)
        position = position_obj.m_nVolume if position_obj else 0
        
        # 策略逻辑优化：包含实时成交量
        buy_condition = (
            close_prices[-2] <= MA20[-2] and 
            current_price > MA20[-1] and  # 使用实时价与最新均线比较
            current_volume > VOL_MA10[-1] * 1.2  # 实时成交量突破均线120%
        )
        
        sell_condition = (
            current_price < MA20[-1] and  # 使用实时价判断
            close_prices[-2] >= MA20[-2]
        )
        
        # 交易执行优化
        if buy_condition and position == 0:
            # 使用卖一价计算购买量
            max_shares = int((cash * ContextInfo.risk_ratio) / (ask_price * 100)) * 100
            if max_shares >= 100:
                order_volume(symbol, max_shares, 0, ContextInfo.accountid, "ORDER_TYPE_BUY", ask_price)
                print(f"委托买入{max_shares}股 @{ask_price:.2f}")
                ContextInfo.position = max_shares
                
        elif sell_condition and position > 0:
            # 使用买一价立即卖出
            order_volume(symbol, position, 0, ContextInfo.accountid, "ORDER_TYPE_SELL", bid_price)
            print(f"委托卖出{position}股 @{bid_price:.2f}")
            ContextInfo.position = 0
            
        # 添加心跳监测
        print(f"Tick监测 @{tick.get('time', '未知时间')} 现价:{current_price:.2f} 仓位:{position}股")
        
    except Exception as e:
        print(f"策略异常: {str(e)}")

def get_position(accountid, symbol):
    try:
        positions = get_trade_detail_data(accountid, "STOCK", "POSITION")
        return next((p for p in positions if p.m_strInstrumentID == symbol), None)
    except Exception as e:
        print(f"持仓查询异常: {str(e)}")
        return None