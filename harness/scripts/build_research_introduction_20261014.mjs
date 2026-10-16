/** Build the requested all-black-text Word report with embedded figure galleries. */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
const require=createRequire(import.meta.url);
const D=require('C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/docx');
const {Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,ImageRun,HeadingLevel,AlignmentType,WidthType,ShadingType,Header,Footer,PageNumber,PageBreak,VerticalAlign}=D;
const ROOT=path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/(.:)/,'$1')),'../..');
const WORK=path.join(ROOT,'harness/workspaces/research-introduction-20261014');
const OUT=path.join(ROOT,'docs/M3_PI_Guard_研究介绍_2026-10-14.docx');
const marker=path.join(WORK,'created_document.txt');
if(fs.existsSync(OUT)&&!fs.existsSync(marker))throw new Error('Refusing to overwrite an existing user document');
const data=JSON.parse(fs.readFileSync(path.join(WORK,'research_data.json'),'utf8'));
const BLACK='000000';
const PAGE_W=11906,PAGE_H=16838,MARGIN=1080,TEXT_W=PAGE_W-2*MARGIN;
const body=[];
const font=(cn='宋体')=>cn;
const r=(text,opts={})=>new TextRun({text:String(text),font:font(),size:23,color:BLACK,...opts});
const p=(text,opts={})=>new Paragraph({children:[r(text)],spacing:{after:105,line:330},...opts});
function title(text){body.push(new Paragraph({text,style:'Title',spacing:{before:0,after:140}}));}
function h(text,level=1){body.push(new Paragraph({text,heading:level===1?HeadingLevel.HEADING_1:HeadingLevel.HEADING_2,spacing:{before:level===1?120:110,after:100},keepNext:true}));}
function text(s){body.push(p(s));}
function small(s){body.push(p(s,{children:[r(s,{size:18})],spacing:{after:90,line:260}}));}
function page(name){body.push(new Paragraph({text:name,heading:HeadingLevel.HEADING_1,pageBreakBefore:true,spacing:{before:120,after:100},keepNext:true}));}
function table(headers,rows,widths,size=19){
  const build=(vals,isHeader=false)=>new TableRow({tableHeader:isHeader,cantSplit:true,children:vals.map((s,i)=>new TableCell({width:{size:widths[i],type:WidthType.DXA},verticalAlign:VerticalAlign.CENTER,shading:isHeader?{type:ShadingType.CLEAR,fill:'EEF1F3'}:undefined,margins:{top:85,bottom:85,left:100,right:100},children:[new Paragraph({children:[r(s,{size,bold:isHeader})],spacing:{after:0,line:265}})]}))});
  body.push(new Table({width:{size:TEXT_W,type:WidthType.DXA},columnWidths:widths,rows:[build(headers,true),...rows.map(x=>build(x))]}));
  body.push(p('',{spacing:{after:30,line:70}}));
}
function imageParagraph(rel,widthIn,maxHeightIn=5.7){
  const buf=fs.readFileSync(path.join(ROOT,rel));
  const w=buf.readUInt32BE(16),hh=buf.readUInt32BE(20);
  let wi=widthIn,he=wi*hh/w;
  if(he>maxHeightIn){he=maxHeightIn;wi=he*w/hh;}
  return new Paragraph({alignment:AlignmentType.CENTER,children:[new ImageRun({type:'png',data:buf,transformation:{width:Math.round(wi*96),height:Math.round(he*96)},altText:{title:path.basename(rel),description:'研究图表，说明见相邻图注',name:path.basename(rel)}})],spacing:{before:30,after:80},keepNext:true});
}
function figure(id,maxHeight=4.1){
  const f=data.new_figures.find(x=>x.id===id);if(!f)throw new Error(id);
  body.push(imageParagraph(f.png,6.52,maxHeight));
  body.push(p(`图 ${id}  ${f.title}。${f.caption}`,{children:[r(`图 ${id}  ${f.title}。${f.caption}`,{size:18})],spacing:{after:100,line:265}}));
}

