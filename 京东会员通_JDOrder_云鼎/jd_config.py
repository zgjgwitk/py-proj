r"""
京东云鼎接口公共配置文件。
包含 getAuthInfo 所需参数及品牌配置表。
"""

# getAuthInfo 参数
APP_KEY: str = "C3AE5FE08E8AAB3FA6E38786F8F4F11F"          # 京东开放平台 AppKey
APP_SECRET: str = "a88abef8b14b4ab3baaf367729394c59"    # 京东开放平台 AppSecret

# 品牌配置表: key=品牌ID, value=(access_token, vender_id) , 来源: SELECT * FROM `ed_base_brand_jd_auth`
BRAND_CONFIGS: dict[int, tuple[str, str]] = {
    # cfg 184-UOOYAA乌丫旗舰店
    184: ("f018b940b8374693a92b1340b92e0c3eizja", "11948323"),
    # cfg 190-牧高笛官方旗舰店
    190: ("c632b7007d074fae81153eb8bc410b94mi3m", "48289"),
    # cfg 1149-CANADA GOOSE官方旗舰店
    1149: ("ab37522890434a82a6ba01de41d47cc5nzuy", "11778525"),
    # cfg 3956-驿氪yike店
    3956: ("aabfb33f76b14f0b87481882109585d2izmi", "17314074"),
    # cfg 5417-ROCK&RIDE珠宝首饰旗舰店
    5417: ("ad7621b90b304bd083d4ef3a96f808d6ixyj", "12438408"),
    # cfg 6930-蕉下官方旗舰店
    6930: ("430ec5f3f4b74ff5862327ddade35800mwzw", "42264"),
    # cfg 6973-京东奥莱官方旗舰店
    6973: ("730003f378f044e1979a17077a252db3mwmd", "17867506"),
    # cfg 7091-Moose Knuckles官方旗舰店
    7091: ("9870b1a3ed0d4a6d829667fe01cd5d7exytn", "12148396"),
    # cfg 7126-MARIUS官方旗舰店
    7126: ("30acb342fe0f46da86b17b3fa86ef389mmzb", "19120634"),
}

# 与云鼎中转约定的 AES 加密 Key(参考 C# 代码常量)
AUTH_SECRET: str = "EGD3F4FE3F64D8EBE2DDC997B1F1FA3"

# 京东云鼎主机配置: key=主机类型, value=(基础地址, 接口路径前缀, serviceStep)
# Pro1: 京东云鼎1.0  Test2: 京东云鼎2.0测试  Pro2: 京东云鼎2.0正式
JD_HOST_CONFIGS: dict[str, tuple[str, str, str]] = {
    "Pro1": ("http://116.196.117.102:8586", "/api/JdOrder", "50"),       # 京东云鼎1.0
    "Test2": ("http://116.196.117.102:8587", "/api/JdOrderOmid", "100"),  # 京东云鼎2.0测试
    "Pro2": ("http://116.196.117.102:8588", "/api/JdOrderOmid", "100"),   # 京东云鼎2.0正式
}


def get_jd_api_url(host_type: str, path_suffix: str) -> str:
    """
    根据主机类型拼接完整的接口地址。
    :param host_type: 主机类型, 取值见 JD_HOST_CONFIGS 的 key
    :param path_suffix: 接口名, 如 GetRtnOrderList / GetPopOrderList
    :return: 完整的接口 URL
    """
    if host_type not in JD_HOST_CONFIGS:
        available = list(JD_HOST_CONFIGS.keys())
        raise ValueError(f"未知的主机类型: {host_type}, 可用类型: {available}")
    base_url, api_prefix, _ = JD_HOST_CONFIGS[host_type]
    return f"{base_url}{api_prefix}/{path_suffix}"


def get_service_step(host_type: str) -> str:
    """
    根据主机类型获取对应的 serviceStep。
    :param host_type: 主机类型, 取值见 JD_HOST_CONFIGS 的 key
    :return: serviceStep 值
    """
    if host_type not in JD_HOST_CONFIGS:
        available = list(JD_HOST_CONFIGS.keys())
        raise ValueError(f"未知的主机类型: {host_type}, 可用类型: {available}")
    _, _, service_step = JD_HOST_CONFIGS[host_type]
    return service_step


# 正向单订单状态配置: key1=主机类型, key2=状态配置(1=已付款, 2=已发货, 3=交易完成)
# 1.0版状态值: WAIT_SELLER_STOCK_OUT / WAIT_GOODS_RECEIVE_CONFIRM / FINISHED_L
# 2.0版状态值: WAIT_STOCK_OUT / WAIT_GOODS_RECEIVE_CONFIRM / FINISHED
ORDER_STATE_CONFIGS: dict[str, dict[int, str]] = {
    "Pro1": {  # 京东云鼎1.0
        1: "WAIT_SELLER_STOCK_OUT,WAIT_GOODS_RECEIVE_CONFIRM,FINISHED_L",  # 已付款
        2: "WAIT_GOODS_RECEIVE_CONFIRM,FINISHED_L",                        # 已发货
        3: "FINISHED_L",                                                   # 交易完成(默认)
    },
    "Test2": {  # 京东云鼎2.0测试
        1: "WAIT_STOCK_OUT,WAIT_GOODS_RECEIVE_CONFIRM,FINISHED",           # 已付款
        2: "WAIT_GOODS_RECEIVE_CONFIRM,FINISHED",                          # 已发货
        3: "FINISHED",                                                     # 交易完成(默认)
    },
    "Pro2": {  # 京东云鼎2.0正式
        1: "WAIT_STOCK_OUT,WAIT_GOODS_RECEIVE_CONFIRM,FINISHED",           # 已付款
        2: "WAIT_GOODS_RECEIVE_CONFIRM,FINISHED",                          # 已发货
        3: "FINISHED",                                                     # 交易完成(默认)
    },
}


def get_order_state(host_type: str, order_state_cfg: int) -> str:
    """
    根据主机类型与状态配置获取正向单 orderState 参数值。
    :param host_type: 主机类型, 取值见 ORDER_STATE_CONFIGS 的 key
    :param order_state_cfg: 状态配置 1=已付款 2=已发货 3=交易完成
    :return: orderState 值
    """
    if host_type not in ORDER_STATE_CONFIGS:
        available = list(ORDER_STATE_CONFIGS.keys())
        raise ValueError(f"未知的主机类型: {host_type}, 可用类型: {available}")
    state_map = ORDER_STATE_CONFIGS[host_type]
    if order_state_cfg not in state_map:
        raise ValueError(f"未知的订单状态配置: {order_state_cfg}, 可用值: {list(state_map.keys())}")
    return state_map[order_state_cfg]
