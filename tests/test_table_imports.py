import hashlib
import json

import pandas as pd
import pytest

import app
from evaluation.table_fixtures import write_xlsx, diverse_workbook, write_xls
from src import data_manager
from src.data_manager import load_table
from src.tools import build_tools, is_sensitive_column


def test_excel_sheet_header_chinese_names_duplicates_and_provenance(tmp_path):
    path = diverse_workbook(tmp_path/'订单.xlsx')
    frame = load_table(path,sheet='十月订单',header_row=3)
    assert frame.shape == (3,6)
    assert list(frame.columns) == ['地区','金额（元）','商品 名称','金额（元）__2','column_5','客户编号']
    assert frame['金额（元）'].mean() == 15 and frame['金额（元）'].isna().sum()==1
    assert frame['客户编号'].tolist()==['001','002','003']
    assert frame.attrs['source_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(frame.attrs['import_info']['column_changes'])==2
    assert frame.attrs['import_info']['sheet_names']==['说明','十月订单','九月订单']
    tool = next(t for t in build_tools(frame) if t.name=='analyze_distribution')
    assert json.loads(tool.invoke({'column':'金额（元）'}))['mean']==15
    reference = load_table(path,sheet='九月订单')
    assert reference['金额（元）'].mean()==8


def test_legacy_excel_import(tmp_path):
    frame = load_table(write_xls(tmp_path/'legacy.xls'))
    assert frame.shape==(2,2) and frame['amount'].sum()==30
    assert frame.attrs['import_info']['sheet']=='Data'


@pytest.mark.parametrize('suffix,encoding,sep',[('.csv','utf-8-sig',','),('.csv','gb18030',','),('.csv','utf-8',';'),('.tsv','utf-8','\t')])
def test_delimiters_encodings_and_identifier_text(tmp_path,suffix,encoding,sep):
    path=tmp_path/('数据'+suffix)
    path.write_text(sep.join(['地区','金额（元）','客户编号'])+'\n'+sep.join(['华东','10','001'])+'\n'+sep.join(['华西','20','002'])+'\n',encoding=encoding)
    frame=load_table(path)
    assert frame['金额（元）'].sum()==30 and frame['客户编号'].tolist()==['001','002']
    assert frame.attrs['import_info']['delimiter']==sep


def test_header_collisions_na_label_and_empty_header_csv(tmp_path):
    path=tmp_path/'headers.csv'
    path.write_text(' 金额 ,金额,金额__2,,NA\n1,2,3,4,5\n', encoding='utf-8')
    frame=load_table(path)
    assert list(frame.columns)==['金额','金额__3','金额__2','column_4','NA']
    assert len(frame.attrs['import_info']['column_changes'])==3


def test_header_offset_csv_and_empty_sheet_recovery(tmp_path):
    path=tmp_path/'offset.csv';path.write_text('说明\n\n地区,金额\n华东,12\n', encoding='utf-8')
    assert load_table(path,header_row=3)['金额'].sum()==12
    book=write_xlsx(tmp_path/'empty.xlsx',{'空页':[], '数据':[['列'],[3]]})
    with pytest.raises(ValueError): load_table(book)
    assert load_table(book,sheet='数据')['列'].sum()==3


def test_formula_cache_and_excel_dates(tmp_path):
    path=write_xlsx(tmp_path/'cached.xlsx',{'表':[['金额','日期'],[{'formula':'10+20','value':30},{'value':46000,'style':1}]]})
    frame=load_table(path)
    assert frame['金额'].iloc[0]==30 and isinstance(frame['日期'].iloc[0],pd.Timestamp)
    assert frame.attrs['import_info']['formula_cells']==1
    missing=write_xlsx(tmp_path/'no-cache.xlsx',{'表':[['金额'],[{'formula':'10+20'}]]})
    with pytest.raises(ValueError,match='已保存结果'): load_table(missing)
    blank=write_xlsx(tmp_path/'blank.xlsx',{'表':[['金额','标记'],[{'formula':'IF(1=1,"",1)','value':'','type':'str'},'合法空字符串']]})
    assert load_table(blank)['金额'].isna().sum()==1
    bad=write_xlsx(tmp_path/'error.xlsx',{'表':[['金额'],[{'formula':'1/0','value':'#DIV/0!','type':'e'}]]})
    with pytest.raises(ValueError,match='公式错误'): load_table(bad)


@pytest.mark.parametrize('row',[0,1.5,101,True])
def test_invalid_header_rows(tmp_path,row):
    path=tmp_path/'data.csv';path.write_text('x\n1\n', encoding='utf-8')
    with pytest.raises(ValueError,match='表头行'): load_table(path,header_row=row)


def test_invalid_formats_sheets_and_limits(tmp_path,monkeypatch):
    path=tmp_path/'renamed.xlsx';path.write_text('not a workbook', encoding='utf-8')
    with pytest.raises(ValueError): load_table(path)
    other=tmp_path/'data.xlsm';other.write_text('unsupported', encoding='utf-8')
    with pytest.raises(ValueError,match='支持'): load_table(other)
    book=diverse_workbook(tmp_path/'rows.xlsx')
    with pytest.raises(ValueError,match='工作表不存在'): load_table(book,sheet='不存在')
    monkeypatch.setattr(data_manager,'MAX_ROWS',2)
    with pytest.raises(ValueError,match='2 行'): load_table(book,sheet='十月订单',header_row=3)


def test_upload_settings_reset_and_reference_sheet_selection(tmp_path):
    path=diverse_workbook(tmp_path/'two.xlsx')
    loaded=app.on_import_upload(str(path))
    assert len(loaded)==12 and loaded[9]['sheet']=='说明'
    changed=app.on_read_table(loaded[9],'十月订单',3)
    assert changed[0].shape==(3,6) and changed[-2]['entries']==[] and changed[-1] is None
    assert '金额（元）__2' in app.import_notes(changed[9])
    reference=app.on_reference_upload(str(path))[0]
    ref=app.on_read_reference(reference,'九月订单',1)[0]
    assert ref['frame'].shape==(2,6) and '九月订单' in app.on_reference_status(ref)
    cleared=app._without_import_source(app.on_session_clear)()
    assert cleared[9] is None and cleared[-1] is None
    assert not app.on_import_settings(None)[0]['visible']


def test_chinese_sensitive_names_follow_existing_redaction_rules():
    assert all(is_sensitive_column(c) for c in ['客户编号','姓名','手机号码','身份证号'])
    assert not is_sensitive_column('金额（元）')
    frame=pd.DataFrame({'姓名':['虚构甲'],'金额（元）':[10]})
    assert '虚构甲' not in app.on_preview(frame)


def test_cli_selects_excel_sheet_and_header(tmp_path):
    from src.cli import main
    path=diverse_workbook(tmp_path/'source.xlsx')
    report=tmp_path/'report.md'
    assert main([str(path),'--sheet','十月订单','--header-row','3','--report',str(report)])==0
    assert '金额（元）' in report.read_text(encoding='utf-8') and '3' in report.read_text(encoding='utf-8')


def test_upload_and_shape_limits_still_apply_to_excel(tmp_path,monkeypatch):
    path=diverse_workbook(tmp_path/'wide.xlsx')
    monkeypatch.setattr(data_manager,'MAX_COLUMNS',2)
    with pytest.raises(ValueError,match='2 列'): load_table(path,sheet='十月订单',header_row=3)
    monkeypatch.setattr(data_manager,'MAX_UPLOAD_MB',0)
    with pytest.raises(ValueError,match='MB'): load_table(path)
