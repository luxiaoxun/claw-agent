#!/usr/bin/env python3
"""
DuckDuckGo 命令行搜索工具 (使用新的 ddgs 库)
用法:
    python search_tool.py text <关键词> [--max-results N] [--region cn]
    python search_tool.py images <关键词> [--max-results N]
    python search_tool.py videos <关键词> [--max-results N]
"""

import argparse
import json
from itertools import islice
from ddgs import DDGS


def search_text(keywords, max_results=10, region='wt-wt'):
    """文本搜索"""
    results = []
    with DDGS() as ddgs:
        try:
            # 新版 ddgs 的 text 搜索方法
            ddgs_gen = ddgs.text(keywords, region=region, safesearch='off', timelimit='y')
            for r in islice(ddgs_gen, max_results):
                results.append(r)
        except Exception as e:
            print(f"搜索过程出错: {e}")
            return []
    return results


def search_images(keywords, max_results=10):
    """图片搜索"""
    results = []
    with DDGS() as ddgs:
        try:
            ddgs_gen = ddgs.images(keywords, safesearch='off', timelimit=None)
            for r in islice(ddgs_gen, max_results):
                results.append(r)
        except Exception as e:
            print(f"搜索过程出错: {e}")
            return []
    return results


def search_videos(keywords, max_results=10):
    """视频搜索"""
    results = []
    with DDGS() as ddgs:
        try:
            ddgs_gen = ddgs.videos(keywords, safesearch='off', timelimit=None, resolution="high")
            for r in islice(ddgs_gen, max_results):
                results.append(r)
        except Exception as e:
            print(f"搜索过程出错: {e}")
            return []
    return results


def print_results(results, output_format='text'):
    """打印搜索结果"""
    if output_format == 'json':
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if not results:
        print("未找到结果")
        return

    for i, result in enumerate(results, 1):
        for key, value in result.items():
            if value:
                # 截断过长的内容
                value_str = str(value)
                if len(value_str) > 200:
                    value_str = value_str[:200] + "..."
                print(f"{key}: {value_str}")

        # 每个结果之间空一行（最后一个结果后不空行）
        if i < len(results):
            print()


def main():
    parser = argparse.ArgumentParser(description='DuckDuckGo 命令行搜索工具')
    subparsers = parser.add_subparsers(dest='command', help='搜索类型', required=True)

    # 文本搜索
    text_parser = subparsers.add_parser('text', help='文本搜索')
    text_parser.add_argument('keywords', help='搜索关键词')
    text_parser.add_argument('--max-results', '-n', type=int, default=10, help='最大结果数 (默认: 10)')
    text_parser.add_argument('--region', '-r', default='wt-wt',
                             help='搜索区域 (默认: wt-wt). 例如: cn-zh, us-en, uk-en')

    # 图片搜索
    images_parser = subparsers.add_parser('images', help='图片搜索')
    images_parser.add_argument('keywords', help='搜索关键词')
    images_parser.add_argument('--max-results', '-n', type=int, default=10, help='最大结果数 (默认: 10)')

    # 视频搜索
    videos_parser = subparsers.add_parser('videos', help='视频搜索')
    videos_parser.add_argument('keywords', help='搜索关键词')
    videos_parser.add_argument('--max-results', '-n', type=int, default=10, help='最大结果数 (默认: 10)')

    # 通用选项
    parser.add_argument('--output', '-o', choices=['text', 'json'], default='text', help='输出格式 (默认: text)')

    args = parser.parse_args()

    # 执行搜索
    try:
        if args.command == 'text':
            results = search_text(args.keywords, args.max_results, args.region)
        elif args.command == 'images':
            results = search_images(args.keywords, args.max_results)
        elif args.command == 'videos':
            results = search_videos(args.keywords, args.max_results)
        else:
            print(f"未知命令: {args.command}")
            return 1

        print_results(results, args.output)

    except Exception as e:
        print(f"搜索出错: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
