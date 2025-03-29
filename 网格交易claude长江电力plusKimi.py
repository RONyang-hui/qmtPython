#encoding:gbk
import numpy as np
import time
from collections import OrderedDict

def init(ContextInfo):
    try:
        # 基本参数
        ContextInfo.tradestock = '600900.SH'
        ContextInfo.set_universe([ContextInfo.tradestock])
        ContextInfo.accountid = '8883556642'
        ContextInfo.max_risk_ratio = 0.6  # 最多使用60%总资产
        ContextInfo.per_grid_ratio = 0.05  # 每格使用总资产的5%
        ContextInfo.min_profit_pct = 1.0  # 最小获利百分比(1%)
        ContextInfo.slippage = 0.002  # 滑点估计
        ContextInfo.min_lots = 100  # 最小交易单位
        
        # 增强版网格参数
        ContextInfo.atr_period = 14  # ATR计算周期
        ContextInfo.grid_scale = 0.5  # ATR调整系数
        ContextInfo.expand_buffer = 2  # 网格扩展缓冲步长
        
        # 高级风险控制
        ContextInfo.max_drawdown = -0.05  # 最大允许回撤
        ContextInfo.position_decay = 0.95  # 持仓衰减系数
        
        # 交易成本参数
        ContextInfo.commission_rate = 0.0003  # 佣金率
        ContextInfo.tax_rate = 0.001  # 印花税率
        
        # 初始化动态网格
        init_dynamic_grid(ContextInfo)
        
        # 趋势分析缓存
        ContextInfo.trend_cache = {
            "ma5": None,
            "ma20": None,
            "ema60": None,
            "last_update": 0
        }
        
        print("=== 智能网格交易系统初始化完成 ===")
        print(f"初始网格范围: {min(ContextInfo.grid_prices):.2f}-{max(ContextInfo.grid_prices):.2f}")
        print(f"动态参数: ATR周期={ContextInfo.atr_period} 网格扩展缓冲={ContextInfo.expand_buffer}步")

    except Exception as e:
        print(f"初始化异常: {str(e)}")
        import traceback
        print(traceback.format_exc())

def init_dynamic_grid(ContextInfo):
    """动态初始化网格参数"""
    try:
        # 获取波动率数据
        hist = get_enhanced_history(ContextInfo, days=ContextInfo.atr_period*2)
        
        # 确保有足够的数据
        if (not hist['high'] or not hist['low'] or not hist['close'] or
            len(hist['high']) < ContextInfo.atr_period or
            len(hist['low']) < ContextInfo.atr_period or
            len(hist['close']) < ContextInfo.atr_period):
            print("警告：历史数据不足，使用默认网格参数")
            # 使用默认值初始化网格
            ContextInfo.grid_upper = 27.0
            ContextInfo.grid_lower = 25.0
            ContextInfo.grid_step = 0.3
            ContextInfo.grid_count = 10
            ContextInfo.grid_prices = np.round(np.linspace(ContextInfo.grid_lower - ContextInfo.grid_step,
                                                         ContextInfo.grid_upper + ContextInfo.grid_step,
                                                         ContextInfo.grid_count), 2).tolist()
            return
        
        # 计算增强ATR
        atr = calculate_real_atr(
            hist['high'], 
            hist['low'], 
            hist['close'],
            ContextInfo.atr_period
        )
        
        # 价格通道计算
        recent_close = hist['close'][-1]
        volatility_band = atr * 3
        upper_band = recent_close + volatility_band
        lower_band = recent_close - volatility_band
        
        # 网格参数动态设定
        grid_step = max(0.1, round(atr * ContextInfo.grid_scale, 2))
        grid_count = int((upper_band - lower_band) / grid_step) + 2
        
        # 生成弹性网格
        base_prices = np.arange(
            lower_band - grid_step*ContextInfo.expand_buffer,
            upper_band + grid_step*(ContextInfo.expand_buffer+1),
            grid_step
        )
        
        # 初始化网格状态
        ContextInfo.grid_prices = np.round(base_prices, 2).tolist()
        ContextInfo.grid_step = grid_step
        ContextInfo.grid_positions = OrderedDict()
        ContextInfo.grid_shares = {}
        ContextInfo.grid_cost = {}
        
        for price in sorted(ContextInfo.grid_prices):
            ContextInfo.grid_positions[price] = 0  # 0:空仓 1:持仓
            ContextInfo.grid_shares[price] = 0
        
        # 状态变量
        ContextInfo.last_extend = 0  # 上次扩展时间
        ContextInfo.total_position = 0
        ContextInfo.grid_profits = 0
        ContextInfo.max_equity = get_total_assets(ContextInfo)  # 用于回撤计算
        
    except Exception as e:
        print(f"网格初始化异常: {str(e)}")
        raise

