/* 芯链哨兵 · 共享世界点阵地图渲染器 v1.0
 *
 * 依赖：assets/dotmap-data.js（window.DOTMAP）
 * 页面数据：可选依赖全局 D（核心面板数组，字段 year / country / n2_... / n3_... / n4_...）
 *
 * 用法：
 *   var map = createDotMap({
 *     canvas: document.getElementById('flowMap'),
 *     stage:  document.querySelector('.mapStage'),   // 可选，默认取 canvas.parentElement
 *     mode:   'all' | 'focus',                       // all=12 节点并列；focus=仅高亮当前经济体
 *     tip:    document.getElementById('mapTip'),     // 可选，左下角提示条
 *     card:   document.getElementById('mapCard'),    // 可选，悬停数据卡片
 *     highlight: 'Mexico',                           // 可选，初始高亮
 *     onHover: function(node|null){}                 // 可选，悬停回调
 *   });
 *   map.setHighlight('Vietnam');   // 切换高亮（all 模式加双圈+青色标签；focus 模式切换唯一节点）
 *   map.setYear(2017);             // 切换年份（重取 D 中的数值并重算半径）
 *   map.refresh();                 // 重取 D 中的数值并重绘
 *   map.resize();                  // 手动重算尺寸（一般 resize 事件已自动处理）
 *   map.destroy();                 // 停止动画
 *
 * 合规约定（勿改）：底图为示意性点阵图形，不含国界线、不标国名，
 * 不作为国界依据；中国领土（含台湾及南海诸岛）完整呈现。
 */