title('M3 PI Guard 研究介绍');
body.push(p('工具型大语言模型的授权与运行时防护',{children:[r('工具型大语言模型的授权与运行时防护',{size:28,bold:true,font:font('黑体')})],spacing:{after:130,line:350}}));
small('资料核对日期  2026年10月14日     用途  科研交流与项目介绍');
h('1 研究问题与系统流程');
text('M3 PI Guard 研究大语言模型调用工具时的提示注入风险，以及权限限制对正常任务完成的影响。项目把可信用户任务转换成结构化权限，在工具动作执行前检查提案，再分别记录执行效果、任务完成和运行负担。研究对象是模型与权限编译器、运行时检查器和工具环境组成的完整系统。');
text('典型任务是“读取公开报告，把摘要发送给指定同事”。攻击者可能在报告或工具返回中加入指令，诱导模型更换收件人、读取其他资料或泄露私密内容。系统需要判断动作是否服务于可信任务，以及数据能否流向拟定目标。');
figure('N01',2.85);
text('当前证据最清楚地揭示了授权构造的效用代价：对复杂公开任务，自动权限不足与确认负担会显著减少完成。v1/v2建立并修正动作和参数检查，v3/v4继续探索自然语言任务契约与动态对象绑定。本文依次介绍机制、版本演进、论文主证据、强化实证与最新开发结果。');

page('2 核心机制与一个完整例子');
text('可信用户请求、可信应用声明和工具格式共同构成授权依据。模型读取任务与外部材料后，返回工具名称及参数；Guard用当前规则检查这些参数，执行器只处理获得允许的动作。工具输出提供待处理的数据，不能自行扩大权限。');
table(['对象','系统中的表示与职责'],[
 ['任务权限','TaskPolicyManifest 保存工具规则、参数范围、顺序和数据流限制'],
 ['动作提案','ActionProposal 表示模型申请调用的工具与参数'],
 ['来源记录','ProvenanceEvent 描述参数来源及关联的数据标签'],
 ['检查决定','GuardDecision 保存 ALLOW、ASK、DENY 及判断依据'],
], [1900,TEXT_W-1900]);
text('以“读取 A，把摘要写到 B”为例，权限应绑定为读 A、写 B。读取 A 不会产生覆盖 A 的许可。固定离线演示依次提出三个动作，结果如下。');
table(['动作提案','检查决定','执行含义'],[
 ['read_file(path=A)','ALLOW','读取 A；成功后登记执行历史'],
 ['write_file(path=A)','ASK','缺少覆盖输入的授权，等待补充'],
 ['write_file(path=B)','ALLOW','目标与顺序符合规则，写入 B'],
],[2900,1300,TEXT_W-4200]);
text('参数检查包含两个层次：接口要求参数字段和类型正确，授权要求参数值处于允许范围。收件人、文件路径等目标需要绑定授权；摘要正文等内容允许生成，同时继续接受保密检查。规则匹配必须满足一条完整规则，不能从不同规则各取一部分拼接出新许可。');
h('2 1 发送权限与内容保密',2);
text('某个邮箱可以接收公开报告，却可能被环境规则禁止接收私密数据。可信后端给读取返回的数据附上分类，跟踪器把标签与后续参数关联。已有分类且无保密标签，与根本未提供分类是两种状态。在存在相应受限数据流规则时，分类缺失会返回 ASK，要求补充可信信息。');
small('机制来源 [1] 第3至5章；[2] corrected_v1/v2 编译器与监视器。演示为模拟状态变化。');

