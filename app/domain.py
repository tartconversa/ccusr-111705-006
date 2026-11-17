"""票根优惠的资格入口与商户核对：目录卡片既有数据约定。"""
import re

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
