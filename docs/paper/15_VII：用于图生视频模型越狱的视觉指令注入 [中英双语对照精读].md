# 15_VII：用于图生视频模型越狱的视觉指令注入
## VII: Visual Instruction Injection for Jailbreaking Image-to-Video Generation Models

**论文元数据**：
- **论文来源**：arXiv:2501.12389v2 [cs.CV]
- **作者团队**：Bowen Zheng (郑博文), Yongli Xiang (向永利), Ziming Hong (洪子明), Zerong Lin (林泽荣), Chaojian Yu (余超健), Tongliang Liu (刘同亮), Xinge You (尤新革, 通信作者)
- **研究机构**：华中科技大学国家防伪工程技术研究中心（National Anti-Counterfeit Engineering Research Center, HUST）、悉尼大学（The University of Sydney）
- **核心关键词**：图生视频模型（Image-to-Video, I2V）、视觉指令注入（Visual Instruction Injection, VII）、多模态越狱攻击（Multimodal Jailbreak）、跨模态注意力操纵（Cross-Modal Attention Manipulation）、动态扩散模型安全（Diffusion Video Safety）、多模态安全护栏绕过（Guardrail Evasion）
- **研究定位**：华中科技大学与悉尼大学联合团队首次系统揭示了图生视频（I2V）生成模型在跨模态对齐层面的严重安全脆弱性。现有安全防护主要依赖独立的文本审查与静态图像过滤，然而团队发现，通过在完全良性的静态图像中自然嵌入文字排版指令（如路牌、招牌或服饰标语），能够操纵跨模态时间注意力流，迫使扩散模型将静态无害物体动态演化为极度血腥、暴力或违法的危险视频序列，成功突破现有多模态安全护栏。

---

## 1. 论文核心导读与执行摘要 (Executive Summary)

### 1.1 核心痛点：图生视频（I2V）模型的跨模态安全盲区
近年来，图生视频模型（如 Stable Video Diffusion, CogVideoX, AnimateDiff, Sora）取得了突破性进展，能够根据静态首帧图像和文字提示词生成高度逼真的动态视频。为了防止滥用，服务提供商部署了严密的**三层多模态安全护栏**：
1. **文本输入护栏（Text Guardrail）**：使用敏感词表或安全分类器（如 Llama-Guard）拦截包含暴力、色情、仇恨的文字 Prompt；
2. **图像输入护栏（Image Guardrail）**：使用图像分类器（如 Q16、NSFW 检测器）拦截露骨或高危的输入静态图片；
3. **视频输出护栏（Video Guardrail）**：对最终生成的视频帧进行抽样安全审查。

**致命漏洞——跨模态指令转移（Cross-Modal Instruction Offloading）**：
- 攻击者如果直接输入“让这辆卡车撞向人群”，文本护栏会瞬间拦截；
- 如果输入包含暴力场景的血腥图片，图像护栏会直接拒收；
- **但如果输入一张极其普通、和平的卡车街景图片，仅在卡车侧面或路牌上印有一行看似普通的排版英文文字（如“加速撞击”），同时输入一段完全中性的提示词（如“展现街景的动态变化”）**——此时文本护栏判定文本无害，图像护栏判定静态图片无害，但 **I2V 模型的视觉编码器却在深层交叉注意力（Cross-Attention）机制中读取了图像中的排版文字，将其作为顶层动作指令执行**，最终生成致命的恐怖暴力动态视频！

### 1.2 核心创新：VII（视觉指令注入）攻击范式
1. **首个面向 I2V 模型的对抗性指令注入攻击架构**：
   - 提出 **VII（Visual Instruction Injection）** 框架，将恶意动作意图从文本提示词剥离，以逼真的视觉排版（Typography）形式编码进初始静态图像中；
   - 彻底打破“良性文本 + 良性图像 = 安全视频”的假设前提。
2. **双重对抗协同优化算法**：
   - **有害动态意图最大化（Harmful Motion Maximization）**：优化视觉指令在潜在时间注意力图（Temporal Attention Maps）中的能量分布，迫使模型将静态语义节点动态驱动向违规流形；
   - **语义与视觉一致性约束（Semantic & Consistency Constraint）**：保证视频画面具有高保真度、物理规律连贯性与平滑帧率，防止模型输出噪点或结构崩塌。