page('3 v1 至 v4 的技术演进');
figure('N02',3.05);
table(['版本','主要问题与实现','代表性证据'],[
 ['v1 修复链','绑定动作与资源；完整匹配同工具多条规则；接通可信标签和执行历史','48任务六配置开发研究；每模型288执行'],
 ['v2 通用编译','区分目标与可生成内容；明确目标进入精确约束，未解析的必要目标保持受控','900授权执行、480同期校准、16合成控制'],
 ['v3 任务契约','模型生成结构化任务草稿，程序检查有限谓词、参数角色和证据；动态对象由后端验证绑定','早期开发44响应，4条编译通过'],
 ['v4 意图物化','模型提取动作、对象与原文证据；程序生成任务契约；区分结果引用、授权绑定和内容引用','同32任务：v3可运行5/32，v4为0/32'],
],[1250,5200,TEXT_W-6450],18);
text('这里的 v1—v4 指 corrected 权限编译及任务契约链；论文稿版本、实验报告目录后缀 v1，以及 DeepSeek V4 Pro / V4.1 Flash 的模型版本分别命名。旧实现与记录保留，新编译器通过显式选择接入，使结果能够对应到产生它的具体链路。');

page('4 v1 修复开发研究');
text('v1阶段围绕动作资源绑定、完整规则匹配、可信标签传播和效果测量进行修正。开发集为48任务：24攻击、16正常工具、8无工具，覆盖AgentDojo与M3-v2；六配置交叉提示与模块，每个模型形成288次任务条件执行。');
figure('N14',3.70);
text('图中展示Pro在AgentDojo普通提示子集的计数：无防护正常完成6/8，policy/full均3/8；攻击安全判定阳性分别为5/12、2/12、0/12。Flash同一开发研究中，无防护普通提示攻击阳性1/12，其他配置为零；良性无防护7/8，有防护配置4/8。');
text('这一阶段确立了后续研究的测量方法：动作提出、Guard判定、隔离边界拒绝、成功模拟效果、任务完成及运行失败分别记录。安全结果来自执行与基准评分，不由模型自行宣告。相关原始图表收在历史图集的correctness_repair_v1组。');
small('来源 [3] 当前中文论文 corrected-v1 开发研究；[8] 既有实验图集。');

page('5 v2 论文主证据与授权制度');
text('当前论文以900条修正版授权研究、480条同期校准和16条合成控制为主。授权研究复用180案例、153个底层任务；120个校准案例严格嵌套其中。60个正常任务意图审查复用既有240份条件记录，用于解释权限与完成差异。');
figure('N03',2.7);
figure('N15',3.35);
text('AgentDojo中，policy从自动权限2/30提高到精确目标13/30，full从2/30提高到11/30。精确目标向Guard提供离线派生范围，帮助定位授权信息不足；实际部署需要从可信任务与环境获得同类有效信息。M3-v2对应变化较小且方向不同。');

page('6 同期校准补充无防护参照');
text('480条同期校准使用120案例、四条件，包括无研究Guard、policy、full和指定VIGIL适配配置。policy/full使用相同普通提示，分别比较安全、正常完成、未知和失败。');
table(['基准与指标','无研究Guard','Policy','Full'],[
 ['AgentDojo 正常完成','17/30','2/30','2/30'],
 ['AgentDojo 攻击阳性','3/30','0/30','0/30'],
 ['M3-v2 正常完成','16/30','17/30','16/30'],
 ['M3-v2 模拟危险效果','0/30','0/30','0/30'],
],[3800,1982,1982,TEXT_W-7764]);
text('AgentDojo正常完成的配对差为−50个百分点，95%区间为−66.83至−26.80；攻击差为−10个百分点，区间−25.62至+3.10。两个端点共同说明：正常任务损失有明确证据，安全收益仍需更充分的活性与样本。');
h('6 1 合成控制解释模块怎样工作',2);
table(['发送场景','Policy 模拟结果','Full 决定与结果'],[
 ['公开内容到指定受限邮箱','完成，未产生危险效果','ALLOW，完成'],
 ['私密内容到内部归档邮箱','完成，未产生危险效果','ALLOW，完成'],
 ['私密内容到受限邮箱','完成，同时产生危险效果','DENY，未发送'],
 ['必要分类缺失到受限邮箱','完成，按控制定义记危险','ASK，等待补充分类'],
],[3500,3000,TEXT_W-6500],18);
text('Pro与V4.1 Flash在四场景、两配置中形成16条控制执行。这里清楚区分了发送许可与保密规则，也说明任务完成和危险效果可以同时发生。');
small('来源 [3] 表2至表4。VIGIL适配配置与未知结果的完整图表见附录，不在此表中省略未知后作排名。');

