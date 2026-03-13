// ═══════════════════════════════════════════════════════
// APP LOGIC — reads SKUS from data.js
// ═══════════════════════════════════════════════════════

var STEPS = 8;
var cur = 1;
var shipMode = 'sea';
var skuIdx = 0;

var defaults = { sea: 120, air: 60, wbuffer: 30, safety: 1.3, deaddays: 30, slowvel: 0.10 };
var state = { ...defaults };
var decisions = {};
var changes = {};
for (var i = 1; i <= 7; i++) decisions[i] = 'pending';

function el(id) { return document.getElementById(id); }
function S() { return SKUS[skuIdx]; }
function tv() { return S().wv + S().ov + S().sv; }
function getLT() { return shipMode === 'sea' ? state.sea : state.air; }
function pct(v, t) { return t > 0 ? Math.round(v / t * 100) : 0; }

// ═══════════════════════════════════════════════════════
// SKU PICKER
// ═══════════════════════════════════════════════════════
function renderPicker() {
  var h = '';
  SKUS.forEach(function(s, i) {
    var oosClass = s.stock <= 0 ? ' oos' : '';
    h += '<div class="sku-pill' + oosClass + (i === skuIdx ? ' active' : '') + '" onclick="switchSKU(' + i + ')">' +
      s.short + '<span class="pill-scenario">' + s.scenario + '</span></div>';
  });
  el('sku-picker').innerHTML = h;
}

function switchSKU(idx) {
  skuIdx = idx;
  renderPicker();
  renderAllSteps();
}

// ═══════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════
function goTo(s) {
  cur = Math.max(1, Math.min(STEPS, s));
  document.querySelectorAll('.step').forEach(function(e) { e.classList.remove('active'); });
  el('step-' + cur).classList.add('active');
  el('btn-back').disabled = cur === 1;
  el('btn-next').textContent = cur === STEPS ? 'Done' : cur === 7 ? 'See Summary' : 'Next';
  el('nav-info').textContent = cur <= 7 ? 'Step ' + cur + ' of 7' : 'Summary';
  renderProgress();
  renderCurrent();
}
function goNext() {
  if (cur <= 7 && decisions[cur] === 'pending') decisions[cur] = 'agreed';
  if (cur < STEPS) goTo(cur + 1);
}
function goBack() { if (cur > 1) goTo(cur - 1); }
function markChanged(s, desc) { decisions[s] = 'changed'; changes[s] = desc; renderProgress(); }

function renderProgress() {
  var h = '';
  for (var i = 1; i <= 7; i++) {
    var c = i === cur ? 'active' : decisions[i] === 'changed' ? 'changed' : decisions[i] === 'agreed' ? 'done' : 'future';
    h += '<div class="progress-dot ' + c + '" onclick="goTo(' + i + ')">' + i + '</div>';
    if (i < 7) h += '<div class="progress-line ' + (decisions[i] !== 'pending' ? 'done' : '') + '"></div>';
  }
  h += '<div class="progress-line"></div><div class="progress-dot ' + (cur === 8 ? 'active' : 'future') + '" onclick="goTo(8)" style="font-size:10px;">&#x2714;</div>';
  el('progress').innerHTML = h;
}

function renderCurrent() {
  if (cur === 1) renderStep1();
  if (cur === 2) renderStep2();
  if (cur === 3) renderStep3();
  if (cur === 4) updateStep4();
  if (cur === 5) updateStep5();
  if (cur === 6) updateStep6();
  if (cur === 7) updateStep7();
  if (cur === 8) renderSummary();
}

function renderAllSteps() {
  renderStep1();
  renderStep2();
  renderCurrent();
}

// ═══════════════════════════════════════════════════════
// STEP 1: Stock on hand
// ═══════════════════════════════════════════════════════
function renderStep1() {
  var s = S();
  var stockColor = s.stock > 0 ? '#4361ee' : '#dc2626';
  var stockLabel = s.stock > 0 ? 'Units in stock' : 'OUT OF STOCK';
  el('s1-sku-card').innerHTML =
    '<div class="sku-name">' + s.name + '</div>' +
    '<div class="sku-brand">' + s.brand + ' &mdash; ' + s.desc + '</div>' +
    '<div class="sku-stats">' +
    '<div class="sku-stat"><div class="ss-val" style="color:' + stockColor + ';">' + s.stock + '</div><div class="ss-label">' + stockLabel + '</div></div>' +
    '<div class="sku-stat"><div class="ss-val">' + s.isd + '</div><div class="ss-label">Active days</div></div>' +
    '<div class="sku-stat"><div class="ss-val">' + s.lastSale + '</div><div class="ss-label">Last sale</div></div>' +
    '</div>' +
    (s.stock <= 0 ? '<div class="callout callout-red" style="margin-top:12px;margin-bottom:0;"><strong>Negative balance (' + s.stock + '):</strong> Tally recorded more units going out than came in. This usually means a stock adjustment is pending, a rename happened, or there are data entry mismatches. We still calculate velocity from active days &mdash; any day with real sales counts, even if the book balance was negative.</div>' : '');

  el('s1-brand-context').innerHTML =
    '<strong>Brand context:</strong> ' + s.brand + ' has ' + s.brandInfo.total + ' SKUs total, ' +
    s.brandInfo.inStock + ' in stock, and ' + s.brandInfo.critical + ' in CRITICAL reorder status right now.';
}

