"""日期工具函数"""
from typing import List, Tuple


def get_year_months(start_date: str, end_date: str) -> List[Tuple[int, int]]:
    """获取年月列表，支持任意起止日期"""
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
