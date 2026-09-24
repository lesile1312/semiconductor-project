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
})();
