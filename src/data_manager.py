"""Bounded table imports with explicit sheet/header selection and provenance."""
from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path
from zipfile import ZipFile, BadZipFile

import pandas as pd

from .value_hints import value_hints

from .i18n import tr

EMPTY_HEADER_ERROR = '选定的表头行没有内容，请检查工作表和表头行号。'
SHEET_COUNT_ERROR = 'Excel 需要包含 1–50 个工作表，请拆分后上传。'

MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', '10'))
MAX_ROWS = int(os.getenv('MAX_ROWS', '200000'))
MAX_COLUMNS = int(os.getenv('MAX_COLUMNS', '200'))
MAX_HEADER_ROW = 100
SUPPORTED_SUFFIXES = {'.csv', '.tsv', '.xlsx', '.xls'}


def _validate_file(uploaded_file):
    path = Path(uploaded_file)
    if not path.is_file():
        raise ValueError(tr('请选择可读取的表格文件。'))
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(tr('支持 .xlsx、.xls、.csv 和 .tsv；其他格式请先另存为其中一种。'))
    if path.stat().st_size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(tr('文件不能超过 {n} MB。', n=MAX_UPLOAD_MB))
    if path.suffix.lower() == '.xlsx':
        try:
            with ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > 5000 or sum(e.file_size for e in entries) > 100 * 1024 * 1024:
                    raise ValueError(tr('Excel 解压后的内容过大，请只保留要分析的数据。'))
                if any(e.filename.lower().endswith('vbaproject.bin') for e in entries):
                    raise ValueError(tr('请将含宏的文件另存为不含宏的 .xlsx 或 CSV。'))
        except BadZipFile as exc:
            raise ValueError(tr('无法读取这个 Excel 文件，请确认它不是加密文件或改过后缀。')) from exc
    return path


def inspect_source(uploaded_file):
    path = _validate_file(uploaded_file)
    kind = path.suffix.lower()[1:]
    sheets = []
    if kind in {'xlsx', 'xls'}:
        try:
            with pd.ExcelFile(path, engine='openpyxl' if kind == 'xlsx' else 'xlrd') as book:
                sheets = book.sheet_names
            if not sheets or len(sheets) > 50:
                raise ValueError(tr(SHEET_COUNT_ERROR))
        except ValueError as exc:
            if str(exc) == tr(SHEET_COUNT_ERROR):
                raise
            raise ValueError(tr('无法读取 Excel；请检查文件格式、密码保护和工作表。')) from exc
        except ImportError as exc:
            raise ValueError(tr('缺少 Excel 读取依赖，请安装项目 requirements.txt。')) from exc
        except Exception as exc:
            raise ValueError(tr('无法读取 Excel（{err}），请尝试另存为 .xlsx。', err=type(exc).__name__)) from exc
    return {'path':str(path), 'format':kind, 'sheets':sheets,
            'sheet':sheets[0] if sheets else None, 'header_row':1}


def _text_options(path):
    raw = path.read_bytes()
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            sample = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(tr('文本编码无法识别，请保存为 UTF-8 CSV 后再上传。'))
    if path.suffix.lower() == '.tsv':
        delimiter = '\t'
    else:
        try:
            delimiter = csv.Sniffer().sniff(sample[:65536], delimiters=',;\t|').delimiter
        except csv.Error:
            delimiter = ','
    return {'encoding':encoding, 'sep':delimiter, 'low_memory':False}


def _column_names(labels):
    normalized = []
    for index, label in enumerate(labels):
        text = '' if label is None or pd.isna(label) else str(label).replace('\r',' ').replace('\n',' ').strip()
        normalized.append(text or f'column_{index+1}')
    reserved, used, names, changes = set(normalized), set(), [], []
    for index, (original, base) in enumerate(zip(labels, normalized)):
        name, number = base, 2
        while name in used:
            name = f'{base}__{number}'
            number += 1
            while name in reserved or name in used:
                name = f'{base}__{number}'
                number += 1
        names.append(name)
        used.add(name)
        old = '' if original is None or pd.isna(original) else str(original)
        if old != name:
            changes.append({'position':index+1, 'original':old, 'column':name})
    return names, changes


