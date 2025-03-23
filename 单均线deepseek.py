以下是整合了**分批建仓、动态止盈止损**的完整策略代码：

```python
#encoding:gbk
import numpy as np
import pandas as pd

def init(ContextInfo):
    ContextInfo.tradestock = '000333.SZ'
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

---

### **代码核心功能说明**

| 模块            | 功能说明                                                                 |
|-----------------|--------------------------------------------------------------------------|
| **分批建仓**    | 将总仓位分3次建立，每批使用1/3资金，降低单次买入风险                     |
| **三重退出机制**| 1. 固定止盈(15%)<br>2. 移动止盈(从最高点回撤5%)<br>3. 强制止损(5%)       |
| **动态跟踪**    | 实时记录每个批次的历史最高价，用于计算移动止盈                           |
| **异常处理**    | 实时/历史模式自动切换，数据不足时跳过交易                                |
| **监控界面**    | 实时显示持仓批次、盈亏比例、信号状态等关键信息                           |

---

### **使用示例**
假设某次交易过程：
```
1. 价格突破MA20(100元)→ 第1批买入1000股@102元
2. 价格上涨至110元→更新最高价为110元
3. 价格回落至104.5元→触发移动止盈(回撤5%)→卖出该批次
   → 盈利：(104.5-102)/102=2.45%
4. 价格再次突破MA20→第2批买入900股@105元
5. 价格涨至120元→触发固定止盈(15%)→卖出
   → 盈利：(120-105)/105=14.28%
```

---

### **参数调节建议**
```python
# 风险偏好型设置
ContextInfo.batch_size = 2           # 减少分批次数
ContextInfo.take_profit_ratio = 1.20 # 提高止盈比例
ContextInfo.stop_loss_ratio = 0.90   # 放宽止损

