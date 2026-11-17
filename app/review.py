"""Candidate review of observed entry facts, never a completed transaction."""

def review_entries(entries):
    qualifying = {}
    for entry in entries:
        detail = entry['detail_fact']
        qualifying.setdefault(detail['business_key'], []).append({'merchant': entry['id'],
                          'city': detail['city'], 'ticket': detail['ticket'], 'voucher_qualification': 'unconfirmed'})
    return qualifying
