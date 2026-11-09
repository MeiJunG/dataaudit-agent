import pytest
from fastapi.testclient import TestClient

from src.artifact_download import record_download_app


def test_record_download_is_an_attachment_and_other_files_are_unavailable(tmp_path):
    name = 'analysis-' + 'a' * 64 + '.json'
    (tmp_path/name).write_text('{"question":"test"}', encoding='utf-8')
    (tmp_path/'private.json').write_text('not an export', encoding='utf-8')
    client = TestClient(record_download_app(tmp_path))
    response = client.get('/analysis-records/'+name)
    assert response.json() == {'question':'test'}
    assert response.headers['content-disposition'] == f'attachment; filename="{name}"'
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/analysis-records/private.json').status_code == 404
    assert client.get('/analysis-records/analysis-'+'b'*64+'.json').status_code == 404
    link = tmp_path/('analysis-'+'c'*64+'.json')
    try:
        link.symlink_to(tmp_path/name)
    except OSError:  # Windows without Developer Mode cannot create symlinks
        pytest.skip('symlinks not permitted on this system')
    assert client.get('/analysis-records/'+link.name).status_code == 404
