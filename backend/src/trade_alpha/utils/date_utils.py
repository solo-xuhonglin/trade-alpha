"""日期工具函数"""
from typing import List, Tuple
import re


def is_valid_api_date(date_str: str) -> bool:
    """验证是否为有效的API日期格式 YYYY-MM-DD"""
    if not isinstance(date_str, str):
        return False
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(pattern, date_str):
        return False
    # 简单的日期范围验证
    try:
        year, month, day = map(int, date_str.split('-'))
        return 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31
    except:
        return False


def is_valid_db_date(date_str: str) -> bool:
    """验证是否为有效的数据库日期格式 YYYYMMDD"""
    if not isinstance(date_str, str):
        return False
    pattern = r'^\d{8}$'
    if not re.match(pattern, date_str):
        return False
    # 简单的日期范围验证
    try:
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])
        return 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31
    except:
        return False


def to_db_format(date_str: str) -> str:
    """将日期转换为数据库格式 YYYYMMDD"""
    if not date_str:
        return date_str
    if is_valid_db_date(date_str):
        return date_str
    if is_valid_api_date(date_str):
        return date_str.replace("-", "")
    raise ValueError(f"Invalid date format: {date_str}, expected YYYY-MM-DD or YYYYMMDD")


def to_api_format(date_str: str) -> str:
    """将日期转换为API格式 YYYY-MM-DD"""
    if not date_str:
        return date_str
    if is_valid_api_date(date_str):
        return date_str
    if is_valid_db_date(date_str):
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    raise ValueError(f"Invalid date format: {date_str}, expected YYYY-MM-DD or YYYYMMDD")


def get_year_months(start_date: str, end_date: str) -> List[Tuple[int, int]]:
    """获取年月列表，支持任意起止日期"""
    # 统一转换为数据库格式
    start_date = to_db_format(start_date)
    end_date = to_db_format(end_date)
    
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    start_month = int(start_date[4:6]) if len(start_date) >= 6 else 1
    end_month = int(end_date[4:6]) if len(end_date) >= 6 else 12
    
    result = []
    for year in range(start_year, end_year + 1):
        m_start = start_month if year == start_year else 1
        m_end = end_month if year == end_year else 12
        for month in range(m_start, m_end + 1):
            result.append((year, month))
    return result


def format_progress(stage: str, year: int, month: int = None, idx: int = 1, total: int = 1) -> str:
    """格式化进度消息"""
    if stage == "load":
        return f"正在加载{year}年数据 ({idx}/{total})"
    elif stage == "label":
        return f"正在计算{year}年标签 ({idx}/{total})"
    elif stage == "norm":
        return f"正在标准化{year}年{month:02d}月 ({idx}/{total})"
    elif stage == "train":
        return f"正在训练{year}年{month:02d}月 ({idx}/{total})"
    elif stage == "backtest":
        return f"正在回测{year}年{month:02d}月 ({idx}/{total})"
    elif stage == "done":
        return "训练完成"
    else:
        return f"处理中 {year}年{month or ''}"
