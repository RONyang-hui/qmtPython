import numpy as np
import pandas as pd

def init(ContextInfo):
    # 标的调整为东阿阿胶
    ContextInfo.tradestock = '000423.SZ'
    ContextInfo.set_universe([ContextInfo.tradestock])
    ContextInfo.accountid = '8883556642'
    
    # ==== 优化后的策略参数 ====
    ContextInfo.MA_period = 30  # 均线周期从20调整为30，适应中期波动:cite[1]:cite[8]
    ContextInfo.VOL_MA_period = 10
    ContextInfo.risk_ratio = 0.85  # 风险比例降低，应对高销售费用率风险:cite[1]
    
    # ==== 分批交易参数优化 ====
    ContextInfo.batch_size = 4           # 分批次数从3增至4，分摊建仓成本:cite[7]
    ContextInfo.position_batches = []    # 存储每批次的[买入价,数量,最高价]
    ContextInfo.stop_loss_ratio = 0.92   # 止损比例从5%放宽至8%:cite[8]
    ContextInfo.take_profit_ratio = 1.12 # 止盈目标从15%降至12%:cite[7]
    ContextInfo.trailing_stop_ratio = 0.06 # 回撤止盈从5%调至6%:cite[1]
    
    # ==== 新增板块联动监控 ====
    ContextInfo.sector_index = '885705.TI'  # 中药板块指数
    ContextInfo.sector_threshold = 0.02     # 板块涨幅超2%增强信号
    
    # 历史数据模式设置
    ContextInfo.history_mode = False
    ContextInfo.lookback_days = 90  # 覆盖近三个月波动周期
    
    print(f"初始化完成 | 标的:{ContextInfo.tradestock} | 均线周期:{ContextInfo.MA_period}日")

def handlebar(ContextInfo):
    try:
        symbol = ContextInfo.tradestock
        
        # =========== 数据获取模块 ===========
        # 获取东阿阿胶与板块指数数据:cite[7]
        tick_data = ContextInfo.get_full_tick([symbol, ContextInfo.sector_index])
        sector_data = tick_data.get(ContextInfo.sector_index, {})
        stock_data = tick_data.get(symbol, {})
        
        # 实时模式数据
        current_price = stock_data.get('last_price', None)
        if current_price is None:
            close_data = ContextInfo.get_history_data(1, '1d', 'close')
            current_price = close_data[symbol][-1] if symbol in close_data else None
        
        # 获取板块涨跌幅:cite[7]
        sector_change = sector_data.get('last_price', 0) / sector_data.get('pre_close', 1) - 1
        
        # =========== 指标计算模块 ===========
        # 计算30日均线
        n_bars = ContextInfo.MA_period + 10
        hist_close = ContextInfo.get_history_data(n_bars, '1d', 'close')
        if symbol not in hist_close or len(hist_close[symbol]) < ContextInfo.MA_period:
            return
        MA30 = pd.Series(hist_close[symbol]).rolling(ContextInfo.MA_period).mean().iloc[-1]
        
        # =========== 账户信息获取 ===========
        account_info = get_trade_detail_data(ContextInfo.accountid, "STOCK", "ACCOUNT")
        cash = account_info[0].m_dBalance if account_info else 0
        position = sum(batch['shares'] for batch in ContextInfo.position_batches)
        
        # =========== 信号增强逻辑 ===========
        # 板块涨幅超2%增强买入信号:cite[7]
        sector_boost = sector_change > ContextInfo.sector_threshold
        buy_signal = (current_price > MA30) or (current_price > MA30*0.98 and sector_boost)
        sell_signal = current_price < MA30*0.98  # 均线下2%触发卖出
        
        # =========== 分批交易执行模块 ===========
        # 买入逻辑（动态批次计算）
        if buy_signal and len(ContextInfo.position_batches) < ContextInfo.batch_size:
            available_batches = ContextInfo.batch_size - len(ContextInfo.position_batches)
            batch_cash = (cash * ContextInfo.risk_ratio) / available_batches
            ask_price = stock_data.get('ask1', current_price*1.002)
            max_shares = int(batch_cash / (ask_price * 100)) * 100
            
            if max_shares >= 100:
                new_batch = {'price': ask_price, 'shares': max_shares, 'high': ask_price}
                ContextInfo.position_batches.append(new_batch)
                order_volume(symbol, max_shares, 0, ContextInfo.accountid, "ORDER_TYPE_BUY", ask_price)
                print(f"▶️ 第{len(ContextInfo.position_batches)}批买入 | 价:{ask_price:.2f} | 量:{max_shares}")
        
        # 卖出逻辑（动态止盈止损）
        sell_batches = []
        for batch in ContextInfo.position_batches:
            batch['high'] = max(batch['high'], current_price)
            profit_ratio = (current_price - batch['price']) / batch['price']
            
            # 触发条件：止盈/移动止盈/止损/技术卖出:cite[8]
            condition_take_profit = profit_ratio >= ContextInfo.take_profit_ratio - 1
            condition_trailing_stop = (batch['high'] - current_price) / batch['high'] >= ContextInfo.trailing_stop_ratio
            condition_stop_loss = current_price <= batch['price'] * ContextInfo.stop_loss_ratio
            condition_technical_sell = sell_signal and profit_ratio > 0  # 盈利时跟随技术信号
            
            if any([condition_take_profit, condition_trailing_stop, condition_stop_loss, condition_technical_sell]):
                sell_batches.append(batch)
        
        # 执行卖出
        for batch in sell_batches:
            bid_price = stock_data.get('bid1', current_price*0.998)
            order_volume(symbol, batch['shares'], 0, ContextInfo.accountid, "ORDER_TYPE_SELL", bid_price)
            ContextInfo.position_batches.remove(batch)
            profit_pct = (bid_price - batch['price']) / batch['price'] * 100
            print(f"◀️ 卖出批次 | 盈亏:{profit_pct:.1f}% | 原因:{'止盈' if profit_pct>0 else '止损'}")
        
        # =========== 监控输出 ===========
        print(f"\n【状态】{symbol} | 价:{current_price:.2f} | MA30:{MA30:.2f}")
        print(f"板块涨跌幅:{sector_change:.2%} | 持仓批次:{len(ContextInfo.position_batches)}")
        print("="*40)
        
    except Exception as e:
        import traceback
        print(f"策略异常: {str(e)}")
        print(traceback.format_exc())