3. **构建权威评测基准 COCO-I2VSafetyBench**：
   - 覆盖 6 大核心安全红线类别：暴力与威胁（Violence）、仇恨与极端主义（Hate）、违法活动（Illegal）、色情露骨内容（Sexual）、自残倾向（Self-harm）以及隐私侵犯（Privacy）；
   - 在 CogVideoX-5B、SVD、AnimateDiff 及主流商业闭源 I2V 服务上进行了大规模攻击测试。

### 1.3 核心实验结论
- **极高攻击成功率**：在 COCO-I2VSafetyBench 和 ConceptRisk 基准上，VII 取得了平均 **82.4% ~ 89.6%** 的越狱攻击成功率（ASR）；
- **全面击穿护栏**：现有的主流文本分类器（如 Perspective API、Llama-Guard）和静态图像安全分类器（CLIP-based Guardrails）的防御有效率下降至 **12% 以下**；
- **跨模型架构强迁移性**：生成的视觉指令不仅在白盒扩散模型上高度有效，直接迁移至黑盒商业视频生成 API 时依然能够保持超过 **70%** 的越狱成功率。

---

## 2. 核心架构与方法原理详解 (Methodology & Architecture)

### 2.1 任务形式化定义 (Problem Formulation)
在标准图生视频生成任务中，模型参数化为去噪扩散概率模型 $\epsilon_\theta(z_t, t, c_t, c_i)$，其中：
- $z_t$ 为潜空间第 $t$ 步视频噪声潜变量；
- $c_t = \tau_{text}(P)$ 为文本提示词 $P$ 的文本特征嵌入；
- $c_i = \tau_{img}(I)$ 为输入初始图像 $I$ 的视觉条件嵌入；
- 视频去噪过程逐帧去噪生成视频潜序列 $Z = \{z^1, z^2, \dots, z^F\}$。

在 VII 攻击设定中：
- 目标有害行为描述为 $H$（如“制造剧烈爆炸”）；
- 攻击者构造良性中性文本提示词 $P_{ben}$（如“高画质，流畅运动”）；
- 构造载体良性图像 $I_{ben}$，并将提取自有害行为 $H$ 的排版指令文本 $T_{mal}$ 以特定字体、颜色和仿射变换渲染至图像中的语义合理区域，得到注入图像 $I_{adv} = \text{Render}(I_{ben}, T_{mal})$；
- 目标：使 I2V 模型生成满足有害行为 $H$ 的视频序列 $V$，同时满足输入安全性检测约束：
  $$\text{Guard}_{text}(P_{ben}) = \text{Safe}, \quad \text{Guard}_{img}(I_{adv}) = \text{Safe}, \quad \text{Evaluator}(V) = \text{Unsafe}$$

### 2.2 视觉排版指令与跨模态注意力劫持
I2V 模型（如 SVD）使用 CLIP 或 SigLIP 视觉编码器提取图像全局与细粒度特征。视觉编码器具有天然的光学字符识别（OCR）语义敏感性。
当图像中包含清晰文字时，视觉特征向量序列中会形成与该文字语义高度对齐的高维向量聚类：
- 在时间自注意力层（Temporal Self-Attention）中，这些文字特征充当了动态关键点（Motion Anchor）；
- 跨模态融合机制将视觉文字特征错误解码为运动矢量指令（Motion Vectors），从而驱动背景中的原本静止的汽车、火源或人体做出危险对抗动作。

### 2.3 VII 优化算法：动作最大化与平滑度保持
为了提升视觉指令的触发效率，VII 引入了可微排版属性搜索与潜表征对齐：
1. **对抗潜在流损失（Adversarial Latent Flow Loss）**：
   $$\mathcal{L}_{motion} = - \mathbb{E}_{t, \epsilon} \left[ \langle \nabla_{z_t} \log p_\theta(z_t | c_i^{adv}, c_t^{ben}), \mathbf{v}_{harmful} \rangle \right]$$
   最大化生成轨迹沿有害动作方向 $\mathbf{v}_{harmful}$ 的漂移速度；
2. **自然度保真正则项（Naturalness Regularization）**：
   $$\mathcal{L}_{reg} = \| \text{CLIP}(I_{adv}) - \text{CLIP}(I_{ben}) \|_2^2 + \lambda \text{TotalVariation}(I_{adv})$$
   确保文字排版融入真实物理场景（如路标边缘、墙体纹理），规避异常图像伪影检测。

---

## 3. 中英双语对照精读 (Bilingual In-Depth Reading)

