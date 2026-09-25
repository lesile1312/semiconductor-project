/* 芯链哨兵 · 真实地理轮廓地图
 * 使用 Natural Earth 1:110m 国家轮廓的经纬度几何，以等距圆柱投影绘制。
 * 国家节点的数值仍来自本地核心面板；底图只负责地理定位。
 * 动效规范：tilt-panel（指针倾斜）、glow-border（焦点边缘光）与
 * spring-cascade（有节制的网络脉冲）；所有粒子均为本地确定性绘制，不引入外部服务。
 */
(function (global) {
  'use strict';
  var CN = {
    Malaysia: '马来西亚', Vietnam: '越南', Singapore: '新加坡', Thailand: '泰国',
    India: '印度', Indonesia: '印度尼西亚', Philippines: '菲律宾', Japan: '日本',
    'South Korea': '韩国', Mexico: '墨西哥', Germany: '德国', Netherlands: '荷兰'
  };
  var COLORS = {
    land: 'rgba(116,151,163,.14)', border: 'rgba(146,185,193,.22)',
    landHot: 'rgba(255,107,95,.48)', landCool: 'rgba(62,214,197,.35)',
    cyan: '#3ed6c5', amber: '#f4bd5b', hot: '#ff6b5f', text: '#eaf7f6'
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
  // 地图本体只保留一层受控的弹簧倾斜，避免外层卡片变换叠加造成首屏“越变越大”。
  var MOTION = { tiltMax: 5.5, spring: .075, damping: .78, glowAlpha: .18, durationBase: 320 };
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
    var motion = { time: 0, frame: 0, visible: true, reduced: false };
    var particles = [], worldDots = [], dotsW = 0, dotsH = 0, fitFrame = 0, resizeObserver = null;
    try { motion.reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) {}
    var a11y = stage.querySelector('.mapA11y') || document.createElement('div');
    a11y.className = 'mapA11y';
    if (!a11y.parentNode) stage.appendChild(a11y);
    function initParticles() {
      var seed = 928371;
      function random() { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }
      particles = [];
      var count = window.innerWidth < 700 ? 52 : 86;
      for (var i = 0; i < count; i++) particles.push({
        u: random(), v: random(), z: .22 + random() * .78,
        phase: random() * Math.PI * 2, drift: .35 + random() * .65,
        size: .32 + random() * 1.1, amber: random() > .86
      });
    }
    function curveControl(a, b) {
      var bend = Math.max(12, Math.min(42, Math.abs(b.x - a.x) * .055));
      return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 - bend };
    }
    function curvePoint(a, b, t) {
      var c = curveControl(a, b), k = 1 - t;
      return { x: k * k * a.x + 2 * k * t * c.x + t * t * b.x, y: k * k * a.y + 2 * k * t * c.y + t * t * b.y };
    }
    function drawParticleField(time) {
      var t = (time || 0) * .001;
      ctx.save();
      particles.forEach(function (q) {
        var depth = q.z, parallaxX = mouse.on ? (mouse.x / Math.max(1, W) - .5) * 8 * depth : 0;
        var parallaxY = mouse.on ? (mouse.y / Math.max(1, H) - .5) * 5 * depth : 0;
        var x = q.u * W + Math.sin(t * .18 * q.drift + q.phase) * 4 * depth + parallaxX;
        var y = q.v * H + Math.cos(t * .14 * q.drift + q.phase) * 2.5 * depth + parallaxY;
        var alpha = (.055 + depth * .12) * (.78 + .22 * Math.sin(t * .65 + q.phase));
        ctx.globalAlpha = Math.max(.025, alpha);
        ctx.fillStyle = q.amber ? COLORS.amber : COLORS.cyan;
        ctx.beginPath(); ctx.arc(x, y, q.size * depth, 0, Math.PI * 2); ctx.fill();
      });
      ctx.restore();
    }
    function pointInRing(x, y, ring) {
      var inside = false;
      for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        var pi = project(ring[i][0], ring[i][1], W, H), pj = project(ring[j][0], ring[j][1], W, H);
        var cross = ((pi.y > y) !== (pj.y > y)) && (x < (pj.x - pi.x) * (y - pi.y) / ((pj.y - pi.y) || 1e-9) + pi.x);
        if (cross) inside = !inside;
      }
      return inside;
    }
    function pointInPolygon(x, y, polygon) {
      if (!polygon || !polygon.length || !pointInRing(x, y, polygon[0])) return false;
      for (var i = 1; i < polygon.length; i++) if (pointInRing(x, y, polygon[i])) return false;
      return true;
    }
    function buildWorldDots() {
      if (!W || !H) return;
      var gap = Math.max(4.8, Math.min(7.2, W / 170)), seed = 671239;
      function random() { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }
      worldDots = [];
      geo.features.forEach(function (f) {
        var geometry = f.geometry, polygons = !geometry ? [] : (geometry.type === 'Polygon' ? [geometry.coordinates] : (geometry.coordinates || []));
        var target = featureNode(f), tone = target ? ((target.n4 || 0) >= .05 ? 'hot' : 'cyan') : 'land';
        polygons.forEach(function (polygon) {
          var outer = polygon && polygon[0]; if (!outer || !outer.length) return;
          var screen = outer.map(function (p) { return project(p[0], p[1], W, H); });
          var minX = W, minY = H, maxX = 0, maxY = 0;
          screen.forEach(function (p) { minX = Math.min(minX, p.x); minY = Math.min(minY, p.y); maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y); });
          for (var y = Math.max(0, Math.floor(minY / gap) * gap); y <= Math.min(H, maxY); y += gap) {
            for (var x = Math.max(0, Math.floor(minX / gap) * gap); x <= Math.min(W, maxX); x += gap) {
              if (!pointInPolygon(x, y, polygon)) continue;
              worldDots.push({ x: x, y: y, z: .34 + random() * .66, phase: random() * Math.PI * 2, size: .58 + random() * .78, tone: tone, country: target && target.n });
            }
          }
        });
      });
      dotsW = W; dotsH = H;
    }
    function drawWorldDots(time) {
      if (!worldDots.length) return;
      var t = (time || 0) * .001;
      ctx.save();
      worldDots.forEach(function (d) {
        var focused = !active || !d.country || d.country === active, depth = d.z;
        var x = d.x + Math.sin(t * .12 + d.phase) * .45 * depth + (mouse.on ? (mouse.x / Math.max(1, W) - .5) * 3.6 * depth : 0);
        var y = d.y + Math.cos(t * .1 + d.phase) * .32 * depth + (mouse.on ? (mouse.y / Math.max(1, H) - .5) * 2.4 * depth : 0);
        var alpha = (d.tone === 'land' ? .17 : .30) + depth * (d.tone === 'land' ? .15 : .28);
        if (!focused) alpha *= .38;
        ctx.globalAlpha = Math.max(.035, alpha * (.82 + .18 * Math.sin(t * .7 + d.phase)));
        ctx.fillStyle = d.tone === 'hot' ? COLORS.hot : d.tone === 'cyan' ? COLORS.cyan : 'rgba(157,190,198,1)';
        var r = d.size * (.78 + depth * .48);
        ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      });
      ctx.restore();
    }
    function drawPulse(p, color, alpha, radius) {
      ctx.save(); ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.shadowColor = color; ctx.shadowBlur = 10;
      ctx.beginPath(); ctx.arc(p.x, p.y, radius, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    }
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
      var control = curveControl(a, b);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.lineCap = 'round';
      if (dashed) { ctx.setLineDash([4, 7]); ctx.lineDashOffset = -2; }
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(control.x, control.y, b.x, b.y); ctx.stroke();
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
    function drawSupplyLinks(time) {
      var map = valuesOf(year), china = project(ANCHORS.China.lon, ANCHORS.China.lat, W, H), us = project(ANCHORS.UnitedStates.lon, ANCHORS.UnitedStates.lat, W, H);
      drawAnchor(china, ANCHORS.China.color); drawAnchor(us, ANCHORS.UnitedStates.color);
      nodes.forEach(function (n, index) {
        var row = map[n.n] || {}, p = px(n), isActive = !active || n.n === active;
        var n2 = Number(row.n2_china_hs8542_import_share) || 0, n3 = Number(row.n3_us_hs8542_export_share) || 0;
        var alpha = isActive ? .18 + Math.min(.34, n2 * .55) : .095;
        var width = isActive ? .7 + Math.min(1.55, n2 * 4) : .58;
        lineCurve(china, p, ANCHORS.China.color, alpha, width, true);
        alpha = isActive ? .18 + Math.min(.34, n3 * .38) : .095;
        width = isActive ? .7 + Math.min(1.55, n3 * 1.8) : .58;
        lineCurve(p, us, ANCHORS.UnitedStates.color, alpha, width, true);
        var showPulse = isActive || n2 >= .14 || n3 >= .55;
        if (showPulse) {
          var phase = ((time || 0) * .000028 + index * .083) % 1;
          drawPulse(curvePoint(china, p, phase), ANCHORS.China.color, isActive ? .78 : .32, 1.15 + Math.min(1.25, n2 * 4));
          drawPulse(curvePoint(p, us, (phase + .38) % 1), ANCHORS.UnitedStates.color, isActive ? .7 : .28, 1.1 + Math.min(1.15, n3 * 1.6));
        }
      });
    }
    function drawPointerLinks() {
      if (!mouse.on) return;
      nodes.forEach(function (n) {
        var p = px(n), dx = p.x - mouse.x, dy = p.y - mouse.y, d = Math.sqrt(dx * dx + dy * dy);
        if (d > 330) return;
        lineCurve({ x: mouse.x, y: mouse.y }, p, COLORS.cyan, Math.max(.04, .28 * (1 - d / 330)), 1, false);
      });
    }
    function draw(time) {
      if (!W || !H) return;
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = 'rgba(5,15,22,.42)'; ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = 'rgba(116,170,180,.12)'; ctx.lineWidth = .6;
      for (var gx = 1; gx < 7; gx++) { ctx.beginPath(); ctx.moveTo(W * gx / 7, 0); ctx.lineTo(W * gx / 7, H); ctx.stroke(); }
      for (var gy = 1; gy < 5; gy++) { ctx.beginPath(); ctx.moveTo(0, H * gy / 5); ctx.lineTo(W, H * gy / 5); ctx.stroke(); }
      drawParticleField(time);
      geo.features.forEach(function (f) { drawGeometry(f.geometry, COLORS.land, COLORS.border); });
      drawWorldDots(time);
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
      drawSupplyLinks(time);
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
      if (focused || hot) {
        var wave = (Math.sin((motion.time || 0) * .0017 + n.r * 1.4) + 1) / 2;
        ctx.save(); ctx.globalAlpha = focused ? .09 + wave * .08 : .035 + wave * .04; ctx.strokeStyle = c; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(p.x, p.y, n.r + 10 + wave * 7, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
      }
      ctx.globalAlpha = focused ? 1 : .36;
      ctx.fillStyle = hot ? COLORS.landHot : COLORS.landCool;
      ctx.beginPath(); ctx.arc(p.x, p.y, 11 + n.r, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = c; ctx.lineWidth = focused ? 1.7 : .8;
      ctx.beginPath(); ctx.arc(p.x, p.y, n.r + (n.n === active ? 7 : 3), 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = c; ctx.beginPath(); ctx.arc(p.x, p.y, n.r, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1;
      if (mode === 'focus' && n.n !== active) return;
      var off = LABEL_OFFSETS[n.n] || [10, -9], tx = p.x + off[0], ty = p.y + off[1];
      var label = CN[n.n] || n.n, fontSize = W < 440 ? 9 : 11;
      ctx.font = '600 ' + fontSize + 'px Inter,"Noto Sans SC",Arial,sans-serif';
      var labelWidth = ctx.measureText(label).width;
      if (W < 440) {
        if (tx + labelWidth > W - 8) tx = p.x - labelWidth - 10;
        if (tx < 8) tx = Math.min(W - labelWidth - 8, p.x + 10);
        ty = Math.max(14, Math.min(H - 9, ty));
      }
      ctx.strokeStyle = 'rgba(146,186,198,.42)'; ctx.lineWidth = .8;
      if (Math.abs(tx - p.x) > 16 || Math.abs(ty - p.y) > 16) { ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(tx, ty); ctx.stroke(); }
      ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(5,15,22,.92)'; ctx.strokeText(label, tx, ty);
      ctx.fillStyle = COLORS.text; ctx.fillText(label, tx, ty);
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
      draw(motion.time);
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
        var p = px(n); b.style.left = (p.x - 22) + 'px'; b.style.top = (p.y - 22) + 'px';
      });
    }
    function animateTilt() {
      var spring = MOTION.spring, damping = MOTION.damping;
      tilt.vx += (tilt.gx - tilt.x) * spring;
      tilt.vy += (tilt.gy - tilt.y) * spring;
      tilt.vx *= damping; tilt.vy *= damping;
      tilt.x += tilt.vx; tilt.y += tilt.vy;
      // 指针事件可能在浏览器切页/缩放时短暂丢失，给弹簧状态加硬边界，杜绝变换漂移。
      tilt.x = Math.max(-1, Math.min(1, tilt.x));
      tilt.y = Math.max(-1, Math.min(1, tilt.y));
      var moving = Math.abs(tilt.x) + Math.abs(tilt.y) + Math.abs(tilt.vx) + Math.abs(tilt.vy) > .012;
      stage.style.setProperty('--tilt-x', (-tilt.y * MOTION.tiltMax).toFixed(3) + 'deg');
      stage.style.setProperty('--tilt-y', (tilt.x * MOTION.tiltMax).toFixed(3) + 'deg');
      stage.style.setProperty('--map-mx', (((tilt.x + 1) / 2) * 100).toFixed(2) + '%');
      stage.style.setProperty('--map-my', (((tilt.y + 1) / 2) * 100).toFixed(2) + '%');
      stage.style.setProperty('--map-glow', String(Math.min(1, tilt.active ? .9 : moving ? .42 : 0)));
      if (moving || tilt.active) tilt.frame = requestAnimationFrame(animateTilt);
      else { tilt.frame = 0; stage.style.setProperty('--map-glow', '0'); }
    }
    function animateScene(time) {
      motion.time = time;
      if (!motion.reduced && motion.visible) {
        draw(time);
        motion.frame = requestAnimationFrame(animateScene);
      } else { motion.frame = 0; }
    }
    function startScene() {
      if (!motion.reduced && motion.visible && !motion.frame) motion.frame = requestAnimationFrame(animateScene);
    }
    function stopScene() {
      if (motion.frame) { cancelAnimationFrame(motion.frame); motion.frame = 0; }
    }
    function bindSceneVisibility() {
      var setVisible = function (visible) { motion.visible = visible; stage.classList.toggle('mapPaused', !visible); if (visible) startScene(); else stopScene(); };
      var onVisibility = function () { setVisible(document.visibilityState !== 'hidden'); };
      document.addEventListener('visibilitychange', onVisibility);
      if ('IntersectionObserver' in window) {
        var observer = new IntersectionObserver(function (entries) {
          setVisible(!!(entries[0] && entries[0].isIntersecting));
        }, { threshold: .05 });
        observer.observe(stage);
        return function () { observer.disconnect(); document.removeEventListener('visibilitychange', onVisibility); };
      }
      return function () { document.removeEventListener('visibilitychange', onVisibility); };
    }
    function startTiltFrame() { if (!tilt.frame) tilt.frame = requestAnimationFrame(animateTilt); }
    function bindTilt() {
      if (motion.reduced) return;
      stage.classList.add('mapInteractive');
      stage.addEventListener('pointerenter', function (e) { if (e.pointerType === 'touch') return; tilt.active = true; startTiltFrame(); });
      stage.addEventListener('pointermove', function (e) {
        if (e.pointerType === 'touch') return;
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
      // 3D 倾斜会改变 getBoundingClientRect() 的外接框；Canvas 适配必须读取未变换的布局尺寸，
      // 否则 ResizeObserver 会把变换后的尺寸再次写回画布，形成“越变越大”的反馈循环。
      var rect = stage.getBoundingClientRect();
      W = stage.clientWidth || rect.width; H = stage.clientHeight || rect.height;
      if (W < 40 || H < 40) return false;
      dpr = window.devicePixelRatio || 1; cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (Math.abs(dotsW - W) > 2 || Math.abs(dotsH - H) > 2) buildWorldDots();
      positionA11y(); draw(motion.time);
      return true;
    }
    function scheduleFit() {
      if (fitFrame) return;
      fitFrame = requestAnimationFrame(function () { fitFrame = 0; fit(); });
    }
    function bind() {
      function updatePointer(e) {
        var r = stage.getBoundingClientRect(); mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top; mouse.on = true;
        var n = hit(mouse.x, mouse.y); if (n !== hover) setHover(n);
        if (tip) tip.textContent = n ? '已定位 ' + (CN[n.n] || n.n) + ' · 查看指标' : '移动鼠标探索风险节点';
      }
      function clearPointer() { mouse.on = false; if (tip) tip.textContent = o.tipIdle || '移动鼠标探索风险节点'; setHover(null); }
      stage.addEventListener('pointermove', updatePointer, { passive: true });
      stage.addEventListener('pointerdown', function (e) { if (e.pointerType === 'touch') updatePointer(e); }, { passive: true });
      stage.addEventListener('pointerleave', clearPointer, { passive: true });
      stage.addEventListener('pointercancel', clearPointer, { passive: true });
      window.addEventListener('resize', scheduleFit, { passive: true });
      window.addEventListener('orientationchange', scheduleFit, { passive: true });
      if (window.visualViewport) window.visualViewport.addEventListener('resize', scheduleFit, { passive: true });
      if ('ResizeObserver' in window) { resizeObserver = new ResizeObserver(scheduleFit); resizeObserver.observe(stage); }
    }
    initParticles();
    nodeValues(); fit(); buildA11y(); bind(); bindTilt();
    scheduleFit(); setTimeout(scheduleFit, 120); setTimeout(scheduleFit, 420);
    var unbindSceneVisibility = bindSceneVisibility();
    startScene();
    return {
      setHighlight: function (name) { active = name; draw(motion.time); return active; },
      setYear: function (value) { year = +value || year; nodeValues(); buildWorldDots(); buildA11y(); draw(motion.time); return year; },
      refresh: function () { nodeValues(); buildWorldDots(); buildA11y(); draw(motion.time); },
      resize: fit,
      destroy: function () {
        stopScene(); if (fitFrame) cancelAnimationFrame(fitFrame); if (resizeObserver) resizeObserver.disconnect();
        if (unbindSceneVisibility) unbindSceneVisibility(); window.removeEventListener('resize', scheduleFit); window.removeEventListener('orientationchange', scheduleFit);
        if (window.visualViewport) window.visualViewport.removeEventListener('resize', scheduleFit);
      }
    };
  }
  global.createPolygonMap = createPolygonMap;
  /*
   * 视觉层：只负责层级、光场和反馈，不改变任何指标或地图数据。
   * 选用 premium-motion-ui 的 glow-border / tilt-panel / press-feedback，
   * 并用一个 rAF 合并指针与滚动更新，避免在移动端堆积监听器。
   */
  function installPremiumMotion() {
    if (!global.document || global.__GTRI_PREMIUM_MOTION__) return;
    global.__GTRI_PREMIUM_MOTION__ = true;
    var doc = global.document;
    var style = doc.createElement('style');
    style.setAttribute('data-gtri-premium-motion', 'true');
    style.textContent = [
      ':root{--gtri-ease:cubic-bezier(.22,1,.36,1);--gtri-cyan:#3ed6c5;--gtri-amber:#f4bd5b;--gtri-red:#ff6b5f}',
      '.gtri-scroll-rail{position:fixed;left:0;top:0;width:var(--gtri-progress,0%);height:2px;z-index:9999;pointer-events:none;background:linear-gradient(90deg,var(--gtri-cyan),var(--gtri-amber),var(--gtri-red));box-shadow:0 0 14px rgba(62,214,197,.72);transition:width .18s var(--gtri-ease)}',
      '.gtri-reveal{opacity:0;transform:translate3d(0,18px,0);transition:opacity .62s var(--gtri-ease),transform .72s var(--gtri-ease);transition-delay:var(--gtri-delay,0ms)}.gtri-reveal.is-visible{opacity:1;transform:none}',
      '.gtri-surface{position:relative;isolation:isolate;--gtri-x:50%;--gtri-y:50%;--gtri-rx:0deg;--gtri-ry:0deg;transition:transform .45s var(--gtri-ease),border-color .35s ease,box-shadow .35s ease}.gtri-surface:before{content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;border-radius:inherit;background:radial-gradient(circle at var(--gtri-x) var(--gtri-y),rgba(62,214,197,.16),transparent 42%),linear-gradient(120deg,transparent 22%,rgba(255,255,255,.055) 44%,transparent 58%);opacity:0;transition:opacity .35s ease}.gtri-surface.gtri-hover:before{opacity:1}.gtri-tilt{transform:perspective(1200px) rotateX(var(--gtri-rx)) rotateY(var(--gtri-ry)) translateZ(0);will-change:transform}.gtri-tilt.gtri-hover{box-shadow:0 24px 65px rgba(0,0,0,.26),inset 0 1px 0 rgba(255,255,255,.06)}',
      '.mapHero,.mapStrip{overflow:hidden}.mapHero:before,.mapStrip:before{content:"";position:absolute;inset:-50%;z-index:0;pointer-events:none;background:conic-gradient(from 180deg at 50% 50%,transparent 0 24%,rgba(62,214,197,.12) 30%,transparent 38% 62%,rgba(244,189,91,.09) 70%,transparent 76%);animation:gtriOrbit 18s linear infinite;mix-blend-mode:screen;opacity:.72}.mapHero>* ,.mapStrip>*{position:relative;z-index:1}',
      '.mapHero .mapStage:before,.mapStrip .mapStage:before{content:"";position:absolute;left:0;right:0;top:-35%;height:28%;z-index:3;pointer-events:none;background:linear-gradient(180deg,transparent,rgba(62,214,197,.12),transparent);border-top:1px solid rgba(62,214,197,.18);filter:blur(.2px);animation:gtriScan 7.5s var(--gtri-ease) infinite}',
      '.gtri-orb{position:absolute;width:160px;height:160px;right:8%;top:8%;border-radius:50%;pointer-events:none;background:radial-gradient(circle,rgba(62,214,197,.14),rgba(62,214,197,.035) 42%,transparent 70%);filter:blur(1px);animation:gtriBreathe 5.5s ease-in-out infinite}',
      '.gtri-press{transition:transform .16s var(--gtri-ease),filter .16s ease}.gtri-press:active{transform:scale(.965);filter:brightness(1.1)}',
      '.gtri-surface:focus-within{border-color:rgba(244,189,91,.64);box-shadow:0 0 0 1px rgba(244,189,91,.2),0 16px 36px rgba(0,0,0,.18)}',
      '@keyframes gtriOrbit{to{transform:rotate(360deg)}}@keyframes gtriScan{0%{transform:translateY(0);opacity:0}15%{opacity:.9}72%{opacity:.55}100%{transform:translateY(520%);opacity:0}}@keyframes gtriBreathe{0%,100%{transform:scale(.84);opacity:.48}50%{transform:scale(1.08);opacity:.82}}',
      '@media(max-width:700px){.gtri-scroll-rail{height:3px}.gtri-tilt{transform:none!important}.gtri-orb{right:-18%;top:4%;opacity:.55}.mapHero .mapStage:before,.mapStrip .mapStage:before{animation-duration:9.5s}}',
      '@media(prefers-reduced-motion:reduce){.gtri-scroll-rail{transition:none}.gtri-reveal{opacity:1;transform:none;transition:none}.mapHero:before,.mapStrip:before,.mapHero .mapStage:before,.mapStrip .mapStage:before,.gtri-orb{animation:none}.gtri-surface,.gtri-tilt{transition:none;transform:none!important}.gtri-surface:before{transition:none;opacity:0!important}}'
    ].join('');
    (doc.head || doc.documentElement).appendChild(style);
    var rail = doc.createElement('div');
    rail.className = 'gtri-scroll-rail';
    rail.setAttribute('aria-hidden', 'true');
    (doc.body || doc.documentElement).appendChild(rail);
    var orb = doc.createElement('span');
    orb.className = 'gtri-orb';
    orb.setAttribute('aria-hidden', 'true');
    var mapHero = doc.querySelector('.mapHero,.mapStrip,.hero');
    if (mapHero) { mapHero.appendChild(orb); }
    var reduce = false;
    try { reduce = !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) {}
    var reveal = Array.prototype.slice.call(doc.querySelectorAll('main>header,main>section,main>footer'));
    reveal.forEach(function (el, i) { el.classList.add('gtri-reveal'); el.style.setProperty('--gtri-delay', Math.min(i * 55, 330) + 'ms'); });
    if ('IntersectionObserver' in global && !reduce) {
      var io = new IntersectionObserver(function (entries) { entries.forEach(function (entry) { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); io.unobserve(entry.target); } }); }, { threshold: .08 });
      reveal.forEach(function (el) { io.observe(el); });
    } else { reveal.forEach(function (el) { el.classList.add('is-visible'); }); }
    var surfaces = Array.prototype.slice.call(doc.querySelectorAll('.mapHero,.mapStrip,.hero,.card,.panel,.finding,.method>div,.sourceGrid>div,.boundary,.auditPanel,.notice'));
    var raf = 0, pending = null, active = null, scrollRaf = 0;
    surfaces.forEach(function (el, i) {
      el.classList.add('gtri-surface');
      // mapStage 已有自己的弹簧倾斜；地图外层只做光晕，避免嵌套 perspective 造成放大漂移。
      if (el.matches('.hero')) el.classList.add('gtri-tilt');
      if (el.matches('button,.btn,.pill,.linkBtn,a')) el.classList.add('gtri-press');
      el.addEventListener('pointermove', function (e) { if (e.pointerType === 'touch' || reduce) return; active = el; pending = e; if (!raf) raf = requestAnimationFrame(flushPointer); }, { passive: true });
      el.addEventListener('pointerenter', function (e) { if (e.pointerType !== 'touch') el.classList.add('gtri-hover'); });
      el.addEventListener('pointerleave', function () { el.classList.remove('gtri-hover'); el.style.setProperty('--gtri-x', '50%'); el.style.setProperty('--gtri-y', '50%'); el.style.setProperty('--gtri-rx', '0deg'); el.style.setProperty('--gtri-ry', '0deg'); });
    });
    function flushPointer() {
      raf = 0;
      if (!active || !pending || reduce) return;
      var rect = active.getBoundingClientRect();
      var x = Math.max(0, Math.min(rect.width, pending.clientX - rect.left));
      var y = Math.max(0, Math.min(rect.height, pending.clientY - rect.top));
      active.style.setProperty('--gtri-x', ((x / Math.max(1, rect.width)) * 100).toFixed(2) + '%');
      active.style.setProperty('--gtri-y', ((y / Math.max(1, rect.height)) * 100).toFixed(2) + '%');
      if (active.classList.contains('gtri-tilt')) {
        active.style.setProperty('--gtri-rx', (((y / Math.max(1, rect.height)) - .5) * -3.2).toFixed(2) + 'deg');
        active.style.setProperty('--gtri-ry', (((x / Math.max(1, rect.width)) - .5) * 4.4).toFixed(2) + 'deg');
      }
    }
    function scrollProgress() {
      scrollRaf = 0;
      var max = Math.max(1, doc.documentElement.scrollHeight - global.innerHeight);
      doc.documentElement.style.setProperty('--gtri-progress', ((global.scrollY || 0) / max * 100).toFixed(2) + '%');
    }
    global.addEventListener('scroll', function () { if (!scrollRaf) scrollRaf = requestAnimationFrame(scrollProgress); }, { passive: true });
    scrollProgress();
  }
  function installSupplementalEvidence() {
    var doc = global.document;
    var select = doc && doc.querySelector('#country');
    var timeline = doc && doc.querySelector('#timeline');
    var footer = doc && doc.querySelector('footer.source');
    var rows = global.PANEL;
    if (!select || !timeline || !footer || !Array.isArray(rows)) return;
    var names = { Malaysia: '马来西亚', Vietnam: '越南', Singapore: '新加坡', Thailand: '泰国', India: '印度', Indonesia: '印度尼西亚', Philippines: '菲律宾', Japan: '日本', 'South Korea': '韩国', Mexico: '墨西哥', Germany: '德国', Netherlands: '荷兰' };
    var section = doc.createElement('section');
    section.className = 'sourceLedger';
    section.innerHTML = '<div class="sourceLedger__head"><div><span>ADDITIONAL SOURCES · NOT SCORED</span><h2>把来源、年份和证据边界放在一起</h2><p>当前国家联动显示政策与资本背景。补充数据用于核查和解释，不直接改变GTRI-v0分数。</p></div><b id="ledger-country">—</b></div><div class="sourceLedger__grid"><article><small>P2 · 正式防务安排</small><div id="ledger-p2">—</div><a id="ledger-p2-link" target="_blank" rel="noopener noreferrer" hidden>查看所选官方来源 ↗</a></article><article><small>P3 · BIS人工范围核对</small><div id="ledger-p3">—</div><p>仅限所选候选规则集合；没有命中不表示没有其他法律暴露。</p><a href="https://www.federalregister.gov/" target="_blank" rel="noopener noreferrer">Federal Register ↗</a></article><article><small>IMF CDIS · 投资头寸</small><div id="ledger-cdis">—</div><p>按直接对手方、不同报告方分别记录；非半导体专项，不代表最终所有者。</p><a href="https://data.imf.org/Datasets/DIP" target="_blank" rel="noopener noreferrer">IMF数据说明 ↗</a></article></div>';
    footer.parentNode.insertBefore(section, footer);
    var style = doc.createElement('style');
    style.textContent = '.sourceLedger{margin:0 0 24px;padding:clamp(20px,3vw,34px);border:1px solid rgba(91,174,184,.2);border-radius:20px;background:linear-gradient(120deg,rgba(13,35,45,.96),rgba(8,23,33,.96))}.sourceLedger__head{display:flex;justify-content:space-between;gap:20px;align-items:flex-end;margin-bottom:20px}.sourceLedger__head span,.sourceLedger article small{color:#67d7cd;font:10px ui-monospace,Consolas,monospace;letter-spacing:.14em}.sourceLedger h2{margin:8px 0;font-size:clamp(20px,2.4vw,27px);color:#eaf4f2}.sourceLedger__head p,.sourceLedger article p{max-width:650px;color:#94aeb7;font-size:12px;line-height:1.7}.sourceLedger__head>b{flex:none;color:#d5e7e4;font:12px ui-monospace,Consolas,monospace}.sourceLedger__grid{display:grid;grid-template-columns:.9fr 1fr 1.3fr;border-top:1px solid rgba(138,180,189,.16)}.sourceLedger article{padding:18px 20px 2px 0}.sourceLedger article+article{padding-left:20px;border-left:1px solid rgba(138,180,189,.13)}.sourceLedger article div{margin-top:12px;color:#e9f3f1;font-size:14px;line-height:1.65}.sourceLedger article a{display:inline-block;margin-top:9px;color:#65d8cf;font-size:11px;text-decoration:none}.sourceLedger article a:hover{text-decoration:underline}.sourceLedger__cdis{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:9px}.sourceLedger__cdis span{padding-top:8px;border-top:1px solid rgba(138,180,189,.15);color:#91aab2;font-size:11px}.sourceLedger__cdis b{display:block;margin-top:4px;color:#eef7f5;font-size:13px}@media(max-width:700px){.sourceLedger__grid{grid-template-columns:1fr}.sourceLedger article,.sourceLedger article+article{padding:16px 0 4px;border-left:0;border-top:1px solid rgba(138,180,189,.13)}.sourceLedger__head{display:block}.sourceLedger__head>b{display:inline-block;margin-top:8px}}';
    doc.head.appendChild(style);
    var walker = doc.createTreeWalker(doc.body, global.NodeFilter.SHOW_TEXT);
    var textNode;
    while ((textNode = walker.nextNode())) {
      textNode.nodeValue = textNode.nodeValue
        .replace(/候选规则已做定向人工核对，尚未逐条法律复核/g, '所选10条候选规则已逐条做范围核对；复核集合非穷尽')
        .replace(/尚未完成覆盖全部实体、产品范围和例外条款的逐条法律复核/g, '尚未覆盖全部规则、实体和产品例外的法律审查')
        .replace(/15项数据完整性与计算检查通过/g, '16项数据与计算检查通过');
    }
    var safeNumber = function (value) { return value == null || value === '' || !isFinite(Number(value)) ? '未报告' : (Number(value) < 0 ? '−' : '') + Math.abs(Number(value)).toLocaleString('zh-CN', { maximumFractionDigits: 1 }) + ' 百万美元'; };
    var render = function () {
      var country = select.value;
      var pair = rows.filter(function (row) { return row.country === country; }).sort(function (a, b) { return Number(a.year) - Number(b.year); });
      if (!pair.length) return;
      var base = pair.find(function (row) { return Number(row.year) === 2017; });
      var recent = pair.find(function (row) { return Number(row.year) === 2022; });
      doc.querySelector('#ledger-country').textContent = (names[country] || country) + ' · 2017 / 2022';
      var p2Label = function (row) { return row.p2_oas_adjustment ? 'ATOP原值 ' + row.p2_atop_observed + '，OAS条约状态核验为 ' + row.p2_us_formal_alliance : (Number(row.p2_us_formal_alliance) === 1 ? '识别到正式安排' : '所选来源未识别到'); };
      doc.querySelector('#ledger-p2').textContent = '2017：' + p2Label(base) + '；2022：' + p2Label(recent) + '。来源：ATOP观察值 / 美国国务院条约记录与目标年逐国材料、NATO成员年份，存在口径断点。';
      var p2url = String(recent.p2_evidence_source_url || '').split(';')[0].trim();
      var link = doc.querySelector('#ledger-p2-link');
      if (p2url.indexOf('https://') === 0) { link.href = p2url; link.hidden = false; } else link.hidden = true;
      doc.querySelector('#ledger-p3').textContent = '2022：文本提及 ' + Number(recent.p3_reviewed_candidate_literal_count || 0) + ' 条；经范围核对为直接新增管制 ' + Number(recent.p3_bis_direct_increase_events_reviewed_subset || 0) + ' 条。仅为非穷尽复核集。';
      var year = recent.cdis_observation_year;
      var lag = Number(recent.cdis_observation_lag_years || 0);
      var inward = safeNumber(recent.cdis_sample_country_inward_from_china_usd_millions);
      var outward = safeNumber(recent.cdis_china_outward_position_in_sample_country_usd_millions);
      doc.querySelector('#ledger-cdis').innerHTML = '<b>' + (year || '年份未提供') + '年末' + (lag ? ' · 目标年滞后' + lag + '年' : '') + '</b><div class="sourceLedger__cdis"><span>该经济体报告：来自中国<b>' + inward + '</b></span><span>中国报告：对该经济体<b>' + outward + '</b></span></div>';
    };
    select.addEventListener('change', render);
    render();
  }
  installSupplementalEvidence();
  installPremiumMotion();
})(this);
