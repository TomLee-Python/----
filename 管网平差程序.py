# 导入所需要的第三方库
import pandas as pd  # 数据的读取、处理
import matplotlib.pyplot as plt  # 绘制管线简图，用于检查
import os  # 对文件的路径、保存进行操作
# 第三方库reportlab：用于生成pdf
from reportlab.lib.pagesizes  import letter  # PDF页面尺寸
from reportlab.lib import colors  # PDF的颜色
from reportlab.lib.styles import getSampleStyleSheet  # PDF样式
from reportlab.pdfgen import canvas  # 在PDF里输入数据，绘制表格，简图
from reportlab.platypus import SimpleDocTemplate, Image, Table, TableStyle, Paragraph, Spacer  # PDF里内容的样式
# pdfbase负责 PDF 底层基础功能（字体、编码、PDF 基础结构）；
# pdfmetrics用于管理 PDF 字体的 “度量信息”（如字体尺寸、编码映射），是注册自定义字体的核心入口
from reportlab.pdfbase import pdfmetrics 
# ttfonts用于管理字体路径与配置默认字体；
# ttfonts模块中的类（Class）TTFont用于加载与使用字体文件
from reportlab.pdfbase.ttfonts import TTFont

# ===================== 一、指定文件路径与管网平差参数 =====================
# 1、统一输入文件的路径
CSV_PATHS = {
    "nodes": "nodes.csv",  # 节点数据
    "pipes": "pipes.csv",  # 管段数据
    "loops": "F:\测试数据\loops.csv"  # 换号数据
}
# 2、统一输出文件的路径
OUT_PATHS = {
    "pipeline_network_img": "network.png",  # 输出管网简图
    "final_results_csv": "final_results_csv.csv",  # 输出平差之后的数据
    "report_pdf": "report.pdf"  # 输出pdf报告
}

# 3、哈代—克罗斯法相关参数
TOLERANCE = 0.05  # 收敛界限（即闭合差允许值）
MAX_ITERATION = 1000  # 最大迭代次数为1000