(function (global) {
  'use strict';

  var TOK = {
    land: 'rgba(122,152,168,.34)',
    cyanRGB: '62,214,197',
    hotRGB: '255,107,95',
    cyan: '#3ed6c5',
    hot: '#ff6b5f',
    halo: 'rgba(5,13,19,.88)',
    label: 'rgba(229,243,243,.96)'
  };

  /* 位打包点阵 -> 归一化坐标数组 */
  function decode(dm) {
    var dots = new Float32Array(dm.cols * dm.rows * 2), n = 0, r, c, k, b, bin, h;
    for (r = 0; r < dm.rows; r++) {
      bin = ''; h = dm.rowsHex[r];
      for (k = 0; k < h.length; k++) {
        b = parseInt(h.charAt(k), 16).toString(2);
        while (b.length < 4) b = '0' + b;
        bin += b;
      }
      for (c = 0; c < dm.cols; c++) {
        if (bin.charAt(c) === '1') { dots[n++] = (c + 0.5) / dm.cols; dots[n++] = (r + 0.5) / dm.rows; }
      }
    }
    return { arr: dots, len: n / 2 };
  }

  /* 从全局 D 取某年的国家数值 */
  function valuesOf(year) {
    var m = {};
    try {
      if (typeof D !== 'undefined') {
        D.forEach(function (x) { if (+x.year === +year) m[x.country] = x; });
      }
    } catch (e) { /* 页面无 D 时保持空值，卡片显示 — */ }
    return m;
  }

  global.createDotMap = function (o) {
    var dm = o.data || global.DOTMAP, cv = o.canvas;
    if (!cv || !dm) { return null; }
    var stage = o.stage || cv.parentElement;
    var ctx = cv.getContext('2d');
    var tip = o.tip || null, card = o.card || null;
    var mode = o.mode || 'all', year = +o.year || 2022;
    var showLabels = o.showLabels !== false;
    var dec = decode(dm), dots = dec.arr, ND = dec.len;

    var nodes = dm.nodes.map(function (n) { return { n: n.n, x: n.x, y: n.y }; });
    var order = [], rank = {};

    /* 取数 -> 半径（按 N4 排名，而非绝对值） */
    function applyValues() {
      var V = o.values || valuesOf(year);
      nodes.forEach(function (nd) {
        var v = V[nd.n] || {};
        nd.n2 = v.n2_china_hs8542_import_share;
        nd.n3 = v.n3_us_hs8542_export_share;
        nd.n4 = v.n4_dual_dependency;
      });
      order = nodes.slice().sort(function (a, b) { return (b.n4 || 0) - (a.n4 || 0); });
      rank = {};
      order.forEach(function (nd, i) { rank[nd.n] = i; });
      var span = nodes.length > 1 ? nodes.length - 1 : 1;
      nodes.forEach(function (nd) { nd.r = 3.1 + (1 - (rank[nd.n] || 0) / span) * 4.1; });
    }
    applyValues();

    var active = o.highlight || null;
    var LF = 1, FONT = '', dpr = 1, W = 0, H = 0, S = 1, OX = 0, OY = 0, SP = 1;
    var labels = [], mouse = { x: -1, y: -1, on: false }, hover = null, t0 = 0, raf = 0;

    var base = document.createElement('canvas'), bctx = base.getContext('2d');
    function pxf(u) { return OX + u * dm.mapW * S; }
    function pyf(v) { return OY + v * dm.mapH * S; }

    function buildBase() {
      base.width = cv.width; base.height = cv.height;
      bctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      bctx.clearRect(0, 0, W, H);
      var rad = Math.max(0.95, Math.min(2.0, SP * 0.4));
      bctx.fillStyle = TOK.land;
      for (var i = 0; i < ND; i++) {
        bctx.beginPath(); bctx.arc(pxf(dots[i * 2]), pyf(dots[i * 2 + 1]), rad, 0, 6.2832); bctx.fill();
      }
    }

    /* 标签候选方位：右 / 左 / 上 / 下 / 斜向，由近及远 */
    var CAND = [[13, -9, 'left'], [13, 9, 'left'], [-13, -9, 'right'], [-13, 9, 'right'], [0, -17, 'center'],
                [0, 21, 'center'], [16, -20, 'left'], [-16, -20, 'right'], [16, 25, 'left'], [-16, 25, 'right'],
                [27, -5, 'left'], [-27, -5, 'right'], [30, 16, 'left'], [-30, 16, 'right']];

    function labelTargets() {
      if (mode === 'focus') {
        return active ? nodes.filter(function (n) { return n.n === active; }) : [];
      }
      return nodes;
    }

    /* 贪心避让：放不下就不画 */
    function layoutLabels() {
      labels = [];
      if (!showLabels) { return; }
      ctx.font = FONT;
      var boxes = [], targets = labelTargets();
      /* 选中经济体优先占位，避免被邻近标签挤掉 */
      if (mode !== 'focus' && active) {
        targets = targets.slice().sort(function (a, b) {
          return (b.n === active ? 1 : 0) - (a.n === active ? 1 : 0);
        });
      }
      for (var i = 0; i < targets.length; i++) {
        var nd = targets[i], x = pxf(nd.x), y = pyf(nd.y);
        var w = ctx.measureText(nd.n).width + 2 * LF, best = null;
        for (var k = 0; k < CAND.length; k++) {
          var ca = CAND[k], tx = x + ca[0] * LF, ty = y + ca[1] * LF;
          var x0 = ca[2] === 'left' ? tx : ca[2] === 'right' ? tx - w : tx - w / 2;
          var y0 = ty - 9 * LF, x1 = x0 + w, y1 = ty + 4 * LF;
          if (x0 < 3 || x1 > W - 3 || y0 < 3 || y1 > H - 3) continue;
          var ok = true;
          for (var m = 0; m < boxes.length; m++) {
            var B = boxes[m];
            if (x0 < B[2] && x1 > B[0] && y0 < B[3] && y1 > B[1]) { ok = false; break; }
          }
          if (ok) { best = { node: nd, tx: tx, ty: ty, anchor: ca[2], dx: ca[0], dy: ca[1], x0: x0, y0: y0, x1: x1, y1: y1 }; break; }
        }
        if (best) { boxes.push([best.x0, best.y0, best.x1, best.y1]); labels.push(best); }
      }
    }

    function fit() {
      if (o.autoHeight !== false && window.innerWidth <= 800) {
        var w0 = stage.clientWidth || stage.getBoundingClientRect().width;
        stage.style.height = Math.max(196, Math.round(w0 / dm.mapW * dm.mapH * (o.heightFactor || 1.52))) + 'px';
      } else if (o.autoHeight !== false) {
        stage.style.height = '';
      }
      var rect = stage.getBoundingClientRect();
      dpr = window.devicePixelRatio || 1;
      W = rect.width; H = rect.height;
      if (W < 40 || H < 40) { return; }
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      S = Math.min(W / dm.mapW, H / dm.mapH) * 0.965;
      OX = (W - dm.mapW * S) / 2; OY = (H - dm.mapH * S) / 2;
      SP = dm.mapW * S / dm.cols;
      LF = W < 560 ? 0.78 : 1;
      FONT = '600 ' + (11.5 * LF).toFixed(1) + "px Inter,'Noto Sans SC',Arial,sans-serif";
      buildBase(); layoutLabels();
    }

    function updateCard() {
      if (!card) { return; }
      if (!hover) { card.className = 'mapCard'; return; }
      var v = hover,
          pct = function (x) { return x == null ? '—' : (x * 100).toFixed(1) + '%'; },
          num = function (x) { return x == null ? '—' : x.toFixed(4); },
          hot = (v.n4 || 0) >= 0.05;
      card.innerHTML = '<b>' + v.n + '</b>' +
        '<div class="row"><span>N2 对华进口依赖</span><em>' + pct(v.n2) + '</em></div>' +
        '<div class="row"><span>N3 对美出口依赖</span><em>' + pct(v.n3) + '</em></div>' +
        '<div class="row"><span>N4 双重依赖</span><em class="' + (hot ? 'hot' : '') + '">' + num(v.n4) + '</em></div>' +
        '<span class="flag">' + (hot
          ? '夹层暴露显著：需同步核查中国投入与美国终端客户'
          : '结构暴露较低，仍需结合企业自身供应商与客户网络判断') + '</span>';
      card.className = 'mapCard on';
      var x = pxf(v.x), y = pyf(v.y);
      card.style.left = Math.max(8, Math.min(W - 198, x + 18)) + 'px';
      card.style.top = Math.max(8, Math.min(H - 124, y - 16)) + 'px';
    }

    function frame(now) {
      var t = (now - t0) / 1000, i, k;
      ctx.clearRect(0, 0, W, H);
      ctx.drawImage(base, 0, 0, W, H);

      /* 鼠标跟随光晕：半径内的点逐个提亮并偏青 */
      if (mouse.on) {
        var R = Math.max(78, S * 0.95);
        ctx.globalCompositeOperation = 'lighter';
        var g = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, R);
        g.addColorStop(0, 'rgba(' + TOK.cyanRGB + ',.20)');
        g.addColorStop(.5, 'rgba(' + TOK.cyanRGB + ',.07)');
        g.addColorStop(1, 'rgba(' + TOK.cyanRGB + ',0)');
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(mouse.x, mouse.y, R, 0, 6.2832); ctx.fill();
        ctx.globalCompositeOperation = 'source-over';
        for (i = 0; i < ND; i++) {
          var x = pxf(dots[i * 2]), y = pyf(dots[i * 2 + 1]), dx = x - mouse.x, dy = y - mouse.y, d2 = dx * dx + dy * dy;
          if (d2 > R * R) continue;
          var q = 1 - Math.sqrt(d2) / R;
          ctx.globalAlpha = Math.min(.95, .32 + q * 1.2);
          ctx.fillStyle = 'rgb(' + Math.round(122 - 60 * q) + ',' + Math.round(152 + 62 * q) + ',' + Math.round(168 + 29 * q) + ')';
          ctx.beginPath(); ctx.arc(x, y, SP * 0.52 * (1 + q * 0.85), 0, 6.2832); ctx.fill();
        }
        ctx.globalAlpha = 1;
        for (i = 0; i < nodes.length; i++) {
          var o2 = nodes[i], nx = pxf(o2.x), ny = pyf(o2.y),
              ex = nx - mouse.x, ey = ny - mouse.y, ed = Math.sqrt(ex * ex + ey * ey);
          if (ed > 330) continue;
          ctx.strokeStyle = 'rgba(' + TOK.cyanRGB + ',' + (0.4 * (1 - ed / 330)).toFixed(3) + ')';
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(mouse.x, mouse.y); ctx.lineTo(nx, ny); ctx.stroke();
        }
      }

      /* 节点 */
      for (i = 0; i < nodes.length; i++) {
        var nd = nodes[i], ax = pxf(nd.x), ay = pyf(nd.y);
        var isFocus = mode === 'focus';
        var on = !isFocus || nd.n === active;
        var hot = (nd.n4 || 0) >= 0.05;
        var cs = isFocus ? TOK.cyanRGB : (hot ? TOK.hotRGB : TOK.cyanRGB);

        if (!on) {   /* 非焦点节点：小暗点 */
          ctx.fillStyle = 'rgba(120,160,175,.55)';
          ctx.beginPath(); ctx.arc(ax, ay, 2.1, 0, 6.2832); ctx.fill();
          continue;
        }
        for (k = 0; k < 2; k++) {
          var ph = ((t * 0.5 + k * 0.5) % 1), rr = 6 + ph * (nd.r + 17);
          ctx.strokeStyle = 'rgba(' + cs + ',' + (0.38 * (1 - ph)).toFixed(3) + ')';
          ctx.lineWidth = 1.4;
          ctx.beginPath(); ctx.arc(ax, ay, rr, 0, 6.2832); ctx.stroke();
        }
        var g2 = ctx.createRadialGradient(ax, ay, 0, ax, ay, nd.r * 4.6);
        g2.addColorStop(0, 'rgba(' + cs + ',.5)');
        g2.addColorStop(1, 'rgba(' + cs + ',0)');
        ctx.fillStyle = g2;
        ctx.beginPath(); ctx.arc(ax, ay, nd.r * 4.6, 0, 6.2832); ctx.fill();
        ctx.fillStyle = hot && !isFocus ? TOK.hot : TOK.cyan;
        ctx.beginPath(); ctx.arc(ax, ay, isFocus ? nd.r + 0.8 : nd.r, 0, 6.2832); ctx.fill();
        ctx.strokeStyle = 'rgba(238,247,247,.85)'; ctx.lineWidth = 1; ctx.stroke();

        /* all 模式下，被选中的经济体加双圈指示 */
        if (!isFocus && nd.n === active) {
          ctx.strokeStyle = 'rgba(255,255,255,.95)'; ctx.lineWidth = 1.7;
          ctx.beginPath(); ctx.arc(ax, ay, nd.r + 6.5, 0, 6.2832); ctx.stroke();
          ctx.strokeStyle = 'rgba(' + cs + ',.45)'; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.arc(ax, ay, nd.r + 11, 0, 6.2832); ctx.stroke();
        }
      }

      /* 标签（选中项最后画，压在其它标签之上） */
      ctx.font = FONT;
      var drawOrder = labels;
      if (mode !== 'focus' && active) {
        drawOrder = labels.slice().sort(function (a, b) {
          return (a.node.n === active ? 1 : 0) - (b.node.n === active ? 1 : 0);
        });
      }
      for (i = 0; i < drawOrder.length; i++) {
        var lb = drawOrder[i], nn = lb.node, bx = pxf(nn.x), by = pyf(nn.y);
        if (Math.abs(lb.dx) > 17 * LF || Math.abs(lb.dy) > 13 * LF) {
          ctx.strokeStyle = 'rgba(146,186,198,.30)'; ctx.lineWidth = .8;
          ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(lb.tx, lb.ty); ctx.stroke();
        }
        ctx.textAlign = lb.anchor === 'right' ? 'right' : lb.anchor === 'center' ? 'center' : 'left';
        ctx.lineWidth = 3.2; ctx.strokeStyle = TOK.halo;
        ctx.strokeText(nn.n, lb.tx, lb.ty);
        ctx.fillStyle = (mode !== 'focus' && nn.n === active) ? TOK.cyan : TOK.label;
        ctx.fillText(nn.n, lb.tx, lb.ty);
      }
      ctx.textAlign = 'left';

      /* 命中检测 */
      if (mouse.on && (card || o.onHover)) {
        var best = 24 * 24, found = null;
        for (i = 0; i < nodes.length; i++) {
          var no = nodes[i];
          if (mode === 'focus' && no.n !== active) continue;
          var dx2 = pxf(no.x) - mouse.x, dy2 = pyf(no.y) - mouse.y, dd = dx2 * dx2 + dy2 * dy2;
          if (dd < best) { best = dd; found = no; }
        }
        if (found !== hover) {
          hover = found;
          updateCard();
          if (o.onHover) { o.onHover(found); }
        }
      }
      raf = requestAnimationFrame(frame);
    }

    function bind() {
      stage.addEventListener('mousemove', function (e) {
        var rc = stage.getBoundingClientRect();
        mouse.x = e.clientX - rc.left; mouse.y = e.clientY - rc.top; mouse.on = true;
        if (tip) { tip.textContent = '光晕随指针移动 · 靠近节点查看数值'; }
      });
      stage.addEventListener('touchmove', function (e) {
        var rc = stage.getBoundingClientRect(), tp = e.touches[0];
        mouse.x = tp.clientX - rc.left; mouse.y = tp.clientY - rc.top; mouse.on = true;
        if (tip) { tip.textContent = '光晕随指针移动 · 靠近节点查看数值'; }
      }, { passive: true });
      stage.addEventListener('mouseleave', function () {
        mouse.on = false; mouse.x = -1; mouse.y = -1;
        if (tip) { tip.textContent = o.tipIdle || '移动鼠标探索风险节点'; }
        if (hover) { hover = null; updateCard(); if (o.onHover) { o.onHover(null); } }
      });
      window.addEventListener('resize', fit);
    }

    fit();
    bind();
    t0 = (global.performance || Date).now();
    raf = requestAnimationFrame(frame);

    return {
      setHighlight: function (name) {
        active = name;
        layoutLabels();
        return active;
      },
      getHighlight: function () { return active; },
      getYear: function () { return year; },
      setYear: function (y) {
        if (y == null || isNaN(+y)) { return year; }
        year = +y; applyValues(); layoutLabels();
        return year;
      },
      refresh: function () { applyValues(); layoutLabels(); },
      resize: fit,
      destroy: function () { cancelAnimationFrame(raf); }
    };
  };
})(this);
