from src.cli import main


def test_cli_report_is_cpu_only_and_preserves_existing_document(tmp_path):
    csv = tmp_path / 'sample.csv'
    csv.write_text('amount,region\n10,East\n,West\n', encoding='utf-8')
    target = tmp_path / 'report.md'
    assert main([str(csv), '--report', str(target)]) == 0
    original = target.read_text(encoding='utf-8')
    assert 'Missing cells: 1 / 4' in original
    assert main([str(csv), '--report', str(target)]) == 1
    assert target.read_text(encoding='utf-8') == original
