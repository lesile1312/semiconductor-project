/* 芯链哨兵 · 真实地理轮廓地图
 * 使用 Natural Earth 1:110m 国家轮廓的经纬度几何，以等距圆柱投影绘制。
 * 国家节点的数值仍来自本地核心面板；底图只负责地理定位。
 */
(function (global) {
  'use strict';
  var CN = {
    Malaysia: '马来西亚', Vietnam: '越南', Singapore: '新加坡', Thailand: '泰国',
    India: '印度', Indonesia: '印度尼西亚', Philippines: '菲律宾', Japan: '日本',
    'South Korea': '韩国', Mexico: '墨西哥', Germany: '德国', Netherlands: '荷兰'
  };
  var COLORS = {
    land: 'rgba(116,151,163,.30)', border: 'rgba(146,185,193,.28)',
    landHot: 'rgba(255,107,95,.48)', landCool: 'rgba(62,214,197,.35)',
    cyan: '#3ed6c5', hot: '#ff6b5f', text: '#eaf7f6'
  };
  var LABEL_OFFSETS = {
    Malaysia: [18, 28], Vietnam: [18, -24], Singapore: [28, 44], Thailand: [-46, -25],
    India: [16, -20], Indonesia: [34, 42], Philippines: [34, -18], Japan: [20, -22],
    'South Korea': [18, -32], Mexico: [14, -11], Germany: [-20, -18], Netherlands: [16, -18]
  };
  var FEATURE_ALIASES = {
    Malaysia: ['Malaysia'], Vietnam: ['Vietnam'], Singapore: ['Singapore'], Thailand: ['Thailand'],
    India: ['India'], Indonesia: ['Indonesia'], Philippines: ['Philippines'], Japan: ['Japan'],
    'South Korea': ['South Korea', 'Republic of Korea'], Mexico: ['Mexico'], Germany: ['Germany'],
    Netherlands: ['Netherlands']
  };
  var ANCHORS = {
    China: { lon: 104, lat: 35, color: '#3ed6c5' },
    UnitedStates: { lon: -100, lat: 38, color: '#f4bd5b' }
  };
  function project(lon, lat, w, h) {
    return { x: (lon + 180) / 360 * w, y: (90 - lat) / 180 * h };
  }
  function rings(geometry) {
    if (!geometry) return [];
    return geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  }
  function valuesOf(year) {
    var out = {};
    try {
      if (typeof D !== 'undefined') D.forEach(function (row) {
        if (+row.year === +year) out[row.country] = row;
      });
    } catch (e) {}
    return out;
  }
  function createPolygonMap(o) {
    var cv = o.canvas, stage = o.stage || (cv && cv.parentElement), geo = o.geo || global.WORLD_GEOMETRY;
    if (!cv || !stage || !geo || !global.DOTMAP) return null;
    var ctx = cv.getContext('2d'), tip = o.tip || null, card = o.card || null;
    var mode = o.mode || 'all', year = +o.year || 2022, active = o.highlight || null;
    var nodes = global.DOTMAP.nodes.map(function (n) { return { n: n.n, lon: n.lon, lat: n.lat }; });
    var W = 0, H = 0, dpr = 1, hover = null, mouse = { x: -1, y: -1, on: false };
    var tilt = { x: 0, y: 0, gx: 0, gy: 0, vx: 0, vy: 0, active: false, frame: 0 };
    var a11y = stage.querySelector('.mapA11y') || document.createElement('div');
    a11y.className = 'mapA11y';
    if (!a11y.parentNode) stage.appendChild(a11y);
    function nodeValues() {
      var map = valuesOf(year);
      nodes.forEach(function (n) {
        var v = map[n.n] || {};
        n.n2 = v.n2_china_hs8542_import_share;
        n.n3 = v.n3_us_hs8542_export_share;
        n.n4 = v.n4_dual_dependency;
      });
      var sorted = nodes.slice().sort(function (a, b) { return (b.n4 || 0) - (a.n4 || 0); });
      var rank = {}; sorted.forEach(function (n, i) { rank[n.n] = i; });
      nodes.forEach(function (n) { n.r = 4 + (1 - (rank[n.n] || 0) / Math.max(1, nodes.length - 1)) * 4; });
    }
    function px(n) { return project(n.lon, n.lat, W, H); }
    function drawRing(ring) {
      ring.forEach(function (point, i) {
        var p = project(point[0], point[1], W, H);
        if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
      });
      ctx.closePath();
    }
    function drawGeometry(geometry, fill, stroke, width) {
      rings(geometry).forEach(function (poly) {
        ctx.beginPath();
        poly.forEach(drawRing);
        ctx.fillStyle = fill; ctx.fill();
        ctx.strokeStyle = stroke; ctx.lineWidth = width || .55; ctx.stroke();
      });
    }
    function featureName(f) { return f && f.properties && (f.properties.name || f.properties.NAME || f.properties.admin); }
    function featureNode(f) {
      var name = featureName(f);
      if (!name) return null;
      for (var i = 0; i < nodes.length; i++) {
        var aliases = FEATURE_ALIASES[nodes[i].n] || [nodes[i].n];
        if (aliases.indexOf(name) >= 0) return nodes[i];
      }
      return null;
    }
    function lineCurve(a, b, color, alpha, width, dashed) {
      var bend = Math.max(12, Math.min(42, Math.abs(b.x - a.x) * .055));
      var cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2 - bend;
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.lineCap = 'round';
      if (dashed) { ctx.setLineDash([4, 7]); ctx.lineDashOffset = -2; }
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(cx, cy, b.x, b.y); ctx.stroke();
      ctx.restore();
    }
    function drawAnchor(p, color) {
      ctx.save();
      ctx.globalAlpha = .86;
      ctx.strokeStyle = color; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(p.x, p.y, 7, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = color; ctx.beginPath(); ctx.arc(p.x, p.y, 2.4, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
    function drawMicroTarget(n) {
      if (n.n !== 'Singapore') return;
      var p = px(n), hot = (n.n4 || 0) >= .05, color = hot ? COLORS.hot : COLORS.cyan;
      ctx.save(); ctx.globalAlpha = active && active !== n.n ? .35 : .9;
      ctx.fillStyle = hot ? 'rgba(255,107,95,.28)' : 'rgba(62,214,197,.25)';
      ctx.strokeStyle = color; ctx.lineWidth = 1.1;
      ctx.beginPath(); ctx.moveTo(p.x - 7, p.y); ctx.lineTo(p.x, p.y - 5); ctx.lineTo(p.x + 7, p.y); ctx.lineTo(p.x, p.y + 5); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.restore();
    }
    function drawSupplyLinks() {
      var map = valuesOf(year), china = project(ANCHORS.China.lon, ANCHORS.China.lat, W, H), us = project(ANCHORS.UnitedStates.lon, ANCHORS.UnitedStates.lat, W, H);
      drawAnchor(china, ANCHORS.China.color); drawAnchor(us, ANCHORS.UnitedStates.color);
      nodes.forEach(function (n) {
        var row = map[n.n] || {}, p = px(n), isActive = !active || n.n === active;
        var n2 = Number(row.n2_china_hs8542_import_share) || 0, n3 = Number(row.n3_us_hs8542_export_share) || 0;
        var alpha = isActive ? .18 + Math.min(.34, n2 * .55) : .095;
        var width = isActive ? .7 + Math.min(1.55, n2 * 4) : .58;
        lineCurve(china, p, ANCHORS.China.color, alpha, width, true);
        alpha = isActive ? .18 + Math.min(.34, n3 * .38) : .095;
        width = isActive ? .7 + Math.min(1.55, n3 * 1.8) : .58;
        lineCurve(p, us, ANCHORS.UnitedStates.color, alpha, width, true);
      });
      ctx.save(); ctx.font = '600 10px Inter,"Noto Sans SC",Arial,sans-serif';
      ctx.fillStyle = 'rgba(62,214,197,.88)'; ctx.fillText('中国投入', Math.min(W - 54, china.x + 8), Math.max(13, china.y - 9));
      ctx.fillStyle = 'rgba(244,189,91,.90)'; ctx.fillText('美国市场', Math.min(W - 54, us.x + 8), Math.max(13, us.y - 9));
      ctx.restore();
    }
    function drawPointerLinks() {
      if (!mouse.on) return;
      nodes.forEach(function (n) {
        var p = px(n), dx = p.x - mouse.x, dy = p.y - mouse.y, d = Math.sqrt(dx * dx + dy * dy);
        if (d > 330) return;
        lineCurve({ x: mouse.x, y: mouse.y }, p, COLORS.cyan, Math.max(.04, .28 * (1 - d / 330)), 1, false);
      });
    }
    function draw() {
      if (!W || !H) return;
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = 'rgba(5,15,22,.42)'; ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = 'rgba(116,170,180,.12)'; ctx.lineWidth = .6;
      for (var gx = 1; gx < 7; gx++) { ctx.beginPath(); ctx.moveTo(W * gx / 7, 0); ctx.lineTo(W * gx / 7, H); ctx.stroke(); }
      for (var gy = 1; gy < 5; gy++) { ctx.beginPath(); ctx.moveTo(0, H * gy / 5); ctx.lineTo(W, H * gy / 5); ctx.stroke(); }
      geo.features.forEach(function (f) { drawGeometry(f.geometry, COLORS.land, COLORS.border); });
      geo.features.forEach(function (f) {
        var target = featureNode(f);
        if (!target) return;
        var hotTarget = (target.n4 || 0) >= .05, focused = !active || target.n === active;
        var fill = hotTarget ? (focused ? 'rgba(255,107,95,.34)' : 'rgba(255,107,95,.12)') : (focused ? 'rgba(62,214,197,.25)' : 'rgba(62,214,197,.09)');
        var stroke = hotTarget ? (focused ? 'rgba(255,107,95,.92)' : 'rgba(255,107,95,.42)') : (focused ? 'rgba(62,214,197,.92)' : 'rgba(62,214,197,.38)');
        drawGeometry(f.geometry, fill, stroke, focused ? 1.25 : .72);
      });
      nodes.forEach(function (n) {
        if (!geo.features.some(function (f) { return featureNode(f) === n; })) drawMicroTarget(n);
      });
      drawSupplyLinks();
      nodes.forEach(function (n) {
        var p = px(n), hot = (n.n4 || 0) >= .05, focused = !active || n.n === active;
        drawGeometryForNode(n, p, hot, focused);
      });
      if (mouse.on) {
        var radius = Math.max(95, Math.min(170, W * .19));
        var g = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, radius);
        g.addColorStop(0, 'rgba(244,189,91,.18)'); g.addColorStop(1, 'rgba(244,189,91,0)');
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(mouse.x, mouse.y, radius, 0, Math.PI * 2); ctx.fill();
        drawPointerLinks();
      }
    }
    function drawGeometryForNode(n, p, hot, focused) {
      var c = hot ? COLORS.hot : COLORS.cyan;
      ctx.globalAlpha = focused ? 1 : .36;
      ctx.fillStyle = hot ? COLORS.landHot : COLORS.landCool;
      ctx.beginPath(); ctx.arc(p.x, p.y, 11 + n.r, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = c; ctx.lineWidth = focused ? 1.7 : .8;
      ctx.beginPath(); ctx.arc(p.x, p.y, n.r + (n.n === active ? 7 : 3), 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = c; ctx.beginPath(); ctx.arc(p.x, p.y, n.r, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1;
      if (mode === 'focus' && n.n !== active) return;
      var off = LABEL_OFFSETS[n.n] || [10, -9], tx = p.x + off[0], ty = p.y + off[1];
      ctx.strokeStyle = 'rgba(146,186,198,.42)'; ctx.lineWidth = .8;
      if (Math.abs(off[0]) > 16 || Math.abs(off[1]) > 16) { ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(tx, ty); ctx.stroke(); }
      ctx.font = '600 11px Inter,"Noto Sans SC",Arial,sans-serif';
      ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(5,15,22,.92)'; ctx.strokeText(CN[n.n] || n.n, tx, ty);
      ctx.fillStyle = COLORS.text; ctx.fillText(CN[n.n] || n.n, tx, ty);
    }
    function showCard(n) {
      if (!card || !n) return;
      var pct = function (x) { return x == null ? '—' : (x * 100).toFixed(1) + '%'; };
      var num = function (x) { return x == null ? '—' : x.toFixed(4); };
      var hot = (n.n4 || 0) >= .05;
      card.innerHTML = '<b>' + (CN[n.n] || n.n) + '</b>' +
        '<div class="row"><span>N2 对华进口依赖</span><em>' + pct(n.n2) + '</em></div>' +
        '<div class="row"><span>N3 对美出口依赖</span><em>' + pct(n.n3) + '</em></div>' +
        '<div class="row"><span>N4 双重依赖</span><em class="' + (hot ? 'hot' : '') + '">' + num(n.n4) + '</em></div>' +
        '<span class="flag">' + year + ' · ' + (hot ? '夹层暴露较高' : '结构暴露较低') + '</span>';
      card.className = 'mapCard on';
      var p = px(n); card.style.left = Math.max(8, Math.min(W - 198, p.x + 18)) + 'px'; card.style.top = Math.max(8, Math.min(H - 124, p.y - 16)) + 'px';
    }
    function setHover(n) {
      hover = n || null;
      if (hover) { showCard(hover); if (o.onHover) o.onHover(hover); }
      else if (card) { card.className = 'mapCard'; if (o.onHover) o.onHover(null); }
      draw();
    }
    function hit(x, y) {
      var best = 26 * 26, found = null;
      nodes.forEach(function (n) { var p = px(n), dx = p.x - x, dy = p.y - y, d = dx * dx + dy * dy; if (d < best) { best = d; found = n; } });
      return found;
    }
    function buildA11y() {
      a11y.innerHTML = '';
      nodes.forEach(function (n) {
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'mapNodeButton'; b.dataset.country = n.n;
        b.setAttribute('aria-label', (CN[n.n] || n.n) + '，' + year + '年风险节点');
        b.addEventListener('focus', function () { active = n.n; setHover(n); });
        b.addEventListener('blur', function () { if (!mouse.on) setHover(null); });
        b.addEventListener('click', function () { active = n.n; setHover(n); });
        a11y.appendChild(b);
      });
      positionA11y();
    }
    function positionA11y() {
      Array.prototype.forEach.call(a11y.children, function (b) {
        var n = nodes.filter(function (x) { return x.n === b.dataset.country; })[0]; if (!n) return;
        var p = px(n); b.style.left = (p.x - 15) + 'px'; b.style.top = (p.y - 15) + 'px';
      });
    }
    function animateTilt() {
      var spring = 0.075, damping = 0.78;
      tilt.vx += (tilt.gx - tilt.x) * spring;
      tilt.vy += (tilt.gy - tilt.y) * spring;
      tilt.vx *= damping; tilt.vy *= damping;
      tilt.x += tilt.vx; tilt.y += tilt.vy;
      var moving = Math.abs(tilt.x) + Math.abs(tilt.y) + Math.abs(tilt.vx) + Math.abs(tilt.vy) > .012;
      stage.style.setProperty('--tilt-x', (-tilt.y * 6.2).toFixed(3) + 'deg');
      stage.style.setProperty('--tilt-y', (tilt.x * 8.2).toFixed(3) + 'deg');
      stage.style.setProperty('--map-mx', (((tilt.x + 1) / 2) * 100).toFixed(2) + '%');
      stage.style.setProperty('--map-my', (((tilt.y + 1) / 2) * 100).toFixed(2) + '%');
      stage.style.setProperty('--map-glow', String(Math.min(1, tilt.active ? .9 : moving ? .42 : 0)));
      if (moving || tilt.active) tilt.frame = requestAnimationFrame(animateTilt);
      else { tilt.frame = 0; stage.style.setProperty('--map-glow', '0'); }
    }
    function startTiltFrame() { if (!tilt.frame) tilt.frame = requestAnimationFrame(animateTilt); }
    function bindTilt() {
      stage.classList.add('mapInteractive');
      stage.addEventListener('pointerenter', function () { tilt.active = true; startTiltFrame(); });
      stage.addEventListener('pointermove', function (e) {
        var r = stage.getBoundingClientRect();
        tilt.gx = Math.max(-1, Math.min(1, ((e.clientX - r.left) / r.width) * 2 - 1));
        tilt.gy = Math.max(-1, Math.min(1, ((e.clientY - r.top) / r.height) * 2 - 1));
        tilt.active = true; startTiltFrame();
      });
      stage.addEventListener('pointerleave', function () {
        tilt.gx = 0; tilt.gy = 0; tilt.active = false; startTiltFrame();
      });
    }
    function fit() {
      var rect = stage.getBoundingClientRect(); W = rect.width; H = rect.height;
      if (W < 40 || H < 40) return;
      dpr = window.devicePixelRatio || 1; cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      positionA11y(); draw();
    }
    function bind() {
      stage.addEventListener('mousemove', function (e) { var r = stage.getBoundingClientRect(); mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top; mouse.on = true; var n = hit(mouse.x, mouse.y); if (n !== hover) setHover(n); if (tip) tip.textContent = n ? '已定位 ' + (CN[n.n] || n.n) + ' · 查看指标' : '移动鼠标探索风险节点'; });
      stage.addEventListener('mouseleave', function () { mouse.on = false; if (tip) tip.textContent = o.tipIdle || '移动鼠标探索风险节点'; setHover(null); });
      window.addEventListener('resize', fit);
    }
    nodeValues(); fit(); buildA11y(); bind(); bindTilt();
    return {
      setHighlight: function (name) { active = name; draw(); return active; },
      setYear: function (value) { year = +value || year; nodeValues(); buildA11y(); draw(); return year; },
      refresh: function () { nodeValues(); buildA11y(); draw(); },
      resize: fit,
      destroy: function () { window.removeEventListener('resize', fit); }
    };
  }
  global.createPolygonMap = createPolygonMap;
})(this);
