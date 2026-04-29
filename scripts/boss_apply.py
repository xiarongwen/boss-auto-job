#!/usr/bin/env python3
"""
BOSS Zhipin Auto Apply - Full Pipeline (Camoufox Edition)
搜索 → 多Agent匹配 → 生成打招呼语 → 发送消息

Usage:
  python boss_apply.py "产品经理"                     # 搜索+匹配+生成
  python boss_apply.py "产品经理" --send              # + 发送
  python boss_apply.py "产品经理" --city=101020100    # 上海
  python boss_apply.py "产品经理" --top=5             # Top 5
  python boss_apply.py "产品经理" --send --dry-run    # 模拟

城市: 101010100=北京 101020100=上海 101280600=深圳 101210100=杭州
"""

import json
import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

SCRIPTS_DIR = Path(__file__).parent
RESUME_FILE = Path.home() / '.hermes' / 'credentials' / 'resume.txt'
OUTPUT_DIR = Path('/tmp/boss_apply')

CITY_NAMES = {
    '101010100': '北京', '101020100': '上海', '101280600': '深圳',
    '101210100': '杭州', '101270100': '成都', '101030100': '天津',
    '101110100': '西安', '101190400': '苏州', '101200100': '武汉',
}


def log(level, msg):
    ts = datetime.now().strftime('%H:%M:%S')
    icons = {'info': '📋', 'ok': '✅', 'warn': '⚠️', 'err': '❌', 'search': '🔍', 'send': '📤'}
    print(f"[{ts}] {icons.get(level, '📋')} {msg}")


def load_resume() -> str:
    if not RESUME_FILE.exists():
        log('err', f'简历不存在: {RESUME_FILE}')
        sys.exit(1)
    return RESUME_FILE.read_text().strip()


def search_jobs(query: str, city: str, pages: int) -> list:
    """Step 1: Camoufox 搜索"""
    log('search', f'搜索 "{query}" 城市={CITY_NAMES.get(city, city)} 页数={pages}')
    log('info', '使用 Camoufox (C++级指纹绕过)')

    script = SCRIPTS_DIR / 'search_camoufox.py'
    result = subprocess.run(
        [sys.executable, str(script), query, f'--city={city}', f'--pages={pages}'],
        capture_output=True, text=True, timeout=180
    )

    output = result.stdout + result.stderr

    # Check for fatal errors
    if 'Code 36' in output or 'Code 32' in output or 'code: 36' in output or 'code: 32' in output:
        code = '36' if '36' in output else '32'
        log('err', f'BOSS code {code}: 账户异常，需要手动验证')
        log('info', '请在 Chrome 中打开 zhipin.com 完成验证后告诉我')
        return []

    if 'No jobs found' in output or '❌' in output.split('===JOBS_JSON_START===')[0] if '===JOBS_JSON_START===' in output else True:
        # Check if we got JSON output anyway
        pass

    # Parse JSON
    if '===JOBS_JSON_START===' in output:
        start = output.index('===JOBS_JSON_START===') + len('===JOBS_JSON_START===')
        end = output.index('===JOBS_JSON_END===')
        try:
            jobs = json.loads(output[start:end].strip())
            log('ok', f'找到 {len(jobs)} 个职位')
            return jobs
        except json.JSONDecodeError as e:
            log('err', f'JSON 解析失败: {e}')

    log('err', '搜索失败')
    log('info', f'输出: {output[-500:]}')
    return []


def save_jobs(jobs: list, query: str, city: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    path = OUTPUT_DIR / f'jobs_{query}_{city}_{ts}.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    log('ok', f'职位已保存: {path}')
    return path


def main():
    parser = argparse.ArgumentParser(description='BOSS Zhipin Auto Apply (Camoufox)')
    parser.add_argument('query', help='搜索关键词')
    parser.add_argument('--city', default='101010100', help='城市代码')
    parser.add_argument('--pages', type=int, default=1, help='搜索页数')
    parser.add_argument('--top', type=int, default=10, help='匹配 Top N')
    parser.add_argument('--send', action='store_true', help='自动发送消息')
    parser.add_argument('--dry-run', action='store_true', help='模拟发送')
    args = parser.parse_args()

    log('info', '=' * 50)
    log('info', 'BOSS 直聘自动求职 (Camoufox Stealth)')
    log('info', f'关键词: {args.query} | 城市: {CITY_NAMES.get(args.city, args.city)}')
    log('info', f'模式: {"发送" if args.send else "仅搜索匹配"}{" (模拟)" if args.dry_run else ""}')
    log('info', '=' * 50)

    resume = load_resume()
    log('info', f'简历: {resume[:60]}...')

    # Step 1: Search
    jobs = search_jobs(args.query, args.city, args.pages)
    if not jobs:
        return

    jobs_path = save_jobs(jobs, args.query, args.city)

    log('info', f'\n搜索完成！共 {len(jobs)} 个职位')
    log('info', f'职位数据: {jobs_path}')

    # Output for agent consumption
    print('\n===SEARCH_RESULT===')
    print(json.dumps({
        'status': 'ok',
        'jobs_file': str(jobs_path),
        'job_count': len(jobs),
        'resume': resume,
        'top_n': args.top,
        'send': args.send,
        'dry_run': args.dry_run,
        'first_5': [
            {'title': j['title'], 'company': j['company'], 'salary': j['salary'],
             'skills': j.get('skills', []), 'job_id': j['job_id']}
            for j in jobs[:5]
        ]
    }, ensure_ascii=False, indent=2))
    print('===SEARCH_RESULT_END===')


if __name__ == '__main__':
    main()
