# 本地来源行为

票根优惠目录列出稳定的 `data-key` 和详情路径；详情需由浏览器导航读取，`城市`选择改变当前页面状态，`票根类别`和`领券预览`是分步出现的可见内容。筛选类别有时会在跳页后重置。详情接口是浏览器页面，不是业务 API；运行时只允许访问环回来源。

`fixtures/portal.json` 提供合成业务资料，不包含真实个人数据。`records.save_catalog` 覆盖同一目录身份；`records.save_detail_entries` 以业务键追加入口访问，不把入口访问等同于资格、授权、可预约或正式提交。测试均只访问本地环回页面。

## 矩阵证据（客服核对，不领取）

`capture.read_matrix_evidence` 对每个商户遍历页面上实际可选的城市与票根类别，逐格执行：

1. 选定请求城市，再选定请求票根类别（城市切换会重置类别，故城市后必须重选类别）；
2. 点击 `#merchant-open` 读取商户说明，等待“读取中”中间态消失；
3. 点击 `#voucher-preview` 读取领券预览，同样越过“核对中”中间态；该按钮只展示资格文本，不产生领取。

每格记录请求坐标与页面回读坐标。坐标漂移（`city_redirected` / `ticket_filter_reset` / `merchant_identity_mismatch`）、预览短暂报错（`preview_transient_error`）、未观测到（`preview_not_observed`）或无法识别（`preview_unrecognized`）一律判 `unknown`；只有坐标一致且预览给出可识别结论（可领取 / 名额待核含名额用尽）才判 `confirmed`。`名额待核/用尽` 是已确认的页面事实，不是无优惠。

采集器只允许点击白名单控件（`#merchant-open`、`#voucher-preview`），控件文本含“领取/提交/下单/购买/支付”等词时拒绝点击；每条证据带 `evidence_only=true`、`claim_submitted=false`，落库前再次校验。

## 故障注入（仅演练）

详情 URL 支持 `?fault=` 查询参数，缺省页面与基线完全一致：

- `reset`：非首项票根类别被页面在下一拍重置回首项；
- `cross-city`：城市选择被静默改写为另一城市；
- `transient`：每个（城市, 票根类别）坐标首次预览返回“系统繁忙请稍后重试”，同坐标再次核对恢复。

故障脚本只在环回演练页面输出，用于验证采集器“保留已确认范围、明确未知、不以空结果否定优惠、不跨类别挪用资格”的行为。
