#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据摄取脚本：从 Yahoo Finance 获取股票历史数据并存入数据库

支持从数据库读取指数成分股列表
"""

import argparse
import logging
from datetime import date, datetime, timedelta
from typing import List

from sqlalchemy import and_, or_

from common.db import Index, IndexConstituent, Symbol, get_session
from data_pipeline.ingest import SymbolConfig, fetch_and_store

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def get_index_constituents_from_db(
    index_symbol: str,
    as_of_date: date | None = None
) -> List[SymbolConfig]:
    """
    从数据库获取指定指数的成分股列表
    
    Args:
        index_symbol: 指数代码（如 ^NDX, ^HSI）
        as_of_date: 查询日期（默认为今天）
    
    Returns:
        成分股配置列表
    """
    if as_of_date is None:
        as_of_date = date.today()
    
    with get_session() as session:
        # 查询指数
        index = session.query(Index).filter(Index.symbol == index_symbol).first()
        if not index:
            raise ValueError(f"指数不存在: {index_symbol}")
        
        logger.info(f"查询指数: {index.name} ({index.symbol})")
        
        # 查询在指定日期有效的成分股
        constituents = (
            session.query(IndexConstituent, Symbol)
            .join(Symbol, IndexConstituent.symbol_id == Symbol.id)
            .filter(
                and_(
                    IndexConstituent.index_id == index.id,
                    IndexConstituent.effective_date <= as_of_date,
                    or_(
                        IndexConstituent.expiry_date.is_(None),
                        IndexConstituent.expiry_date > as_of_date,
                    ),
                )
            )
            .order_by(IndexConstituent.symbol)
            .all()
        )
        
        if not constituents:
            raise ValueError(f"指数 {index_symbol} 在 {as_of_date} 没有成分股数据")
        
        logger.info(f"找到 {len(constituents)} 只成分股")
        
        # 转换为 SymbolConfig 列表
        configs = []
        for constituent, symbol in constituents:
            configs.append(
                SymbolConfig(
                    symbol=symbol.symbol,
                    full_name=symbol.full_name,
                    exchange=symbol.exchange,
                    currency=symbol.currency,
                )
            )
        
        return configs


def ingest_hsi_constituents():
    """摄取恒生指数成分股数据"""
    
    # 定义要获取的股票列表（恒生指数成分股）
    symbols = [
        SymbolConfig(symbol='0005.HK', full_name='HSBC Holdings', exchange='HKEX'),
        SymbolConfig(symbol='0011.HK', full_name='Hang Seng Bank', exchange='HKEX'),
        SymbolConfig(symbol='0023.HK', full_name='Bank of East Asia', exchange='HKEX'),
        SymbolConfig(symbol='0388.HK', full_name='HKEx', exchange='HKEX'),
        SymbolConfig(symbol='0939.HK', full_name='CCB', exchange='HKEX'),
        SymbolConfig(symbol='1299.HK', full_name='AIA', exchange='HKEX'),
        SymbolConfig(symbol='1398.HK', full_name='ICBC', exchange='HKEX'),
        SymbolConfig(symbol='2318.HK', full_name='Ping An', exchange='HKEX'),
        SymbolConfig(symbol='2388.HK', full_name='BOC Hong Kong', exchange='HKEX'),
        SymbolConfig(symbol='2628.HK', full_name='China Life', exchange='HKEX'),
        SymbolConfig(symbol='3328.HK', full_name='Bank of Communications', exchange='HKEX'),
        SymbolConfig(symbol='3988.HK', full_name='Bank of China', exchange='HKEX'),
    ]
    
    # 设置日期范围
    start_date = date(2013, 7, 13)
    end_date = date(2016, 12, 12)
    
    logger.info(f"开始摄取数据，日期范围: {start_date} 到 {end_date}")
    logger.info(f"股票数量: {len(symbols)}")
    
    try:
        # 执行数据摄取
        report = fetch_and_store(
            symbols=symbols,
            start=start_date,
            end=end_date,
            force=True  # 强制覆盖已存在的数据
        )
        
        # 输出摄取报告
        logger.info("=" * 60)
        logger.info("数据摄取完成！")
        logger.info(f"总共处理股票数: {report.total_symbols}")
        logger.info(f"总共写入行数: {report.total_rows}")
        logger.info("=" * 60)
        
        # 详细报告
        for summary in report.symbols:
            logger.info(
                f"股票: {summary.symbol:10s} | "
                f"行数: {summary.rows_written:5d} | "
                f"日期范围: {summary.start} 到 {summary.end}"
            )
        
        return report
        
    except Exception as e:
        logger.error(f"数据摄取失败: {e}")
        import traceback
        traceback.print_exc()
        raise


def ingest_single_stock(symbol: str, start_date: date, end_date: date):
    """摄取单个股票的数据"""
    
    # 添加 .HK 后缀（如果需要）
    if not symbol.endswith('.HK'):
        symbol = f"{symbol.zfill(4)}.HK"
    
    symbols = [SymbolConfig(symbol=symbol, exchange='HKEX')]
    
    logger.info(f"开始摄取股票 {symbol} 的数据")
    logger.info(f"日期范围: {start_date} 到 {end_date}")
    
    try:
        report = fetch_and_store(
            symbols=symbols,
            start=start_date,
            end=end_date,
            force=True
        )
        
        logger.info("=" * 60)
        logger.info(f"股票 {symbol} 数据摄取完成！")
        logger.info(f"写入行数: {report.total_rows}")
        logger.info("=" * 60)
        
        return report
        
    except Exception as e:
        logger.error(f"数据摄取失败: {e}")
        import traceback
        traceback.print_exc()
        raise


def ingest_index_constituents(
    index_symbol: str,
    start_date: date,
    end_date: date,
    as_of_date: date | None = None,
    force: bool = False
):
    """
    从数据库读取指数成分股并摄取数据
    
    Args:
        index_symbol: 指数代码（如 ^NDX, ^HSI）
        start_date: 开始日期
        end_date: 结束日期
        as_of_date: 查询成分股的基准日期（默认为今天）
        force: 是否强制覆盖已存在的数据
    """
    logger.info("=" * 60)
    logger.info(f"开始摄取指数成分股数据")
    logger.info("=" * 60)
    logger.info(f"指数代码: {index_symbol}")
    logger.info(f"成分股基准日期: {as_of_date or date.today()}")
    logger.info(f"数据时间段: {start_date} 至 {end_date}")
    logger.info(f"强制更新: {'是' if force else '否'}")
    logger.info("=" * 60)
    
    try:
        # 从数据库获取成分股列表
        symbols = get_index_constituents_from_db(index_symbol, as_of_date)
        
        logger.info(f"\n成分股列表:")
        for i, config in enumerate(symbols, 1):
            logger.info(f"  {i:3d}. {config.symbol:10s} - {config.full_name}")
        
        logger.info(f"\n开始获取历史数据...")
        
        # 执行数据摄取
        report = fetch_and_store(
            symbols=symbols,
            start=start_date,
            end=end_date,
            force=force
        )
        
        # 输出摄取报告
        logger.info("\n" + "=" * 60)
        logger.info("数据摄取完成！")
        logger.info("=" * 60)
        logger.info(f"总共处理股票数: {report.total_symbols}")
        logger.info(f"总共写入行数: {report.total_rows}")
        logger.info("=" * 60)
        
        # 详细报告
        if hasattr(report, 'symbols'):
            for summary in report.symbols:
                logger.info(
                    f"股票: {summary.symbol:10s} | "
                    f"行数: {summary.rows_written:5d} | "
                    f"日期范围: {summary.start} 到 {summary.end}"
                )
        
        return report
        
    except Exception as e:
        logger.error(f"数据摄取失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="从 Yahoo Finance 获取股票历史数据并存入数据库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 从数据库读取 NASDAQ-100 成分股，获取最近1年数据
  python ingest_stock_data.py --index ^NDX
  
  # 指定时间段
  python ingest_stock_data.py --index ^NDX --start 2023-01-01 --end 2023-12-31
  
  # 获取恒生指数数据
  python ingest_stock_data.py --index ^HSI --start 2020-01-01
  
  # 获取单个股票数据
  python ingest_stock_data.py --symbol 0700.HK --start 2023-01-01 --end 2023-12-31
  
  # 使用旧方法（硬编码的恒生指数成分股）
  python ingest_stock_data.py --legacy
        """
    )
    
    parser.add_argument(
        "--index",
        type=str,
        help="指数代码（如 ^NDX, ^HSI），从数据库读取成分股"
    )
    
    parser.add_argument(
        "--symbol",
        type=str,
        help="单个股票代码（如 0700.HK, AAPL）"
    )
    
    parser.add_argument(
        "--start",
        type=str,
        help="开始日期（格式: YYYY-MM-DD，默认为1年前）"
    )
    
    parser.add_argument(
        "--end",
        type=str,
        help="结束日期（格式: YYYY-MM-DD，默认为今天）"
    )
    
    parser.add_argument(
        "--as-of",
        type=str,
        help="查询成分股的基准日期（格式: YYYY-MM-DD，默认为今天）"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖已存在的数据"
    )
    
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="使用旧方法（硬编码的恒生指数成分股）"
    )
    
    args = parser.parse_args()
    
    # 解析日期
    def parse_date(date_str: str) -> date:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"日期格式错误: {date_str}，应为 YYYY-MM-DD")
            exit(1)
    
    if args.start:
        start_date = parse_date(args.start)
    else:
        start_date = date.today() - timedelta(days=365)
    
    if args.end:
        end_date = parse_date(args.end)
    else:
        end_date = date.today()
    
    if args.as_of:
        as_of_date = parse_date(args.as_of)
    else:
        as_of_date = None
    
    # 验证日期范围
    if start_date > end_date:
        logger.error("开始日期不能晚于结束日期")
        exit(1)
    
    try:
        if args.legacy:
            # 使用旧方法
            logger.info("使用旧方法（硬编码的恒生指数成分股）")
            ingest_hsi_constituents()
        elif args.index:
            # 从数据库读取指数成分股
            ingest_index_constituents(
                index_symbol=args.index,
                start_date=start_date,
                end_date=end_date,
                as_of_date=as_of_date,
                force=args.force
            )
        elif args.symbol:
            # 获取单个股票数据
            ingest_single_stock(args.symbol, start_date, end_date)
        else:
            # 默认使用旧方法
            logger.info("未指定参数，使用旧方法（硬编码的恒生指数成分股）")
            logger.info("提示: 使用 --index ^NDX 从数据库读取指数成分股")
            ingest_hsi_constituents()
            
    except Exception as e:
        logger.error(f"执行失败: {e}")
        exit(1)