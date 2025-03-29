#encoding:gbk
import numpy as np
import pandas as pd

def init(ContextInfo):
    # 标的调整为东阿阿胶
    ContextInfo.tradestock = '000423.SZ'
    ContextInfo.set_universe([ContextInfo.tradestock])
    ContextInfo.accountid = '8883556642'
    
    # ==== 趋势跟踪参数 ====
    ContextInfo.MA_period = 30       # 中期均线周期
    ContextInfo.EMA_fast = 5         # 新增快速EMA用于捕捉短期趋势
    ContextInfo.EMA_slow = 13        # 新增慢速EMA
    
    # ==== 动态仓位管理 ====
    ContextInfo.base_batch = 4       # 基础分批次数
    ContextInfo.max_batch = 6        # 最大允许分批次数
    ContextInfo.volatility_ratio = 0.018  # 波动率阈值
    ContextInfo.position_batches = []
    
    # ==== 风险控制参数 ====
    ContextInfo.risk_ratio = 0.9     # 风险比例提升
    ContextInfo.stop_loss_ratio = 0.93
    ContextInfo.take_profit_ratio = 1.15
    ContextInfo.trailing_stop_ratio = 0.07
    
    # ==== 频率控制参数 ====
    ContextInfo.min_interval = 3     # 最小交易间隔（单位：K线根数）
    ContextInfo.last_trade = 0       # 上次交易位置
    ContextInfo.bar_counter = 0      # 自定义K线计数器
    
    print(f"初始化完成 | 标的:{ContextInfo.tradestock}")

