#encoding:gbk
import numpy as np
import time

def init(ContextInfo):
    try:
        ContextInfo.tradestock = '600900.SH'  # 长江电力
        ContextInfo.set_universe([ContextInfo.tradestock])
        ContextInfo.accountid = '3556642'
        
        # 获取历史数据用于ATR计算
        hist_data = ContextInfo.get_history_data(30, '1d', ['high','low','close'])
        if not hist_data or ContextInfo.tradestock not in hist_data:
            print("警告：历史数据获取失败，使用默认网格参数")
            high_prices = []
            low_prices = []
            closes = []
        else:
            high_prices = [x for x in hist_data[ContextInfo.tradestock]['high'] if x > 0]
            low_prices = [x for x in hist_data[ContextInfo.tradestock]['low'] if x > 0]
            closes = [x for x in hist_data[ContextInfo.tradestock]['close'] if x > 0]
        
        # 计算动态ATR (Average True Range)
        if len(closes) > 1:
            true_ranges = []
            for i in range(1, len(closes)):
                tr1 = high_prices[i] - low_prices[i]
                tr2 = abs(high_prices[i] - closes[i-1])
                tr3 = abs(low_prices[i] - closes[i-1])
                true_ranges.append(max(tr1, tr2, tr3))
            atr = np.mean(true_ranges) if true_ranges else 0.3
        else:
            atr = 0.3  # 默认ATR
        
        # 网格参数优化设定
        ContextInfo.grid_upper = max(high_prices[-20:]) if high_prices else 27.0  
        ContextInfo.grid_lower = min(low_prices[-20:]) if low_prices else 25.0
        grid_range = ContextInfo.grid_upper - ContextInfo.grid_lower
        
        # 根据价格区间动态调整网格数量
        if grid_range < 1:
            ContextInfo.grid_count = 6
        elif grid_range < 2:
            ContextInfo.grid_count = 8
        else:
            ContextInfo.grid_count = 10
        
        # 调整网格步长，确保合理值
        ContextInfo.grid_step = max(0.1, min(0.5, round(atr * 0.6, 2)))
        
        # 资金管理参数
        ContextInfo.per_grid_ratio = 0.05   # 每格使用总资产的5%
        ContextInfo.max_risk_ratio = 0.6    # 最多使用60%总资产
        ContextInfo.min_profit_pct = 1.0    # 最小获利百分比(1%)
        ContextInfo.slippage = 0.002        # 滑点估计
        ContextInfo.min_lots = 100          # 最小交易单位
        
        # 生成网格价格列表
        lower_bound = ContextInfo.grid_lower - ContextInfo.grid_step
        upper_bound = ContextInfo.grid_upper + ContextInfo.grid_step * 2
        step = (upper_bound - lower_bound) / (ContextInfo.grid_count - 1)
        
        ContextInfo.grid_prices = np.round(
            np.linspace(lower_bound, upper_bound, ContextInfo.grid_count), 2
        ).tolist()
        
        # 网格状态管理
        ContextInfo.grid_positions = {price: 0 for price in ContextInfo.grid_prices}
        ContextInfo.grid_shares = {price: 0 for price in ContextInfo.grid_prices}
        ContextInfo.grid_cost = {}    # 记录每格买入成本价
        ContextInfo.grid_profits = 0  # 累计网格利润
        ContextInfo.total_position = 0
        ContextInfo.last_price = None
        ContextInfo.last_update = time.time()
        
        # 趋势过滤缓存
        ContextInfo.trend_cache = {"ma20": None, "ma60": None, "timestamp": 0}
        
        print(f"=== 网格交易初始化成功 ===")
        print(f"网格范围: {lower_bound:.2f} - {upper_bound:.2f}")
        print(f"网格步长: {ContextInfo.grid_step:.2f} ({round(ContextInfo.grid_step/closes[-1]*100, 2)}%)")
        print(f"网格数量: {ContextInfo.grid_count}")
        print(f"网格价格: {[round(p, 2) for p in ContextInfo.grid_prices]}")
        
    except Exception as e:
        print(f"初始化异常: {str(e)}")
        import traceback
        print(traceback.format_exc())