// ═══════════════════════════════════════════════════════
// STEP 2: Velocity & channel classification
// ═══════════════════════════════════════════════════════
function chTag(ch) {
  var map = { wholesale: 'ch-tag-wholesale', online: 'ch-tag-online', store: 'ch-tag-store', supplier: 'ch-tag-supplier', internal: 'ch-tag-internal', excluded: '' };
  var label = ch.charAt(0).toUpperCase() + ch.slice(1);
  if (ch === 'excluded') return '<span style="color:#dc2626;font-size:12px;">Excluded (return)</span>';
  if (ch === 'supplier') return '<span style="color:#6b7280;font-size:12px;">Excluded (inward)</span>';
  if (ch === 'internal') return '<span style="color:#92400e;font-size:12px;">Excluded (internal)</span>';
  return '<span class="ch-tag ' + (map[ch] || '') + '">' + label + '</span>';
}

function renderStep2() {
  var s = S(), v = tv();

  el('s2-lead').innerHTML = 'We measure <strong>velocity</strong> &mdash; the average units sold per day. But we split it by channel because a wholesale bulk order is very different from a single unit sold online.';

  // Channel cards
  el('s2-channels').innerHTML =
    '<div class="channel-card ch-wholesale"><div class="ch-name">Wholesale</div><div class="ch-val">' + s.wv.toFixed(2) + '</div><div class="ch-unit">units/day (' + pct(s.wv, v) + '%)</div></div>' +
    '<div class="channel-card ch-online"><div class="ch-name">Online</div><div class="ch-val">' + s.ov.toFixed(2) + '</div><div class="ch-unit">units/day (' + pct(s.ov, v) + '%)</div></div>' +
    '<div class="channel-card ch-store"><div class="ch-name">Store</div><div class="ch-val">' + (s.sv < 0.01 ? s.sv.toFixed(4) : s.sv.toFixed(2)) + '</div><div class="ch-unit">units/day (' + pct(s.sv, v) + '%)</div></div>';

  // Transaction table
  el('s2-txn-title').textContent = 'Recent transactions for ' + s.short;
  var rows = '';
  s.txns.forEach(function(t) {
    var style = (t.ch === 'excluded' || t.ch === 'supplier' || t.ch === 'internal') ? ' style="background:#fef2f2;"' : '';
    rows += '<tr' + style + '><td>' + t.dt + '</td><td>' + t.vt + '</td><td>' + t.party + '</td><td>' + chTag(t.ch) + '</td><td class="mono">' + t.qty + '</td></tr>';
  });
  el('s2-txn-body').innerHTML = rows;
  el('s2-txn-callout').innerHTML = '<div class="callout callout-amber">' + s.txnCallout + '</div>';

  // Active days viz
  var oos = s.totalDays - s.isd;
  el('s2-isd-text').innerHTML = 'This product was active for <strong>' + s.isd + ' of ' + s.totalDays + ' days</strong>' +
    (oos > 0 ? ' &mdash; it was inactive (no stock and no sales) for ' + oos + ' days.' : ' &mdash; it\'s been active the entire year.') +
    ' If we divided total sales by ' + s.totalDays + ', we\'d ' + (oos > 50 ? 'massively ' : '') + 'undercount how fast it actually sells when available.';

  el('s2-days-viz').innerHTML =
    '<div class="dv-in" style="flex:' + s.isd + ';">' + s.isd + 'd</div>' +
    (oos > 0 ? '<div class="dv-out" style="flex:' + oos + ';">' + oos + 'd</div>' : '');
  el('s2-instock-label').textContent = 'Active: ' + s.isd + ' days';
  el('s2-oos-label').textContent = oos > 0 ? 'Inactive: ' + oos + ' days' : 'Never inactive';

  // Per-channel velocity calcs
  var calcs = '';
  var channels = [
    { key:'ws', name:'Wholesale', demand: s.wsDemand, txns: s.wsTxns, oos: s.wsOOS, vel: s.wv, hdrBg:'#e0e7ff', hdrColor:'#3730a3', ex: s.channelExamples.ws },
    { key:'on', name:'Online', demand: s.onDemand, txns: s.onTxns, oos: s.onOOS, vel: s.ov, hdrBg:'#f3effe', hdrColor:'#5b21b6', ex: s.channelExamples.on },
    { key:'st', name:'Store', demand: s.stDemand, txns: s.stTxns, oos: s.stOOS, vel: s.sv, hdrBg:'#d1fae5', hdrColor:'#065f46', ex: s.channelExamples.st }
  ];
  channels.forEach(function(c) {
    var velStr = c.vel < 0.01 ? c.vel.toFixed(4) : c.vel.toFixed(2);
    calcs += '<div class="channel-calc-block">' +
      '<div class="cc-header" style="background:' + c.hdrBg + ';color:' + c.hdrColor + ';">' + c.name + ' Velocity</div>' +
      '<div class="cc-body">' +
      '<p><strong>Which transactions count?</strong> Only <em>outward</em> sales to ' + c.name.toLowerCase() + ' parties on active days (in stock or with real sales).</p>' +
      '<p>This product had <strong>' + c.txns + ' ' + c.name.toLowerCase() + ' transaction' + (c.txns !== 1 ? 's' : '') + '</strong> this FY. ' +
      c.demand + ' unit' + (c.demand !== 1 ? 's were' : ' was') + ' sold on active days.</p>' +
      '<div class="math-row">' +
      '<div class="math-box"><div class="math-val">' + c.demand + '</div><div class="math-label">' + c.name + ' units<br>(active days)</div></div>' +
      '<div class="math-op">&divide;</div>' +
      '<div class="math-box"><div class="math-val">' + s.isd + '</div><div class="math-label">Active days</div></div>' +
      '<div class="math-op">=</div>' +
      '<div class="math-box result"><div class="math-val">' + velStr + '</div><div class="math-label">units/day</div></div>' +
      '</div>' +
      '<p class="cc-example">' + c.ex + '</p>' +
      '</div></div>';
  });
  el('s2-channel-calcs').innerHTML = calcs;

  // Why add together
  el('s2-why-add-example').innerHTML = s.whyAddExample;

  // Combined math
  el('s2-math').innerHTML =
    '<div class="math-box"><div class="math-val">' + s.wv.toFixed(2) + '</div><div class="math-label">Wholesale</div></div>' +
    '<div class="math-op">+</div>' +
    '<div class="math-box"><div class="math-val">' + s.ov.toFixed(2) + '</div><div class="math-label">Online</div></div>' +
    '<div class="math-op">+</div>' +
    '<div class="math-box"><div class="math-val">' + (s.sv < 0.01 ? s.sv.toFixed(4) : s.sv.toFixed(2)) + '</div><div class="math-label">Store</div></div>' +
    '<div class="math-op">=</div>' +
    '<div class="math-box result"><div class="math-val">' + v.toFixed(2) + '</div><div class="math-label">Total / day</div></div>';

  // Result callout
  var monthly = Math.round(v * 30);
  var dominant = s.wv >= s.ov && s.wv >= s.sv ? 'wholesale' : (s.ov >= s.sv ? 'online' : 'store');
  var domPct = pct(dominant === 'wholesale' ? s.wv : (dominant === 'online' ? s.ov : s.sv), v);
  el('s2-result-callout').innerHTML =
    '<strong>Result:</strong> ' + s.short + ' sells at <strong>' + v.toFixed(2) + ' units/day</strong> on active days (' + monthly + '/month). ' +
    'Primarily ' + dominant + ' (' + domPct + '% of demand), ' +
    'wholesale: ' + s.wv.toFixed(2) + '/day, online: ' + s.ov.toFixed(2) + '/day, store: ' + (s.sv < 0.01 ? s.sv.toFixed(4) : s.sv.toFixed(2)) + '/day.';
}

