"""只审阅已观察的详情入口，不把候选记录当作已完成的业务。"""

def review_entries(entries):
    qualifying = {}
    for entry in entries:
        detail = entry['detail_fact']
        qualifying.setdefault(detail['business_key'], []).append({'merchant': entry['id'],
                          'city': detail['city'], 'ticket': detail['ticket'], 'voucher_qualification': 'unconfirmed'})
    return qualifying
