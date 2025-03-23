#encoding:gbk

# 导入外部程序包
import numpy as np  # 主要用于科学计算的Python包
import pandas as pd  # 建立在numpy和其他众多第三方库基础上的python包

# 初始化模块
def init(ContextInfo):
    # 设定股票池，即要操作的股票
    ContextInfo.tradestock = '000333.SZ'  # 美的集团
    ContextInfo.set_universe([ContextInfo.tradestock])
    # 设定账号
    ContextInfo.accountid = '55003498'
    
        # 网格交易参数设置（根据美的集团当前价格调整）
    ContextInfo.grid_upper = 85.0  # 上限调整为85元
    ContextInfo.grid_lower = 75.0  # 下限调整为75元
    ContextInfo.grid_count = 5      # 网格数量保持5层
    ContextInfo.per_grid_ratio = 0.15  # 每层使用15%资金

    # 生成网格价格点
    grid_step = (ContextInfo.grid_upper - ContextInfo.grid_lower) / ContextInfo.grid_count
    ContextInfo.grid_prices = [ContextInfo.grid_lower + i * grid_step for i in range(ContextInfo.grid_count + 1)]
# 输出结果示例：[75.0, 77.0, 79.0, 81.0, 83.0, 85.0]
    # 初始化网格状态，0表示未持仓，1表示已持仓
    ContextInfo.grid_positions = [0] * (ContextInfo.grid_count + 1)
    
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
                    # 计算买入股数 (资金除以价格，取整数)
                    buy_shares = int(per_grid_value / current_price / 100) * 100  # 确保是100的整数倍
                    if buy_shares >= 100:  # 最小买入单位是100股
                        # 执行买入
                        order_volume(ContextInfo.accountid, ContextInfo.tradestock, "BUY", buy_shares)
                        ContextInfo.grid_positions[i] = 1  # 标记该网格已持仓
                        print(f"网格交易: 价格下穿{grid_price}，买入{buy_shares}股")
            
            # 价格上穿网格线 (上一个价格在网格线之下，当前价格在网格线之上)
            elif ContextInfo.last_price <= grid_price and current_price > grid_price:
                # 如果该网格已持仓，则卖出
                if ContextInfo.grid_positions[i] == 1:
                    # 获取该网格的持仓数量 (这里简化处理，假设之前买入的数量可以全部卖出)
                    # 实际应用中应该跟踪每个网格的具体持仓
                    position = get_position(ContextInfo.accountid, ContextInfo.tradestock)
                    if position > 0:
                        # 执行卖出
                        sell_shares = min(position, int(per_grid_value / grid_price / 100) * 100)
                        if sell_shares >= 100:
                            order_volume(ContextInfo.accountid, ContextInfo.tradestock, "SELL", sell_shares)
                            ContextInfo.grid_positions[i] = 0  # 标记该网格已清仓
                            print(f"网格交易: 价格上穿{grid_price}，卖出{sell_shares}股")
        
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

# 获取当前股票价格 - 修改为使用ContextInfo.get_history_data
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

# 获取股票持仓数量
def get_position(accountid, stockcode):
    try:
        # 获取当前股票持仓信息
        position_data = get_trade_detail_data(accountid, "STOCK", "POSITION")
        for position in position_data:
            if position.m_strInstrumentID == stockcode:
                return position.m_nVolume
        return 0
    except Exception as e:
        print(f"[ERROR] 获取持仓失败：{str(e)}")
        return 0