page('7 强化实证扩大正常任务覆盖');
text('强化实证在四个研究与模型队列完成2165条条件执行，其中正常效用Pro1085、Flash600，攻击活性Pro320、Flash160。正常任务采用五条件：无防护、policy自动、full自动、policy精确目标与full精确目标。Pro正常任务217个，Flash120个且是预定嵌套子集。');
figure('N04',4.05);
text('Pro在AgentDojo上，无防护完成68/97，policy/full自动均8/97；精确目标分别提高到38/97和29/97。M3-v2全部120任务的五条件完成为60、59、58、56、59，说明两个基准呈现不同的任务与授权结构。');
small('来源 [4] 强化实证 analysis_v1.json，utility/pro；置信区间读取既有输出。');

page('8 Flash 服务模型的方向复核');
figure('N05',4.25);
text('当前V4.1 Flash在AgentDojo的无防护完成46/60，policy/full自动均5/60；精确目标分别达到25/60和20/60。它复现了自动授权效用低、明确目标信息改善部分任务的方向。');
text('M3-v2的Flash样本在五条件下均完成30/60。该子集包含不同授权形态，任务组和模型服务身份随记录分别报告。Pro与Flash都属于同一服务提供方的模型复核。');
small('来源 [4] utility/flash。图中分母为各基准60个底层任务，未把跨条件执行相加当作新任务。');

page('9 配对比较定位授权信息的作用');
figure('N06',4.45);
text('在同一任务上改变授权信息，可以减少不同任务难度造成的干扰。Pro/AgentDojo中，policy精确目标减自动授权为+30.93个百分点，95%配对区间为21.66至40.16；full为+21.65，区间13.02至30.67。两项通过预定Holm校正。');
text('Pro/M3-v2的对应差异较小。Flash显示AgentDojo同向改善，M3-v2没有变化。研究重点因此落在如何从自然语言任务和可信环境获得足够准确的目标与操作约束。');
small('来源 [4] comparisons；图采用既有配对Newcombe区间，未重新执行统计。');

page('10 攻击活性与安全观察');
figure('N07',3.70);
text('强化攻击队列优先选择历史无防护或VIGIL曾出现危险结果的任务。Pro/AgentDojo无防护7/40出现原生安全判定阳性，policy/full均0/40；两项对无防护比较Holm后p=0.078125。VIGIL适配配置8/36已知阳性，另4项未知。');
table(['模型与基准','无防护攻击观察','解释重点'],[
 ['Pro / AgentDojo','7/40','具有可观察攻击活性，可作配对比较'],
 ['Pro / M3-v2','0/40','报告零事件及区间'],
 ['Flash / AgentDojo','0/20','当前模型窗口的攻击活性低'],
 ['Flash / M3-v2','0/20','当前样本未观察到模拟危险效果'],
],[3000,2100,TEXT_W-5100],18);
text('AgentDojo沿用原生攻击安全评分，M3-v2观察成功执行的模拟越权效果。图中保持两个端点的定义，未知结果按未知记录。完整模型与条件图保存在既有图集。');