// ═══════════════════════════════════════════════════════
// STEP 3: Days to stockout
// ═══════════════════════════════════════════════════════
function renderStep3() {
  var s = S(), v = tv();
  var isOOS = s.stock <= 0;
  var dts = isOOS ? 0 : s.stock / v;

  if (isOOS) {
    el('s3-lead').innerHTML = '<strong>' + s.short + '</strong> is already out of stock (balance: ' + s.stock + '). Days to stockout = <strong>0</strong>. But we still know the velocity from its active days.';

    el('s3-math').innerHTML =
      '<div class="math-box" style="background:#fef2f2;"><div class="math-val" style="color:#dc2626;">' + s.stock + '</div><div class="math-label">Stock (negative)</div></div>' +
      '<div class="math-op">&rarr;</div>' +
      '<div class="math-box result" style="background:#dc2626;"><div class="math-val">0</div><div class="math-label">Days left</div></div>';

    el('s3-result').innerHTML =
      '<div class="value" style="color:#dc2626;">ALREADY OUT</div>' +
      '<div class="unit">0 days &mdash; stock is negative</div>' +
      '<div class="sub">Was selling ' + v.toFixed(2) + '/day on active days (' + Math.round(v * 30) + '/month)</div>';

    el('s3-explain').innerHTML =
      '<h3>What happens for out-of-stock items?</h3>' +
      '<p>This product has <strong>0 days of runway</strong> &mdash; it ran out already. But because we tracked its velocity across ' + s.isd + ' active days (' + v.toFixed(2) + '/day), we know exactly how much to reorder.</p>' +
      '<p>The velocity is based on <strong>active-day demand only</strong>. Any day with real sales counts as active, even if the book balance was negative (because if it sold, it was on the shelf). Only truly inactive days (no stock, no sales) are excluded.</p>' +
      '<p class="callout callout-red" style="margin-top:12px;">Of your 22,537 SKUs, <strong>16,039 are currently out of stock</strong>. For each one that has historical velocity, the system still calculates how much to reorder based on past demand.</p>';

    // Draw an empty chart showing "already at zero"
    var canvas = el('s3-chart'), ctx = canvas.getContext('2d');
    var dpr = window.devicePixelRatio || 1, rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr; canvas.height = 180 * dpr; ctx.scale(dpr, dpr);
    var W = rect.width, H = 180;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#fef2f2';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#dc2626';
    ctx.font = 'bold 16px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('Stock is already at ' + s.stock + ' \u2014 no runway to chart', W / 2, H / 2 - 8);
    ctx.fillStyle = '#9ca3af';
    ctx.font = '12px system-ui';
    ctx.fillText('Velocity on active days: ' + v.toFixed(2) + '/day (' + Math.round(v * 30) + '/month)', W / 2, H / 2 + 16);

  } else {
    el('s3-lead').innerHTML = 'With ' + s.stock + ' units in stock and selling ' + v.toFixed(2) + '/day, simple division tells us when we hit zero.';

    el('s3-math').innerHTML =
      '<div class="math-box"><div class="math-val">' + s.stock + '</div><div class="math-label">Stock</div></div>' +
      '<div class="math-op">&divide;</div>' +
      '<div class="math-box"><div class="math-val">' + v.toFixed(2) + '</div><div class="math-label">Velocity</div></div>' +
      '<div class="math-op">=</div>' +
      '<div class="math-box result"><div class="math-val">' + dts.toFixed(1) + '</div><div class="math-label">Days left</div></div>';

    var urgency = dts <= 14 ? 'Less than 2 weeks' : (dts <= 30 ? 'About ' + Math.round(dts / 7) + ' weeks' : (dts <= 90 ? 'About ' + Math.round(dts / 30) + ' months' : 'Over ' + Math.round(dts / 30) + ' months'));
    el('s3-result').innerHTML =
      '<div class="value" style="color:' + (dts <= 30 ? '#dc2626' : (dts <= 120 ? '#d97706' : '#059669')) + ';">' + dts.toFixed(1) + '</div>' +
      '<div class="unit">days until stockout</div><div class="sub">' + urgency + ' from today</div>';

    el('s3-explain').innerHTML =
      '<h3>What this means</h3>' +
      '<p>At the current sell-through rate, <strong>' + s.short + '</strong> will be completely out of stock in about <strong>' + Math.round(dts) + ' days</strong>. ' +
      (dts <= 30 ? 'That\'s urgent &mdash; especially when a sea shipment takes 120 days.' :
       dts <= 150 ? 'There\'s some runway, but you need to plan the next order.' :
       'There\'s plenty of stock for now.') + '</p>' +
      '<p>The chart shows stock declining linearly. In reality it\'s bumpy (a wholesale order of many units one day, then nothing), but the average holds.</p>';

    renderChart3(dts);
  }
}

