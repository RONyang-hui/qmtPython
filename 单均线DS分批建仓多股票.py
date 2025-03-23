## 推荐股票及代码修改

根据您的需求，以下是检索到的适合单均线策略的A股股票推荐及代码修改：

### 推荐股票
根据基本面情况（现金流、ROA、负债率等关键指标），推荐以下股票：
- **贵州茅台（600519.SH）**：作为白酒行业的龙头企业，具有稳定的现金流、较高的ROA和较低的负债率。
- **美的集团（000333.SZ）**：家电行业的领军企业，基本面稳健，现金流充裕，ROA表现良好。
- **招商银行（600036.SH）**：银行业绩稳定，资产质量良好，负债率控制合理。
- **中国平安（601318.SH）**：保险行业巨头，现金流稳定，ROA表现优异。
- **海康威视（002415.SZ）**：安防领域龙头企业，基本面良好，负债率较低。

### 修改后的代码
以下是将推荐股票整合到您的策略代码中，并替换股票号等的修改代码：

```python
#encoding:gbk
import numpy as np
import pandas as pd

def init(ContextInfo):
    # 推荐的股票列表
    ContextInfo.tradestock = '600519.SH'  # 贵州茅台
    # ContextInfo.tradestock = '000333.SZ'  # 美的集团
    # ContextInfo.tradestock = '600036.SH'  # 招商银行
    # ContextInfo.tradestock = '601318.SH'  # 中国平安
    # ContextInfo.tradestock = '002415.SZ'  # 海康威视
    ContextInfo.set_universe([ContextInfo.tradestock])
    ContextInfo.accountid = '8883556642'
    
    # 基础策略参数
    ContextInfo.MA_period = 20
    ContextInfo.VOL_MA_period = 10
    ContextInfo.risk_ratio = 0.95
    
    # 分批交易参数
    ContextInfo.batch_size = 3          # 分批建仓次数
    ContextInfo.position_batches = []   # 存储每批次的[买入价,数量,最高价]
    ContextInfo.stop_loss_ratio = 0.95   # 止损比例(5%)
    ContextInfo.take_profit_ratio = 1.15 # 止盈比例(15%)
    ContextInfo.trailing_stop_ratio = 0.05 # 移动止盈回撤比例(5%)
    
    # 历史数据模式设置
    ContextInfo.history_mode = False
    ContextInfo.lookback_days = 60
    
    print(f"初始化完成 | 标的:{ContextInfo.tradestock} | 分批次数:{ContextInfo.batch_size}")

def handlebar(ContextInfo):
    try:
        symbol = ContextInfo.tradestock
        
        # =========== 数据获取模块 ===========
        use_history_mode = False
        tick_data = ContextInfo.get_full_tick([symbol])
        
        # 实时模式数据
        if not use_history_mode and tick_data and symbol in tick_data:
            tick = tick_data[symbol]
            current_price = tick.get('last_price', None)
            bid_price = tick.get('bid1', current_price*0.998 if current_price else None)
            ask_price = tick.get('ask1', current_price*1.002 if current_price else None)
            current_volume = tick.get('volume', 0)
            
            if None in [current_price, bid_price, ask_price]:
                print("实时数据异常，切换历史模式")
                use_history_mode = True

        # 历史模式数据
        if use_history_mode or not tick_data:
            close_data = ContextInfo.get_history_data(ContextInfo.lookback_days, '1d', 'close')
            if symbol not in close_data or len(close_data[symbol]) < ContextInfo.MA_period:
                print("历史数据不足")
                return
                
            close_prices = close_data[symbol]
            current_price = close_prices[-1]
            bid_price = current_price * 0.998
            ask_price = current_price * 1.002
            print(f"历史模式 | 最新价:{current_price:.2f}")

        # =========== 指标计算模块 ===========
        # 获取足够的历史数据
        n_bars = ContextInfo.MA_period + 10
        hist_close = ContextInfo.get_history_data(n_bars, '1d', 'close')
        if symbol not in hist_close or len(hist_close[symbol]) < ContextInfo.MA_period:
            print("指标数据不足")
            return
            
        close_series = hist_close[symbol]
        MA20 = pd.Series(close_series).rolling(ContextInfo.MA_period).mean().values[-1]
        
        # =========== 账户信息获取 ===========
        account_info = get_trade_detail_data(ContextInfo.accountid, "STOCK", "ACCOUNT")
        if not account_info:
            print("账户信息获取失败")
            return
            
        cash = account_info[0].m_dBalance
        position = sum(batch['shares'] for batch in ContextInfo.position_batches)
        
        # =========== 信号生成模块 ===========
        buy_signal = current_price > MA20
        sell_signal = current_price < MA20
        
        # =========== 分批交易执行模块 ===========
        # 买入逻辑（分批次建仓）
        if buy_signal and len(ContextInfo.position_batches) < ContextInfo.batch_size:
            available_batches = ContextInfo.batch_size - len(ContextInfo.position_batches)
            batch_cash = (cash * ContextInfo.risk_ratio) / available_batches
            max_shares = int(batch_cash / (ask_price * 100)) * 100
            
            if max_shares >= 100:
                # 记录批次信息
                new_batch = {
                    'price': ask_price,
                    'shares': max_shares,
                    'high': ask_price  # 初始化最高价
                }
                ContextInfo.position_batches.append(new_batch)
                # 执行买入
                order_volume(symbol, max_shares, 0, ContextInfo.accountid, "ORDER_TYPE_BUY", ask_price)
                print(f"▶️ 第{len(ContextInfo.position_batches)}批买入 | 数量:{max_shares} | 成本:{ask_price:.2f}")

        # 卖出逻辑（动态止盈止损）
        sell_batches = []
        for batch in ContextInfo.position_batches:
            # 更新最高价
            batch['high'] = max(batch['high'], current_price)
            
            # 止盈条件
            take_profit = current_price >= batch['price'] * ContextInfo.take_profit_ratio
            # 移动止盈（从最高点回撤）
            trailing_stop = (batch['high'] - current_price) / batch['high'] >= ContextInfo.trailing_stop_ratio
            # 止损条件
            stop_loss = current_price <= batch['price'] * ContextInfo.stop_loss_ratio
            
            if sell_signal or take_profit or trailing_stop or stop_loss:
                sell_batches.append(batch)

        # 执行卖出
        for batch in sell_batches:
            order_volume(symbol, batch['shares'], 0, ContextInfo.accountid, "ORDER_TYPE_SELL", bid_price)
            ContextInfo.position_batches.remove(batch)
            profit = (bid_price - batch['price']) / batch['price'] * 100
            print(f"◀️ 批次卖出 | 数量:{batch['shares']} | 盈亏:{profit:.1f}%")

        # =========== 监控输出 ===========
        print(f"\n【策略状态】{'历史' if use_history_mode else '实时'}模式")
        print(f"当前价:{current_price:.2f} | MA20:{MA20:.2f}")
        print(f"持仓批次:{len(ContextInfo.position_batches)} | 总股数:{position}")
        print("---------------------------------")
        
    except Exception as e:
        import traceback
        print(f"策略异常: {str(e)}")
        print(traceback.format_exc())

def get_position(accountid, symbol):
    try:
        positions = get_trade_detail_data(accountid, "STOCK", "POSITION")
        return next((p for p in positions if p.m_strInstrumentID == symbol), None)
    except:
        return None
```

### 使用说明
1. **股票选择**：根据基本面情况，选择了贵州茅台、美的集团、招商银行、中国平安和海康威视作为推荐股票。您可以根据实际情况选择其中一只股票进行交易。
2. **代码修改**：将代码中的`ContextInfo.tradestock`变量修改为您选择的股票代码。
3. **策略运行**：运行修改后的代码，策略将根据单均线策略对选定的股票进行分批建仓和动态止盈止损操作。

希望以上内容对您有所帮助！