# ===================== 二、数据的读取 =====================
# 1、检测各个被读取的csv文件是否存在
def check_file_existence(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在")  # 抛出异常
# 调用check_file_existence函数      
for file_type, file_path in CSV_PATHS.items():  # 键为文件数据类型，如nodes，用type接收;值为文件路径，如nodes.csv，用path接收
    check_file_existence(file_path) 

# 2、用pandas库读取数据：节点、管段、环号，生成DataFame，用于数据分析
nodes_df = pd.read_csv(CSV_PATHS['nodes'] ,encoding='gbk')
pipes_df = pd.read_csv(CSV_PATHS['pipes'] ,encoding='gbk')
loops_df = pd.read_csv(CSV_PATHS['loops'] ,encoding='gbk')
# 3、生成嵌套字典，方便后续查找数据
nodes = nodes_df.set_index("节点编号").to_dict("index")  # 指定索引列，将该列内容设定为键，同行的内容即为值
pipes = pipes_df.set_index("管段编号").to_dict("index")
loops_dict = {}
for loop_id ,loop_data in loops_df.groupby("环编号"):
    loops_dict[loop_id] = loop_data  # 此时字典内容变为{"环号1": ["管段1", "管段2", ...], ...}


# ===================== 三、绘制管线简图 =====================
def plot_network(nodes, pipes, chart_title = "管网简图"):
    plt.rcParams['font.sans-serif'] = ['SimSun']  # 解决中文乱码，让中文正常显示
    plt.rcParams['axes.unicode_minus'] = False  # # 修复负号显示（必须保留）
    plt.figure(figsize=(10,10))  # 创建画布，规定画布宽高比

    # 1、绘制节点
    for node_id, node_data in nodes.items():
        plt.plot(node_data["x"], node_data["y"], "ro", markersize=10)  # 获取节点坐标，绘制红色节点，尺寸10
        plt.text(node_data["x"], node_data["y"], node_id, fontsize=10, ha="center")  # 在指定节点坐标处，居中添加节点编号
    # 2、绘制管段
    for pipe_id, pipe_data in pipes.items():
        start_node = pipe_data["管段起点"]
        end_node = pipe_data["管段终点"]
        if start_node not in nodes or end_node not in nodes:
            print(f"管段{pipe_id}的节点{start_node}/{end_node}不存在")
            continue  # 跳过绘制
        x1, y1 = nodes[start_node]["x"], nodes[start_node]["y"]  # start_node只是节点编号，具体坐标在字典nodes里
        x2, y2 = nodes[end_node]["x"], nodes[end_node]["y"]
        # 连接节点，绘制管线
        plt.plot([x1, x2], [y1, y2], "b-", linewidth=2)
        plt.text((x1+x2)/2, (y1+y2)/2, f'管段{pipe_id}', fontsize=8, ha="center")  # 添加管段信息

    # 3、规范图表样式
    plt.title(chart_title)  # 图名
    plt.savefig(OUT_PATHS["pipeline_network_img"], dpi=150, bbox_inches="tight")  # 保存图片，调整清晰度，去掉多余空白
    plt.show()  # 自动弹出图片

# 调用plot_network函数
plot_network(nodes, pipes)


# ===================== 四、Hardy-Cross平差计算 =====================
def hardy_cross(pipes, loops_df, tolerance=TOLERANCE, max_iteration=MAX_ITERATION):
    
    iteration = 0  # 初始化迭代次数

    # 关于数据的一切操作以loops_copy为核心，最后返回的是loops_copy
    loops_copy = {k: v.copy() for k ,v in loops_dict.items()}  # 字典推导式：拷贝数据到副本，防止原数据被修改
    
    # ===========遍历各环，取出公共管段，并存储=========== 
    # 1、定义空字典存储“环号—包含的管段”键值对
    loop_pipes_dict = {}
    for loop_id, loop_data in loops_df.groupby("环编号"):
        loop_pipes_dict[loop_id] = loop_data["管段编号"].tolist()
    # 2、定义空字典存储“管段—对应的环号”键值对
    pipe_loops_dict = {}
    for loop_id, current_pipes in loop_pipes_dict.items():
        for pipe in current_pipes:
            if pipe not in pipe_loops_dict:
                pipe_loops_dict[pipe] = []
            pipe_loops_dict[pipe].append(loop_id)      
    # 3、存储公共管段与对应环号
    shared_pipe_in_loops = {pipe :loops for pipe ,loops in pipe_loops_dict.items() if len(loops)>1}

    # 开始平差迭代大循环
    converge_flag = False  # 初始化收敛标志
    while iteration < MAX_ITERATION:
        iteration += 1  # 累计迭代次数
        # 定义空字典loop_corr_flows，存储每个环对应的校正流量，方便后续把校正流量加到管段上
        loop_corr_flows = {}
        # 存储每个环的闭合差，用于后期遍历闭合差后与tolerance进行比较，判断程序是否终止
        closure_errors_lst = []  

        # 1、计算并记录每个环的闭合差，校正流量（用loops_copy的最新流量）
        for loop_id ,loop_data in loops_df.groupby("环编号"):  # 按具体环编号进行分组，环编号赋予给loop_id，对应管段编号与方向赋予给loop_data
            delta_h = 0  # 初始化该环闭合差
            sum_sq = 0  # 初始化该环abs(sq)的累加值
            for _, row in loop_data.iterrows():  # iterrows()产生一个元组（行索引，行数据）
                current_pipe_id = row["管段编号"]
                # 从loops_copy取当前环该管段的最新流量，而非原始loops_df
                pipe_row = loops_copy[loop_id][loops_copy[loop_id]["管段编号"] == current_pipe_id]
                Q = pipe_row["管段流量 (L/s)"].iloc[0]  # 取单个值
                L = row["管段长度 (m)"]
                D = row["管段直径 (mm)"]                  

                # 用海曾威廉公式计算各管段的水头损失
                pipe_h=10.67*((abs(Q)/1000)**1.852)*L/((100**1.852)*(D/1000)**4.87)  # L/s
                #  pipe_h=10.67*((abs(Q))**1.852)*L/((100**1.852)*(D/1000)**4.87)  # m^3/s
                # 累加管段水头损失，算出该环的闭合差
                delta_h += Q/abs(Q) * pipe_h

                # 计算出各管段的|sq|
                if Q != 0:
                    sum_sq += abs(pipe_h/Q)
                
            # 计算该环校正流量
            delta_q = -delta_h/(2*sum_sq)
            # 将该环的校正流量与闭合差存入各自的字典中
            loop_corr_flows[loop_id] = delta_q
            closure_errors_lst.append(abs(delta_h))
        
        # 2、在所有环校正流量算完后，更新一次每个环的管段流量
        for loop_id ,loop_data in loops_df.groupby("环编号"):  # 遍历每个环
            pipes_in_loop = loop_data["管段编号"]
            for pipe in pipes_in_loop:  # 遍历该环的管段是否为公共管段
                # 定位到该管段在loops_copy中的行，才能有效更新流量
                pipe_idx = loops_copy[loop_id][loops_copy[loop_id]["管段编号"] == pipe].index[0]                
                Q = loops_copy[loop_id].loc[pipe_idx, "管段流量 (L/s)"]  # 取出该管段的流量
                # 判断管段是否为公共管段
                if pipe not in shared_pipe_in_loops:  
                    Q += loop_corr_flows[loop_id]
                else:  # 公共管段：加本环叫流量，并减去邻环校正流量
                    loops_list = pipe_loops_dict[pipe]  # 取出公共管段对应环号组成的列表
                    for loop in loops_list:  # 遍历该列表
                        if loop == loop_id: 
                            Q += loop_corr_flows[loop]
                        else:
                            Q -= loop_corr_flows[loop]
                loops_copy[loop_id].loc[pipe_idx, "管段流量 (L/s)"] = Q
        
        # 3、检查收敛是否超出范围
        if all(current_delta_h < tolerance for current_delta_h in closure_errors_lst):  # 若各个环的闭合差都小于允许值，提前终止程序
            converge_flag = True
            print(f"已迭代{iteration}次，平差成功")
            break   
                    
    if not converge_flag:
        print(f"已迭代到最大次数：{MAX_ITERATION}次，闭合差不满足要求")

    return loops_copy  # 即将pipes_copy返回除去
# 调用函数
pipe_network = hardy_cross(pipes, loops_df)  # 变量接收被返回的pipes_copy，也是个字典

 # ===================== 五、导出csv文件 =====================
result_data = []  # 接收不同类型数据：管段编号、管长、管径、最终流量
for loop_id ,loop_data in pipe_network.items():  #  遍历最新数据，添加平差后的数据到列表
    for _, row in loop_data.iterrows():
        current_pipe_id = row["管段编号"]
        L = row["管段长度 (m)"]
        D = row["管段直径 (mm)"]
        Q = row["管段流量 (L/s)"]
        result_data.append({
            "环编号": loop_id,
            "管段编号": current_pipe_id,
            "管段长度 (m)": L,
            "管段直径 (mm)": D,
            "管段流量 (L/s)": Q
        })
result_df = pd.DataFrame(result_data)  #  将列表转换成dataframe
result_df.to_csv(OUT_PATHS["final_results_csv"], index=False, encoding="gbk", errors="ignore")  # 将dataframe输出位csv
print(f"\n结果已保存到CSV：{os.path.abspath(OUT_PATHS['final_results_csv'])}")  # 打印该csv的路径

# ===================== 六、导出pdf报告 =====================
def generate_pdf():

    # 1、用系统默认宋体文件（simsun.ttc）
    font_path = r"C:\Windows\Fonts\simsun.ttc"
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"未找到宋体文件：{font_path}，请确认路径")
    
    # 2、注册字体（名称用简洁的“SimSun”，避免拼写错）
    pdfmetrics.registerFont(TTFont('SimSun', font_path))

    # 3、创建pdf文件，指定其尺寸（默认为letter）与路径
    doc = SimpleDocTemplate(OUT_PATHS["report_pdf"])  # 创建pdf文件，定义其尺寸（默认为letter）与路径
    elements = []  # 定义一个空列表，用于存储 PDF 的所有内容元素（标题、图片、表格等），后续一次性渲染到 PDF
    styles = getSampleStyleSheet()  # 获取 ReportLab 预设的样式表（实际是个字典）（包含 Title、Heading1、Normal 等样式），避免手动定义文本格式
    
    # 4. 所有样式统一用注册的SimSun字体
    styles['Title'].fontName = 'SimSun'  # 标题
    styles['Title'].fontSize = 20
    styles['Heading2'].fontName = 'SimSun'  # 二级标题
    styles['Heading2'].fontSize = 16
    styles['Normal'].fontName = 'SimSun'  # 普通文本
    styles['Normal'].fontSize = 12

    # 5、添加标题
    # 用Paragraph类创建格式化文本，传入两个参数：1、文字内容；2、对应的样式（如styles["Title"]）
    title = Paragraph("管网平差报告", styles['Title'])
    elements.append(title)
    # 添加一段空白区域，两个参数表示（行数，单行的高度）
    elements.append(Spacer(1,20))

    # 6、添加管线简图
    # 判断图片文件路径是否存在，存在则添加，不存在则提示
    if os.path.exists(OUT_PATHS["pipeline_network_img"]):
        img = Image(OUT_PATHS["pipeline_network_img"], width=500, height=400)  # 调整图片的尺寸
        elements.append(Paragraph("管线简图", styles['Heading2']))  # 先添加二级标题，在添加图片
        elements.append(img)
        elements.append(Spacer(1, 20))
    else:
        elements.append(Paragraph("未找到管线简图", styles['Normal']))  # 用正文样式输出提示文字
        elements.append(Spacer(1, 20))
    elements.append(Paragraph("管网平差结果", styles['Heading2']))

    # 7、添加平差结果表格（先有表格结构table，才有表格样式tablestyle）
    # 将dataframe的表头、数据内容处理为嵌套列表，如此，Table类才能正确处理数据
    # 取表头
    table_header = result_df.columns.tolist()
    # 取数据行，逐个处理
    table_rows = []
    for row in result_df.values.tolist():
        new_row = []
        for idx, val in enumerate(row):
            if idx==0 or idx==1:
                new_row.append(int(val))
            else:
                new_row.append(val)
        table_rows.append(new_row)
    table_data = [table_header] + table_rows  # colums是取每列的表头，values是逐行取除了第一行以外的每行数据
    # 用Table（接收数据列表）将数据转换为表格
    table = Table(table_data, repeatRows=1)  # 创建PDF表格对象，并设置 “分页时表头重复显示”
    # 用TableStyle（接收样式指令列表）调整表格样式
    # (列索引,行索引)：索引从0开始算
    table_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),  # 第一行（即表头）单元格的背景色
        ('BACKGROUND', (0,1), (-1,-1), colors.lightblue), # 其他数据的单元格背景色
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),  # 文字颜色
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),  # 对齐方式（CENTER/LEFT/RIGHT）
        ('FONTNAME', (0,0), (-1,-1), 'SimSun'),  # 字体（宋体）
        ('FONTSIZE', (0,0), (-1,0), 10),  # 表头区的字号
        ('FONTSIZE', (0,1), (-1,-1), 8),  # 数据区的字号
        ('BOTTOMPADDING', (0,0), (-1,0), 8),  # 单元格内文字到底部内边的距离（避免文字贴边）
        ('GRID', (0,0), (-1,-1), 1, colors.black),  # 网格线（参数为(网格线的覆盖范围，线宽， 颜色)）
        
    ])
    table.setStyle(table_style)  # 对纯数据表格添加表格样式
    elements.append(table)
    # 创建PDF（对已创建的文档对象doc添加内容），bilud的第一个参数必须为列表
    doc.build(elements)
    return OUT_PATHS["report_pdf"]

# 调用生成PDF的函数
pdf_path = generate_pdf()
print(f"PDF报告已生成：{os.path.abspath(pdf_path)}")