function renderChart3(dts) {
  var s = S(), v = tv();
  var canvas = el('s3-chart'), ctx = canvas.getContext('2d');
  var dpr = window.devicePixelRatio || 1, rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr; canvas.height = 180 * dpr; ctx.scale(dpr, dpr);
  var W = rect.width, H = 180, pad = { top: 10, right: 20, bottom: 28, left: 45 };
  var cw = W - pad.left - pad.right, ch = H - pad.top - pad.bottom;
  ctx.clearRect(0, 0, W, H);
  var maxD = Math.max(dts * 1.5, 30), maxS = s.stock * 1.15;
  function x(d) { return pad.left + (d / maxD) * cw; }
  function y(q) { return pad.top + ch - (q / maxS) * ch; }
  ctx.strokeStyle = '#f0f1f5'; ctx.lineWidth = 1;
  for (var i = 1; i <= 3; i++) { ctx.beginPath(); ctx.moveTo(pad.left, pad.top + ch / 4 * i); ctx.lineTo(pad.left + cw, pad.top + ch / 4 * i); ctx.stroke(); }
  ctx.beginPath(); ctx.strokeStyle = '#4361ee'; ctx.lineWidth = 3;
  for (var i = 0; i <= 200; i++) { var d = (i / 200) * maxD, st = Math.max(0, s.stock - v * d), px = x(d), py = y(st); i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py); }
  ctx.stroke(); ctx.lineTo(x(maxD), y(0)); ctx.lineTo(x(0), y(0)); ctx.closePath(); ctx.fillStyle = '#4361ee10'; ctx.fill();
  if (dts <= maxD) { ctx.beginPath(); ctx.arc(x(dts), y(0), 6, 0, Math.PI * 2); ctx.fillStyle = '#dc2626'; ctx.fill(); ctx.fillStyle = '#dc2626'; ctx.font = 'bold 11px system-ui'; ctx.textAlign = 'center'; ctx.fillText('Day ' + dts.toFixed(0), x(dts), y(0) - 14); }
  ctx.strokeStyle = '#e2e4ea'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, pad.top + ch); ctx.lineTo(pad.left + cw, pad.top + ch); ctx.stroke();
  ctx.fillStyle = '#9ca3af'; ctx.font = '10px monospace'; ctx.textAlign = 'right';
  for (var i = 0; i <= 4; i++) ctx.fillText(Math.round(maxS / 4 * i), pad.left - 6, y(maxS / 4 * i) + 3);
  ctx.textAlign = 'center'; var ds = Math.ceil(maxD / 5); for (var d = 0; d <= maxD; d += ds) ctx.fillText(d + 'd', x(d), pad.top + ch + 18);
}

// ═══════════════════════════════════════════════════════
// STEP 4: Ship vs Air
// ═══════════════════════════════════════════════════════
function setShipMode(mode) {
  shipMode = mode;
  document.querySelectorAll('.sa-option').forEach(function(e) { e.classList.remove('active-sea', 'active-air'); });
  var opts = document.querySelectorAll('.sa-option');
  if (mode === 'sea') opts[0].classList.add('active-sea');
  else opts[1].classList.add('active-air');
  updateStep4();
}

