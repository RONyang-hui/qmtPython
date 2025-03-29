#encoding:gbk
import numpy as np
from datetime import datetime

class AdvancedGridStrategy:
    """
    增强型网格交易策略，包含以下优化：
    1. 动态波动率调整网格间距（基于ATR）
    2. 趋势过滤（双均线系统）
    3. 动态中枢重置机制
    4. 金字塔式加仓逻辑
    5. 闲置资金货币基金增强
    6. 多标的支持
    """
    
    def __init__(self):
        self.version = "2.1"
        self.update_date = "2024-05-20"

    def init(self, ContextInfo):
        # ========== 全局参数 ==========
        self.context = ContextInfo
        self.context.trade_stocks = ['600900.SH', '510300.SH']  # 多标的示例
        self.context.accountid = '3556642'
        self.context.risk_free_rate = 0.02  # 无风险利率（货币基金收益率）
        
        # ========== 动态参数初始化 ==========
        self._init_dynamic_params()
        
        # ========== 状态跟踪 ==========
        self.context.grid_data = {
            stock: {
                'positions': {},
                'cost': 0.0,
                'last_action': None
            } for stock in self.context.trade_stocks
        }
        
        print(f"策略初始化完成（版本{self.version}）")

    def handlebar(self, ContextInfo):
        try:
            # ===== 每日预处理 =====
            current_date = datetime.now().strftime("%Y-%m-%d")
            print(f"\n===== {current_date} 策略执行 =====")
            
            # ===== 闲置资金增强 =====
            self._enhance_idle_cash()
            
            # ===== 多标的循环 =====
            for stock in self.context.trade_stocks:
                self._process_single_stock(stock)
                
        except Exception as e:
            print(f"全局异常捕获: {str(e)}")

    # ========== 核心逻辑模块 ==========
    def _process_single_stock(self, stock):
        """ 单标的处理流程 """
        # 获取当前价格
        current_price = self._get_current_price(stock)
        
        # 趋势判断（双均线过滤）
        if not self._check_trend(stock):
            return
            
        # 波动率计算（ATR）
        atr = self._calculate_atr(stock, period=14)
        
        # 动态调整网格参数
        self._adjust_grid_params(stock, current_price, atr)
        
        # 执行网格交易
        self._execute_grid_trading(stock, current_price)
        
        # 风险控制
        self._risk_management(stock, current_price)

    def _adjust_grid_params(self, stock, current_price, atr):
        """ 动态调整网格参数 """
        # 中枢重置条件（价格偏离中枢超20%）
        if (abs(current_price - self.context.grid_center[stock]) / self.context.grid_center[stock]) > 0.2:
            self._reset_grid_center(stock)
            
        # 波动率自适应步长
        new_step = max(0.1, round(atr * 0.6, 2))  # 步长=ATR*60%
        if new_step != self.context.grid_step[stock]:
            print(f"{stock} 网格步长更新: {self.context.grid_step[stock]} → {new_step}")
            self.context.grid_step[stock] = new_step
            self._generate_grid(stock)

    def _execute_grid_trading(self, stock, current_price):
        """ 执行网格交易 """
        grid_prices = self.context.grid_prices[stock]
        last_price = self.context.last_price.get(stock, current_price)
        
        for level in grid_prices:
            # 买入信号：价格下穿网格线
            if (current_price < level) and (last_price >= level):
                self._pyramid_buy(stock, level, current_price)
                
            # 卖出信号：价格上穿网格线且有盈利
            elif (current_price > level) and (last_price <= level):
                self._smart_sell(stock, level, current_price)
                
        self.context.last_price[stock] = current_price

    # ========== 功能模块 ==========
    def _init_dynamic_params(self):
        """ 初始化动态参数 """
        self.context.grid_config = {
            stock: {
                'step': 0.2,  # 初始步长
                'center': None,  # 网格中枢
                'upper': None,
                'lower': None,
                'levels': 10,  # 网格层级
                'position_ratio': 0.05  # 单网格仓位比例
            } for stock in self.context.trade_stocks
        }
        
        # 初始化网格参数
        for stock in self.context.trade_stocks:
            hist_data = self.context.get_history_data(30, '1d', ['high','low','close'], stock)
            closes = [x for x in hist_data['close'] if x > 0]
            self.context.grid_config[stock]['center'] = np.mean(closes[-20:])  # 20日均线作为初始中枢
            self._generate_grid(stock)

    def _generate_grid(self, stock):
        """ 生成网格价格 """
        cfg = self.context.grid_config[stock]
        center = cfg['center']
        step = cfg['step']
        levels = cfg['levels']
        
        # 生成对称网格
        grid_prices = np.round(
            np.arange(center - step*levels, 
                     center + step*(levels+1), 
                     step
        ), 2)
        self.context.grid_prices[stock] = grid_prices.tolist()
        print(f"{stock} 网格更新: {grid_prices}")

    def _pyramid_buy(self, stock, level, price):
        """ 金字塔加仓逻辑 """
        # 基础仓位
        base_qty = self._calculate_position(stock, price)
        
        # 下跌深度加成（每下跌1%增加5%仓位）
        depth = (self.context.grid_config[stock]['center'] - price) / price
        add_ratio = min(0.2, depth * 0.05)  # 最大加成20%
        final_qty = int(base_qty * (1 + add_ratio))
        
        # 执行买入
        if self._check_cash_available(stock, final_qty * price):
            self._place_order(stock, 'BUY', final_qty, price)
            self._update_grid_data(stock, level, final_qty, price)

    def _smart_sell(self, stock, level, price):
        """ 智能卖出（盈利保护+趋势跟踪） """
        cost = self.context.grid_data[stock]['positions'].get(level, {}).get('cost', 0)
        if cost == 0:
            return
            
        # 盈利检查（至少1%收益）
        if (price / cost - 1) < 0.01:
            return
            
        # 趋势加强（价格高于均线逐步减仓）
        ma_ratio = price / self.context.grid_config[stock]['center']
        sell_ratio = min(1.0, max(0.5, ma_ratio - 1.0))  # 价格超中枢10%时卖出50%
        
        hold_qty = self.context.grid_data[stock]['positions'][level]['qty']
        sell_qty = int(hold_qty * sell_ratio)
        
        self._place_order(stock, 'SELL', sell_qty, price)
        self._update_grid_data(stock, level, -sell_qty, price)

    # ========== 风控模块 ==========
    def _risk_management(self, stock, price):
        """ 多层风控体系 """
        # 单标的最大回撤控制
        total_cost = self.context.grid_data[stock]['cost']
        current_value = sum(pos['qty']*price for pos in self.context.grid_data[stock]['positions'].values())
        profit_ratio = (current_value - total_cost) / total_cost if total_cost >0 else 0
        
        # 止损逻辑
        if profit_ratio < -0.07:
            print(f"{stock} 触发止损！")
            self._close_all_positions(stock)
            
        # 波动率熔断
        recent_volatility = self._calculate_volatility(stock, 5)
        if recent_volatility > 0.15:
            print(f"{stock} 波动率超15%，暂停交易")
            self._close_all_positions(stock)

    def _enhance_idle_cash(self):
        """ 闲置资金货币基金增强 """
        idle_cash = self.context.get_available_cash()
        if idle_cash > 10000:  # 超过1万元部分增强
            enhance_amount = idle_cash - 10000
            self.context.order_money('511990.SH', enhance_amount*0.95)  # 95%投入货基

    # ========== 工具函数 ==========
    def _check_trend(self, stock):
        """ 双均线趋势过滤 """
        ma20 = np.mean(self.context.get_history_data(20, '1d', 'close', stock))
        ma60 = np.mean(self.context.get_history_data(60, '1d', 'close', stock))
        return ma20 > ma60  # 仅允许多头趋势交易

    def _calculate_atr(self, stock, period=14):
        """ 计算ATR波动率 """
        hist = self.context.get_history_data(period+1, '1d', ['high','low','close'], stock)
        tr = [max(hist['high'][i]-hist['low'][i], 
             abs(hist['high'][i]-hist['close'][i-1]),
             abs(hist['low'][i]-hist['close'][i-1])) 
             for i in range(1, len(hist))]
        return np.mean(tr[-period:])

    def _reset_grid_center(self, stock):
        """ 重置网格中枢 """
        new_center = np.mean([
            max(self.context.get_history_data(10, '1d', 'high', stock)),
            min(self.context.get_history_data(10, '1d', 'low', stock))
        ])
        self.context.grid_config[stock]['center'] = new_center
        self._generate_grid(stock)
        print(f"{stock} 中枢重置为: {new_center}")

    # ========== 订单管理 ==========
    def _place_order(self, stock, side, qty, price):
        """ 增强订单执行 """
        if side == 'BUY':
            order_price = price * 1.003  # 滑点+手续费
            order_volume(stock, qty, order_price, self.context.accountid)
        else:
            order_price = price * 0.997
            order_volume(stock, -qty, order_price, self.context.accountid)
        print(f"{stock} {side} {qty}股 @ {order_price}")

    def _close_all_positions(self, stock):
        """ 清空标的持仓 """
        current_qty = self.context.get_position(stock)
        if current_qty > 0:
            self._place_order(stock, 'SELL', current_qty, self._get_current_price(stock))

# ========== 策略实例化 ==========
strategy = AdvancedGridStrategy()

def init(ContextInfo):
    strategy.init(ContextInfo)

def handlebar(ContextInfo):
    strategy.handlebar(ContextInfo)