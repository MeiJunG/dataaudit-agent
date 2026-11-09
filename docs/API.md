# 用代码调用 DataAudit

网页里能做的分析，也可以从 Python 调用。应用基于 Gradio，接口通过官方的 `gradio_client` 访问；
每个 `Client` 拥有自己的会话状态，相当于一个独立的浏览器标签页。

## 最小示例

```bash
python app.py                      # 先启动应用
python examples/api_client.py examples/office_orders.csv "按 region 分组，统计 amount 的总和。"
```

```python
from gradio_client import Client, handle_file

client = Client("http://127.0.0.1:7860/", verbose=False)
client.predict(handle_file("examples/office_orders.csv"), api_name="/on_upload")
answer, trace, report = client.predict("哪些列有空值？请统计数量和比例。", api_name="/on_submit")
print(answer)          # Markdown 格式的结论
print(trace[0])        # 第一步工具调用：tool、arguments、status、result、duration_ms
```

英文页面的接口地址是 `http://127.0.0.1:7860/en/`，接口名和参数相同，返回的固定文字是英文。

同一个 `client` 上继续 `predict(..., api_name="/on_submit")` 就是追问，会沿用前面选过的字段和图表设置。

## 常用接口

| 接口 | 参数 | 作用 |
|---|---|---|
| `/on_upload` | 文件 | 读入表格（默认第一个工作表、第一行是列名） |
| `/on_import_settings` | 无 | 读取工作簿的工作表列表 |
| `/on_read_table` | 工作表名, 列名所在行 | 改读其他工作表或表头行 |
| `/on_submit` | 问题 | 运行 Agent，返回 `(回答, 工具调用记录, 报告文件)` |
| `/on_clear` | 无 | 移除当前表格 |
| `/on_current_export` | 无 | 生成当前分析记录的 JSON 下载链接 |

完整列表和参数类型：打开网页底部的 **通过 API 使用**，或运行

```python
Client("http://127.0.0.1:7860/").view_api()
```

## 注意

- 返回的 `trace` 是真实执行过的工具调用；回答里的数字来自这些结果。
- 上传大小、行列数受 `.env` 里的 `MAX_UPLOAD_MB`、`MAX_ROWS`、`MAX_COLUMNS` 限制。
- 应用没有用户登录。默认只监听本机 `127.0.0.1`；如果要给其他人用，请放在你自己的登录/防火墙后面，
  不要直接把端口暴露到公网。