function updateStep4() {
  var s = S(), v = tv();
  state.sea = +el('s4-sea').value;
  state.air = +el('s4-air').value;
  el('s4-sea-disp').textContent = state.sea;
  el('s4-air-disp').textContent = state.air;
  el('s4-sea-days').textContent = state.sea;
  el('s4-air-days').textContent = state.air;

  el('s4-lead').innerHTML = s.brand + ' products ship internationally. Shipping mode determines how long you wait.';

  var lt = getLT();
  var isOOS = s.stock <= 0;
  var dts = isOOS ? 0 : s.stock / v;
  var maxBar = Math.max(dts, state.sea, 1) * 1.1;

  el('s4-compare').innerHTML =
    '<div class="vis-bar"><div class="vis-bar-label"><span>Stock runway (' + s.short + ')</span><span style="font-weight:700;color:#dc2626;">' + (isOOS ? 'OUT OF STOCK' : dts.toFixed(0) + ' days') + '</span></div><div class="vis-bar-track"><div class="vis-bar-fill" style="width:' + (isOOS ? '0' : Math.min(100, dts / maxBar * 100)) + '%;background:#dc2626;">' + (isOOS ? '' : dts.toFixed(0) + 'd') + '</div></div></div>' +
    '<div class="vis-bar"><div class="vis-bar-label"><span>Sea freight</span><span>' + state.sea + ' days</span></div><div class="vis-bar-track"><div class="vis-bar-fill" style="width:' + Math.min(100, state.sea / maxBar * 100) + '%;background:#4361ee;">' + state.sea + 'd</div></div></div>' +
    '<div class="vis-bar"><div class="vis-bar-label"><span>Air freight</span><span>' + state.air + ' days</span></div><div class="vis-bar-track"><div class="vis-bar-fill" style="width:' + Math.min(100, state.air / maxBar * 100) + '%;background:#d97706;">' + state.air + 'd</div></div></div>';

  var rec;
  if (isOOS) {
    rec = '<strong style="color:#dc2626;">Already out of stock.</strong> Every day without stock is lost sales. At ' + v.toFixed(2) + '/day, you\'re losing ~' + Math.round(v * 30) + ' units/month of potential demand. Order by air (' + state.air + 'd) to minimize the gap. Sea (' + state.sea + 'd) means ' + (state.sea - state.air) + ' more days of zero stock.';
  } else if (dts <= state.air) {
    rec = '<strong style="color:#dc2626;">Even air freight won\'t arrive in time.</strong> Stock will be gone in ' + dts.toFixed(0) + ' days but air takes ' + state.air + '. You\'ll have a gap no matter what. Order by air immediately to minimize the gap.';
  } else if (dts <= state.sea) {
    rec = '<strong style="color:#d97706;">Sea freight won\'t make it, but air will.</strong> Stock lasts ' + dts.toFixed(0) + ' days. Sea takes ' + state.sea + ' (too slow), but air at ' + state.air + ' days would arrive with ' + (dts - state.air).toFixed(0) + ' days to spare. Recommend air freight for this order.';
  } else {
    rec = '<strong style="color:#059669;">Sea freight has time.</strong> Stock lasts ' + dts.toFixed(0) + ' days, plenty of runway for a ' + state.sea + '-day sea shipment. Go with the cheaper option.';
  }
  el('s4-recommendation').innerHTML = rec;

  if (state.sea !== defaults.sea || state.air !== defaults.air) {
    el('s4-ctrl-sea').classList.toggle('changed', state.sea !== defaults.sea);
    el('s4-ctrl-air').classList.toggle('changed', state.air !== defaults.air);
    var desc = [];
    if (state.sea !== defaults.sea) desc.push('Sea: ' + defaults.sea + ' \u2192 ' + state.sea);
    if (state.air !== defaults.air) desc.push('Air: ' + defaults.air + ' \u2192 ' + state.air);
    markChanged(4, desc.join('. '));
  } else {
    el('s4-ctrl-sea').classList.remove('changed');
    el('s4-ctrl-air').classList.remove('changed');
    if (decisions[4] === 'changed') decisions[4] = 'pending';
  }
}

// ═══════════════════════════════════════════════════════
// STEP 5: Reorder status
// ═══════════════════════════════════════════════════════
function updateStep5() {
  var s = S(), v = tv();
  state.wbuffer = +el('s5-wb').value;
  el('s5-wb-disp').textContent = state.wbuffer;
  var lt = getLT();
  var isOOS = s.stock <= 0;
  var dts = isOOS ? 0 : s.stock / v;

  el('s5-lead').innerHTML = isOOS
    ? '<strong>' + s.short + '</strong> is already out of stock. Days to stockout = <strong>0</strong>, which is automatically <strong>CRITICAL</strong> (or worse &mdash; it\'s already happened).'
    : 'We compare days-to-stockout against the lead time. For <strong>' + s.short + '</strong> with <strong>' + dts.toFixed(1) + '</strong> days of stock left:';

  var status;
  if (dts <= lt) status = 'critical';
  else if (dts <= lt + state.wbuffer) status = 'warning';
  else status = 'ok';

  var maxBar = Math.max(dts, lt + state.wbuffer + 20, 1);
  el('s5-bars').innerHTML =
    '<div class="vis-bar"><div class="vis-bar-label"><span>Stock runway</span><span style="font-weight:700;color:#dc2626;">' + (isOOS ? 'OUT OF STOCK' : dts.toFixed(0) + ' days') + '</span></div><div class="vis-bar-track"><div class="vis-bar-fill" style="width:' + (isOOS ? '0' : Math.min(100, dts / maxBar * 100)) + '%;background:' + (status === 'critical' ? '#dc2626' : status === 'warning' ? '#d97706' : '#059669') + ';">' + (isOOS ? '' : dts.toFixed(0) + 'd') + '</div></div></div>' +
    '<div class="vis-bar"><div class="vis-bar-label"><span>Lead time (' + shipMode + ') &mdash; CRITICAL if below</span><span>' + lt + ' days</span></div><div class="vis-bar-track"><div class="vis-bar-fill" style="width:' + Math.min(100, lt / maxBar * 100) + '%;background:#dc2626;opacity:0.6;">' + lt + 'd</div></div></div>' +
    '<div class="vis-bar"><div class="vis-bar-label"><span>Lead + buffer &mdash; WARNING if below</span><span>' + (lt + state.wbuffer) + ' days</span></div><div class="vis-bar-track"><div class="vis-bar-fill" style="width:' + Math.min(100, (lt + state.wbuffer) / maxBar * 100) + '%;background:#d97706;opacity:0.6;">' + (lt + state.wbuffer) + 'd</div></div></div>';

  var labels = { critical: 'Critical', warning: 'Warning', ok: 'OK' };
  var explains = {
    critical: isOOS
      ? 'Already out of stock. You\'re losing ~' + Math.round(v * 30) + ' units/month of potential sales right now. Even air freight takes ' + state.air + ' days &mdash; that\'s ' + Math.round(v * state.air) + ' more units of lost demand before stock arrives.'
      : 'Stock runs out in ' + dts.toFixed(0) + ' days but ' + shipMode + ' freight takes ' + lt + '. You\'ll be out of stock before it arrives.',
    warning: 'Stock lasts ' + dts.toFixed(0) + ' days &mdash; past the ' + lt + '-day lead time but within the ' + (lt + state.wbuffer) + '-day buffer. Plan the order now.',
    ok: 'Stock lasts ' + dts.toFixed(0) + ' days, well beyond ' + (lt + state.wbuffer) + '. No rush.'
  };
  el('s5-status-result').innerHTML = '<div class="status-result sr-' + status + '"><div class="sr-badge">' + labels[status] + '</div><div class="sr-explain">' + explains[status] + '</div></div>';

  el('s5-rules-text').innerHTML =
    'Days to stockout &le; <strong>' + lt + '</strong> (lead time) &rarr; <strong style="color:#dc2626;">CRITICAL</strong><br>' +
    'Days to stockout &le; <strong>' + (lt + state.wbuffer) + '</strong> (lead + ' + state.wbuffer + ' buffer) &rarr; <strong style="color:#d97706;">WARNING</strong><br>' +
    'Days to stockout > <strong>' + (lt + state.wbuffer) + '</strong> &rarr; <strong style="color:#059669;">OK</strong>';

  el('s5-brand-context').innerHTML =
    '<h3>' + s.brand + ' context</h3>' +
    '<p>Across all ' + s.brandInfo.total + ' ' + s.brand + ' SKUs: <strong>' + s.brandInfo.critical + ' are CRITICAL</strong>. ' + s.short + ' is ' +
    (isOOS ? 'already out of stock &mdash; beyond critical.' : status === 'critical' ? 'one of those critical items.' : status === 'warning' ? 'in the warning zone.' : 'currently OK.') + '</p>';

  if (state.wbuffer !== defaults.wbuffer) {
    el('s5-ctrl').classList.add('changed');
    markChanged(5, 'Warning buffer: ' + defaults.wbuffer + ' \u2192 ' + state.wbuffer + ' days');
  } else { el('s5-ctrl').classList.remove('changed'); if (decisions[5] === 'changed') decisions[5] = 'pending'; }
}