def handlebar(ContextInfo):
    try:
        # 低频操作控制
        if hasattr(ContextInfo, 'last_update') and time.time() - ContextInfo.last_update < 30:
            return
        ContextInfo.last_update = time.time()
        
        # 获取增强市场数据
        current_price = get_enhanced_price(ContextInfo)
        total_assets = get_total_assets(ContextInfo)
        if not current_price or total_assets <= 0:
            return
            
        # 更新最大权益值
        ContextInfo.max_equity = max(ContextInfo.max_equity, total_assets)
        
        # 增强趋势过滤
        if not enhanced_trend_filter(ContextInfo):
            print("趋势不符合交易条件")
            return
            
        # 动态调整网格
        check_grid_expansion(ContextInfo, current_price)
        
        # 执行网格交易
        process_grid_trading(ContextInfo, current_price, total_assets)
        
        # 风险控制检查
        perform_risk_control(ContextInfo, current_price, total_assets)
        
        # 持仓衰减机制
        decay_positions(ContextInfo)
        
        # 状态报告
        smart_status_report(ContextInfo, current_price)

    except Exception as e:
        print(f"策略执行异常: {str(e)}")
        import traceback
        print(traceback.format_exc())

def enhanced_trend_filter(ContextInfo):
    """增强趋势过滤器"""
    try:
        # 每4小时更新一次趋势数据
        if hasattr(ContextInfo.trend_cache, 'last_update') and time.time() - ContextInfo.trend_cache["last_update"] < 14400:
            return ContextInfo.trend_cache["result"]
            
        # 获取多周期数据
        ma5 = get_moving_average(ContextInfo, 5)
        ma20 = get_moving_average(ContextInfo, 20)
        ema60 = get_exponential_ma(ContextInfo, 60)
        
        # 趋势判断逻辑
        trend_cond1 = ma20 > ema60 * 1.01  # MA20在EMA60上方1%
        trend_cond2 = ma5 > ma20  # 短期趋势向上
        slope = get_ma_slope(ContextInfo, 20)  # MA20斜率
        
        # 综合趋势判断
        trend_ok = trend_cond1 and trend_cond2 and (slope > 0)
        
        # 更新缓存
        ContextInfo.trend_cache.update({
            "ma5": ma5,
            "ma20": ma20,
            "ema60": ema60,
            "last_update": time.time(),
            "result": trend_ok
        })
        
        return trend_ok
        
    except Exception as e:
        print(f"趋势过滤异常: {str(e)}")
        return True

def process_grid_trading(ContextInfo, current_price, total_assets):
    """执行网格交易逻辑"""
    # 动态资金分配
    position_value = ContextInfo.total_position * current_price
    available_ratio = ContextInfo.max_risk_ratio - (position_value / total_assets)
    grid_value = total_assets * ContextInfo.per_grid_ratio * min(1.0, available_ratio*2)
    
    for price in ContextInfo.grid_positions:
        # 买入信号：价格下穿网格且无持仓
        if cross_down(current_price, getattr(ContextInfo, 'last_price', current_price), price):
            if ContextInfo.grid_positions[price] == 0 and grid_value > 0:
                execute_buy(ContextInfo, price, current_price, grid_value)
                
        # 卖出信号：价格上穿网格且有持仓
        elif cross_up(current_price, getattr(ContextInfo, 'last_price', current_price), price):
            if ContextInfo.grid_positions[price] == 1:
                execute_sell(ContextInfo, price, current_price)
    
    ContextInfo.last_price = current_price