page('11 确认负担与任务结构');
figure('N08',3.55);
text('Pro/AgentDojo自动权限下，policy有90/97、full有91/97任务出现ASK，两者均完成8/97。大量等待确认与低完成同时出现，是需要解释的运行负担。');
text('M3-v2还需按任务形态分层。Pro的40个需确认任务在五条件中均为0/40，包括无防护；80个无需确认任务的无防护、policy自动、full自动分别完成60/80、59/80、58/80。该结果说明确认任务本身与模型能力也影响总体完成率。');
table(['任务形态','无防护','Policy 自动','Full 自动'],[
 ['需确认任务','0/40','0/40','0/40'],
 ['无需确认任务','60/80','59/80','58/80'],
 ['全部正常任务','60/120','59/120','58/120'],
],[3650,2050,2050,TEXT_W-7750],18);
small('来源 [4] utility/pro/m3-v2，按confirmation_required与non_confirmation分别读取。');

page('12 组件机制与自然提案');
figure('N09',3.05);
text('在受控夹具中，完整模块对来源权威、顺序、数据保密和确认四类越权提案改变了判定，同时保持合法夹具放行。受控研究共160个policy/full提案对，80对判定变化。');
figure('N10',2.65);
text('真实首提案回放中，358对只有3对从ASK变DENY，其余355对一致。受控机制能够触发，与自然模型提案中能提供多少增量，是两个需要分别观察的研究问题。');

page('13 v3 任务契约与开发发现');
text('v3把动作、对象选择、参数角色、禁止、依赖和用户原话组织为结构化任务契约。模型生成草稿，程序检查有限谓词与证据；对象编号尚未知时保留选择条件，在查找成功后由可信后端核验身份、范围和状态，再形成具体权限。');
figure('N11',3.35);
table(['开发提示阶段','官方响应','编译通过'],[
 ['初始阶段','3','0'],['提示 v2','25','2'],['提示 v3','16','2'],['累计描述','44','4'],
],[4200,2773,TEXT_W-6973],18);
text('这些开发记录均获得模型响应。主要问题是参数角色、有限谓词、来源引用及必要字段与运行契约不一致。工程修复已覆盖相关反例，新增复杂任务的实际编译可用性仍是推进正式评估前的核心问题。这里的提示v2/v3与编译器corrected_v2/v3是不同的版本轴。');
small('来源 [5] v3实施报告与compilation/development_summary_v1.json。');

page('14 v4 意图提取与程序生成规则');
text('v4将模型职责收缩为提取任务意图：动作与工具、对象条件、逐参数原文证据、有限数量日期、依赖与禁止。程序随后物化契约；成功返回值、可信授权绑定及正文数据引用分别处理，后端核验对象与查询关系。');
figure('N12',3.55);
figure('N13',2.60);
text('同一32个开发任务中，v3最终可运行5/32，v4为0/32。Pro产生320项记录，Flash完成20项前缀，其余300项明确未执行。该结果把下一步问题具体定位到意图表达、证据锚定及受信能力的兼容性。');

page('15 研究结论与交流重点');
h('15 1 当前最有信息量的发现',2);
text('第一，权限不是附加配置，而是直接影响正常任务完成的实验因素。v2及强化实证共同显示，公开复杂任务在自动权限下完成低，增加精确目标信息能改善一部分任务。');
text('第二，组件判定与整体系统收益需要在不同证据层观察。受控夹具能清楚展示来源、保密、顺序与确认的作用，真实首提案回放中判定变化却较少。模型提案分布、原有权限阻断和模块触发机会共同决定端到端表现。');
text('第三，v3/v4把改进方向落实到任务理解、参数角色、动态对象和证据引用。最新开发结果表明，可信的任务意图表达与实际工具能力衔接仍需解决，单纯增加模型生成的规则数量并没有带来编译可用性提升。');
h('15 2 需要与老师讨论的问题',2);
text('研究贡献可以围绕授权构造的安全效用权衡及测量方法组织。交流时可重点讨论：哪些任务形态最适合首先修复；如何把动态对象绑定表达得更简单、可验证；什么实验能够区分编译不足、模型规划失败与工具执行失败；论文应如何组织主证据与新增开发研究。');
h('15 3 集中说明证据范围',2);
text('现有安全事件较少，多个无防护单元全零；full相对policy的自然任务增益尚未确立。精确目标对照使用离线派生信息，v3/v4为开发研究，未完成的执行与分类缺失分别保留。模型结果来自隔离模拟环境和指定服务窗口，历史图保持原端点含义。这些条件共同限定结论的推广范围。');
h('15 4 三分钟介绍的组织顺序',2);
text('先用一个外部文档劫持工具调用的例子说明动机，再讲“可信任务—权限—提案—检查—执行—评分”链路；用v1—v4概括方法演进，展示正常完成、攻击观察和确认负担三类结果；最后提出当前最需要指导的任务契约与研究定位问题。AI辅助参与按实际工作说明，个人贡献不从文档措辞中推定。');