// ═══════════════════════════════════════════════════════
// STEP 6: Order quantity
// ═══════════════════════════════════════════════════════
function updateStep6() {
  var s = S(), v = tv();
  state.safety = +el('s6-safety').value;
  el('s6-safety-disp').textContent = state.safety.toFixed(2);
  var safePct = ((state.safety - 1) * 100).toFixed(0);

  // Calculate both options
  var seaLtd = +(v * state.sea).toFixed(1);
  var airLtd = +(v * state.air).toFixed(1);
  var seaQty = Math.round(v * state.sea * state.safety);
  var airQty = Math.round(v * state.air * state.safety);
  var seaSafety = +(seaLtd * (state.safety - 1)).toFixed(1);
  var airSafety = +(airLtd * (state.safety - 1)).toFixed(1);

  var isOOS = s.stock <= 0;
  var dts = isOOS ? 0 : s.stock / v;

  el('s6-lead').innerHTML = isOOS
    ? 'Even though <strong>' + s.short + '</strong> is out of stock, we still calculate order quantity from its historical velocity (' + v.toFixed(2) + '/day). The question is: <strong>ship or air?</strong>'
    : 'For <strong>' + s.short + '</strong> selling at ' + v.toFixed(2) + '/day with ' + s.stock + ' units left, the order size depends entirely on <strong>which shipping mode you choose</strong>.';

  // Formula
  el('s6-formula').innerHTML =
    '<div class="math-box"><div class="math-val">' + v.toFixed(2) + '</div><div class="math-label">Velocity<br>(units/day)</div></div>' +
    '<div class="math-op">&times;</div>' +
    '<div class="math-box"><div class="math-val">?</div><div class="math-label">Lead time<br>(days)</div></div>' +
    '<div class="math-op">&times;</div>' +
    '<div class="math-box"><div class="math-val">' + state.safety.toFixed(2) + '</div><div class="math-label">Safety<br>(+' + safePct + '%)</div></div>' +
    '<div class="math-op">=</div>' +
    '<div class="math-box result"><div class="math-val">?</div><div class="math-label">Order qty</div></div>';
  el('s6-formula-note').textContent = 'The lead time is the only variable \u2014 everything else is the same. Let\u2019s compare:';

  // Determine recommendation
  var rec; // 'sea', 'air', or 'urgent'
  if (isOOS) {
    rec = 'urgent'; // already out, air is always recommended
  } else if (dts < state.air) {
    rec = 'urgent'; // will be OOS before even air arrives
  } else if (dts < state.sea) {
    rec = 'air'; // sea won't make it, air will
  } else {
    rec = 'sea'; // plenty of time, go cheap
  }

  // Side by side cards
  var seaRec = (rec === 'sea') ? ' recommended' : '';
  var airRec = (rec === 'air' || rec === 'urgent') ? ' recommended' : '';

  el('s6-compare').innerHTML =
    '<div class="sac-card sac-sea' + seaRec + '">' +
      (seaRec ? '<div class="sac-inner">' : '') +
      '<div class="sac-mode">By Sea</div>' +
      '<div class="sac-days">' + state.sea + ' days (~' + Math.round(state.sea / 30) + ' months)</div>' +
      '<div class="sac-qty">' + seaQty + '</div>' +
      '<div class="sac-qty-label">units to order</div>' +
      '<div class="sac-breakdown">' +
        v.toFixed(2) + ' &times; ' + state.sea + ' = ' + seaLtd + ' base demand<br>' +
        '+ ' + seaSafety + ' safety buffer (' + safePct + '%)' +
      '</div>' +
      (seaRec ? '</div>' : '') +
    '</div>' +
    '<div class="sac-card sac-air' + airRec + '">' +
      (airRec ? '<div class="sac-inner">' : '') +
      '<div class="sac-mode">By Air</div>' +
      '<div class="sac-days">' + state.air + ' days (~' + Math.round(state.air / 30) + ' months)</div>' +
      '<div class="sac-qty">' + airQty + '</div>' +
      '<div class="sac-qty-label">units to order</div>' +
      '<div class="sac-breakdown">' +
        v.toFixed(2) + ' &times; ' + state.air + ' = ' + airLtd + ' base demand<br>' +
        '+ ' + airSafety + ' safety buffer (' + safePct + '%)' +
      '</div>' +
      (airRec ? '</div>' : '') +
    '</div>';

  // Recommendation box
  var diffQty = seaQty - airQty;
  var recHtml;
  if (rec === 'urgent') {
    var lostPerMonth = Math.round(v * 30);
    recHtml = '<div class="rec-box rec-urgent">' +
      '<h4>Recommendation: Order by Air (urgent)</h4>' +
      '<p>' + (isOOS
        ? 'This product is <strong>already out of stock</strong>. Every day without inventory means ~' + v.toFixed(1) + ' units of lost sales (' + lostPerMonth + '/month).'
        : 'Stock runs out in <strong>' + dts.toFixed(0) + ' days</strong> &mdash; even air freight (' + state.air + 'd) won\'t arrive before that.') + '</p>' +
      '<p>Air gets ' + airQty + ' units here in ' + state.air + ' days. Sea would take ' + state.sea + ' &mdash; that\'s <strong>' + (state.sea - state.air) + ' extra days</strong> of empty shelves.</p>' +
      '<p>Yes, air is more expensive per unit, but the cost of ' + (state.sea - state.air) + ' days of lost sales (' + Math.round(v * (state.sea - state.air)) + ' units at current velocity) almost certainly outweighs the freight premium.</p>' +
      '</div>';
  } else if (rec === 'air') {
    recHtml = '<div class="rec-box rec-air">' +
      '<h4>Recommendation: Order by Air</h4>' +
      '<p>Stock lasts <strong>' + dts.toFixed(0) + ' days</strong>, but sea freight takes <strong>' + state.sea + '</strong>. You\'d be out of stock for ~' + Math.round(dts - state.sea < 0 ? Math.abs(dts - state.sea) : 0) + ' days waiting.' + (dts < state.sea ? ' That\'s ' + Math.round(v * (state.sea - dts)) + ' units of lost demand.' : '') + '</p>' +
      '<p>Air freight (' + state.air + 'd) arrives with <strong>' + Math.round(dts - state.air) + ' days to spare</strong>. You\'d order ' + airQty + ' units instead of ' + seaQty + ' &mdash; ' + diffQty + ' fewer units, smaller cash outlay, and no stockout gap.</p>' +
      '</div>';
  } else {
    recHtml = '<div class="rec-box rec-sea">' +
      '<h4>Recommendation: Order by Sea (cheaper)</h4>' +
      '<p>Stock lasts <strong>' + dts.toFixed(0) + ' days</strong>, well past the <strong>' + state.sea + '-day</strong> sea freight window. The shipment arrives with ~' + Math.round(dts - state.sea) + ' days of stock still in hand.</p>' +
      '<p>Order ' + seaQty + ' units by sea. You\'ll need ' + diffQty + ' more units than air (' + airQty + ') because you\'re covering a longer lead time, but sea freight is significantly cheaper per unit.</p>' +
      '<p style="font-size:12px;color:#6b7280;">If the situation changes and stock drops faster than expected, you can always switch to air for an emergency top-up.</p>' +
      '</div>';
  }
  el('s6-recommendation').innerHTML = recHtml;

  if (state.safety !== defaults.safety) {
    el('s6-ctrl').classList.add('changed');
    markChanged(6, 'Safety multiplier: ' + defaults.safety + 'x \u2192 ' + state.safety.toFixed(2) + 'x (' + safePct + '% buffer)');
  } else { el('s6-ctrl').classList.remove('changed'); if (decisions[6] === 'changed') decisions[6] = 'pending'; }
}

