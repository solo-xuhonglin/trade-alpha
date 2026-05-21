"""API 参数验证器"""

from typing import Optional, Annotated
from fastapi import Query, HTTPException
from pydantic import AfterValidator
import re


def validate_date(v: Optional[str]) -> Optional[str]:
    """验证普通日期格式，支持 YYYY-MM-DD 或 YYYYMMDD"""
    if v is None:
        return v
    
    if isinstance(v, str):
        api_pattern = r'^\d{4}-\d{2}-\d{2}$'
        db_pattern = r'^\d{8}$'
        
        if re.match(api_pattern, v):
            try:
                year, month, day = map(int, v.split('-'))
                if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return v
            except:
                pass
        
        if re.match(db_pattern, v):
            try:
                year = int(v[:4])
                month = int(v[4:6])
                day = int(v[6:8])
                if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return v
            except:
                pass
    
    raise ValueError(f"Invalid date format: '{v}'. Expected YYYY-MM-DD or YYYYMMDD")


def validate_trade_date(v: Optional[str]) -> Optional[str]:
    """验证交易日期格式 (trade_date)，支持 YYYYMMDD 或 YYYY-MM-DD 格式，统一转换为 YYYYMMDD 格式返回"""
    if v is None:
        return v
    
    if isinstance(v, str):
        # 检查是否已经是 YYYYMMDD 格式
        db_pattern = r'^\d{8}$'
        if re.match(db_pattern, v):
            try:
                year = int(v[:4])
                month = int(v[4:6])
                day = int(v[6:8])
                if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return v
            except:
                pass
        
        # 检查是否是 YYYY-MM-DD 格式，如果是则转换为 YYYYMMDD
        api_pattern = r'^\d{4}-\d{2}-\d{2}$'
        if re.match(api_pattern, v):
            try:
                year, month, day = map(int, v.split('-'))
                if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return f"{year:04d}{month:02d}{day:02d}"
            except:
                pass
    
    raise ValueError(f"Invalid trade date format: '{v}'. Trade date (trade_date) must be in YYYYMMDD or YYYY-MM-DD format")


def validate_date_range(start_date: Optional[str], end_date: Optional[str]) -> None:
    """验证日期范围，确保 start_date <= end_date"""
    if start_date and end_date:
        # 统一转换为 YYYYMMDD 格式进行比较
        start_db = start_date.replace('-', '') if '-' in start_date else start_date
        end_db = end_date.replace('-', '') if '-' in end_date else end_date
        
        if start_db > end_db:
            raise ValueError(f"Start date '{start_date}' must be before end date '{end_date}'")


# 类型别名
DateQuery = Annotated[Optional[str], AfterValidator(validate_date)]
"""普通日期查询参数，支持 YYYY-MM-DD 或 YYYYMMDD"""

TradeDateQuery = Annotated[Optional[str], AfterValidator(validate_trade_date)]
"""交易日期查询参数 (trade_date)，支持 YYYY-MM-DD 或 YYYYMMDD，统一转换为 YYYYMMDD 格式"""