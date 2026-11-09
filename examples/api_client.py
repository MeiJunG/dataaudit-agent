"""Call a running DataAudit app from Python.

    pip install gradio_client
    python examples/api_client.py examples/office_orders.csv "按 region 分组，统计 amount 的总和。"

Start the app first (python app.py). Each Client gets its own session state, like a browser tab.
"""
import json
import sys

from gradio_client import Client, handle_file

URL = 'http://127.0.0.1:7860/'


def main(path, question):
    client = Client(URL, verbose=False)
    client.predict(handle_file(path), api_name='/on_upload')          # load the table
    answer, trace, _report = client.predict(question, api_name='/on_submit')
    print(answer)
    print('\n工具调用：')
    for step in trace:
        print(f"  第 {step['step']} 步 {step['tool']} · {step['status']} · {json.dumps(step['arguments'], ensure_ascii=False)}")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