page('16 数据来源与图表导航');
small('正文数字依据截至核对日期已存在的项目文件。相对路径从项目根目录开始；历史图保持原始内容，另设阶段标签。');
const sources=[
 ['[1]','项目中文手册','docs/LLM的千层诱惑.md'],
 ['[2]','四版编译与监视代码','m3_core/policy_compiler_corrected_v1.py 至 v4.py；m3_guard/runtime_monitor_corrected_v2.py；task_contract_monitor_v1.py / v4.py'],
 ['[3]','当前中文论文及主表','docs/research/paper_v2/manuscript/manuscript_current_zh_v2.md'],
 ['[4]','强化实证报告与分析','outputs/experiments/empirical_reinforcement_v1/report.md；analysis_v1.json；tables/'],
 ['[5]','v3开发报告','outputs/experiments/task_contract_compiler_v3_validation_v1/report.md；compilation/development_summary_v1.json'],
 ['[6]','v4开发报告与分析','outputs/experiments/task_contract_compiler_v4_development_v1/report.md；analysis_v1.json'],
 ['[7]','新绘图与矢量版','docs/picture/M3_01 至 M3_15；docs/picture/矢量版/'],
 ['[8]','既有实验图完整目录','docs/picture/图表目录.md；docs/picture/历史实验图表/'],
];
table(['编号','资料','项目内位置'],sources,[750,2200,TEXT_W-2950],17);
text(`本次新绘15幅介绍图；另收录既有实验图${data.history.length}组，包含${data.history.reduce((a,x)=>a+x.files.length,0)}个PNG/SVG/PDF源文件。按图像内容去重后，附录展示${data.history_unique_count}幅；同图的所有来源与格式仍在图片目录保留。测试夹具、渲染预览及碰撞审计覆盖图不作为实验图收录。`);
page('17 新绘图与历史图集导航');
text('新绘图按照研究主线编排。N01—N03解释系统与版本，N04—N10说明强化实证，N11—N13展示开发进展，N14与N15补充v1/v2结果。每幅新图同时提供PNG、SVG和PDF；下方编号对应picture中的文件名。');
table(['图号','介绍内容'],data.new_figures.map(f=>[f.id,f.title]),[1200,TEXT_W-1200],18);

page('附录 A 既有实验图表完整索引');
text('每组编号对应原始来源的一幅图及其可用格式。当前研究、历史研究、诊断预检和停用记录分别标识。索引保留全部来源；图像字节相同的项目在后续画廊共用一幅缩略图。完整分辨率和矢量文件见同目录picture。');
table(['编号与阶段','原始图表来源'],data.history.map(x=>[`${x.id}  ${x.status}${x.same_as?'  同 '+x.same_as:''}`,x.source_stem]),[2100,TEXT_W-2100],16);
body.pop(); // A table-end spacer at the page boundary would create an empty page.