def handlebar(ContextInfo):
    try:
        # 检查更新频率 (每60秒更新一次)
        current_time = time.time()
        if current_time - ContextInfo.last_update < 60:
            return
        ContextInfo.last_update = current_time

        # 获取当前价格
        current_price = get_current_price(ContextInfo)
        if not current_price:
            print("获取当前价格失败")
            return
            
        # 趋势过滤 (日线MA20与MA60对比)
        if not check_trend(ContextInfo):
            print(f"趋势不符合交易条件，当前价格: {current_price:.2f}")
            return
            
        # 获取账户信息
        total_assets = get_total_assets(ContextInfo)
        available_cash = get_available_cash(ContextInfo)
        
        # 风险控制检查
        if check_risk_control(ContextInfo, current_price, total_assets):
            return
            
        # 计算每格购买金额
        grid_value = total_assets * ContextInfo.per_grid_ratio
        
        # 首次运行时初始化last_price
        if ContextInfo.last_price is None:
            ContextInfo.last_price = current_price
            print(f"初始价格: {current_price:.2f}")
            return
            
        # 逐格判断交易条件
        for grid_price in ContextInfo.grid_prices:
            # 买入：当价格下穿网格线
            if cross_down(current_price, ContextInfo.last_price, grid_price):
                # 检查该网格是否已持仓和资金是否足够
                if (ContextInfo.grid_positions[grid_price] == 0 and 
                    available_cash >= grid_value * 0.95):
                    
                    # 计算买入数量并执行买入
                    buy_qty = calculate_lots(grid_value, current_price, ContextInfo)
                    if buy_qty >= ContextInfo.min_lots:
                        order_price = min(current_price * 1.002, grid_price * 0.997)
                        execute_order(ContextInfo, 'BUY', buy_qty, order_price)
                        
                        # 更新持仓状态
                        update_position(ContextInfo, grid_price, buy_qty, order_price)
                        print(f"⬇️ 网格买入: {buy_qty}股 @ {order_price:.2f} | 网格: {grid_price:.2f}")
                    
            # 卖出：当价格上穿网格线
            elif cross_up(current_price, ContextInfo.last_price, grid_price):
                # 检查该网格是否有持仓
                if ContextInfo.grid_positions[grid_price] == 1:
                    cost = ContextInfo.grid_cost.get(grid_price, 0)
                    profit_pct = (current_price / cost - 1) * 100 if cost > 0 else 0
                    
                    # 只在有盈利时卖出
                    if profit_pct >= ContextInfo.min_profit_pct:
                        sell_qty = ContextInfo.grid_shares[grid_price]
                        if sell_qty >= ContextInfo.min_lots:
                            order_price = max(current_price * 0.998, grid_price * 1.003)
                            execute_order(ContextInfo, 'SELL', sell_qty, order_price)
                            
                            # 计算利润并更新状态
                            profit = (order_price - cost) * sell_qty
                            ContextInfo.grid_profits += profit
                            
                            # 更新持仓状态
                            update_position(ContextInfo, grid_price, -sell_qty, order_price)
                            print(f"⬆️ 网格卖出: {sell_qty}股 @ {order_price:.2f} | 盈利: {profit:.2f} | 网格: {grid_price:.2f}")
        
        # 更新上次价格
        ContextInfo.last_price = current_price
        
        # 定期状态报告
        print_status(ContextInfo, current_price, total_assets)
        
    except Exception as e:
        print(f"策略执行异常: {str(e)}")
        import traceback
        print(traceback.format_exc())

def get_current_price(ContextInfo):
    """获取当前价格，支持实时和历史模式"""
    try:
        # 尝试获取实时行情
        tick_data = ContextInfo.get_full_tick([ContextInfo.tradestock])
        if tick_data and ContextInfo.tradestock in tick_data:
            return tick_data[ContextInfo.tradestock].get('last_price')
        
        # 实时行情获取失败，回退到日线收盘价
        hist_data = ContextInfo.get_history_data(1, '1d', 'close')
        if hist_data and ContextInfo.tradestock in hist_data:
            return hist_data[ContextInfo.tradestock][-1]
            
        return None
    except:
        return None

def get_total_assets(ContextInfo):
    """获取账户总资产"""
    try:
        account_info = get_trade_detail_data(ContextInfo.accountid, "STOCK", "ACCOUNT")
        if account_info:
            return account_info[0].m_dBalance + account_info[0].m_dMarketValue
        return 100000  # 默认资金
    except:
        return 100000

def get_available_cash(ContextInfo):
    """获取账户可用资金"""
    try:
        account_info = get_trade_detail_data(ContextInfo.accountid, "STOCK", "ACCOUNT")
        if account_info:
            return account_info[0].m_dAvailable
        return 50000  # 默认可用资金
    except:
        return 50000

