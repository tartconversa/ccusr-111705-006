# 票根优惠的资格入口与商户核对

这是票根优惠资料的本地演练门户与目录采集器。演练数据仅在环回地址提供，不会操作真实用户、订单或商户。

## 采集流程

- `app.capture.read_catalog` 读取目录；`app.capture.read_detail_entry` 走卡片到详情并接收可选业务选择，`app.domain.interpret_entry` 确认业务身份，`app.records.save_detail_entries` 追加详情入口收据。
- `app.capture.read_matrix_evidence(origin, evidence_dir, fault, retries)` 对目录中每个商户，按 **城市 × 票根类别** 逐格真实浏览：选定城市与类别 → 打开商户说明 → 点击只读的“核对资格”领券预览。每格独立成一条证据，业务键为 `城市:商户:票根类别`，同一商户的不同类别**不去重、不合并**。
- `app.records.save_matrix_evidence` 只追加不覆盖，并在落库前断言 `evidence_only=True`、`claim_submitted=False`；`app.review.build_matrix_review` 生成客服核对报告（含每格观测文本、未知原因、HTML 快照与整页截图路径）。

## 未知与边界（客服投诉对应的处理原则）

- 只依据本格自己的页面观测下结论，**不把另一类票根的资格挪用过来**；
- 票根类别筛选被页面重置、详情跳到其他城市、商户身份不符：该格记 `unknown` 并写明原因，已读到的商户说明等已确认内容仍保留；
- 领券预览短暂报错：按原坐标重试（`--retries`），重试成功则确认并记录尝试次数；重试耗尽仍是 `unknown`；
- 空结果或未观测到只表示“未确认”，**绝不解释为“无优惠”**。

## 运行

站点约定见 `docs/portal.md`；测试时从本地任意空闲端口启动演练站点。安装锁定依赖并准备 Chromium 后：

- `python -m unittest discover -s tests -v`：运行全部测试（含矩阵与故障恢复）。
- `python -m compileall -q app tests`：检查代码。
- `python -m app.site`：启动本地演练站点。
- `python -m app.cli`：另一个终端观察目录输出。
- `python -m app.cli matrix --db 证据.sqlite3 --evidence-dir 证据目录`：生成客服核对证据（只读，不领取）。
- `python -m app.cli matrix --fault reset|cross-city|transient`：演练筛选重置、跳城、预览短暂报错三类故障下的证据保留。

两个终端命令用于人工演示，自动测试不依赖固定端口。所有访问仅限环回来源，页面上不存在、采集器也绝不点击任何领取/提交类控件。
