#encoding:gbk
import numpy as np
import pandas as pd

def init(ContextInfo):
    # 基础配置
    ContextInfo.tradestock = '000423.SZ'  # 东阿阿胶
    ContextInfo.set_universe([ContextInfo.tradestock])
    ContextInfo.accountid = '3556642'
    
    # 策略核心参数 - 基于波动特性优化
    ContextInfo.MA_period = 30  # 均线周期调整为30日
    ContextInfo.risk_ratio = 0.85  # 风控比例降低以应对高波动
    
    # 分批建仓与止盈止损参数
    ContextInfo.batch_size = 4  # 增加分批次数，降低单批风险
    ContextInfo.position_batches = []  
    ContextInfo.stop_loss_ratio = 0.92  # 止损比例8%
    ContextInfo.take_profit_ratio = 1.12  # 止盈目标12%
    ContextInfo.trailing_stop_ratio = 0.06  # 移动止盈回撤6%
    
    # 数据缓存
    ContextInfo.lookback_days = 60
    ContextInfo.data_cache = {'MA': None, 'last_update': None}
    
    print(f"策略初始化: {ContextInfo.tradestock} | MA{ContextInfo.MA_period}")

def handlebar(ContextInfo):
    try:
        symbol = ContextInfo.tradestock
        today = pd.Timestamp.now().strftime('%Y%m%d')
        
        # ===== 1. 高效数据获取 =====
        # 使用缓存减少重复计算
        if ContextInfo.data_cache['last_update'] != today:
            # 获取K线数据
            hist_data = ContextInfo.get_history_data(ContextInfo.MA_period + 10, '1d', ['close', 'open', 'high', 'low'])
            if symbol not in hist_data or len(hist_data[symbol]) < ContextInfo.MA_period:
                return
                
            # 计算均线
            close_series = hist_data[symbol]
            ContextInfo.data_cache['MA'] = pd.Series(close_series).rolling(ContextInfo.MA_period).mean().iloc[-1]
            ContextInfo.data_cache['last_update'] = today
        
        # 获取实时价格
        tick = ContextInfo.get_full_tick([symbol]).get(symbol, {})
        current_price = tick.get('last_price')
        bid_price = tick.get('bid1', current_price*0.998 if current_price else None)
        ask_price = tick.get('ask1', current_price*1.002 if current_price else None)
        
        # 如果实时数据获取失败，使用日线收盘价
        if current_price is None:
            close_data = ContextInfo.get_history_data(1, '1d', 'close')
            if symbol not in close_data:
                return
            current_price = close_data[symbol][-1]
            bid_price = current_price * 0.998
            ask_price = current_price * 1.002
            
        MA = ContextInfo.data_cache['MA']
            
        # ===== 2. 账户信息获取 =====
        account_info = get_trade_detail_data(ContextInfo.accountid, "STOCK", "ACCOUNT")
        if not account_info:
            return
        cash = account_info[0].m_dBalance
        position = sum(batch['shares'] for batch in ContextInfo.position_batches)
        
        # ===== 3. 信号生成 =====
        buy_signal = current_price > MA
        sell_signal = current_price < MA
        
        # ===== 4. 交易执行 =====
        # 买入逻辑
        if buy_signal and len(ContextInfo.position_batches) < ContextInfo.batch_size and cash > 0:
            available_batches = ContextInfo.batch_size - len(ContextInfo.position_batches)
            batch_cash = (cash * ContextInfo.risk_ratio) / max(1, available_batches)
            shares = int(batch_cash / (ask_price * 100)) * 100
            
            if shares >= 100:
                batch = {'price': ask_price, 'shares': shares, 'high': ask_price}
                ContextInfo.position_batches.append(batch)
                order_volume(symbol, shares, 0, ContextInfo.accountid, "ORDER_TYPE_BUY", ask_price)
                print(f"▶️ 买入 {shares}股 @ {ask_price:.2f}")
                
        # 卖出逻辑 - 使用列表推导提高效率
        sell_indices = []
        for i, batch in enumerate(ContextInfo.position_batches):
            # 更新最高价
            batch['high'] = max(batch['high'], current_price)
            
            # 合并判断条件，减少重复计算
            take_profit = current_price >= batch['price'] * ContextInfo.take_profit_ratio
            trailing_stop = (batch['high'] - current_price) / batch['high'] >= ContextInfo.trailing_stop_ratio
            stop_loss = current_price <= batch['price'] * ContextInfo.stop_loss_ratio
            
            if sell_signal or take_profit or trailing_stop or stop_loss:
                sell_indices.append(i)
                
        # 倒序移除，避免索引变化问题
        for i in sorted(sell_indices, reverse=True):
            batch = ContextInfo.position_batches[i]
            order_volume(symbol, batch['shares'], 0, ContextInfo.accountid, "ORDER_TYPE_SELL", bid_price)
            profit = (bid_price - batch['price']) / batch['price'] * 100
            print(f"◀️ 卖出 {batch['shares']}股 @ {bid_price:.2f} | {profit:.1f}%")
            ContextInfo.position_batches.pop(i)
            
        # ===== 5. 状态输出 =====
        if ContextInfo.position_batches:
            avg_cost = sum(b['price']*b['shares'] for b in ContextInfo.position_batches) / position if position else 0
            profit_rate = (current_price/avg_cost-1)*100 if avg_cost else 0
            print(f"持仓: {position}股 | 成本: {avg_cost:.2f} | 盈亏: {profit_rate:.1f}%")
        print(f"价格: {current_price:.2f} | MA: {MA:.2f} | 信号: {'买入' if buy_signal else '卖出' if sell_signal else '持有'}")
        
    except Exception as e:
        print(f"错误: {str(e)}")

def get_position(accountid, symbol):
    try:
        positions = get_trade_detail_data(accountid, "STOCK", "POSITION")
        return next((p for p in positions if p.m_strInstrumentID == symbol), None)
    except:
        return None