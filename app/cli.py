"""本地演练门户采集命令行：目录快照与票根类别 × 城市矩阵核对。

用法：
  python -m app.cli                      # 仅打印目录（原演示）
  python -m app.cli matrix --db 证据.sqlite3 --evidence-dir 证据目录
  python -m app.cli matrix --fault transient   # 演练故障恢复
"""
import argparse
import json
import sys
from pathlib import Path

from .capture import read_catalog, read_matrix_evidence
from .records import save_catalog, save_matrix_evidence, matrix_summary
from .review import build_matrix_review, format_matrix_review_text

DEFAULT_ORIGIN = 'http://127.0.0.1:8765/'


def main(argv=None):
    parser = argparse.ArgumentParser(description='票根优惠本地演练采集器（只读核对，不领取）')
    parser.add_argument('command', nargs='?', default='catalog', choices=('catalog', 'matrix'))
    parser.add_argument('--origin', default=DEFAULT_ORIGIN)
    parser.add_argument('--db', default='records/evidence.sqlite3')
    parser.add_argument('--evidence-dir', default='records/artifacts')
    parser.add_argument('--fault', choices=('reset', 'cross-city', 'transient'),
                        help='演练故障注入：reset/cross-city/transient')
    parser.add_argument('--retries', type=int, default=1, help='领券预览短暂报错时的重试次数')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出报告')
    args = parser.parse_args(argv)

    if args.command == 'catalog':
        print(json.dumps(read_catalog(args.origin), ensure_ascii=False, indent=2))
        return 0

    rows = read_matrix_evidence(
        args.origin, evidence_dir=Path(args.evidence_dir),
        fault=args.fault, retries=args.retries)
    saved = save_matrix_evidence(Path(args.db), rows)
    review = build_matrix_review(rows)
    if args.json:
        print(json.dumps({'saved_rows': saved, 'summary': matrix_summary(Path(args.db)),
                          'review': review}, ensure_ascii=False, indent=2))
    else:
        print(format_matrix_review_text(review))
        print('-' * 60)
        print(f'已追加 {saved} 条证据到 {args.db}（不去重）；'
              f'页面快照/截图位于 {args.evidence_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
