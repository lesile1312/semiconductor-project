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
    function drawGeometry(geometry, fill, stroke) {
      rings(geometry).forEach(function (poly) {
        ctx.beginPath();
        poly.forEach(drawRing);
        ctx.fillStyle = fill; ctx.fill();
        ctx.strokeStyle = stroke; ctx.lineWidth = .55; ctx.stroke();
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
      nodes.forEach(function (n) {
        var p = px(n), hot = (n.n4 || 0) >= .05, focused = !active || n.n === active;
        drawGeometryForNode(n, p, hot, focused);
      });
      if (mouse.on) {
        var radius = Math.max(95, Math.min(170, W * .19));
        var g = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, radius);
        g.addColorStop(0, 'rgba(244,189,91,.18)'); g.addColorStop(1, 'rgba(244,189,91,0)');
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(mouse.x, mouse.y, radius, 0, Math.PI * 2); ctx.fill();
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
    nodeValues(); fit(); buildA11y(); bind();
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