# 保守型设置
ContextInfo.batch_size = 5           # 增加分批次数
ContextInfo.trailing_stop_ratio = 0.03 # 收紧移动止盈
ContextInfo.stop_loss_ratio = 0.97   # 严格止损
```

---

### **注意事项**
1. 需确保交易接口支持`get_trade_detail_data`和`order_volume`函数
2. 回测时建议将`lookback_days`设为MA周期的2-3倍
3. 实际交易中可添加`time.sleep()`避免频繁报单
4. 建议搭配5%的总体仓位控制使用（通过调整`risk_ratio`参数）






---

### **假设场景设定（账户50,000元）**
- **账户资金**：50,000元现金（无持仓）
- **标的股票**：000333.SZ（假设当前价格=20元，MA20=19.5元）
- **策略参数**：
  - 分3批建仓
  - 止盈15%、止损5%、移动止盈回撤5%
  - 风险比例95%（可用资金=50,000×0.95=47,500元）

---

### **周一交易流程模拟**

#### **09:30 开盘**
- **实时数据**：
  - 最新价 `20.1元`（突破MA20=19.5元）
  - 买一价 `20.05元`，卖一价 `20.15元`
- **策略运行**：
  1. **信号判断**：当前价(20.1) > MA20(19.5) → **触发买入信号**
  2. **第1批建仓**：
     - 每批资金：47,500元 / 3批 ≈ **15,833元/批**
     - 可买股数：`15,833元 / 20.15元 ≈ 785股` → 取整为**700股**（A股需100股整数倍，按低价保守计算）
     - **实际买入**：700股 @20.15元，花费 `700×20.15=14,105元`
     - 剩余现金：50,000 - 14,105 = **35,895元**
     - 持仓批次记录：`[{价:20.15, 数量:700, 最高价:20.15}]`

---

#### **10:30 价格上涨**
- **实时数据**：
  - 最新价 `21.5元`（MA20仍为19.5元）
  - 当前批次最高价更新为 `21.5元`
- **策略运行**：
  1. **信号判断**：价格仍高于MA20 → **不触发卖出**
  2. **动态跟踪**：
     - 当前盈利：`(21.5-20.15)/20.15 ≈ +6.7%`（未达止盈条件）
     - 移动止盈回撤：`(21.5 - 当前价)/21.5 = 0%` → **不触发**
  3. **第2批建仓**：
     - 剩余批次：3批 - 1批 = 2批可用
     - 可用资金：47,500元 - 14,105元 = 33,395元 → **16,697.5元/批**
     - 可买股数：`16,697.5元 / 21.5元 ≈ 776股` → 取整为**700股**（避免冲击市场）
     - **实际买入**：700股 @21.5元，花费 `700×21.5=15,050元`
     - 剩余现金：35,895 - 15,050 = **20,845元**
     - 持仓批次更新：  
       `[{价:20.15, 数量:700, 最高价:21.5}, {价:21.5, 数量:700, 最高价:21.5}]`

---

#### **13:30 价格震荡**
- **实时数据**：
  - 最新价 `22.3元` → 批次1最高价更新至 `22.3元`
  - MA20缓慢上升至 `20.0元`
- **策略运行**：
  1. **信号判断**：价格仍高于MA20 → **继续持有**
  2. **第3批建仓**：
     - 剩余批次：3批 - 2批 = 1批可用
     - 可用资金：47,500元 - (14,105+15,050)=18,345元 → **18,345元/批**
     - 可买股数：`18,345元 / 22.3元 ≈ 822股` → 取整为**800股**
     - **实际买入**：800股 @22.3元，花费 `800×22.3=17,840元`
     - 剩余现金：20,845 - 17,840 = **3,005元**
     - 持仓批次更新：  
       `[{价:20.15, 数量:700, 最高价:22.3}, {价:21.5, 数量:700, 最高价:22.3}, {价:22.3, 数量:800, 最高价:22.3}]`

---

#### **14:00 价格回调**
- **实时数据**：
  - 最新价 `21.0元`（从最高22.3元下跌）
  - 移动止盈回撤计算：`(22.3-21.0)/22.3 ≈ 5.8% > 5%`
- **策略运行**：
  1. **触发移动止盈**：
     - 卖出第1批持仓（700股@20.15元）
     - 卖出价=买一价 `20.95元`
     - 盈利：`(20.95-20.15)/20.15 ≈ +3.97%` → 实际盈利 `700×0.8=560元`
  2. **资金变化**：
     - 现金恢复：3,005 + 700×20.95 = **17,670元**
     - 剩余持仓：  
       `[{价:21.5, 数量:700, 最高价:22.3}, {价:22.3, 数量:800, 最高价:22.3}]`

---

#### **14:30 价格二次下跌**
- **实时数据**：
  - 最新价 `20.5元`（跌破MA20=20.0元）
  - **触发卖出信号**
- **策略运行**：
  1. **强制平仓所有批次**（因价格跌破MA20）：
     - 卖出第2批（700股@21.5元）：  
       卖出价=20.5元，亏损 `(20.5-21.5)/21.5 ≈ -4.65%` → 亏损 `700×1.0=700元`
     - 卖出第3批（800股@22.3元）：  
       卖出价=20.5元，亏损 `(20.5-22.3)/22.3 ≈ -8.07%` → 亏损 `800×1.8=1,440元`
  2. **最终资金**：
     - 现金总额：17,670 + (700×20.5) + (800×20.5) = **17,670 + 14,350 + 16,400 = 48,420元**
     - 总亏损：50,000 - 48,420 = **-1,580元**（-3.16%）

---

### **关键差异（对比5,000元账户）**
| 场景               | 5,000元账户               | 50,000元账户               |
|--------------------|--------------------------|---------------------------|
| **单批次交易量**   | 100股                    | 700-800股                 |
| **价格冲击影响**    | 可忽略                   | 可能影响卖一档流动性       |
| **止损执行难度**    | 容易成交                 | 大额卖单可能导致滑点       |
| **单日最大回撤**   | -3.16%                  | -3.16%（同比例）          |

---

### **策略优化建议（针对大资金）**
1. **增加分批次数**：  
   将 `batch_size` 从3改为5，降低单批交易量，减少市场冲击。  
   ```python
   ContextInfo.batch_size = 5  # 分5批建仓
   ```

2. **动态调整止盈**：  
   根据持仓规模提高止盈比例，例如：  
   ```python
   # 持仓越多，止盈比例越高（例：每500股增加1%）
   profit_ratio = 0.15 + (total_shares // 500) * 0.01
   ```

3. **滑点控制**：  
   大额订单拆分为多笔小单，避免集中成交：  
   ```python
   # 示例：将700股拆分为7笔100股
   for _ in range(7):
       order_volume(symbol, 100, ...)
   ```

4. **波动率过滤**：  
   增加ATR指标过滤，避免在低波动时段建仓：  
   ```python
   # 若ATR(14)<2%，暂停交易
   atr = calculate_ATR(14)
   if atr < 0.02 * current_price:
       pause_trading()
   ```

---

### **总结**
- **大资金优势**：  
  能更充分分摊成本，但需注意流动性风险。
- **核心风险**：  
  单批次亏损绝对值放大（示例中单批最大亏损1,440元），需严格止损。
- **参数适配**：  
  资金量扩大10倍时，建议同步调整 `batch_size` 和 `trailing_stop_ratio` 以平衡风险。