def _xlsx_formulas(path, sheet, header_row):
    # Inspect saved caches rather than treating legitimate blank formula results as absent caches.
    from xml.etree import ElementTree as ET
    from posixpath import normpath
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    rel = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    formulas = 0
    with ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        selected = next(e for e in workbook.findall(ns+'sheets/'+ns+'sheet') if e.get('name')==sheet)
        relationships = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        target = next(e.get('Target') for e in relationships if e.get('Id')==selected.get(rel))
        member = target.lstrip('/') if target.startswith('/') else normpath('xl/'+target)
        with archive.open(member) as stream:
            for _, element in ET.iterparse(stream,events=('end',)):
                if element.tag != ns+'c':
                    continue
                coordinate = element.get('r','')
                row_text = ''.join(c for c in coordinate if c.isdigit())
                if not row_text or int(row_text)<header_row:
                    element.clear()
                    continue
                formula = element.find(ns+'f')
                if formula is not None:
                    formulas += 1
                    cached = element.find(ns+'v')
                    if cached is None or (cached.text is None and element.get('t') not in {'str','inlineStr'}):
                        raise ValueError(tr('{sheet} 的 {cell} 是公式，但没有可用的已保存结果。请在 Excel 中重新计算并保存，或粘贴为值后再上传。', sheet=sheet, cell=coordinate))
                    if element.get('t')=='e':
                        raise ValueError(tr('{sheet} 的 {cell} 保存了公式错误，请在 Excel 中修正后再上传。', sheet=sheet, cell=coordinate))
                element.clear()
    return formulas


def load_table(uploaded_file, sheet=None, header_row=1):
    source = inspect_source(uploaded_file)
    path, kind = Path(source['path']), source['format']
    if isinstance(header_row,bool) or not isinstance(header_row,(int,float)) or not float(header_row).is_integer() or not 1 <= header_row <= MAX_HEADER_ROW:
        raise ValueError(tr('表头行需要是 1–{n} 的整数。', n=MAX_HEADER_ROW))
    header_row = int(header_row)
    selected = source['sheet'] if sheet in (None,'') else sheet
    if source['sheets'] and selected not in source['sheets']:
        raise ValueError(tr('所选工作表不存在，请重新选择。'))
    info = {'format':kind, 'sheet':selected if source['sheets'] else None, 'header_row':header_row,
            'sheet_names':source['sheets']}
    try:
        if kind in {'csv','tsv'}:
            options = _text_options(path)
            labels_frame = pd.read_csv(path, header=None, skiprows=header_row-1, nrows=1,
                                       dtype=str, keep_default_na=False, **options)
            frame = pd.read_csv(path, header=0, skiprows=header_row-1, nrows=MAX_ROWS+1, dtype=object, **options)
            info.update({'encoding':options['encoding'], 'delimiter':options['sep']})
        else:
            with pd.ExcelFile(path, engine='openpyxl' if kind=='xlsx' else 'xlrd') as book:
                labels_frame = book.parse(selected, header=None, skiprows=header_row-1,nrows=1,keep_default_na=False)
                frame = book.parse(selected, header=header_row-1, nrows=MAX_ROWS+1, dtype=object).infer_objects(copy=False)
        if labels_frame.empty:
            raise ValueError(tr(EMPTY_HEADER_ERROR))
        labels = labels_frame.iloc[0].tolist()
        # A blank header may sit above populated cells and must retain a distinct field.
        labels += [''] * max(0,len(frame.columns)-len(labels))
        names, changes = _column_names(labels[:len(frame.columns)])
        frame.columns = names
        if kind in {'csv','tsv'}:
            for column in frame:
                values = frame[column].dropna().astype(str)
                if values.empty or values.str.match(r'^[+-]?0\d').any() or values.str.match(r'^[+-]?\d{16,}$').any():
                    continue
                numeric = pd.to_numeric(frame[column],errors='coerce')
                if numeric.notna().sum() == len(values):
                    frame[column] = numeric
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(tr('表格读取失败（{err}），请检查分隔符、表头和文件格式。', err=type(exc).__name__)) from exc
    if len(frame)>MAX_ROWS:
        raise ValueError(tr('表格不能超过 {n} 行。', n=f'{MAX_ROWS:,}'))
    if len(frame.columns)>MAX_COLUMNS:
        raise ValueError(tr('表格不能超过 {n} 列。', n=MAX_COLUMNS))
    if len(frame.columns)==0:
        raise ValueError(tr('表格至少需要一列。'))
    info['value_hints'] = value_hints(frame)
    info['column_changes'] = changes
    info['formula_cells'] = _xlsx_formulas(path,selected,header_row) if kind=='xlsx' else None
    frame.attrs['_source_path'] = str(path.resolve())
    frame.attrs['import_info'] = info
    with path.open('rb') as stream:
        frame.attrs['source_sha256'] = hashlib.file_digest(stream,'sha256').hexdigest()
    return frame


def load_csv(uploaded_file):
    """Compatibility entry point; new code should use load_table."""
    return load_table(uploaded_file)