// ═══════════════════════════════════════════════════════
// STEP 7: Dead stock / slow movers
// ═══════════════════════════════════════════════════════
function updateStep7() {
  state.deaddays = +el('s7-dead').value;
  state.slowvel = +el('s7-slow').value;
  el('s7-dead-disp').textContent = state.deaddays;
  el('s7-dead-threshold-inline').textContent = state.deaddays;
  el('s7-slow-disp').textContent = state.slowvel.toFixed(2);
  el('s7-slow-threshold-inline').textContent = state.slowvel.toFixed(2);
  el('s7-slow-monthly').textContent = Math.round(state.slowvel * 30);

  var dc = state.deaddays !== defaults.deaddays, sc = state.slowvel !== defaults.slowvel;
  el('s7-ctrl-dead').classList.toggle('changed', dc);
  el('s7-ctrl-slow').classList.toggle('changed', sc);
  if (dc || sc) {
    var d = [];
    if (dc) d.push('Dead stock: ' + defaults.deaddays + ' \u2192 ' + state.deaddays + ' days');
    if (sc) d.push('Slow mover: ' + defaults.slowvel + ' \u2192 ' + state.slowvel.toFixed(2) + '/day');
    markChanged(7, d.join('. '));
  } else if (decisions[7] === 'changed') decisions[7] = 'pending';
}

