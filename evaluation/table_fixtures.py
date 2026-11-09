"""Tiny synthetic import fixtures, authored as file-format records for software tests."""
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile, ZIP_DEFLATED
import struct


def write_xlsx(path, sheets):
    def letter(index):
        result = ''
        while index:
            index,rem = divmod(index-1,26)
            result = chr(65+rem)+result
        return result
    main = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    types = ['<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
             '<Default Extension="xml" ContentType="application/xml"/>',
             '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
             '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    workbook, relationships = [], []
    with ZipFile(path,'w',ZIP_DEFLATED) as archive:
        archive.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="'+rel+'/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        for i,(name,rows) in enumerate(sheets.items(),1):
            workbook.append(f'<sheet name={quoteattr(name)} sheetId="{i}" r:id="rId{i}"/>')
            relationships.append(f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>')
            types.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
            data = []
            for r,row in enumerate(rows,1):
                cells = []
                for c,value in enumerate(row,1):
                    coord = f'{letter(c)}{r}'
                    if value is None: continue
                    if isinstance(value,dict):
                        formula = '<f>'+escape(value['formula'])+'</f>' if 'formula' in value else ''
                        cached = '<v>'+escape(str(value['value']))+'</v>' if value.get('value') is not None else ''
                        value_type = ' t='+quoteattr(value['type']) if 'type' in value else ''
                        cells.append(f'<c r="{coord}" s="{value.get("style",0)}"{value_type}>{formula}{cached}</c>')
                    elif isinstance(value,bool):
                        cells.append(f'<c r="{coord}" t="b"><v>{int(value)}</v></c>')
                    elif isinstance(value,(int,float)):
                        cells.append(f'<c r="{coord}"><v>{value}</v></c>')
                    else:
                        cells.append(f'<c r="{coord}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>')
                data.append(f'<row r="{r}">'+''.join(cells)+'</row>')
            archive.writestr(f'xl/worksheets/sheet{i}.xml',f'<worksheet xmlns="{main}"><sheetData>'+''.join(data)+'</sheetData></worksheet>')
        relationships.append(f'<Relationship Id="styles" Type="{rel}/styles" Target="styles.xml"/>')
        archive.writestr('xl/workbook.xml',f'<workbook xmlns="{main}" xmlns:r="{rel}"><sheets>'+''.join(workbook)+'</sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(relationships)+'</Relationships>')
        archive.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'+''.join(types)+'</Types>')
        archive.writestr('xl/styles.xml',f'<styleSheet xmlns="{main}"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" xfId="0"/><xf numFmtId="14" xfId="0" applyNumberFormat="1"/><xf numFmtId="10" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    return Path(path)


def diverse_workbook(path):
    return write_xlsx(path,{
        '说明':[['说明','提示'],['虚构示例','请选十月订单，列名在第 3 行。']],
        '十月订单':[['十月订单（虚构数据）'],[],['地区','金额（元）','商品 名称','金额（元）',None,'客户编号'],
                ['华东',10,'文具',12,'待复核','001'],['华西',20,'纸张',25,'正常','002'],['华东',None,'文具',30,'正常','003']],
        '九月订单':[['地区','金额（元）','商品 名称','金额（元）',None,'客户编号'],
                ['华东',8,'文具',8,'正常','001'],['华西',8,'纸张',8,'正常','002']]})


def write_xls(path):
    """A minimal BIFF8 workbook with no executable content or external dependency."""
    def record(code,payload=b''):
        return struct.pack('<HH',code,len(payload))+payload
    def bof(kind):
        return record(0x0809,struct.pack('<HHHHII',0x0600,kind,0x0DBB,1997,0,6))
    def label(r,c,text):
        return record(0x0204,struct.pack('<HHHHB',r,c,0,len(text),0)+text.encode('ascii'))
    sheet = bof(0x0010)+record(0x0200,struct.pack('<IIHHH',0,3,0,2,0))
    sheet += label(0,0,'region')+label(0,1,'amount')+label(1,0,'East')+label(2,0,'West')
    sheet += record(0x0203,struct.pack('<HHHd',1,1,0,10))+record(0x0203,struct.pack('<HHHd',2,1,0,20))+record(0x000A)
    prefix = bof(0x0005)+record(0x0042,struct.pack('<H',1252))
    bounds = lambda offset: record(0x0085,struct.pack('<IBBBB',offset,0,0,4,0)+b'Data')
    offset = len(prefix)+len(bounds(0))+4
    Path(path).write_bytes(prefix+bounds(offset)+record(0x000A)+sheet)
    return Path(path)


def domain_workbook(path):
    """Five content domains plus intentionally unnormalized representations; all fictitious."""
    from datetime import date, timedelta
    serial = lambda d: (d-date(1899,12,30)).days
    dates = [date(2026,1,1)+timedelta(days=i) for i in range(45)]
    grades = [['学号','班级','语文','数学','英语'],
              ['001','一班',80,90,70],['002','一班',60,50,80],['003','二班',90,None,95],
              ['004','二班',70,70,85],['005','一班',None,60,60],['006','二班',85,100,90]]
    sales = [['日期','地区','销售额（元）','数量（件）','状态','税率'],
             ['2026-01-01','华东',1200,12,'已完成',{'value':.13,'style':2}],
             ['2026-01-10','华东',800,8,'已完成',{'value':.13,'style':2}],
             ['2026-01-20','华西',1500,15,'已完成',{'value':.13,'style':2}],
             ['2026-02-01','华西',None,4,'待确认',{'value':.13,'style':2}],
             ['2026-02-03','华东',-200,-2,'退款',{'value':.13,'style':2}]]
    stocks = [['日期','股票代码','收盘价','最高价','最低价','成交量','涨跌幅']]+[
        [{'value':serial(d),'style':1},'DEMO',None if i==20 else 100+i*.5,101+i*.5,99+i*.5,1000+i*10,
         None if i==0 else {'value':.005,'style':2}] for i,d in enumerate(dates)]
    inventory = [['商品编码','品类','库存数量','安全库存'],['0001','文具',5,10],['0002','纸张',20,10],
                 ['0003','文具',0,5],['0004','耗材',12,10],['0002','纸张',8,10]]
    survey = [['答卷编号','年龄段','满意度','满意评分','愿意推荐'],
              ['01','18–25','满意',4,True],['02','26–35','一般',3,False],['03','18–25','非常满意',5,True],
              ['04','36–45','满意',4,True],['05','26–35',None,None,False],['06','36–45','不满意',1,False]]
    formats = [['日期文字','金额文字','涨幅文字','重量文字'],
               ['01/02/2026','￥1,200.00','5%','10kg'],['02/03/2026','$800.00','-2%','2吨'],
               ['2026/03/04','1,500元','0.5%','30kg']]
    return write_xlsx(path,{'成绩':grades,'销售':sales,'股价':stocks,'库存':inventory,'问卷':survey,'格式与单位':formats})