def execute_buy(ContextInfo, grid_price, market_price, grid_value):
    """增强买入执行"""
    # 价格合理性检查
    if market_price > grid_price * 1.02:  # 防止异常高价买入
        return
        
    # 获取盘口数据
    tick = ContextInfo.get_full_tick([ContextInfo.tradestock])
    if not tick:
        return
        
    # 计算最优价格
    ask1 = tick[ContextInfo.tradestock].get('ask1_price', market_price)
    price = min(ask1 * 1.001, grid_price * 0.995)  # 保守报价
    
    # 计算委托数量
    available_cash = get_available_cash(ContextInfo)
    commission = price * ContextInfo.min_lots * ContextInfo.commission_rate
    max_qty = int((available_cash - commission) / price // 100) * 100
    qty = min(ContextInfo.min_lots*5, max_qty)  # 限制单次委托量
    
    if qty >= ContextInfo.min_lots:
        if order_volume(ContextInfo.tradestock, qty, 0, ContextInfo.accountid, "ORDER_TYPE_BUY", price):
            update_position(ContextInfo, grid_price, qty, price, 'BUY')
            print(f"智能买入 {qty}股 @ {price:.2f} | 网格: {grid_price:.2f}")

def execute_sell(ContextInfo, grid_price, market_price):
    """增强卖出执行"""
    # 获取持仓信息
    position = ContextInfo.grid_shares.get(grid_price, 0)
    if position < ContextInfo.min_lots:
        return
        
    # 计算保本价格（含交易成本）
    cost_price = ContextInfo.grid_cost.get(grid_price, 0)
    if cost_price <= 0:
        return
        
    # 计算最低卖出价
    min_profit_price = cost_price * (1 + ContextInfo.min_profit_pct/100 + 
                                    ContextInfo.commission_rate*2 + 
                                    ContextInfo.tax_rate)
                                    
    if market_price < min_profit_price:
        return
        
    # 获取盘口数据
    tick = ContextInfo.get_full_tick([ContextInfo.tradestock])
    if not tick:
        return
        
    # 设置智能卖出价
    bid1 = tick[ContextInfo.tradestock].get('bid1_price', market_price)
    price = max(bid1 * 0.999, min_profit_price)
    
    if order_volume(ContextInfo.tradestock, position, 0, ContextInfo.accountid, "ORDER_TYPE_SELL", price):
        profit = calculate_net_profit(position, cost_price, price, ContextInfo)
        ContextInfo.grid_profits += profit
        update_position(ContextInfo, grid_price, -position, price, 'SELL')
        print(f"智能卖出 {position}股 @ {price:.2f} | 净利: {profit:.2f}")

def check_grid_expansion(ContextInfo, current_price):
    """智能网格扩展"""
    if not ContextInfo.grid_prices:
        return
        
    current_max = max(ContextInfo.grid_prices)
    current_min = min(ContextInfo.grid_prices)
    buffer = ContextInfo.grid_step * ContextInfo.expand_buffer
    
    # 向上扩展条件
    if current_price > (current_max - buffer):
        new_prices = []
        next_price = current_max + ContextInfo.grid_step
        while next_price <= current_price + buffer*2:
            new_prices.append(round(next_price, 2))
            next_price += ContextInfo.grid_step
        
        for price in new_prices:
            if price not in ContextInfo.grid_positions:
                ContextInfo.grid_positions[price] = 0
                ContextInfo.grid_shares[price] = 0
        print(f"向上扩展网格至 {new_prices[-1]:.2f}")
    
    # 向下扩展条件
    elif current_price < (current_min + buffer):
        new_prices = []
        next_price = current_min - ContextInfo.grid_step
        while next_price >= current_price - buffer*2:
            new_prices.append(round(next_price, 2))
            next_price -= ContextInfo.grid_step
        
        for price in new_prices:
            if price not in ContextInfo.grid_positions:
                ContextInfo.grid_positions[price] = 0
                ContextInfo.grid_shares[price] = 0
        print(f"向下扩展网格至 {new_prices[-1]:.2f}")
    
    # 保持有序字典
    ContextInfo.grid_positions = OrderedDict(sorted(ContextInfo.grid_positions.items()))
    ContextInfo.grid_prices = list(ContextInfo.grid_positions.keys())

def perform_risk_control(ContextInfo, price, total_assets):
    """增强风险控制"""
    # 回撤控制
    current_equity = total_assets + ContextInfo.grid_profits
    if hasattr(ContextInfo, 'max_equity') and ContextInfo.max_equity > 0:
        drawdown = (current_equity - ContextInfo.max_equity) / ContextInfo.max_equity
        if drawdown < ContextInfo.max_drawdown:
            print(f"触发最大回撤 {drawdown:.2%}，清仓止损")
            liquidate_all(ContextInfo, price)
            return True
    
    # 流动性检查
    hist_volume = ContextInfo.get_history_data(3, '1d', 'volume')
    if hist_volume and ContextInfo.tradestock in hist_volume:
        if hist_volume[ContextInfo.tradestock]['volume'][-1] < 1e6:
            print("流动性不足，暂停交易")
            return True
        
    return False

def liquidate_all(ContextInfo, price):
    """清仓所有持仓"""
    for grid_price in ContextInfo.grid_positions:
        if ContextInfo.grid_positions[grid_price] == 1:
            execute_sell(ContextInfo, grid_price, price)

def decay_positions(ContextInfo):
    """持仓衰减机制"""
    decay_factor = ContextInfo.position_decay ** (1/144)  # 每分钟衰减
    for price in ContextInfo.grid_shares:
        if ContextInfo.grid_shares[price] > 0:
            decayed = int(ContextInfo.grid_shares[price] * decay_factor)
            if decayed < ContextInfo.min_lots:
                ContextInfo.grid_shares[price] = 0
                ContextInfo.grid_positions[price] = 0
                print(f"持仓衰减清仓 @ {price:.2f}")

def smart_status_report(ContextInfo, price):
    """智能状态报告"""
    try:
        if int(time.time()) % 300 < 10:  # 每5分钟报告一次
            active_grids = sum(1 for v in ContextInfo.grid_positions.values() if v > 0)
            total_assets = get_total_assets(ContextInfo)
            current_equity = total_assets + ContextInfo.grid_profits
            if hasattr(ContextInfo, 'max_equity') and ContextInfo.max_equity > 0:
                drawdown = (current_equity - ContextInfo.max_equity) / ContextInfo.max_equity
            else:
                drawdown = 0
            
            print("\n==== 智能网格交易状态 ====")
            print(f"当前价格: {price:.2f} | 总资产: {total_assets:.2f}")
            print(f"持仓总量: {ContextInfo.total_position}股 | 激活网格: {active_grids}/{len(ContextInfo.grid_prices)}")
            print(f"累计利润: {ContextInfo.grid_profits:.2f} | 最大回撤: {drawdown:.2%}")
            
            # 显示所有激活的网格
            if active_grids > 0:
                print("\n激活的网格:")
                for grid_price, is_active in ContextInfo.grid_positions.items():
                    if is_active:
                        shares = ContextInfo.grid_shares[grid_price]
                        cost = ContextInfo.grid_cost.get(grid_price, 0)
                        if cost > 0:
                            profit_pct = (price / cost - 1) * 100
                        else:
                            profit_pct = 0
                        print(f"  网格 {grid_price:.2f}: {shares}股 | 成本 {cost:.2f} | 盈亏 {profit_pct:.1f}%")
            print("="*30)
    except Exception as e:
        print(f"状态报告异常: {str(e)}")

# ----------- 辅助函数增强 -----------
def get_enhanced_history(ContextInfo, days=30):
    """获取多维度历史数据"""
    try:
        return {
            'high': ContextInfo.get_history_data(days, '1d', 'high').get(ContextInfo.tradestock, {}).get('high', []),
            'low': ContextInfo.get_history_data(days, '1d', 'low').get(ContextInfo.tradestock, {}).get('low', []),
            'close': ContextInfo.get_history_data(days, '1d', 'close').get(ContextInfo.tradestock, {}).get('close', []),
            'volume': ContextInfo.get_history_data(days, '1d', 'volume').get(ContextInfo.tradestock, {}).get('volume', [])
        }
    except:
        return {'high':[], 'low':[], 'close':[], 'volume':[]}

def calculate_real_atr(highs, lows, closes, period):
    """计算真实ATR（带异常值处理）"""
    true_ranges = []
    for i in range(1, min(len(highs), len(lows), len(closes))):
        h, l, c_prev = highs[i], lows[i], closes[i-1]
        tr1 = h - l
        tr2 = abs(h - c_prev)
        tr3 = abs(l - c_prev)
        true_ranges.append(max(tr1, tr2, tr3))
    
    # 异常值过滤（去除前10%最大值）
    if len(true_ranges) > 5:
        sorted_tr = sorted(true_ranges)
        cutoff = sorted_tr[int(len(sorted_tr)*0.9)]
        true_ranges = [min(tr, cutoff) for tr in true_ranges]
    
    return np.mean(true_ranges[-period:]) if true_ranges else 0.3

def get_exponential_ma(ContextInfo, window):
    """计算指数移动平均"""
    closes = ContextInfo.get_history_data(window*2, '1d', 'close').get(ContextInfo.tradestock, {}).get('close', [])
    closes = closes[-window*2:]
    if len(closes) < window:
        return None
    weights = np.exp(np.linspace(-1., 0., window))
    weights /= weights.sum()
    return np.dot(closes[-window:], weights)

def calculate_net_profit(qty, cost, price, ContextInfo):
    """计算净收益（扣除所有费用）"""
    buy_cost = cost * qty * (1 + ContextInfo.slippage)
    buy_commission = buy_cost * ContextInfo.commission_rate
    sell_revenue = price * qty * (1 - ContextInfo.slippage)
    sell_commission = sell_revenue * ContextInfo.commission_rate
    sell_tax = sell_revenue * ContextInfo.tax_rate
    return sell_revenue - sell_commission - sell_tax - buy_cost - buy_commission

def get_enhanced_price(ContextInfo):
    """获取增强价格数据（支持多源）"""
    try:
        # 尝试获取实时行情
        tick_data = ContextInfo.get_full_tick([ContextInfo.tradestock])
        if tick_data and ContextInfo.tradestock in tick_data:
            return tick_data[ContextInfo.tradestock].get('last_price')
        
        # 回退到分钟K线
        hist_data = ContextInfo.get_history_data(1, '1m', 'close').get(ContextInfo.tradestock, {}).get('close', [])
        if hist_data:
            return hist_data[-1]
            
        # 最后回退到日线
        hist_data = ContextInfo.get_history_data(1, '1d', 'close').get(ContextInfo.tradestock, {}).get('close', [])
        if hist_data:
            return hist_data[-1]
            
        return None
    except Exception as e:
        print(f"获取价格异常: {str(e)}")
        return None

def get_total_assets(ContextInfo):
    """获取账户总资产"""
    try:
        # 模拟获取账户信息
        account_info = {
            'balance': 100000,
            'market_value': 0
        }
        return account_info.get('balance', 0) + account_info.get('market_value', 0)
    except Exception as e:
        print(f"获取总资产异常: {str(e)}")
        return 100000

def get_available_cash(ContextInfo):
    """获取账户可用资金"""
    try:
        # 模拟获取账户信息
        account_info = {
            'available': 50000
        }
        return account_info.get('available', 0)
    except Exception as e:
        print(f"获取可用资金异常: {str(e)}")
        return 50000

def get_moving_average(ContextInfo, window):
    """计算简单移动平均"""
    closes = ContextInfo.get_history_data(window*2, '1d', 'close').get(ContextInfo.tradestock, {}).get('close', [])
    closes = closes[-window*2:]
    if len(closes) < window:
        return None
    return np.mean(closes[-window:])

def get_ma_slope(ContextInfo, window):
    """计算移动平均斜率"""
    ma1 = get_moving_average(ContextInfo, window)
    ma2 = get_moving_average(ContextInfo, window+1)
    if ma1 is None or ma2 is None:
        return 0
    return (ma1 - ma2) / ma1

def cross_up(current, previous, level):
    """检查价格是否上穿某一水平"""
    return previous <= level and current > level

def cross_down(current, previous, level):
    """检查价格是否下穿某一水平"""
    return previous >= level and current < level

def update_position(ContextInfo, grid_price, qty, price, direction):
    """更新网格持仓状态"""
    try:
        # 更新网格状态
        ContextInfo.grid_positions[grid_price] = 1 if qty > 0 else 0
        ContextInfo.grid_shares[grid_price] = max(0, ContextInfo.grid_shares.get(grid_price, 0) + qty)
        
        # 更新总持仓
        ContextInfo.total_position += qty
        
        # 买入时记录成本，卖出时清除成本记录
        if qty > 0 and direction == 'BUY':
            ContextInfo.grid_cost[grid_price] = price * (1 + ContextInfo.slippage)
        elif qty < 0 and direction == 'SELL' and ContextInfo.grid_shares[grid_price] == 0:
            ContextInfo.grid_cost.pop(grid_price, None)
    except Exception as e:
        print(f"更新持仓状态异常: {str(e)}")