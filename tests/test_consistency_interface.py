from app import on_consistency_example,on_preview


def test_consistency_preview_masks_ids_and_displays_missing_cells():
    result=on_consistency_example()
    assert result[0].shape==(6,6)
    html=on_preview(result[0])
    assert '已隐藏' in html and 'A001' not in html
    assert '空值' in html and 'recorded_amount' in html
    assert result[-3]=='' and result[-2]==[]
    assert '上传表格后' in on_preview(None)
