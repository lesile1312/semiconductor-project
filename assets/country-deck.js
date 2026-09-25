(() => {
  const rows = window.PANEL;
  const yearSelect = document.querySelector('#year');
  const countrySelect = document.querySelector('#country');
  const mapSection = document.querySelector('.mapHero');
  if (!Array.isArray(rows) || !yearSelect || !countrySelect || !mapSection) return;

  const countries = [...new Set(rows.map(row => row.country))];
  const nameFor = country => {
    const option = [...countrySelect.options].find(item => item.value === country);
    return option?.textContent || country;
  };
  const rowsByYear = new Map([2017, 2022].map(year => [
    year,
    new Map(rows.filter(row => Number(row.year) === year).map(row => [row.country, row]))
  ]));
  const pct = (value, digits = 1) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))
    ? `${(Number(value) * 100).toFixed(digits)}%`
    : '缺失';
  const n4 = (row, digits = 2) => row ? pct(row.n4_dual_dependency, digits) : '缺失';
  const bandFor = row => {
    const value = row?.n4_dual_dependency;
    if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) return 'unknown';
    return Number(value) >= 0.05 ? 'high' : 'standard';
  };
  const safeYear = () => Number(yearSelect.value) === 2017 ? 2017 : 2022;

  const section = document.createElement('section');
  section.className = 'countryDeck';
  section.id = 'country-deck';
  section.setAttribute('aria-labelledby', 'country-deck-title');
  section.innerHTML = `
    <div class="countryDeck__head">
      <div>
        <span class="countryDeck__eyebrow">NODE ATLAS · 12 ECONOMIES</span>
        <h2 id="country-deck-title">关键节点，一眼看清</h2>
        <p>按 2022 年 N4 排列。选择国家后，地图与下方画像会同步更新。</p>
      </div>
      <div class="countryDeck__tools" aria-label="国家卡片浏览控制">
        <button class="countryDeck__arrow" type="button" data-scroll="left" aria-label="向左浏览国家">‹</button>
        <span class="countryDeck__count" aria-hidden="true">01 / 12</span>
        <button class="countryDeck__arrow" type="button" data-scroll="right" aria-label="向右浏览国家">›</button>
      </div>
    </div>
    <div class="countryDeck__viewport" tabindex="0" aria-label="横向浏览12个经济体；可以使用左右方向键">
      <div class="countryDeck__rail" role="group" aria-label="经济体风险画像卡片"></div>
    </div>
    <p class="countryDeck__status" aria-live="polite" aria-atomic="true"></p>`;
  mapSection.insertAdjacentElement('afterend', section);

  const viewport = section.querySelector('.countryDeck__viewport');
  const rail = section.querySelector('.countryDeck__rail');
  const status = section.querySelector('.countryDeck__status');
  const leftButton = section.querySelector('[data-scroll="left"]');
  const rightButton = section.querySelector('[data-scroll="right"]');
  const counter = section.querySelector('.countryDeck__count');
  const row2022 = rowsByYear.get(2022);
  const ordered = countries
    .filter(country => row2022?.has(country))
    .sort((left, right) => {
      const a = row2022.get(left).n4_dual_dependency;
      const b = row2022.get(right).n4_dual_dependency;
      const av = a !== null && a !== undefined && a !== '' && Number.isFinite(Number(a)) ? Number(a) : null;
      const bv = b !== null && b !== undefined && b !== '' && Number.isFinite(Number(b)) ? Number(b) : null;
      if (av === null) return bv === null ? 0 : 1;
      if (bv === null) return -1;
      return bv - av;
    });

  const makeCard = (country, index) => {
    const current = rowsByYear.get(safeYear())?.get(country);
    const historic = rowsByYear.get(2017)?.get(country);
    const recent = rowsByYear.get(2022)?.get(country);
    const name = nameFor(country);
    const iso = current?.iso3 || recent?.iso3 || country;
    const card = document.createElement('a');
    card.className = 'countryCard';
    card.dataset.country = country;
    card.dataset.band = bandFor(current);
    card.href = `?country=${encodeURIComponent(country)}&year=${safeYear()}`;
    card.innerHTML = `
      <div class="countryCard__top">
        <div class="countryCard__identity"><span class="countryCard__iso">${iso}</span><strong class="countryCard__name">${name}</strong></div>
        <span class="countryCard__rank" aria-label="2022年双重依赖排序第${index + 1}位">${String(index + 1).padStart(2, '0')}</span>
      </div>
      <div class="countryCard__metric"><strong class="countryCard__value" data-value="n4">${n4(current)}</strong><span class="countryCard__label">N4 · 双重依赖</span></div>
      <div class="countryCard__breakdown">
        <div><span>N2 · 对华进口</span><b data-value="n2">${pct(current?.n2_china_hs8542_import_share)}</b></div>
        <div><span>N3 · 对美出口</span><b data-value="n3">${pct(current?.n3_us_hs8542_export_share)}</b></div>
      </div>
      <div class="countryCard__foot"><span class="countryCard__trend">N4 · 2017 ${n4(historic)} → 2022 ${n4(recent)}</span><span class="countryCard__open">查看画像 ↗</span></div>`;
    return card;
  };

  ordered.forEach((country, index) => rail.append(makeCard(country, index)));
  const cards = [...rail.querySelectorAll('.countryCard')];

  const updateCards = () => {
    const year = safeYear();
    const selected = countrySelect.value;
    cards.forEach(card => {
      const country = card.dataset.country;
      const row = rowsByYear.get(year)?.get(country);
      card.dataset.band = bandFor(row);
      card.querySelector('[data-value="n4"]').textContent = n4(row);
      card.querySelector('[data-value="n2"]').textContent = pct(row?.n2_china_hs8542_import_share);
      card.querySelector('[data-value="n3"]').textContent = pct(row?.n3_us_hs8542_export_share);
      card.href = `?country=${encodeURIComponent(country)}&year=${year}`;
      const isSelected = country === selected;
      card.classList.toggle('is-selected', isSelected);
      if (isSelected) card.setAttribute('aria-current', 'true');
      else card.removeAttribute('aria-current');
      card.setAttribute('aria-label', `${nameFor(country)}，${year}年：N4双重依赖${n4(row)}，N2对华进口${pct(row?.n2_china_hs8542_import_share)}，N3对美出口${pct(row?.n3_us_hs8542_export_share)}。选择以查看完整画像。`);
    });
    updateCounter(selected);
  };

  const updateStatus = () => {
    const index = ordered.indexOf(countrySelect.value);
    const row = rowsByYear.get(safeYear())?.get(countrySelect.value);
    status.textContent = index >= 0
      ? `已选：${nameFor(countrySelect.value)} · ${safeYear()} 年 N4 ${n4(row)} · 地图与完整画像已同步`
      : `${safeYear()} 年数据暂缺；卡片保留来源年份对照，不补造数值。`;
  };
  const updateCounter = country => {
    const index = ordered.indexOf(country);
    counter.textContent = `${index < 0 ? '--' : String(index + 1).padStart(2, '0')} / ${String(ordered.length).padStart(2, '0')}`;
  };

  const writeUrl = (method = 'replaceState') => {
    const url = new URL(window.location.href);
    url.searchParams.set('country', countrySelect.value);
    url.searchParams.set('year', String(safeYear()));
    history[method]({}, '', `${url.pathname}${url.search}${url.hash}`);
  };

  const clearHover = () => {
    cards.forEach(card => card.classList.remove('is-active', 'push-left', 'push-right'));
    updateCounter(countrySelect.value);
  };
  const activateCard = card => {
    clearHover();
    if (!card) return;
    const index = cards.indexOf(card);
    card.classList.add('is-active');
    updateCounter(card.dataset.country);
    cards[index - 1]?.classList.add('push-left');
    cards[index + 1]?.classList.add('push-right');
  };

  rail.addEventListener('pointerover', event => {
    if (event.pointerType !== 'mouse') return;
    const card = event.target.closest('.countryCard');
    if (card && rail.contains(card) && !card.classList.contains('is-active')) activateCard(card);
  });
  rail.addEventListener('pointerleave', () => {
    const focused = rail.querySelector('.countryCard:focus');
    if (focused) activateCard(focused);
    else clearHover();
  });
  rail.addEventListener('focusin', event => {
    const card = event.target.closest('.countryCard');
    if (card) activateCard(card);
  });
  rail.addEventListener('focusout', () => queueMicrotask(() => {
    const focused = rail.querySelector('.countryCard:focus');
    if (focused) activateCard(focused);
    else if (!rail.matches(':hover')) clearHover();
  }));
  let fromCard = false;
  let suppressHistory = false;
  rail.addEventListener('click', event => {
    const card = event.target.closest('.countryCard');
    if (!card) return;
    event.preventDefault();
    fromCard = true;
    countrySelect.value = card.dataset.country;
    countrySelect.dispatchEvent(new Event('change', { bubbles: true }));
    fromCard = false;
    writeUrl('pushState');
  });

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  section.querySelectorAll('[data-scroll]').forEach(button => button.addEventListener('click', () => {
    viewport.scrollBy({ left: (button.dataset.scroll === 'left' ? -1 : 1) * viewport.clientWidth * 0.78, behavior: reducedMotion.matches ? 'auto' : 'smooth' });
  }));
  const updateArrows = () => {
    const max = Math.max(0, viewport.scrollWidth - viewport.clientWidth - 2);
    leftButton.disabled = viewport.scrollLeft <= 1;
    rightButton.disabled = viewport.scrollLeft >= max;
  };
  viewport.addEventListener('scroll', updateArrows, { passive: true });
  window.addEventListener('resize', updateArrows, { passive: true });

  let lastSelected = countrySelect.value;
  countrySelect.addEventListener('change', () => {
    lastSelected = countrySelect.value;
    updateCards();
    updateStatus();
    if (!fromCard && !suppressHistory) writeUrl('pushState');
  });
  yearSelect.addEventListener('change', () => {
    queueMicrotask(() => {
      if (rowsByYear.get(safeYear())?.has(lastSelected)) countrySelect.value = lastSelected;
      countrySelect.dispatchEvent(new Event('change', { bubbles: true }));
      updateArrows();
    });
  }, true);

  const applyUrlState = () => {
    suppressHistory = true;
    const params = new URLSearchParams(window.location.search);
    const year = Number(params.get('year'));
    const country = params.get('country');
    if (year === 2017 || year === 2022) {
      yearSelect.value = String(year);
      yearSelect.dispatchEvent(new Event('change', { bubbles: true }));
    }
    queueMicrotask(() => {
      if (countries.includes(country) && rowsByYear.get(safeYear())?.has(country)) {
        countrySelect.value = country;
        countrySelect.dispatchEvent(new Event('change', { bubbles: true }));
        cards.find(card => card.dataset.country === country)?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: reducedMotion.matches ? 'auto' : 'smooth' });
      } else {
        updateCards();
        updateStatus();
      }
      suppressHistory = false;
    });
  };
  window.addEventListener('popstate', applyUrlState);

  updateCards();
  updateStatus();
  updateArrows();
  applyUrlState();

  // Evidence-layer UI: keep additional sources visible and auditable without scoring them.
  const integrationStyles = document.createElement('style');
  integrationStyles.textContent = `
    .integrationLayer{position:relative;overflow:hidden;margin:30px 0 24px;padding:clamp(22px,3.4vw,42px);border:1px solid rgba(91,174,184,.22);border-radius:22px;background:linear-gradient(120deg,rgba(13,35,45,.98),rgba(8,23,33,.96) 58%,rgba(11,33,42,.98));box-shadow:0 24px 60px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.035)}
    .integrationLayer:before{content:"";position:absolute;top:0;left:7%;right:7%;height:1px;background:linear-gradient(90deg,transparent,rgba(62,214,197,.7),rgba(255,184,77,.52),transparent);opacity:.8}
    .integrationHead{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;margin-bottom:24px}.integrationHead h2{margin:7px 0 8px;font-size:clamp(22px,2.6vw,30px);letter-spacing:-.035em}.integrationHead p{max-width:670px;margin:0;color:#9db5bd;line-height:1.7}.integrationEyebrow{font-size:10px;letter-spacing:.18em;color:#64d7cc;text-transform:uppercase}.integrationYear{flex:none;padding:8px 11px;border:1px solid rgba(91,174,184,.24);border-radius:999px;color:#bdd3d7;font:11px/1.2 ui-monospace,Consolas,monospace}
    .integrationGrid{display:grid;grid-template-columns:.88fr 1fr 1.36fr;gap:0;border-top:1px solid rgba(138,180,189,.17)}.integrationCell{min-width:0;padding:20px 22px 4px 0}.integrationCell+.integrationCell{padding-left:22px;border-left:1px solid rgba(138,180,189,.13)}.integrationCell h3{margin:0 0 7px;color:#e7f1f0;font-size:15px}.integrationKicker{display:block;margin-bottom:13px;color:#7fa1aa;font-size:10px;letter-spacing:.12em;text-transform:uppercase}.integrationValue{display:block;color:#f1f7f5;font-size:20px;line-height:1.35;font-weight:650}.integrationCell p{margin:9px 0 0;color:#9bb2b9;font-size:12px;line-height:1.65}.integrationCell a{display:inline-block;margin-top:11px;color:#65d8cf;font-size:12px;text-decoration:none}.integrationCell a:hover{text-decoration:underline}.integrationPairs{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:15px}.integrationPairs>div{padding:10px 0;border-top:1px solid rgba(138,180,189,.17);color:#8da8b1;font-size:11px;line-height:1.45}.integrationPairs b{display:block;margin-top:4px;color:#ecf6f4;font-size:15px;font-weight:600}.integrationCoverage{margin-top:23px;padding-top:19px;border-top:1px solid rgba(138,180,189,.14)}.integrationCoverage__head{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;margin-bottom:12px}.integrationCoverage__head h3{margin:5px 0 0;font-size:15px;color:#e7f1f0}.integrationCoverage__period{color:#8ba5ad;font:11px/1.4 ui-monospace,Consolas,monospace}.integrationCoverage__groups{display:grid;grid-template-columns:1.35fr .9fr 1fr;gap:10px}.integrationCoverage__group{min-width:0;padding:14px;border:1px solid rgba(119,157,167,.14);border-radius:12px;background:rgba(5,18,27,.36)}.integrationCoverage__group h4{margin:0 0 10px;color:#8ba7af;font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase}.integrationCoverage__items{display:grid;gap:9px}.integrationCoverage__item{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:start;gap:10px;padding-top:8px;border-top:1px solid rgba(119,157,167,.11)}.integrationCoverage__item:first-child{padding-top:0;border-top:0}.integrationCoverage__item strong{display:block;color:#dce9e9;font-size:11px;font-weight:600}.integrationCoverage__item small{display:block;margin-top:2px;color:#829ba3;font-size:10px;line-height:1.45}.integrationCoverage__value{color:#6ee0d2;font:600 11px/1.5 ui-monospace,Consolas,monospace;white-space:nowrap}.integrationCoverage__value.is-limited{color:#f0c36a}.integrationCoverage__value.is-off{color:#9babb0}.integrationCoverage__note{margin:10px 0 0;color:#78929b;font-size:10px;line-height:1.55}.integrationFoot{display:flex;justify-content:space-between;gap:20px;margin-top:21px;padding-top:14px;border-top:1px solid rgba(138,180,189,.13);color:#819ba4;font-size:11px;line-height:1.6}.integrationFoot strong{color:#bad3d5;font-weight:550}
    @media(max-width:860px){.integrationGrid{grid-template-columns:1fr 1fr}.integrationCell:last-child{grid-column:1/-1;padding-left:0;border-left:0;border-top:1px solid rgba(138,180,189,.13);margin-top:14px}.integrationCell:nth-child(2){padding-right:0}.integrationHead{align-items:flex-start}.integrationCoverage__groups{grid-template-columns:1fr 1fr}.integrationCoverage__group:last-child{grid-column:1/-1}}
    @media(max-width:560px){.integrationLayer{padding:21px 17px;border-radius:18px}.integrationHead{display:block}.integrationYear{display:inline-block;margin-top:14px}.integrationGrid{grid-template-columns:1fr}.integrationCell,.integrationCell+.integrationCell,.integrationCell:last-child{grid-column:auto;padding:17px 0 4px;border-left:0;border-top:1px solid rgba(138,180,189,.13);margin:0}.integrationCoverage__groups{grid-template-columns:1fr}.integrationCoverage__group:last-child{grid-column:auto}.integrationCoverage__head{align-items:flex-start}.integrationFoot{display:block}.integrationFoot span{display:block;margin-top:5px}}
    @media(prefers-reduced-motion:reduce){.integrationLayer{scroll-behavior:auto}}
  `;
  document.head.append(integrationStyles);

  const boundary = document.querySelector('.boundary');
  if (boundary && Array.isArray(window.PILOT_INDEX)) {
    const displayNames = Object.fromEntries([...countrySelect.options].map(option => [option.value, option.textContent]));
    const integration = document.createElement('section');
    integration.className = 'integrationLayer';
    integration.setAttribute('aria-labelledby', 'integration-title');
    integration.innerHTML = `
      <div class="integrationHead"><div><span class="integrationEyebrow">SOURCE CROSSWALK · EVIDENCE ONLY</span><h2 id="integration-title">把来源接起来，也把边界留下</h2><p>选中的国家与年份会同步到下方证据层。联盟资料、BIS候选规则与投资头寸各自保留来源年份和观察口径，不并入 GTRI-v0 分数。</p></div><span class="integrationYear" id="integration-year">—</span></div>
      <div class="integrationGrid">
        <article class="integrationCell"><span class="integrationKicker">P2 · 正式防务安排</span><h3 id="integration-p2-label">—</h3><strong class="integrationValue" id="integration-p2-value">—</strong><p id="integration-p2-note">—</p><a id="integration-p2-link" target="_blank" rel="noopener noreferrer" hidden>查看来源记录 ↗</a></article>
        <article class="integrationCell"><span class="integrationKicker">P3 · BIS政策证据</span><h3>选定规则的人工范围核对</h3><div class="integrationPairs"><div>文本提及该国<b id="integration-p3-mentions">—</b></div><div>核认为直接新增管制<b id="integration-p3-events">—</b></div></div><p>只覆盖本次选定复核集合；零值只表示集合内未记到命中，不代表没有其他法律暴露。该层不计分。</p></article>
        <article class="integrationCell"><span class="integrationKicker">IMF CDIS · 双边投资头寸</span><h3 id="integration-cdis-period">—</h3><div class="integrationPairs"><div>该经济体报告：来自中国的流入头寸<b id="integration-cdis-in">—</b></div><div>中国报告：对该经济体的流出头寸<b id="integration-cdis-out">—</b></div></div><p>两方向分别来自不同报告方，按直接对手方统计；不是半导体专项投资，也不代表最终所有者。未报告保持为空，不当作零。</p></article>
      </div>
      <div class="integrationCoverage" aria-label="所选年份的数据来源覆盖"><div class="integrationCoverage__head"><div><span class="integrationEyebrow">SOURCE COVERAGE · 12-ECONOMY SAMPLE</span><h3>覆盖率、证据量与未接入来源分开看</h3></div><span id="integration-coverage-period" class="integrationCoverage__period">—</span></div><div class="integrationCoverage__groups"><section class="integrationCoverage__group"><h4>核心指标来源</h4><div class="integrationCoverage__items" id="integration-core-coverage"></div><p class="integrationCoverage__note">覆盖率表示该目标年面板中有可用记录的经济体数量，不代表来源准确度或指数预测能力。</p></section><section class="integrationCoverage__group"><h4>补充证据（不全入分）</h4><div class="integrationCoverage__items" id="integration-context-coverage"></div><p class="integrationCoverage__note">BIS仅反映所选复核规则；CDIS保留报告方向和源年份。</p></section><section class="integrationCoverage__group"><h4>暂未接入</h4><div class="integrationCoverage__items" id="integration-unjoined-coverage"></div><p class="integrationCoverage__note">缺少事件明细或企业/产品匹配键，因此不推算命中数和国家风险值。</p></section></div></div>
      <div class="integrationFoot"><span><strong>跨源说明</strong> · 2017 P2以 ATOP 观察值为主；2022 P2由美国国务院 / NATO 官方资料编码。ATOP 2018结构字段另作参照。</span><span>新增证据仅用于解释、核验与预警，不改变核心指数口径。</span></div>`;
    boundary.insertAdjacentElement('beforebegin', integration);

    const rankBody = document.querySelector('.rankTable tbody');
    if (rankBody) {
      const rows2022 = window.PILOT_INDEX
        .filter(row => Number(row.year) === 2022)
        .sort((left, right) => Number(left.rank_equal_weight_within_year) - Number(right.rank_equal_weight_within_year));
      rankBody.replaceChildren(...rows2022.map(row => {
        const tr = document.createElement('tr');
        [row.rank_equal_weight_within_year, displayNames[row.country] || row.country, Number(row.gtri_v0_equal_weight).toFixed(3), Number(row.gtri_v0_theory_weight).toFixed(3)]
          .forEach(value => { const td = document.createElement('td'); td.textContent = String(value); tr.append(td); });
        return tr;
      }));
    }

    const showNumber = value => value === null || value === undefined || value === '' || !Number.isFinite(Number(value))
      ? '未报告'
      : `${Number(value) < 0 ? '−' : ''}${Math.abs(Number(value)).toLocaleString('zh-CN', { maximumFractionDigits: 1 })} 百万美元`;
    const coverageRows = Array.isArray(window.SOURCE_COVERAGE) ? window.SOURCE_COVERAGE : [];
    const coverageByKey = new Map(coverageRows.map(item => [`${item.source_id}:${Number(item.target_year)}`, item]));
    const coverageFor = (sourceId, year) => coverageByKey.get(`${sourceId}:${year}`);
    const appendCoverageItem = (target, label, value, note, state = 'ok') => {
      const item = document.createElement('div');
      item.className = 'integrationCoverage__item';
      const copy = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = label;
      const detail = document.createElement('small');
      detail.textContent = note;
      copy.append(title, detail);
      const metric = document.createElement('span');
      metric.className = `integrationCoverage__value${state === 'limited' ? ' is-limited' : state === 'off' ? ' is-off' : ''}`;
      metric.textContent = value;
      item.append(copy, metric);
      target.append(item);
    };
    const renderCoverage = year => {
      const coreTarget = document.querySelector('#integration-core-coverage');
      const contextTarget = document.querySelector('#integration-context-coverage');
      const unjoinedTarget = document.querySelector('#integration-unjoined-coverage');
      if (!coreTarget || !contextTarget || !unjoinedTarget || !coverageRows.length) return;
      coreTarget.replaceChildren(); contextTarget.replaceChildren(); unjoinedTarget.replaceChildren();
      const ratio = row => row ? `${row.rows_with_observed_values}/${row.expected_country_rows}` : '无记录';
      const trade = coverageFor('comtrade_hs8542', year);
      const unga = coverageFor('unga_ideal_points', year);
      const tiva = coverageFor('oecd_tiva_2025', year);
      const p2 = year === 2017 ? coverageFor('atop_v5_1', year) : coverageFor('p2_us_state_nato_2022', year);
      appendCoverageItem(coreTarget, 'UN Comtrade · HS8542', ratio(trade), 'Reporter自报；N2/N3/N4与来源集中度');
      appendCoverageItem(coreTarget, 'UNGA · 理想点', ratio(unga), `${unga?.source_observation_year || '年份未记录'} · 三年窗口`);
      appendCoverageItem(coreTarget, 'OECD TiVA · C26_27', ratio(tiva), '宽口径电子/电气行业，不等于半导体专属');
      appendCoverageItem(coreTarget, year === 2017 ? 'ATOP v5.1 · P2' : '国务院/NATO · P2', ratio(p2),
        year === 2017 ? '2017目标年观察；2018仅作结构参照' : '2022目标年重建；与ATOP口径存在来源断点', 'limited');
      const bis = coverageFor('bis_federal_register_reviewed_subset', year);
      appendCoverageItem(contextTarget, 'BIS · 选定规则范围核对', `${bis?.reviewed_subset_positive_hits ?? '—'} 条命中`,
        `${bis?.panel_rows_with_source_record ?? 0}/12摘要行；非全量规则审查`, 'limited');
      const cdis = coverageFor('imf_cdis_positions', year);
      appendCoverageItem(contextTarget, 'IMF CDIS · 双边投资头寸', `${cdis?.rows_with_observed_values ?? 0}/12`,
        `${cdis?.source_observation_year || '年份未记录'}观测 · 流入${cdis?.cdis_inward_values_reported ?? 0}/12 · 流出${cdis?.cdis_outward_values_reported ?? 0}/12`, 'limited');
      appendCoverageItem(unjoinedTarget, 'GDELT · 中美双边事件', '未接入', '缺少可复现事件级导出；不从图表反推', 'off');
      appendCoverageItem(unjoinedTarget, 'GTA / CSL · 政策与实体筛查', '未接入', '尚无真实企业/产品标识和历史匹配键', 'off');
      document.querySelector('#integration-coverage-period').textContent = `${year}目标年 · 样本12国`;
    };
    const renderEvidence = () => {
      const year = safeYear();
      const country = countrySelect.value;
      const row = rowsByYear.get(year)?.get(country);
      if (!row) return;
      document.querySelector('#integration-year').textContent = `${displayNames[country] || country} · ${year}`;
      const p2Year = row.p2_source_year ?? year;
      const source = String(row.p2_measurement_source || '');
      document.querySelector('#integration-p2-label').textContent = source.includes('ATOP')
        ? (row.p2_oas_adjustment ? 'ATOP v5.1 + OAS条约状态核对' : 'ATOP v5.1 观察值')
        : '美国国务院条约记录与目标年材料 / NATO成员年份';
      document.querySelector('#integration-p2-value').textContent = `目标年值 ${Number(row.p2_us_formal_alliance) === 1 ? '1 · 识别到正式安排' : '0 · 所选来源未识别到'}`;
      const p2Note = row.p2_oas_adjustment
        ? `ATOP原始值 ${row.p2_atop_observed}；OAS记录《里约条约》对墨西哥于2004年终止，因此核验值为0。`
        : `${p2Year}年证据 · ${row.p2_treaty_or_basis || '0仅指所选正式防务安排口径，不代表没有其他安全合作。'}`;
      document.querySelector('#integration-p2-note').textContent = p2Note;
      const sourceLink = document.querySelector('#integration-p2-link');
      const firstUrl = String(row.p2_evidence_source_url || '').split(';')[0].trim();
      if (firstUrl.startsWith('https://')) { sourceLink.href = firstUrl; sourceLink.hidden = false; }
      else { sourceLink.removeAttribute('href'); sourceLink.hidden = true; }

      const literalHits = Number(row.p3_reviewed_candidate_literal_count);
      const directEvents = Number(row.p3_bis_direct_increase_events_reviewed_subset);
      document.querySelector('#integration-p3-mentions').textContent = Number.isFinite(literalHits) ? `${literalHits} 条` : '未报告';
      document.querySelector('#integration-p3-events').textContent = Number.isFinite(directEvents) ? `${directEvents} 条` : '未报告';

      const observationYear = row.cdis_observation_year;
      const lag = Number(row.cdis_observation_lag_years);
      document.querySelector('#integration-cdis-period').textContent = observationYear
        ? `${observationYear} 年末${lag > 0 ? ` · 滞后 ${lag} 年` : ' · 同年观测'}`
        : '该观察年未提供';
      document.querySelector('#integration-cdis-in').textContent = showNumber(row.cdis_sample_country_inward_from_china_usd_millions);
      document.querySelector('#integration-cdis-out').textContent = showNumber(row.cdis_china_outward_position_in_sample_country_usd_millions);
      renderCoverage(year);
    };
    countrySelect.addEventListener('change', renderEvidence);
    yearSelect.addEventListener('change', () => queueMicrotask(renderEvidence));
    renderEvidence();

    document.querySelectorAll('p,span,div.sub').forEach(node => {
      if (!node.childElementCount) node.textContent = node.textContent
        .replaceAll('候选规则已做定向人工核对，尚未逐条法律复核', '所选10条候选规则已逐条做范围核对；集合非穷尽，不构成全量法律审查')
        .replaceAll('P3尚未完成逐条法律复核', 'P3仅覆盖所选复核集合，未覆盖全部BIS规则及企业实体映射')
        .replaceAll('候选规则已做定向人工核对，尚未逐条法律复核', '所选10条候选规则已逐条做范围核对；集合非穷尽，不构成全量法律审查');
    });
  }
})();
