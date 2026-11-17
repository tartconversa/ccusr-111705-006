"""只审阅已观察的详情入口与矩阵证据，不把候选记录当作已完成的业务。

报告原则：
- 每条（商户, 城市, 票根类别）矩阵格独立呈现，不按商户合并、不去重；
- 只引用本格自己的观测，不把另一类票根的资格挪用过来；
- 空结果/报错/坐标漂移一律标 unknown 并给出原因，绝不解释成“无优惠”；
- 所有记录都是只读核对证据，claim_submitted 恒为 False。
"""
from .domain import (STATE_CONFIRMED, STATE_UNKNOWN,
                     PREVIEW_AVAILABLE, PREVIEW_QUOTA_PENDING)

_PREVIEW_LABELS = {
    PREVIEW_AVAILABLE: '页面显示可领取（仅预览，未领取）',
    PREVIEW_QUOTA_PENDING: '页面显示名额待核/用尽（仅预览）',
    'preview_transient_error': '领券预览短暂报错，未能确认',
    'preview_not_observed': '未观测到领券预览结论（不等于无优惠）',
    'preview_unrecognized': '预览结论无法识别，需人工复核',
}

_REASON_LABELS = {
    'merchant_identity_mismatch': '详情页商户身份与目录不一致',
    'city_redirected': '详情跳转到其他城市，请求城市未被确认',
    'ticket_filter_reset': '票根类别筛选被页面重置，请求类别未被确认',
    'preview_transient_error': '领券预览短暂报错',
    'preview_not_observed': '未取得领券预览结论',
    'preview_unrecognized': '预览结论不在可识别范围内',
}


def review_entries(entries):
    qualifying = {}
    for entry in entries:
        detail = entry['detail_fact']
        qualifying.setdefault(detail['business_key'], []).append({'merchant': entry['id'],
                          'city': detail['city'], 'ticket': detail['ticket'], 'voucher_qualification': 'unconfirmed'})
    return qualifying


def build_matrix_review(rows):
    """把矩阵证据转成客服核对报告：逐格列出结论、未知原因与证据位置。"""
    cells = []
    for row in rows:
        detail = row['detail_fact']
        state = detail['state']
        cell = {
            'merchant': row['id'],
            'requested_city': row['requested_city'],
            'requested_ticket': row['requested_ticket'],
            'business_key': detail['business_key'],
            'state': state,
            'confirmed_scope': state == STATE_CONFIRMED,
            'unknown_reasons': [_REASON_LABELS.get(reason, reason)
                                for reason in detail['reasons']],
            'preview_reading': _PREVIEW_LABELS.get(
                detail['preview_status'], detail['preview_status']),
            'merchant_terms': detail['merchant_terms'],
            'observed_city': detail['observed_city'],
            'observed_ticket': detail['observed_ticket'],
            'preview_attempts': detail['attempts'],
            'recovered_after_retry': detail['recovered_after_retry'],
            'evidence_only': row['evidence_only'],
            'claim_submitted': row['claim_submitted'],
            'artifacts': row.get('artifacts', {}),
            'observed_texts': row['observed_texts'],
            'cross_category_borrowing': 'never_used',
        }
        cells.append(cell)

    confirmed = [c for c in cells if c['state'] == STATE_CONFIRMED]
    unknown = [c for c in cells if c['state'] == STATE_UNKNOWN]
    return {
        'purpose': '客服核对用证据；仅预览资格，未领取任何优惠',
        'total_cells': len(cells),
        'confirmed_cells': len(confirmed),
        'unknown_cells': len(unknown),
        'deduplication': 'disabled_by_design_each_city_ticket_cell_is_separate',
        'empty_result_policy': '空结果或报错记为 unknown，不解释为无优惠',
        'eligibility_boundary': '每格只采用本格观测，不挪用其他票根类别的资格',
        'cells': cells,
    }


def format_matrix_review_text(review):
    """生成纯文本版客服报告，便于工单粘贴。"""
    lines = [
        f"票根优惠商户核对证据（{review['purpose']}）",
        f"矩阵格总数：{review['total_cells']}；已确认：{review['confirmed_cells']}；"
        f"未知待核：{review['unknown_cells']}",
        f"去重策略：{review['deduplication']}",
        f"空结果策略：{review['empty_result_policy']}",
        f"资格边界：{review['eligibility_boundary']}",
        '-' * 60,
    ]
    for cell in review['cells']:
        head = (f"[{cell['state']}] {cell['merchant']} / {cell['requested_city']} / "
                f"{cell['requested_ticket']}（key={cell['business_key']}）")
        lines.append(head)
        lines.append(f"  - 领券预览：{cell['preview_reading']}")
        lines.append(f"  - 商户说明：{cell['merchant_terms']}；"
                     f"页面回读城市/类别：{cell['observed_city']}/{cell['observed_ticket']}；"
                     f"预览尝试 {cell['preview_attempts']} 次"
                     f"{'（重试后恢复）' if cell['recovered_after_retry'] else ''}")
        if cell['unknown_reasons']:
            lines.append(f"  - 未知原因：{'；'.join(cell['unknown_reasons'])}")
        lines.append('  - 资格来源：仅本格观测，不挪用其他票根类别；只读证据，未领取')
    return '\n'.join(lines)
