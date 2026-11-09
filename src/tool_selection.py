"""Small model-selected tool families and unambiguous Unicode field resolution."""
import unicodedata

FAMILIES = {
    'tables':{'list_workbook_sheets','inspect_sheet_layout','query_rows','aggregate_rows','calculate_row_metric'},
    'general':{'inspect_schema','check_missing_values','check_duplicates','analyze_distribution','validate_data_types','create_chart','check_key_uniqueness','list_workbook_sheets','inspect_sheet_layout','query_rows','aggregate_rows','calculate_row_metric'},
    'profile':{'inspect_schema','check_missing_values','check_duplicates','analyze_distribution','detect_outliers','validate_data_types','check_correlations'},
    'filter':{'inspect_schema','filter_and_aggregate','check_missing_values','check_duplicates'},
    'chart':{'inspect_schema','create_chart','check_missing_values','check_duplicates','analyze_distribution'},
    'rules':{'inspect_schema','check_numeric_range','compare_columns','validate_categories','check_key_uniqueness','check_text_quality','check_required_if','check_date_order','check_missing_values','check_duplicates','validate_data_types'},
    'groups':{'inspect_schema','compare_groups','analyze_distribution','check_missing_values','check_duplicates'},
    'dates':{'inspect_schema','inspect_date_column','summarize_time_series','create_chart','check_missing_values','check_duplicates'},
    'report':{'inspect_schema','generate_quality_report','check_missing_values','check_duplicates'},
}
FIELD_ARGUMENTS = {'column','columns','subset','x','y','group_column','metric_column','date_column',
                   'left_column','right_column','start_column','end_column','condition_column','filter_column','required_columns'}


def select_family_tools(tools,family):
    if family is None:
        return tools
    if family not in FAMILIES:
        raise ValueError('Unknown tool family.')
    return [t for t in tools if t.name in FAMILIES[family]]


def resolve_field_arguments(arguments,columns):
    labels = list(columns)
    def normalize(value): return unicodedata.normalize('NFKC',value).strip()
    mappings=[]
    def resolve(value,parameter):
        if not isinstance(value,str) or value in labels:
            return value
        matches=[c for c in labels if normalize(str(c))==normalize(value)]
        if len(matches)>1:
            raise ValueError(f'Ambiguous column spelling: {value}. Use an exact displayed field name.')
        if len(matches)==1:
            mappings.append({'parameter':parameter,'requested':value,'column':str(matches[0])})
            return matches[0]
        return value
    result={}
    for key,value in arguments.items():
        if key in FIELD_ARGUMENTS:
            result[key]=[resolve(v,key) for v in value] if isinstance(value,list) else resolve(value,key)
        else:
            result[key]=value
    return result,mappings


FAMILY_INSTRUCTIONS = {
    'chart':'当前任务是绘图。用户指定指标列并要求平均值时，必须传 y=该实际指标列、method=mean；合计用 sum。只有用户明确要求记录数时才使用 count 并省略 y。不要把数值走势改画成记录数。日期线按用户要求选择 day/week/month。',
    'filter':'当前任务是按明确条件筛选后计算。使用 filter_and_aggregate；常数阈值不是第二个列名。ge 是不低于，lt 是小于。不要用分组频数代替筛选计数。',
    'profile':'单个字段的每种取值数量、频率、均值等使用 analyze_distribution。每种类别的数量不是给定条件的筛选计数。',
    'rules':'如果问题是某字段能否作为主键，使用 check_key_uniqueness 检查这些字段的缺失和重复。整行查重不能证明某个字段唯一。',
}