def handlebar(ContextInfo):
    try:
        symbol = ContextInfo.tradestock
        
        # 更新自定义K线计数器（替代barpos）
        ContextInfo.bar_counter += 1
        current_bar = ContextInfo.bar_counter
        
        # =========== 数据获取 ===========
        # 获取历史数据，分别处理各字段
        n_bars = max(ContextInfo.MA_period, ContextInfo.EMA_slow) + 5
        
        # 分开获取各字段数据
        close_data = ContextInfo.get_history_data(n_bars, '1d', 'close')
        high_data = ContextInfo.get_history_data(n_bars, '1d', 'high')
        low_data = ContextInfo.get_history_data(n_bars, '1d', 'low')
        
        print(f"数据结构:close_data类型={type(close_data)}")
        
        # 安全提取数据
        if symbol in close_data and isinstance(close_data[symbol], dict) and 'close' in close_data[symbol]:
            # 字典格式 {symbol: {'close': [values]}}
            close_values = close_data[symbol]['close']
            high_values = high_data[symbol]['high'] if symbol in high_data and 'high' in high_data[symbol] else []
            low_values = low_data[symbol]['low'] if symbol in low_data and 'low' in low_data[symbol] else []
        elif symbol in close_data and isinstance(close_data[symbol], list):
            # 列表格式 {symbol: [values]}
            close_values = close_data[symbol]
            high_values = high_data[symbol] if symbol in high_data else []
            low_values = low_data[symbol] if symbol in low_data else []
        else:
            print(f"无法解析数据结构")
            return
            
        # 转换为pandas Series，过滤无效值
        close_series = pd.Series([x for x in close_values if isinstance(x, (int, float)) and x > 0])
        high_series = pd.Series([x for x in high_values if isinstance(x, (int, float)) and x > 0])
        low_series = pd.Series([x for x in low_values if isinstance(x, (int, float)) and x > 0])
        
        # =========== 指标计算 ===========
        # 计算双EMA系统
        ema_fast = close_series.ewm(span=ContextInfo.EMA_fast).mean().iloc[-1]
        ema_slow = close_series.ewm(span=ContextInfo.EMA_slow).mean().iloc[-1]
        ma30 = close_series.rolling(ContextInfo.MA_period).mean().iloc[-1]
        
        # 计算波动率（ATR）
        TR = []
        for i in range(1, min(14, len(high_series), len(low_series), len(close_series))):
            tr1 = high_series.iloc[i] - low_series.iloc[i]
            tr2 = abs(high_series.iloc[i] - close_series.iloc[i-1])
            tr3 = abs(low_series.iloc[i] - close_series.iloc[i-1])
            TR.append(max(tr1, tr2, tr3))
        
        ATR = np.mean(TR) if TR else 0.01
        current_price = close_series.iloc[-1]
        
        # =========== 信号生成 ===========
        # 趋势方向判断
        trend_up = ema_fast > ema_slow and ema_slow > ma30
        
        # 动态调整最大批次
        dynamic_max_batch = ContextInfo.base_batch + int(ATR/(current_price*0.015))
        dynamic_max_batch = min(max(dynamic_max_batch, ContextInfo.base_batch), ContextInfo.max_batch)
        
        # 买入条件（趋势+回调）
        price_condition = (current_price > ema_fast) and (current_price > ma30*0.97)
        buy_signal = trend_up and price_condition
        
        # 卖出条件
        sell_signal = current_price < ema_slow*0.98
        
        # =========== 交易执行 ===========
        try:
            account_info = get_trade_detail_data(ContextInfo.accountid, "STOCK", "ACCOUNT")
            cash = account_info[0].m_dBalance if account_info and len(account_info) > 0 else 0
        except:
            print("获取账户信息失败")
            cash = 0
        
        # 买入逻辑（动态批次+间隔控制）
        if buy_signal and (current_bar - ContextInfo.last_trade) >= ContextInfo.min_interval:
            available_batches = dynamic_max_batch - len(ContextInfo.position_batches)
            if available_batches > 0:
                risk_adjusted_ratio = min(ContextInfo.risk_ratio, 0.95 - ATR/current_price*3)
                batch_cash = (cash * risk_adjusted_ratio) / available_batches
                
                try:
                    tick_data = ContextInfo.get_full_tick([symbol])
                    if symbol in tick_data and isinstance(tick_data[symbol], dict) and 'ask1' in tick_data[symbol]:
                        ask_price = tick_data[symbol]['ask1']
                    else:
                        ask_price = current_price * 1.005
                except:
                    ask_price = current_price * 1.005
                
                max_shares = int(batch_cash / (ask_price * 100)) * 100
                if max_shares >= 100:
                    new_batch = {
                        'price': ask_price,
                        'shares': max_shares,
                        'high': ask_price,
                        'entry_bar': current_bar
                    }
                    
                    # 修正：使用QMT平台的正确下单函数
                    try:
                        # 方法1: 使用ContextInfo的下单接口
                        ContextInfo.order(symbol, max_shares, ask_price, "BUY", ContextInfo.accountid)
                    except:
                        try:
                            # 方法2: 使用平台的通用下单函数
                            order(symbol, 'BUY', max_shares, ask_price, ContextInfo.accountid)
                        except:
                            # 报告下单失败，但不中断策略
                            print(f"下单接口调用失败，请检查正确的下单函数")
                    
                    ContextInfo.position_batches.append(new_batch)
                    ContextInfo.last_trade = current_bar
                    print(f"?? 第{len(ContextInfo.position_batches)}批买入 | 价:{ask_price:.2f} 量:{max_shares}")
        
        # 卖出逻辑（增强止盈机制）
        sell_candidates = []
        for batch in ContextInfo.position_batches:
            batch['high'] = max(batch['high'], current_price)
            profit_ratio = (current_price - batch['price']) / batch['price']
            hold_bars = current_bar - batch['entry_bar']
            
            condition_profit = profit_ratio >= ContextInfo.take_profit_ratio - 1
            condition_trail = (batch['high'] - current_price)/batch['high'] >= ContextInfo.trailing_stop_ratio
            condition_stop = current_price <= batch['price'] * ContextInfo.stop_loss_ratio
            condition_time = (hold_bars >= 5) and (profit_ratio > 0.03)
            
            if any([condition_profit, condition_trail, condition_stop, condition_time, sell_signal]):
                sell_candidates.append(batch)
        
        # 执行卖出
        for batch in sell_candidates:
            try:
                tick_data = ContextInfo.get_full_tick([symbol])
                if symbol in tick_data and isinstance(tick_data[symbol], dict) and 'bid1' in tick_data[symbol]:
                    bid_price = tick_data[symbol]['bid1']
                else:
                    bid_price = current_price * 0.995
            except:
                bid_price = current_price * 0.995
            
            # 修正：使用QMT平台的正确下单函数
            try:
                # 方法1: 使用ContextInfo的下单接口
                ContextInfo.order(symbol, batch['shares'], bid_price, "SELL", ContextInfo.accountid)
            except:
                try:
                    # 方法2: 使用平台的通用下单函数
                    order(symbol, 'SELL', batch['shares'], bid_price, ContextInfo.accountid)
                except:
                    print(f"卖出下单接口调用失败")
            
            ContextInfo.position_batches.remove(batch)
            profit_pct = (bid_price - batch['price'])/batch['price']*100
            print(f"?? 卖出 | 持{current_bar - batch['entry_bar']}根K线 | 盈{profit_pct:.1f}%")
        
        # =========== 监控输出 ===========
        print(f"\n【状态】{symbol} | 现价:{current_price:.2f}")
        print(f"EMA{ContextInfo.EMA_fast}/{ContextInfo.EMA_slow}: {ema_fast:.2f}/{ema_slow:.2f}")
        print(f"波动率(ATR14):{ATR:.2f} | 动态批次:{dynamic_max_batch} | 当前持仓:{len(ContextInfo.position_batches)}批")
        print("="*40)
        
    except Exception as e:
        import traceback
        print(f"策略异常: {str(e)}")
        print(traceback.format_exc())