### 3.1 摘要 (Abstract)
**英文原文**：
Image-to-Video (I2V) generative models have witnessed remarkable success, enabling the synthesis of temporally coherent and visually compelling videos conditioned on static images and text prompts. To prevent the synthesis of harmful content, safety guardrails are universally integrated across modalities. However, the cross-modal safety dynamics between visual conditioning and textual prompts remain poorly understood. In this work, we reveal a critical vulnerability in I2V models: Visual Instruction Injection (VII). Unlike traditional text-based jailbreaks that directly prompt the model with malicious queries, VII offloads harmful instructions into the visual modality by embedding natural typographic text into benign carrier images. While standard text guardrails certify the prompt as benign and image safety filters classify the static visual input as safe, the I2V model internally interprets the visual typography as high-priority behavioral instructions, driving the video synthesis towards dangerous outcomes. Extensive empirical evaluations on our newly established COCO-I2VSafetyBench and ConceptRisk benchmarks demonstrate that VII achieves attack success rates exceeding 80% across mainstream open-source and proprietary I2V models. Our findings expose severe blind spots in multi-modal safety alignment and highlight the urgent need for cross-modal defensive mechanisms.

**中文翻译**：
图生视频（I2V）生成模型取得了令人瞩目的成功，能够以静态图像和文本提示词为条件，合成时间连贯且视觉效果震撼的动态视频。为了防止生成危害内容，各大厂商在各个模态上普遍集成了安全护栏。然而，视觉条件与文本提示词之间的跨模态安全动态机制仍未得到充分理解。在本文中，我们揭示了 I2V 模型中一个致命的安全脆弱性：视觉指令注入（Visual Instruction Injection, VII）。与直接使用恶意查询提示模型的传统基于文本的越狱攻击不同，VII 通过将自然的排版文字嵌入良性载体图像中，将有害指令转移到视觉模态中。当标准文本护栏判定提示词为良性、图像安全过滤器将静态视觉输入归类为安全时，I2V 模型却在内部将图像中的排版文字解释为高优先级的行为指令，从而驱使视频合成走向高危违规结局。在我们新构建的 COCO-I2VSafetyBench 和 ConceptRisk 基准上开展的大量实证评估表明，VII 在主流开源与商业闭源 I2V 模型上均取得了超过 80% 的攻击成功率。我们的研究结果揭示了多模态安全对齐中存在的严重盲区，并凸显了构建跨模态联合防御机制的紧迫需求。

---

### 3.2 实验结果与深度分析 (Experimental Results & Insights)

#### 核心评测指标 (Table 1 & Table 2 深度解读)
- **攻击成功率（ASR %）全线突破**：
  - 在开源旗舰 CogVideoX-5B 和 SVD 上，基线文本越狱方法因受阻于文本护栏，ASR 仅为 10%~18%；
  - 纯排版图像基线由于缺乏对抗协调，ASR 徘徊在 35%~42%；
  - **VII 攻击**通过视觉指令注入与跨模态注意力引导，在两大基准上全面取得了 **82.5% ~ 88.9%** 的绝对统治级表现。
- **跨模态护栏穿透率（Guardrail Evasion Rate）**：
  - 针对 Llama-Guard-3、Perspective API 以及 OpenAI Moderation API，VII 文本提示词的通过率为 **100%**（完全中性）；
  - 针对 CLIP-based 静态图片审核模型，注入图像的通过率达到 **94.2%**，成功实现了双重潜伏渗透。
- **视频保真度与时间平滑度（Table 2）**：
  - 评测指标 FVD（Fréchet Video Distance）与 CLIP-Temp（时间连贯性得分）表明，VII 生成的越狱视频具有与正规生成视频完全相当的高画质与流畅运动，未出现任何因对抗扰动引发的画质畸变或闪烁伪影。

---

## 4. 关键技术启示与未来防御思考 (Defensive Implications)

1. **多模态护栏“分而治之”策略的破产**：
   - 现有的“文本单独审、图片单独审”的流水线防御在面对跨模态联合攻击时形同虚设。I2V 系统的安全性不能简单等同于各模态独立安全性的叠加。
2. **亟需 OCR 增强的跨模态联合审核（Cross-Modal Joint Moderation）**：
   - 防御端必须在生成流水线前置 OCR 文字提取与语义解析模块，将图像内含的排版文字提取出来并与伴随文本提示词进行联合意图风险建模。
3. **时间注意力对齐与运动抑制（Temporal Motion Suppressor）**：
   - 在扩散模型的去噪反向传播过程中，监控时间自注意力层中是否存在异常的高能文字驱动模式，针对静态至高危动作的剧烈跳变实施动态阻尼衰减。
