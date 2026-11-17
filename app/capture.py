"""使用真实 Chromium 浏览公开目录，并按票根类别 × 城市逐格核对商户详情与领券预览。

所有交互都是只读核对：页面上不存在、采集器也绝不点击任何“领取/提交/下单”类
控件。每个（商户, 城市, 票根类别）矩阵格独立成一条证据，互不去重、互不挪用。
"""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from .domain import (interpret_card, interpret_entry, interpret_matrix_observation,
                     interpret_preview, matrix_business_key, PREVIEW_TRANSIENT_ERROR)

_LOCAL_HOSTS = ('127.0.0.1', 'localhost')
# 只允许点击明确的只读核对/预览/说明类控件；任何领取/提交类按钮都不触碰。
_SAFE_CONTROL_IDS = {'merchant-open', 'voucher-preview'}
_UNSAFE_WORDS = ('领取', '提交', '下单', '购买', '支付', '确认领取', '立即领取')
_WAIT_TIMEOUT_MS = 4000


def _ensure_local(origin):
    parts = urlsplit(origin)
    if parts.hostname not in _LOCAL_HOSTS or parts.scheme != 'http':
        raise ValueError('只允许本地演练来源')


def _with_fault(url, fault):
    if not fault:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query['fault'] = fault
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _select_options(page, select_id):
    locator = page.locator(f'#{select_id} option')
    if not locator.count():
        raise ValueError(f'页面缺少维度选项：#{select_id}')
    return locator.evaluate_all('(nodes) => nodes.map(n => n.value)')


def _safe_click(page, control_id):
    """点击前校验控件确为只读核对用途，杜绝误触领取/提交。"""
    locator = page.locator(f'#{control_id}')
    if locator.count() != 1:
        raise ValueError(f'控件不唯一：#{control_id}')
    text = (locator.inner_text() or '').strip()
    if any(word in text for word in _UNSAFE_WORDS):
        raise ValueError(f'拒绝点击疑似业务提交控件：#{control_id}')
    if control_id not in _SAFE_CONTROL_IDS:
        raise ValueError(f'未授权点击的控件：#{control_id}')
    locator.click()


_PENDING_MARKERS = ('读取中', '核对中', '加载中', '请稍候')


def _wait_final_text(page, locator, timeout=_WAIT_TIMEOUT_MS):
    """轮询等待输出越过“读取中/核对中”中间态并出现实质文本；超时则保留当前值，
    交由领域层记为未观测，而不是把中间态或空值当作结论。"""
    locator.wait_for(state='attached', timeout=timeout)
    deadline = page.evaluate('() => Date.now()') + timeout
    while True:
        text = locator.inner_text().strip()
        if text and not any(marker in text for marker in _PENDING_MARKERS):
            return locator.inner_text()
        if page.evaluate('() => Date.now()') >= deadline:
            return locator.inner_text()
        page.wait_for_timeout(50)


def _stabilize_ticket(page, requested_ticket):
    """城市切换会重置票根类别；选定后等待页面自身脚本跑完，再由调用方回读真实值。"""
    page.locator('#ticket').select_option(requested_ticket)
    page.wait_for_timeout(120)


def _save_artifacts(page, evidence_dir, safe_key, phase):
    if evidence_dir is None:
        return {}
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    base = f'{safe_key}_{phase}'
    html_path = evidence_dir / f'{base}.html'
    png_path = evidence_dir / f'{base}.png'
    html_path.write_text(page.content(), encoding='utf-8')
    page.screenshot(path=str(png_path), full_page=True)
    return {'html': str(html_path), 'screenshot': str(png_path)}


def read_catalog(origin):
    _ensure_local(origin)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(origin, wait_until='domcontentloaded')
            if not page.locator('main').count():
                raise ValueError('来源目录未加载')
            items = page.locator('.card').evaluate_all('(nodes) => nodes.map(n => ({id:n.dataset.key,name:n.querySelector("h2").textContent,summary:n.querySelector("p").textContent,href:n.querySelector("a").getAttribute("href")}))')
            return [{'source': page.url, **item, 'catalog_fact': interpret_card(item)} for item in items]
        finally:
            browser.close()


def read_detail_entry(origin, item_id, selection=None):
    _ensure_local(origin)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(origin, wait_until='domcontentloaded')
            card = page.locator(f'.card[data-key="{item_id}"]')
            if card.count() != 1:
                raise ValueError('card identity is not unique')
            catalog = {'id': item_id, 'summary': card.locator('p').inner_text()}
            card.locator('a').click()
            if page.locator('main').get_attribute('data-key') != item_id:
                raise ValueError('detail identity differs from catalog')
            if selection is not None:
                page.locator('#city').select_option(selection)
            catalog_fact = interpret_card(catalog)
            entry_signal = {'city': page.locator('#city').input_value(), 'ticket': page.locator('#ticket').input_value(), 'merchant': page.locator('main').get_attribute('data-key')}
            return {'id': item_id, 'source': page.url, 'catalog_fact': catalog_fact,
                    'opening_summary': page.locator('#summary').inner_text(),
                    'detail_fact': interpret_entry(catalog_fact, entry_signal)}
        finally:
            browser.close()