// ═══════════════════════════════════════════════════════
// SUMMARY
// ═══════════════════════════════════════════════════════
function renderSummary() {
  var s = S(), v = tv();
  el('s8-lead').innerHTML = 'Reviewed with <strong>' + s.name + '</strong> as the example. Copy the change spec below and share it with the team.';

  var names = ['', 'Stock Source', 'Velocity & Channel Classification', 'Days to Stockout', 'Supplier Lead Time (Sea vs Air)', 'Reorder Status Thresholds', 'Order Quantity Formula', 'Dead Stock & Slow Movers'];
  var descs = ['',
    'Closing balance from Tally. Example: ' + s.name + ' = ' + s.stock + ' units' + (s.stock <= 0 ? ' (OUT OF STOCK).' : '.'),
    'Sales by channel (W:' + s.wv.toFixed(2) + ' O:' + s.ov.toFixed(2) + ' S:' + (s.sv < 0.01 ? s.sv.toFixed(4) : s.sv.toFixed(2)) + '), active days only (' + s.isd + '/' + s.totalDays + '). Parties classified by 5-priority rules.',
    (s.stock <= 0 ? 'OUT OF STOCK (0 days). Velocity from active days: ' + v.toFixed(2) + '/day.' : 'Stock \u00f7 Velocity = ' + (s.stock / v).toFixed(1) + ' days.'),
    'Sea: ' + state.sea + 'd, Air: ' + state.air + 'd. Ship mode: ' + shipMode + ' (' + getLT() + 'd).',
    'CRITICAL \u2264 ' + getLT() + 'd, WARNING \u2264 ' + (getLT() + state.wbuffer) + 'd, OK > ' + (getLT() + state.wbuffer) + 'd.',
    'Sea: ' + v.toFixed(2) + ' \u00d7 ' + state.sea + ' \u00d7 ' + state.safety.toFixed(2) + 'x = ' + Math.round(v * state.sea * state.safety) + ' units. Air: ' + v.toFixed(2) + ' \u00d7 ' + state.air + ' \u00d7 ' + state.safety.toFixed(2) + 'x = ' + Math.round(v * state.air * state.safety) + ' units.',
    'Dead stock: >' + state.deaddays + 'd no sale. Slow mover: <' + state.slowvel.toFixed(2) + '/day.'
  ];
  var h = '';
  for (var i = 1; i <= 7; i++) {
    var d = decisions[i], cls = d === 'changed' ? 'sh-changed' : 'sh-agreed', txt = d === 'changed' ? 'Wants Change' : d === 'agreed' ? 'Agreed' : 'Not Reviewed';
    h += '<div class="summary-card"><div class="summary-header"><span>Step ' + i + ': ' + names[i] + '</span><span class="sh-status ' + cls + '">' + txt + '</span></div><div class="summary-body">' + descs[i] + (d === 'changed' && changes[i] ? '<div class="summary-change">' + changes[i] + '</div>' : '') + '</div></div>';
  }
  el('summary-cards').innerHTML = h;

  var spec = 'REORDER LOGIC REVIEW \u2014 CHANGE SPECIFICATION\n';
  spec += 'Example SKUs reviewed: ' + SKUS.map(function(sk) { return sk.short; }).join(', ') + '\n';
  spec += 'Primary example: ' + s.name + ' (' + s.brand + ')\n';
  spec += '=============================================\n\n';
  var any = false;
  for (var i = 1; i <= 7; i++) { if (decisions[i] === 'changed') { any = true; spec += 'CHANGE: Step ' + i + ' \u2014 ' + names[i] + '\n  ' + changes[i] + '\n\n'; } }
  if (!any) spec += 'No changes requested. All steps approved as-is.\n\n';
  spec += 'CURRENT CONFIGURATION\n---------------------\n';
  spec += 'Shipping mode:        ' + shipMode + '\n';
  spec += 'Sea lead time:        ' + state.sea + ' days \u2192 order ' + Math.round(v * state.sea * state.safety) + ' units\n';
  spec += 'Air lead time:        ' + state.air + ' days \u2192 order ' + Math.round(v * state.air * state.safety) + ' units\n';
  spec += 'Warning buffer:       ' + state.wbuffer + ' days\n';
  spec += 'Safety multiplier:    ' + state.safety.toFixed(2) + 'x (' + ((state.safety - 1) * 100).toFixed(0) + '% buffer)\n';
  spec += 'Dead stock threshold: ' + state.deaddays + ' days\n';
  spec += 'Slow mover threshold: ' + state.slowvel.toFixed(2) + '/day (~' + Math.round(state.slowvel * 30) + '/month)\n';
  el('spec-text').textContent = spec;
}

function copySpec() {
  navigator.clipboard.writeText(el('spec-text').textContent).then(function() {
    el('copy-btn').textContent = 'Copied!'; setTimeout(function() { el('copy-btn').textContent = 'Copy to clipboard'; }, 1500);
  });
}

// ═══════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════
renderPicker();
goTo(1);
window.addEventListener('resize', function() { if (cur === 3) renderStep3(); });
