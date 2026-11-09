"""Exercise live chart selection, chart/download callbacks, and dataset reset via Gradio."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gradio_client import Client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:7860')
    parser.add_argument('--output', type=Path, default=Path('results/chart-web.json'))
    args = parser.parse_args()
    client = Client(args.url, verbose=False)
    client.predict(api_name='/on_office_example')
    cases = [('按 region 分组，用 amount 合计画柱状图。', 'bar'),
             ('画 amount 的直方图。', 'histogram'),
             ('按 order_date 每天汇总 amount 合计，画折线图。', 'line')]
    results = []
    for question, kind in cases:
        answer, trace, _ = client.predict(question, api_name='/on_submit')
        observations = [e['structured_result'] for e in trace if e['tool'] == 'create_chart' and e['status'] == 'ok']
        assert observations and observations[-1]['chart_type'] == kind, (answer, trace)
        # Layout-component updates (Tabs) are omitted by Gradio's public client API.
        plot, file = client.predict(trace, api_name='/on_agent_chart')
        figure = json.loads(plot['plot'])
        filename = file['value'] if isinstance(file, dict) else file
        # gradio_client may expose downloadable files as local paths or FileData dictionaries.
        if isinstance(filename, dict):
            filename = filename.get('path')
        assert filename and Path(filename).is_file(), file
        content = Path(filename).read_text(encoding='utf-8')
        assert 'plotly.js v' in content and '<script src=' not in content
        if kind == 'bar':
            assert dict(zip(figure['data'][0]['x'], figure['data'][0]['y'])) == {'East':360,'North':540,'West':160}
        elif kind == 'histogram':
            # The tool evidence is independent of Plotly's numeric-array encoding.
            assert sum(p['y'] for p in observations[-1]['data']) == 8
        else:
            assert observations[-1]['excluded_x_rows'] == 1
        results.append({'question':question, 'chart_type':kind, 'success':True,
                        'answer':answer, 'offline_export_bytes':Path(filename).stat().st_size,
                        'observation':observations[-1]})
        print(f'{kind}: chart and offline download passed', flush=True)
    cleared = client.predict(api_name='/on_consistency_example')
    assert cleared[-2] == []
    _, file = client.predict([], api_name='/on_agent_chart')
    assert not file['visible'] and file['value'] is None
    client.predict(api_name='/on_clear')
    _, file = client.predict([], api_name='/on_agent_chart')
    assert not file['visible']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'cases':results, 'dataset_reset':True, 'clear_reset':True,
                                      'scope':'Live server callbacks, not browser rendering'}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('CHART_WEB_OK', flush=True)


if __name__ == '__main__':
    main()
