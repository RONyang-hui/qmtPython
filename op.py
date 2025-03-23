#encoding:gbk

# 导入外部程序包
import numpy as np  # 主要用于科学计算的Python包
import pandas as pd  # 建立在numpy和其他众多第三方库基础上的python包

# 初始化模块
def init(ContextInfo):
    # 设定股票池，即要操作的股票
    ContextInfo.tradestock = '603833.SH'  # 欧派家居
    ContextInfo.set_universe([ContextInfo.tradestock])
    # 设定账号
    ContextInfo.accountid = '8883556642'
    
    # 网格交易参数设置
    ContextInfo.grid_upper = 70.0  # 网格上限价格
    ContextInfo.grid_lower = 60.0  # 网格下限价格
    ContextInfo.grid_count = 10    # 网格数量
    ContextInfo.per_grid_ratio = 0.10  # 每个网格使用的资金比例(总资金的10%)

    # 生成网格价格点
    grid_step = (ContextInfo.grid_upper - ContextInfo.grid_lower) / ContextInfo.grid_count
    ContextInfo.grid_prices = [ContextInfo.grid_lower + i * grid_step for i in range(ContextInfo.grid_count + 1)]
    # 初始化网格状态，0表示未持仓，1表示已持仓
    ContextInfo.grid_positions = [0] * (ContextInfo.grid_count + 1)
    
    # 记录每个网格持有的股票数量
    ContextInfo.grid_shares = [0] * (ContextInfo.grid_count + 1)
    
    # 记录上一次的价格，用于判断价格穿越网格线
    ContextInfo.last_price = 0
    
    # 打印网格信息
    print("网格交易策略初始化完成")
    print(f"交易标的: {ContextInfo.tradestock}")
    print(f"网格上限: {ContextInfo.grid_upper}")
    print(f"网格下限: {ContextInfo.grid_lower}")
    print(f"网格数量: {ContextInfo.grid_count}")
    print(f"网格价格点: {ContextInfo.grid_prices}")

# 基本运行模块
def handlebar(ContextInfo):
    try:
        # 使用get_history_data获取当前最新价格
        current_price = get_current_price(ContextInfo.tradestock, ContextInfo)
        
        # 如果是首次运行，初始化last_price
        if ContextInfo.last_price == 0:
            ContextInfo.last_price = current_price
            return
        
        # 获取账户资金
        totalvalue = get_totalvalue(ContextInfo.accountid, 'STOCK')
        
        # 单网格资金
        per_grid_value = totalvalue * ContextInfo.per_grid_ratio
        
        # 检查每个网格线
        for i in range(len(ContextInfo.grid_prices)):
            grid_price = ContextInfo.grid_prices[i]
            
            # 价格下穿网格线 (上一个价格在网格线之上，当前价格在网格线之下)
            if ContextInfo.last_price >= grid_price and current_price < grid_price:
                # 如果该网格未持仓，则买入
                if ContextInfo.grid_positions[i] == 0:
                    # 计算买入金额
                    buy_value = per_grid_value
                    if buy_value >= 5000:  # 最小买入金额设为5000元
                        # 获取当前持仓总金额
                        current_position_value = get_position_value(ContextInfo.accountid, ContextInfo.tradestock)
                        # 计算买入后的目标持仓金额
                        target_value = current_position_value + buy_value
                        # 执行买入 - 使用order_target_value
                        order_target_value(ContextInfo.tradestock, target_value, ContextInfo, ContextInfo.accountid)
                        # 估算买入的股数
                        ContextInfo.grid_shares[i] = int(buy_value / current_price / 100) * 100
                        ContextInfo.grid_positions[i] = 1  # 标记该网格已持仓
                        print(f"网格交易: 价格下穿{grid_price}，买入约{ContextInfo.grid_shares[i]}股，价值约{buy_value:.2f}元")
            
            # 价格上穿网格线 (上一个价格在网格线之下，当前价格在网格线之上)
            elif ContextInfo.last_price <= grid_price and current_price > grid_price:
                # 如果该网格已持仓，则卖出
                if ContextInfo.grid_positions[i] == 1 and ContextInfo.grid_shares[i] > 0:
                    # 获取当前持仓总金额
                    current_position_value = get_position_value(ContextInfo.accountid, ContextInfo.tradestock)
                    # 要卖出的金额
                    sell_value = current_price * ContextInfo.grid_shares[i]
                    # 计算卖出后的目标持仓金额
                    target_value = max(0, current_position_value - sell_value)
                    # 执行卖出 - 使用order_target_value
                    order_target_value(ContextInfo.tradestock, target_value, ContextInfo, ContextInfo.accountid)
                    print(f"网格交易: 价格上穿{grid_price}，卖出约{ContextInfo.grid_shares[i]}股，价值约{sell_value:.2f}元")
                    ContextInfo.grid_positions[i] = 0  # 标记该网格已清仓
                    ContextInfo.grid_shares[i] = 0  # 清空该网格的持仓数量
        
        # 更新上一次价格
        ContextInfo.last_price = current_price
        
    except Exception as e:
        print(f"[ERROR] 执行网格交易发生异常: {str(e)}")

# 获取账户资金
def get_totalvalue(accountid, datatype):  # （账号，商品类型）# 调用模块：获取账户资金
    result = 0  # 设置值为0
    resultlist = get_trade_detail_data(accountid, datatype, "ACCOUNT")  # （账号，商品类型，账户类型）
    for obj in resultlist:
        result = obj.m_dBalance  # 账户可用资金余额
    return result

# 获取当前股票价格 - 使用ContextInfo.get_history_data
def get_current_price(stockcode, ContextInfo):
    try:
        # 使用ContextInfo.get_history_data获取价格
        price_data = ContextInfo.get_history_data(1, '1d', 'close')
        if stockcode in price_data:
            return price_data[stockcode][-1]  # 返回最新价格
        return 0
    except Exception as e:
        print(f"[ERROR] 获取价格失败：{str(e)}")
        return 0

# 获取股票持仓价值
def get_position_value(accountid, stockcode):
    try:
        position_data = get_trade_detail_data(accountid, "STOCK", "POSITION")
        for position in position_data:
            if position.m_strInstrumentID == stockcode:
                # 持仓数量 * 当前价格
                return position.m_nVolume * position.m_dNewPrice
        return 0
    except Exception as e:
        print(f"[ERROR] 获取持仓价值失败：{str(e)}")
        return 0