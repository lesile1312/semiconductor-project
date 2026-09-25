(() => {
  const mainFooter = document.querySelector('main > footer');
  if (!mainFooter) return;

  const style = document.createElement('style');
  style.textContent = `
    .contextBrief{display:grid;grid-template-columns:minmax(250px,.68fr) minmax(0,1.32fr);gap:28px;margin:32px 0 8px;padding:26px 0 28px;border-top:1px solid #284654;border-bottom:1px solid #284654;color:#eef7f7}
    .contextBrief__intro{padding:7px 26px 8px 0;border-right:1px solid #284654}
    .contextBrief__tag{display:inline-flex;align-items:center;border:1px solid rgba(244,189,91,.38);border-radius:999px;padding:5px 9px;color:#f4bd5b;font-size:11px;letter-spacing:.04em}
    .contextBrief__intro h2{margin:14px 0 10px;font-size:clamp(22px,2.5vw,30px);line-height:1.2;letter-spacing:-.025em}
    .contextBrief__intro p{margin:0;color:#a8bcc2;font-size:14px;line-height:1.75}
    .contextBrief__boundary{display:block;margin-top:16px;color:#7f97a0;font-size:12px;line-height:1.65}
    .contextBrief__rows{position:relative;padding-left:28px}
    .contextBrief__rows:before{content:"";position:absolute;left:7px;top:22px;bottom:22px;width:1px;background:linear-gradient(#3ed6c5 0%,#f4bd5b 54%,#526a73 100%);opacity:.72}
    .contextLane{position:relative;display:grid;grid-template-columns:112px minmax(0,1fr) minmax(132px,auto);gap:16px;align-items:start;padding:16px 0;border-bottom:1px solid rgba(40,70,84,.72)}
    .contextLane:last-child{border-bottom:0}
    .contextLane:before{content:"";position:absolute;left:-26px;top:23px;width:7px;height:7px;border:1px solid #3ed6c5;border-radius:50%;background:#071018;box-shadow:0 0 12px rgba(62,214,197,.32)}
    .contextLane:nth-child(2):before{border-color:#f4bd5b;box-shadow:0 0 12px rgba(244,189,91,.28)}
    .contextLane:nth-child(3):before{border-color:#7f97a0;box-shadow:none}
    .contextLane__kind{display:block;padding-top:3px;color:#8ca7b0;font-size:11px;line-height:1.5}
    .contextLane__body h3{margin:0 0 5px;font-size:16px;line-height:1.4}
    .contextLane__body p{margin:0;color:#a8bcc2;font-size:12.5px;line-height:1.7}
    .contextLane__body p+p{margin-top:6px;color:#829ba4}
    .contextLane__links{display:flex;flex-wrap:wrap;gap:6px 13px;margin-top:8px}
    .contextLane__links a{color:#65dfd1;font-size:11px;text-decoration:none;text-underline-offset:3px}
    .contextLane__links a:hover{text-decoration:underline}
    .contextLane__links a:focus-visible{outline:2px solid #f4bd5b;outline-offset:3px;border-radius:2px}
    .contextLane__state{justify-self:end;max-width:170px;padding:5px 8px;border-left:2px solid #3ed6c5;color:#b9d3d5;font-size:11px;line-height:1.5}
    .contextLane:nth-child(2) .contextLane__state{border-color:#f4bd5b;color:#e5d2a5}
    .contextLane:nth-child(3) .contextLane__state{border-color:#60747b;color:#9aadb2}
    .contextBrief__foot{grid-column:2;margin:0;color:#7f97a0;font-size:11px;line-height:1.65}
    @media(max-width:780px){.contextBrief{grid-template-columns:1fr;gap:12px}.contextBrief__intro{padding:4px 0 17px;border-right:0;border-bottom:1px solid #284654}.contextBrief__intro h2{max-width:22ch}.contextBrief__rows{padding-left:24px}.contextBrief__foot{grid-column:1}}
    @media(max-width:540px){.contextBrief{margin:26px 0 8px;padding:20px 0 22px}.contextBrief__rows{padding-left:20px}.contextBrief__rows:before{left:4px}.contextLane{grid-template-columns:minmax(0,1fr);gap:5px;padding:14px 0}.contextLane:before{left:-19px;top:19px}.contextLane__kind{padding:0}.contextLane__state{justify-self:start;max-width:none;margin-top:4px}.contextLane__links{gap:8px 12px}}
    @media(prefers-reduced-motion:reduce){.contextLane__links a{scroll-behavior:auto}}
  `;
  document.head.appendChild(style);

  const section = document.createElement('section');
  section.id = 'external-context';
  section.className = 'contextBrief';
  section.setAttribute('aria-labelledby', 'contextBriefTitle');
  section.innerHTML = `
    <div class="contextBrief__intro">
      <span class="contextBrief__tag">背景脉络 · 不进入核心指数</span>
      <h2 id="contextBriefTitle">地缘环境、政策规则与企业名单，是三个不同层次</h2>
      <p>GTRI观察的是第三方经济体的半导体投入、美国市场联系和供应来源结构。事件库描绘宏观环境，政策库记录措施，实体清单才可能与企业名称匹配；它们不能直接相加成一个国家分数。</p>
      <span class="contextBrief__boundary">下面列出本轮核对后保留的背景来源、待接入候选和暂不采用的数据。目录统计只说明数据库覆盖，不是本研究计算出的风险结果。</span>
    </div>
    <div class="contextBrief__rows" aria-label="外部风险来源的适用层次">
      <article class="contextLane">
        <span class="contextLane__kind">宏观关系</span>
        <div class="contextLane__body">
          <h3>GDELT 中美双边事件</h3>
          <p>实验室目录标注约 177 万条中美互动事件，覆盖 1979 年至 2026 年 4 月。它可帮助读者查看双边合作与冲突的时序背景，但不是第三方国家的半导体贸易或企业受限记录。</p>
          <div class="contextLane__links"><a href="https://riskalab-databank.vercel.app/gdelt/timeline" target="_blank" rel="noopener noreferrer">查看实验室事件时间线</a><a href="https://riskalab-databank.vercel.app/gdelt" target="_blank" rel="noopener noreferrer">查看数据集说明</a></div>
        </div>
        <span class="contextLane__state">选作背景参照<br>不生成国家分值</span>
      </article>
      <article class="contextLane">
        <span class="contextLane__kind">政策与主体</span>
        <div class="contextLane__body">
          <h3>GTA 政策记录与美国综合出口管制清单</h3>
          <p>GTA目录收录2008—2026年的贸易与产业政策措施，并提供实施方、受影响经济体、HS商品范围和日期，适合后续筛选半导体相关措施；美国综合出口管制清单（CSL）则按个人、企业或船只列出受许可要求或禁令约束的主体。</p>
          <p>这是最接近“政策—商品—企业”的补充方向。但目前没有真实企业 BOM、供应商和客户名称；GTA 数据下载需注册，CSL目录也未提供可回溯至2017/2022的历史快照。本轮不报告命中数、不回填历史风险，也不把二者并入GTRI。</p>
          <div class="contextLane__links"><a href="https://riskalab-databank.vercel.app/library/global-trade-alert" target="_blank" rel="noopener noreferrer">GTA 数据说明</a><a href="https://riskalab-databank.vercel.app/library/us-export-control-list" target="_blank" rel="noopener noreferrer">CSL 数据说明</a><a href="https://www.trade.gov/consolidated-screening-list" target="_blank" rel="noopener noreferrer">美国官方清单入口</a></div>
        </div>
        <span class="contextLane__state">优先候选<br>需企业名称与历史口径</span>
      </article>
      <article class="contextLane">
        <span class="contextLane__kind">运营连续性</span>
        <div class="contextLane__body">
          <h3>航运通道与武装冲突</h3>
          <p>IMF PortWatch自2019年起提供主要海上咽喉的每日船舶通行数，但不是货值、吨位或半导体货流；UCDP/PRIO与ACLED关注武装冲突、政治暴力和抗议，更适合有明确工厂、港口或路线位置时做运营安全评估。</p>
          <p>当前面板没有企业设施或运输路线信息，这些数据与技术管制也不是同一风险概念，因此本轮不纳入地图或核心指标。</p>
          <div class="contextLane__links"><a href="https://riskalab-databank.vercel.app/risk-databases" target="_blank" rel="noopener noreferrer">查看风险数据库目录</a><a href="https://riskalab-databank.vercel.app/conflict-databases" target="_blank" rel="noopener noreferrer">查看冲突数据库目录</a><a href="https://riskalab-databank.vercel.app/library" target="_blank" rel="noopener noreferrer">查看经典数据集库</a></div>
        </div>
        <span class="contextLane__state">暂不纳入<br>待有真实路线数据</span>
      </article>
    </div>
    <p class="contextBrief__foot">本说明区用于交代数据适配边界。任何政策或清单记录进入企业建议前，仍需核对适用对象、商品范围、生效时间和实体匹配结果。</p>
  `;
  mainFooter.insertAdjacentElement('beforebegin', section);
})();