def check_trend(ContextInfo):
    """检查趋势是否适合交易 (缓存计算结果以提高效率)"""
    current_day = time.strftime('%Y%m%d')
    
    # 如果今日已计算过，直接返回缓存结果
    if ContextInfo.trend_cache["timestamp"] == current_day:
        ma20 = ContextInfo.trend_cache["ma20"]
        ma60 = ContextInfo.trend_cache["ma60"]
    else:
        # 重新计算均线
        hist_data = ContextInfo.get_history_data(60, '1d', 'close')
        if not hist_data or ContextInfo.tradestock not in hist_data:
            return True  # 数据不足时默认允许交易
            
        closes = hist_data[ContextInfo.tradestock]
        ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else None
        ma60 = np.mean(closes) if len(closes) >= 60 else None
        
        # 更新缓存
        ContextInfo.trend_cache = {
            "ma20": ma20,
            "ma60": ma60,
            "timestamp": current_day
        }
    
    # 趋势判断：MA20 > MA60 为多头趋势
    if ma20 is not None and ma60 is not None:
        return ma20 >= ma60 * 0.98  # 允许2%的容差
    return True

def check_risk_control(ContextInfo, current_price, total_assets):
    """风险控制检查"""
    try:
        # 计算当前持仓比例
        position_value = ContextInfo.total_position * current_price
        position_ratio = position_value / total_assets if total_assets > 0 else 0
        
        # 如果持仓比例超过最大风险比例，暂停买入
        if position_ratio > ContextInfo.max_risk_ratio:
            print(f"风险控制: 当前持仓比例 {position_ratio:.1%} 超过限制 {ContextInfo.max_risk_ratio:.1%}")
            return True
            
        return False
    except:
        return False

def calculate_lots(grid_value, price, ContextInfo):
    """计算买入股数(向下取整到100的倍数)"""
    if price <= 0:
        return 0
    shares = int(grid_value / price / ContextInfo.min_lots) * ContextInfo.min_lots
    return max(0, shares)

def execute_order(ContextInfo, direction, qty, price):
    """执行交易订单"""
    try:
        if direction == 'BUY':
            order_volume(ContextInfo.tradestock, qty, 0, 
                        ContextInfo.accountid, "ORDER_TYPE_BUY", price)
        else:
            order_volume(ContextInfo.tradestock, qty, 0, 
                        ContextInfo.accountid, "ORDER_TYPE_SELL", price)
        return True
    except:
        print(f"下单失败: {direction} {qty}股 @ {price:.2f}")
        return False

def update_position(ContextInfo, grid_price, qty, price):
    """更新网格持仓状态"""
    # 更新网格状态
    ContextInfo.grid_positions[grid_price] = 1 if qty > 0 else 0
    ContextInfo.grid_shares[grid_price] = max(0, ContextInfo.grid_shares.get(grid_price, 0) + qty)
    
    # 更新总持仓
    ContextInfo.total_position += qty
    
    # 买入时记录成本，卖出时清除成本记录
    if qty > 0:
        ContextInfo.grid_cost[grid_price] = price * (1 + ContextInfo.slippage)
    elif qty < 0 and ContextInfo.grid_shares[grid_price] == 0:
        ContextInfo.grid_cost.pop(grid_price, None)

def cross_up(current, previous, level):
    """检查价格是否上穿某一水平"""
    return previous <= level and current > level

def cross_down(current, previous, level):
    """检查价格是否下穿某一水平"""
    return previous >= level and current < level

def print_status(ContextInfo, price, total_assets):
    """打印策略状态"""
    # 每10分钟输出一次详细状态(减少日志量)
    if int(time.time()) % 600 < 60:
        active_grids = sum(1 for v in ContextInfo.grid_positions.values() if v > 0)
        
        print("\n==== 网格策略状态 ====")
        print(f"当前价格: {price:.2f} | 总资产: {total_assets:.2f}")
        print(f"持仓总量: {ContextInfo.total_position}股 | 激活网格: {active_grids}/{ContextInfo.grid_count}")
        print(f"累计利润: {ContextInfo.grid_profits:.2f}")
        
        # 显示所有激活的网格
        if active_grids > 0:
            print("\n激活的网格:")
            for grid_price, is_active in ContextInfo.grid_positions.items():
                if is_active:
                    shares = ContextInfo.grid_shares[grid_price]
                    cost = ContextInfo.grid_cost.get(grid_price, 0)
                    profit_pct = (price / cost - 1) * 100 if cost > 0 else 0
                    print(f"  网格 {grid_price:.2f}: {shares}股 | 成本 {cost:.2f} | 盈亏 {profit_pct:.1f}%")
        print("="*30)