def _observe_one_cell(page, catalog_fact, requested_city, requested_ticket, evidence_dir, safe_key, retries):
    """在当前详情页核对一个（城市 × 票根类别）格，返回独立证据行。"""
    page.locator('#city').select_option(requested_city)
    _stabilize_ticket(page, requested_ticket)

    # 商户说明（详情条款）：先打开再做领券预览。
    _safe_click(page, 'merchant-open')
    merchant_detail_text = _wait_final_text(page, page.locator('#merchant-detail'))
    detail_artifacts = _save_artifacts(page, evidence_dir, safe_key, 'detail')

    # 领券预览（只核对资格，绝不领取）；短暂报错时按原坐标重试，结论以本格观测为准。
    attempts = 0
    recovered = False
    voucher_text = ''
    preview_artifacts = {}
    while True:
        attempts += 1
        # 每次预览前重新断言请求坐标：同值选择不会触发 change，故障页则会再次暴露。
        page.locator('#city').select_option(requested_city)
        _stabilize_ticket(page, requested_ticket)
        _safe_click(page, 'voucher-preview')
        voucher_text = _wait_final_text(page, page.locator('#voucher'))
        scope_text = page.locator('#voucher-scope').inner_text()
        preview_artifacts = _save_artifacts(page, evidence_dir, safe_key, f'preview_attempt_{attempts}')
        if interpret_preview(voucher_text) != PREVIEW_TRANSIENT_ERROR or attempts > retries:
            break
        recovered = True  # 记录曾遇到短暂故障；最终文本决定状态，重试成功仍可确认。
        page.wait_for_timeout(120)

    observed = {
        'city': page.locator('#city').input_value(),
        'ticket': page.locator('#ticket').input_value(),
        'merchant': page.locator('main').get_attribute('data-key'),
    }
    texts = {
        'voucher': voucher_text,
        'scope': scope_text,
        'merchant_detail': merchant_detail_text,
        'recovered': recovered,
        'attempts': attempts,
    }
    detail_fact = interpret_matrix_observation(
        catalog_fact,
        {'city': requested_city, 'ticket': requested_ticket},
        observed, texts)
    detail_fact['business_key'] = matrix_business_key(
        requested_city, catalog_fact['identity'], requested_ticket)
    return {
        'id': catalog_fact['identity'],
        'source': page.url,
        'requested_city': requested_city,
        'requested_ticket': requested_ticket,
        'catalog_fact': catalog_fact,
        'observed_texts': texts,
        'artifacts': {'detail': detail_artifacts, 'preview': preview_artifacts},
        'detail_fact': detail_fact,
        'evidence_only': True,
        'claim_submitted': False,
    }


def read_matrix_evidence(origin, evidence_dir=None, fault=None, retries=1):
    """对目录中每个商户，按城市 × 票根类别逐格走详情与领券预览。

    - 每个矩阵格独立一条记录，业务键含票根类别，绝不按商户去重；
    - 筛选重置/跳城/预览报错：本格标记 unknown 并给出 reasons，已读到的
      商户说明等已确认内容仍保留在记录里；
    - 空结果只表示“未观测到”，不会被解释为“无优惠”；
    - 不向任何其他类别借用资格结论。
    """
    _ensure_local(origin)
    catalog = read_catalog(origin)
    rows = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            for item in catalog:
                page = context.new_page()
                try:
                    page.goto(origin, wait_until='domcontentloaded')
                    card = page.locator(f'.card[data-key="{item["id"]}"]')
                    if card.count() != 1:
                        raise ValueError('card identity is not unique')
                    card.locator('a').click()
                    if fault:
                        page.goto(_with_fault(page.url, fault), wait_until='domcontentloaded')
                    if page.locator('main').get_attribute('data-key') != item['id']:
                        raise ValueError('detail identity differs from catalog')
                    cities = _select_options(page, 'city')
                    tickets = _select_options(page, 'ticket')
                    catalog_fact = item['catalog_fact']
                    for city in cities:
                        for ticket in tickets:
                            safe_key = re.sub(r'[^0-9A-Za-z一-鿿_-]+', '_',
                                              f'{item["id"]}_{city}_{ticket}')
                            row = _observe_one_cell(
                                page, catalog_fact, city, ticket,
                                evidence_dir, safe_key, retries)
                            rows.append(row)
                finally:
                    page.close()
        finally:
            browser.close()
    return rows
