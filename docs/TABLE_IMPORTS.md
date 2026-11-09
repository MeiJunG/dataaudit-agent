# Table imports

DataAudit accepts `.xlsx`, legacy `.xls`, `.csv` and `.tsv` for both current and reference tables. The web interface and CLI use the same validated reader. Files remain on the inference/application server; the original uploaded bytes are not modified.

## Excel

Upload a workbook, then use **读取设置 · 工作表与表头** to choose a worksheet and **列名在第几行**. Click **按设置重新读取** to apply the selection. The default is the first worksheet, with column names on row 1. Excel settings open after upload so the active worksheet is visible. A workbook with a cover or instruction sheet can be switched to the data sheet even when the first sheet fails to load.

For reference files, use **参考表读取设置** and **重新读取参考表**. One sheet is analyzed per table. The same workbook may be selected twice with different sheets to compare two periods. Worksheets are never silently merged.

Changing the current sheet/header clears the prior answer, chart, report, reference and session history. Changing the reference sheet/header clears the comparison results/history while retaining the current table. Dataset exports record the original file SHA-256 plus selected sheet, header row and column-name changes, distinguishing two analyses of the same file.

The fixture [multi_sheet_orders.xlsx](../examples/multi_sheet_orders.xlsx) contains fictional data and deliberate header issues:

- Select **十月订单**, with header row **3**: three rows, six columns, mean `金额（元）` 15, one missing amount.
- Select **九月订单**, with header row **1**, as the reference: two rows and mean amount 8.
- The duplicated fourth header becomes `金额（元）__2`; the empty fifth header becomes `column_5`. Both changes are shown in the reading settings.

## Column names and table shape

No fixed English schema is required. Chinese, English, spaces, parentheses and units in names are supported: `地区`, `金额（元）`, `商品 名称`, `sales amount` are valid. Ask using the displayed field names; the model receives actual column metadata and is instructed to map descriptions to exact names.

Leading/trailing header whitespace is trimmed and header line breaks become spaces. Blank headers receive `column_<position>`. Duplicate names receive `__2`, `__3`, etc., avoiding existing-name collisions. Changes retain source position and original name, appear in the reading settings and are stored in JSON records. The original file is unchanged. These changes identify columns; they do not resolve a business ambiguity between two identically named fields.

Use one row per record and one column per field, with one selected header row. Titles/notes above that row are excluded. Multi-row merged headers are not flattened into a business schema; merged data cells are not filled down. Totals, subtotals and notes below the header are not automatically removed. For analysis, prepare a rectangular detail table or select the appropriate worksheet/header first.

## Values, formulas and formatting

Excel cells are read as underlying values. Numeric/currency display styles are not a unit conversion: an Excel cell displayed as `20%` usually stores `0.2`. Dates stored as Excel dates are read as dates. Text with currency symbols, localized separators or percentages is not silently rewritten into a business measure.

Text-typed Excel identifiers retain leading zeros. In CSV/TSV imports, integer-like values with leading zeros or 16+ digits stay text during import; other fully numeric columns are inferred as numbers. Identifiers already rounded or changed by Excel cannot be restored. Individual tools may explicitly coerce a selected field for a requested numeric operation; inferred import dtype alone is not a semantic identifier classifier.

Formula execution/recalculation is not part of the upload workflow. The reader uses saved calculation results. For `.xlsx`, a missing formula cache or a cached formula error causes an actionable import error, rather than being silently counted as a normal blank. Legitimate cached empty-string formulas may appear as missing cells. After modifying formulas, recalculate and save in Excel, or paste results as values before uploading. `.xls` uses its legacy reader's saved results; it does not provide the same formula-cache diagnostics as `.xlsx`.

Default Pandas missing-value tokens apply, including empty cells and common text markers such as `N/A` and `NA`. A literal category named `NA` may therefore be treated as missing in data cells; header labels are preserved. Users needing custom missing-token or locale rules should preprocess the source; the current UI does not expose those controls.

The implementation uses [Pandas Excel readers](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html), [openpyxl saved-value semantics](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html), and [xlrd for legacy `.xls`](https://xlrd.readthedocs.io/en/latest/). It does not execute macros or refresh external workbook links.

## CSV and TSV

Text imports try UTF-8 (with or without BOM), then GB18030. TSV uses tabs. CSV detects common comma, semicolon, tab or pipe delimiters, falling back to comma when detection is inconclusive. Detection is not universal; unusual files can be saved as UTF-8 comma-separated CSV. Header-row selection also works for text files.

## Limits

Defaults remain 10 MB per uploaded file, 200,000 data rows and 200 columns. A header row must be 1–100. Excel workbooks may have up to 50 worksheets. `.xlsx` ZIP containers are limited to 5000 members and 100 MiB of declared expanded content. Password-protected files, `.xlsm`, `.xlsb`, `.ods`, images/PDF tables and automatic cross-sheet joins are not supported by this importer. Convert these sources to a supported plain table first.

Sensitive-looking Chinese labels such as 姓名、手机号、身份证号、客户编号 now use the existing preview/sample-redaction behavior. This extends the naming heuristic; it is not complete privacy classification or an anonymization guarantee.

## CLI and validation

```bash
python -m src.cli examples/multi_sheet_orders.xlsx --sheet 十月订单 --header-row 3 --report outputs/excel-report.md
python -m evaluation.check_table_imports_web --output results/table-imports-web.json
```

`evaluation/table_fixtures.py` builds small synthetic XLSX/BIFF8 fixtures directly from file-format records. Unit tests exercise actual readers, header collisions, UTF-8/GB18030 and delimiters, typed dates, cached/missing/error/empty-string formulas, legacy XLS, limits, CLI selection, state resets and Chinese-name redaction. Live model checks use exact computed means and chart observations; these are development prompts, not independent reliability estimates.


## Recorded outcome

The final server run passed 166 tests in 10.30 seconds. All six multi-format live model cases and five earlier CSV comparison cases passed. Actual XLSX browser upload/selection/analysis/download/reset checks and 390/1280px geometry checks passed; see [EXCEL_VISUAL_QA.json](EXCEL_VISUAL_QA.json). The compact [evaluation record](../evaluation/table-imports.summary.json) includes API-harness corrections. These are synthetic development checks, not broad data or model guarantees.