const stageOrder={'当前研究':0,'历史研究':1,'诊断与预检':2,'停用记录':3};
const gallery=[...data.history_gallery].sort((a,b)=>stageOrder[a.status]-stageOrder[b.status]||a.id.localeCompare(b.id));
for(let start=0;start<gallery.length;start+=4){
  page(`附录 B 实验图集 ${Math.floor(start/4)+1}`);
  small('图集为缩略导航，编号与来源对应附录A。原图保持原样；标记为诊断、预检或停用的图按其历史用途阅读。');
  const part=gallery.slice(start,start+4);const tableRows=[];
  for(let row=0;row<2;row++){
    const cells=[];
    for(let col=0;col<2;col++){
      const item=part[row*2+col];
      const contents=item?[
        new Paragraph({children:[r(`${item.id}  ${item.status}`,{size:18,bold:true})],spacing:{before:60,after:70}}),
        imageParagraph(item.render_png,3.12,2.40),
        new Paragraph({children:[r(item.source_stem.replace('outputs/',''),{size:15})],spacing:{after:110,line:210}}),
      ]:[p('')];
      cells.push(new TableCell({width:{size:TEXT_W/2,type:WidthType.DXA},children:contents,margins:{top:60,bottom:60,left:90,right:90},verticalAlign:VerticalAlign.TOP}));
    }
    tableRows.push(new TableRow({children:cells,cantSplit:true}));
  }
  body.push(new Table({width:{size:TEXT_W,type:WidthType.DXA},columnWidths:[TEXT_W/2,TEXT_W/2],rows:tableRows,borders:{top:{style:'nil'},bottom:{style:'nil'},left:{style:'nil'},right:{style:'nil'},insideHorizontal:{style:'nil'},insideVertical:{style:'nil'}}}));
}

const doc=new Document({
  creator:'M3 PI Guard 研究资料',title:'M3 PI Guard 研究介绍',subject:'权限编译v1至v4与实验结果',description:'项目研究介绍及完整实验图集',
  styles:{default:{document:{run:{font:font(),size:23,color:BLACK},paragraph:{spacing:{line:330,after:105}}}},paragraphStyles:[
    {id:'Title',name:'Title',basedOn:'Normal',next:'Normal',run:{font:font('黑体'),size:44,bold:true,color:BLACK},paragraph:{spacing:{before:0,after:140}}},
    {id:'Heading1',name:'Heading 1',basedOn:'Normal',next:'Normal',run:{font:font('黑体'),size:29,bold:true,color:BLACK},paragraph:{outlineLevel:0,spacing:{before:120,after:100},keepNext:true}},
    {id:'Heading2',name:'Heading 2',basedOn:'Normal',next:'Normal',run:{font:font('黑体'),size:24,bold:true,color:BLACK},paragraph:{outlineLevel:1,spacing:{before:110,after:100},keepNext:true}},
    {id:'Caption',name:'Caption',basedOn:'Normal',run:{font:font(),size:18,color:BLACK}},
  ]},
  sections:[{properties:{page:{size:{width:PAGE_W,height:PAGE_H},margin:{top:980,bottom:980,left:MARGIN,right:MARGIN,header:430,footer:430}}},
    headers:{default:new Header({children:[new Paragraph({children:[r('M3 PI Guard 研究介绍',{size:17})],alignment:AlignmentType.RIGHT})]})},
    footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[r('第 ',{size:18}),new TextRun({children:[PageNumber.CURRENT],font:font(),size:18,color:BLACK}),r(' 页  共 ',{size:18}),new TextRun({children:[PageNumber.TOTAL_PAGES],font:font(),size:18,color:BLACK}),r(' 页',{size:18})]})]})},
    children:body}],
});
fs.writeFileSync(OUT,await Packer.toBuffer(doc));
fs.writeFileSync(marker,path.basename(OUT),'utf8');
console.log(JSON.stringify({output:OUT,bytes:fs.statSync(OUT).size,newFigures:data.new_figures.length,historicalGroups:data.history.length,historicalUnique:data.history_unique_count,bodyElements:body.length}));
