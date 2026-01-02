#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化测试脚本 - 批量测试所有案例
"""

import os
import subprocess
import sys
from pathlib import Path

def run_test(test_file):
    """运行单个测试文件"""
    print(f"\n{'='*60}")
    print(f"测试文件: {test_file}")
    print(f"{'='*60}")

    try:
        # 运行解析器，设置超时为5秒
        result = subprocess.run(
            ['python3', 'mini_parser.py', test_file, '--no-ast'],
            capture_output=True,
            text=True,
            timeout=5
        )

        # 输出结果
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        return result.returncode

    except subprocess.TimeoutExpired:
        print("❌ 测试超时！可能存在死循环")
        return -1
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        return -1

def main():
    test_dir = Path('test_cases')

    if not test_dir.exists():
        print("错误: test_cases 目录不存在")
        return

    # 获取所有测试文件
    test_files = sorted(test_dir.glob('*.mini'))

    if not test_files:
        print("错误: 没有找到测试文件")
        return

    print(f"找到 {len(test_files)} 个测试文件")

    # 分类统计
    passed = []
    failed = []
    timeout = []

    for test_file in test_files:
        returncode = run_test(str(test_file))

        filename = test_file.name

        # fail测试预期失败，其他测试预期成功
        if 'fail' in filename:
            if returncode != 0:
                passed.append(filename)
            else:
                failed.append(filename)
        else:
            if returncode == 0:
                passed.append(filename)
            elif returncode == -1:
                timeout.append(filename)
            else:
                failed.append(filename)

    # 输出汇总
    print(f"\n\n{'='*60}")
    print("测试汇总")
    print(f"{'='*60}")
    print(f"✓ 通过: {len(passed)}")
    print(f"✗ 失败: {len(failed)}")
    print(f"⏱ 超时: {len(timeout)}")
    print(f"总计: {len(test_files)}")

    if failed:
        print(f"\n失败的测试:")
        for f in failed:
            print(f"  - {f}")

    if timeout:
        print(f"\n超时的测试:")
        for f in timeout:
            print(f"  - {f}")

    if passed and not failed and not timeout:
        print(f"\n🎉 所有测试通过！")

if __name__ == '__main__':
    main()
