"""票根优惠的资格入口与商户核对：目录卡片既有数据约定。"""
import re

# 领券预览中可被客服直接核对的观测结论；仅代表页面展示，不代表已领取。
PREVIEW_AVAILABLE = 'available_observed'
PREVIEW_QUOTA_PENDING = 'quota_pending'
PREVIEW_TRANSIENT_ERROR = 'preview_transient_error'
PREVIEW_NOT_OBSERVED = 'preview_not_observed'
PREVIEW_UNRECOGNIZED = 'preview_unrecognized'

CONFIRMED_PREVIEW_STATUSES = (PREVIEW_AVAILABLE, PREVIEW_QUOTA_PENDING)

# 商户说明（条款）观测信号。
TERMS_SEEN = 'terms_seen'
TERMS_PENDING = 'terms_pending'
TERMS_NOT_OBSERVED = 'terms_not_observed'

STATE_CONFIRMED = 'confirmed'
STATE_UNKNOWN = 'unknown'

TRANSIENT_ERROR_MARKERS = ('系统繁忙', '请稍后重试', '暂时无法', '网络异常')

def interpret_card(item):
    parts = item['summary'].split(' · ', 1)
    if len(parts) != 2:
        raise ValueError('卡片摘要格式无效')
    condition, observation = parts
    found = re.fullmatch(r"(?P<amount>可领取|名额待核)", observation)
    if not found:
        raise ValueError('卡片状态未识别')
    amount = found.group('amount')
    return {'kind': 'benefit', 'identity': item['id'], 'condition': condition, 'eligibility': observation, 'state': int(amount) if amount.isdigit() else amount}

def interpret_entry(catalog_fact, signal):
    if signal['merchant'] != catalog_fact['identity']:
        raise ValueError('ticket merchant mismatch')
    return {'business_key': f"{signal['city']}:{signal['merchant']}:{signal['ticket']}", 'city': signal['city'], 'ticket': signal['ticket']}

def matrix_business_key(city, merchant, ticket):
    """业务键以客服请求核对的（城市, 商户, 票根类别）为准，保证每个矩阵格独立可追溯。"""
    return f'{city}:{merchant}:{ticket}'

def interpret_preview(preview_text):
    """只解读本格领券预览文本；空文本是“未观测到”，绝不是“无优惠”。"""
    if not preview_text:
        return PREVIEW_NOT_OBSERVED
    if any(marker in preview_text for marker in TRANSIENT_ERROR_MARKERS):
        return PREVIEW_TRANSIENT_ERROR
    if '名额待核' in preview_text or '名额用尽' in preview_text:
        return PREVIEW_QUOTA_PENDING
    if '可领取' in preview_text:
        return PREVIEW_AVAILABLE
    return PREVIEW_UNRECOGNIZED

def interpret_merchant_terms(scope_text, detail_text):
    combined = f'{scope_text} {detail_text}'
    if not combined.strip():
        return TERMS_NOT_OBSERVED
    if '条款已见' in scope_text or '可凭' in detail_text:
        return TERMS_SEEN
    if '资格待核' in combined:
        return TERMS_PENDING
    return TERMS_NOT_OBSERVED

def interpret_matrix_observation(catalog_fact, requested, observed, texts):
    """判定单个（城市 × 票根类别）矩阵格的证据状态。

    严格规则：
    - 只使用本格自己的观测文本，不接收任何其他票根类别的结论；
    - 页面回读坐标与请求坐标不一致（筛选重置/跳城/商户不符）→ unknown；
    - 预览报错或未观测到 → unknown，已确认的商户说明等信号仍原样保留；
    - 只有坐标一致且预览给出可识别结论时才记 confirmed；
    - 任何情况下 evidence_only=True、claim_submitted=False（流程不触发领取）。
    """
    reasons = []
    merchant = catalog_fact['identity']
    business_key = matrix_business_key(requested['city'], merchant, requested['ticket'])

    if observed['merchant'] != merchant:
        reasons.append('merchant_identity_mismatch')
    if observed['city'] != requested['city']:
        reasons.append('city_redirected')
    if observed['ticket'] != requested['ticket']:
        reasons.append('ticket_filter_reset')

    preview_status = interpret_preview(texts.get('voucher', ''))
    if preview_status == PREVIEW_TRANSIENT_ERROR:
        reasons.append('preview_transient_error')
    elif preview_status == PREVIEW_NOT_OBSERVED:
        reasons.append('preview_not_observed')
    elif preview_status == PREVIEW_UNRECOGNIZED:
        reasons.append('preview_unrecognized')
    # 短暂报错后重试成功：故障已被恢复观测覆盖，不再作为未知原因，但保留尝试次数。

    terms_status = interpret_merchant_terms(texts.get('scope', ''), texts.get('merchant_detail', ''))

    if preview_status in CONFIRMED_PREVIEW_STATUSES and not any(
            r in reasons for r in ('merchant_identity_mismatch', 'city_redirected',
                                   'ticket_filter_reset', 'preview_not_observed',
                                   'preview_unrecognized', 'preview_transient_error')):
        state = STATE_CONFIRMED
    else:
        state = STATE_UNKNOWN

    return {
        'business_key': business_key,
        'requested_city': requested['city'],
        'requested_ticket': requested['ticket'],
        'observed_city': observed['city'],
        'observed_ticket': observed['ticket'],
        'observed_merchant': observed['merchant'],
        'state': state,
        'preview_status': preview_status,
        'merchant_terms': terms_status,
        'reasons': reasons,
        'evidence_only': True,
        'claim_submitted': False,
        'recovered_after_retry': bool(texts.get('recovered')),
        'attempts': texts.get('attempts', 1),
    }
