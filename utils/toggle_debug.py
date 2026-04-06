#!/usr/bin/env python3
"""
快速切换 PDE 策略调试模式的工具

用法:
    python utils/toggle_debug.py --enable   # 启用调试模式
    python utils/toggle_debug.py --disable  # 禁用调试模式
    python utils/toggle_debug.py --status   # 查看当前状态
"""

import argparse
import json
import os
from pathlib import Path

def get_config_path():
    """获取配置文件路径"""
    project_root = Path(__file__).parent.parent
    return project_root / "config" / "polymarket_pde_config.py"

def toggle_debug(enable: bool) -> bool:
    """切换调试模式"""
    config_path = get_config_path()
    
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        return False
    
    # 读取文件内容
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找并替换 debug_raw_data 行
    if '"debug_raw_data": False,' in content:
        if enable:
            content = content.replace('"debug_raw_data": False,', '"debug_raw_data": True,')
            action = "启用"
        else:
            print("✅ 调试模式已经是禁用状态")
            return True
    elif '"debug_raw_data": True,' in content:
        if not enable:
            content = content.replace('"debug_raw_data": True,', '"debug_raw_data": False,')
            action = "禁用"
        else:
            print("✅ 调试模式已经是启用状态")
            return True
    else:
        print("❌ 无法找到 debug_raw_data 配置项")
        return False
    
    # 写回文件
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 成功{action}调试模式")
    print(f"📝 配置文件已更新: {config_path}")
    print("\n🔄 重启策略以应用更改:")
    print("   python live/run_polymarket_pde.py --mode sandbox")
    
    return True

def check_status():
    """检查当前状态"""
    config_path = get_config_path()
    
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if '"debug_raw_data": True,' in content:
        print("🔍 调试模式: **启用**")
        print("\n📊 将输出以下原始数据:")
        print("   • BTC 价格和变动 (bps)")
        print("   • UP/DOWN token 买卖价")
        print("   • 价差百分比")
        print("   • 订单大小")
        print("   • 时间戳")
    elif '"debug_raw_data": False,' in content:
        print("🔍 调试模式: **禁用**")
        print("\n📊 无原始数据输出")
    else:
        print("❌ 无法确定调试模式状态")

def main():
    parser = argparse.ArgumentParser(description="切换 PDE 策略调试模式")
    parser.add_argument("--enable", action="store_true", help="启用调试模式")
    parser.add_argument("--disable", action="store_true", help="禁用调试模式")
    parser.add_argument("--status", action="store_true", help="查看当前状态")
    
    args = parser.parse_args()
    
    if args.status:
        check_status()
    elif args.enable:
        toggle_debug(True)
    elif args.disable:
        toggle_debug(False)
    else:
        print("请指定操作: --enable, --disable, 或 --status")
        print("\n示例:")
        print("  python utils/toggle_debug.py --enable")
        print("  python utils/toggle_debug.py --disable")
        print("  python utils/toggle_debug.py --status")

if __name__ == "__main__":
    main()
