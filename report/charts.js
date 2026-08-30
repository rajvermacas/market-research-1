(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const el = (n, a) => { const e = document.createElementNS(NS, n); for (const k in a || {}) e.setAttribute(k, a[k]); return e; };
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const usd = (v) => (v < 0 ? "−$" : "$") + Math.round(Math.abs(v)).toLocaleString();
  const usdK = (v) => (v < 0 ? "−$" : "$") + Math.round(Math.abs(v) / 1000) + "K";
  const pct = (v) => (v < 0 ? "−" : "") + Math.abs(v).toFixed(1) + "%";
  const ym = (s) => { const [y, m] = s.split("-").map(Number); return y + (m - 1) / 12; };

  function frame(host, h, pad) {
    host.innerHTML = "";
    const W = 900;
    const svg = el("svg", { class: "chart", viewBox: `0 0 ${W} ${h}`, preserveAspectRatio: "none", role: "img" });
    host.appendChild(svg);
    const tip = document.createElement("div");
    tip.className = "tip";
    host.appendChild(tip);
    return { svg, W, H: h, p: pad, tip };
  }

  function showTip(f, host, px, py, html) {
    f.tip.innerHTML = html;
    f.tip.style.opacity = "1";
    const hw = host.clientWidth, r = f.tip.offsetWidth, hh = f.tip.offsetHeight;
    const sx = hw / f.W, sy = host.clientHeight / f.H;
    let x = px * sx + 14, y = py * sy - hh - 12;
    if (x + r > hw - 4) x = px * sx - r - 14;
    if (x < 4) x = 4;
    if (y < 4) y = py * sy + 16;
    f.tip.style.left = x + "px";
    f.tip.style.top = y + "px";
  }
  const hideTip = (f) => { f.tip.style.opacity = "0"; };

  /* Round a raw [lo,hi] out to a domain whose ticks land on 1/2/2.5/5 x 10^n. */
  function niceScale(lo, hi, target) {
    const n = target || 5;
    const span = (hi - lo) || Math.abs(hi) || 1;
    const raw = span / n;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw - 1e-9) || 10 * mag;
    const y0 = Math.floor(lo / step) * step;
    const y1 = Math.ceil(hi / step) * step;
    const ticks = [];
    for (let v = y0; v <= y1 + step / 2; v += step) ticks.push(Math.abs(v) < step / 1e6 ? 0 : v);
    return { y0: y0, y1: y1, ticks: ticks };
  }

  function yAxis(f, g, sc, fmt) {
    sc.ticks.forEach((v) => {
      const y = f.p.t + (f.H - f.p.t - f.p.b) * (1 - (v - sc.y0) / (sc.y1 - sc.y0));
      g.appendChild(el("line", { class: "gridline", x1: f.p.l, x2: f.W - f.p.r, y1: y, y2: y }));
      const t = el("text", { class: "tick", x: f.p.l - 9, y: y + 3.5, "text-anchor": "end" });
      t.textContent = fmt(v);
      g.appendChild(t);
    });
  }

  /* ---------- line chart: strategy vs buy & hold ---------- */
  function lineChart(hostId, series) {
    const host = document.getElementById(hostId);
    const f = frame(host, 330, { l: 58, r: 74, t: 16, b: 30 });
    const g = el("g"); f.svg.appendChild(g);
    const all = series.flatMap((s) => s.pts);
    const x0 = Math.min(...all.map((p) => ym(p.d))), x1 = Math.max(...all.map((p) => ym(p.d)));
    const sc = niceScale(0, Math.max(...all.map((p) => p.v)), 5);
    const y0 = sc.y0, y1 = sc.y1;
    const X = (d) => f.p.l + (f.W - f.p.l - f.p.r) * ((ym(d) - x0) / (x1 - x0));
    const Y = (v) => f.p.t + (f.H - f.p.t - f.p.b) * (1 - (v - y0) / (y1 - y0));

    yAxis(f, g, sc, (v) => (v === 0 ? "$0" : usdK(v)));
    for (let yr = 2010; yr <= 2026; yr += 2) {
      const x = X(yr + "-01");
      const t = el("text", { class: "tick", x: x, y: f.H - f.p.b + 17, "text-anchor": "middle" });
      t.textContent = yr;
      g.appendChild(t);
    }
    g.appendChild(el("line", { class: "axisline", x1: f.p.l, x2: f.W - f.p.r, y1: Y(0), y2: Y(0) }));

    series.forEach((s) => {
      const d = s.pts.map((p, i) => (i ? "L" : "M") + X(p.d).toFixed(1) + " " + Y(p.v).toFixed(1)).join(" ");
      g.appendChild(el("path", { d: d, fill: "none", stroke: css(s.color), "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      const last = s.pts[s.pts.length - 1];
      g.appendChild(el("circle", { cx: X(last.d), cy: Y(last.v), r: 4, fill: css(s.color), stroke: css("--surface"), "stroke-width": 2 }));
      const lb = el("text", { class: "dlabel", x: X(last.d) + 9, y: Y(last.v) + 4, fill: css(s.color) });
      lb.textContent = usdK(last.v);
      g.appendChild(lb);
    });

    const cross = el("line", { class: "axisline", y1: f.p.t, y2: f.H - f.p.b, opacity: 0, stroke: css("--rule-strong") });
    g.appendChild(cross);
    const dots = series.map((s) => { const c = el("circle", { r: 4.5, fill: css(s.color), stroke: css("--surface"), "stroke-width": 2, opacity: 0 }); g.appendChild(c); return c; });
    const hit = el("rect", { x: f.p.l, y: f.p.t, width: f.W - f.p.l - f.p.r, height: f.H - f.p.t - f.p.b, fill: "transparent" });
    g.appendChild(hit);

    const move = (ev) => {
      const r = f.svg.getBoundingClientRect();
      const cx = ev.touches ? ev.touches[0].clientX : ev.clientX;
      const sx = ((cx - r.left) / r.width) * f.W;
      const target = x0 + ((sx - f.p.l) / (f.W - f.p.l - f.p.r)) * (x1 - x0);
      const base = series[0].pts;
      let bi = 0, bd = Infinity;
      base.forEach((p, i) => { const dd = Math.abs(ym(p.d) - target); if (dd < bd) { bd = dd; bi = i; } });
      const px = X(base[bi].d);
      cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("opacity", 0.9);
      let rows = "", ty = Infinity;
      series.forEach((s, i) => {
        const p = s.pts[Math.min(bi, s.pts.length - 1)];
        dots[i].setAttribute("cx", X(p.d)); dots[i].setAttribute("cy", Y(p.v)); dots[i].setAttribute("opacity", 1);
        ty = Math.min(ty, Y(p.v));
        rows += `<div class="row"><span><i style="background:${css(s.color)}"></i> ${s.name}</span><span>${usd(p.v)}</span></div>`;
      });
      showTip(f, host, px, ty, `<b>${base[bi].d}</b>${rows}`);
    };
    const leave = () => { cross.setAttribute("opacity", 0); dots.forEach((d) => d.setAttribute("opacity", 0)); hideTip(f); };
    hit.addEventListener("mousemove", move);
    hit.addEventListener("touchmove", move, { passive: true });
    hit.addEventListener("mouseleave", leave);
    hit.addEventListener("touchend", leave);
  }

  /* ---------- yearly bars ---------- */
  function barChart(hostId, rows, key, fmt, title, height) {
    const host = document.getElementById(hostId);
    const f = frame(host, height, { l: 58, r: 20, t: 30, b: 30 });
    const g = el("g"); f.svg.appendChild(g);
    const vals = rows.map((r) => r[key]);
    const sc = niceScale(Math.min(0, Math.min(...vals)), Math.max(...vals), 4);
    const y0 = sc.y0, y1 = sc.y1;
    const Y = (v) => f.p.t + (f.H - f.p.t - f.p.b) * (1 - (v - y0) / (y1 - y0));
    const iw = (f.W - f.p.l - f.p.r) / rows.length;
    const bw = Math.min(iw - 8, 34);

    yAxis(f, g, sc, fmt);
    const ttl = el("text", { class: "dlabel", x: f.p.l, y: 14, fill: css("--ink-2") });
    ttl.textContent = title;
    g.appendChild(ttl);
    g.appendChild(el("line", { class: "axisline", x1: f.p.l, x2: f.W - f.p.r, y1: Y(0), y2: Y(0) }));

    rows.forEach((r, i) => {
      const v = r[key];
      const cx = f.p.l + iw * (i + 0.5);
      const yv = Y(v), yz = Y(0);
      const top = Math.min(yv, yz), h = Math.max(Math.abs(yv - yz), 1.5);
      const col = css(v >= 0 ? "--s1" : "--neg");
      const rect = el("rect", { x: cx - bw / 2, y: top, width: bw, height: h, fill: col, rx: 3, style: "cursor:crosshair" });
      g.appendChild(rect);
      if (i % 2 === 0 || rows.length <= 10) {
        const t = el("text", { class: "tick", x: cx, y: f.H - f.p.b + 17, "text-anchor": "middle" });
        t.textContent = "'" + String(r.year).slice(2);
        g.appendChild(t);
      }
      const enter = () => showTip(f, host, cx, top, `<b>${r.year}</b>
        <div class="row"><span>Net P&amp;L</span><span>${usd(r.net_usd)}</span></div>
        <div class="row"><span>% of notional</span><span>${pct(r.sum_ret_pct)}</span></div>
        <div class="row"><span>Trades</span><span>${r.trades}</span></div>
        <div class="row"><span>Win rate</span><span>${(r.win_rate * 100).toFixed(0)}%</span></div>
        <div class="row"><span>Avg notional</span><span>${usdK(r.mean_notional)}</span></div>`);
      rect.addEventListener("mouseenter", enter);
      rect.addEventListener("mousemove", enter);
      rect.addEventListener("mouseleave", () => hideTip(f));
    });
  }

  /* ---------- underwater ---------- */
  function underwater(hostId, pts) {
    const host = document.getElementById(hostId);
    const f = frame(host, 240, { l: 58, r: 20, t: 16, b: 30 });
    const g = el("g"); f.svg.appendChild(g);
    const x0 = ym(pts[0].d), x1 = ym(pts[pts.length - 1].d);
    const sc = niceScale(Math.min(...pts.map((p) => p.v)), 0, 4);
    const y0 = sc.y0, y1 = sc.y1;
    const X = (d) => f.p.l + (f.W - f.p.l - f.p.r) * ((ym(d) - x0) / (x1 - x0));
    const Y = (v) => f.p.t + (f.H - f.p.t - f.p.b) * (1 - (v - y0) / (y1 - y0));

    yAxis(f, g, sc, (v) => (v === 0 ? "$0" : usdK(v)));
    for (let yr = 2010; yr <= 2026; yr += 2) {
      const t = el("text", { class: "tick", x: X(yr + "-01"), y: f.H - f.p.b + 17, "text-anchor": "middle" });
      t.textContent = yr;
      g.appendChild(t);
    }
    const line = pts.map((p, i) => (i ? "L" : "M") + X(p.d).toFixed(1) + " " + Y(p.v).toFixed(1)).join(" ");
    g.appendChild(el("path", { d: line + ` L ${X(pts[pts.length - 1].d).toFixed(1)} ${Y(0)} L ${X(pts[0].d).toFixed(1)} ${Y(0)} Z`, fill: css("--neg"), opacity: 0.16 }));
    g.appendChild(el("path", { d: line, fill: "none", stroke: css("--neg"), "stroke-width": 2, "stroke-linejoin": "round" }));
    g.appendChild(el("line", { class: "axisline", x1: f.p.l, x2: f.W - f.p.r, y1: Y(0), y2: Y(0) }));

    const worst = pts.reduce((a, b) => (b.v < a.v ? b : a));
    g.appendChild(el("circle", { cx: X(worst.d), cy: Y(worst.v), r: 4, fill: css("--neg"), stroke: css("--surface"), "stroke-width": 2 }));
    const wx = X(worst.d), mid = (f.p.l + f.W - f.p.r) / 2;
    const wl = el("text", {
      class: "dlabel", x: wx + (wx > mid ? -10 : 10), y: Y(worst.v) + 16,
      fill: css("--neg"), "text-anchor": wx > mid ? "end" : "start"
    });
    wl.textContent = usd(worst.v) + " · " + worst.d;
    g.appendChild(wl);

    const cross = el("line", { class: "axisline", y1: f.p.t, y2: f.H - f.p.b, opacity: 0 });
    g.appendChild(cross);
    const dot = el("circle", { r: 4.5, fill: css("--neg"), stroke: css("--surface"), "stroke-width": 2, opacity: 0 });
    g.appendChild(dot);
    const hit = el("rect", { x: f.p.l, y: f.p.t, width: f.W - f.p.l - f.p.r, height: f.H - f.p.t - f.p.b, fill: "transparent" });
    g.appendChild(hit);
    const move = (ev) => {
      const r = f.svg.getBoundingClientRect();
      const cx = ev.touches ? ev.touches[0].clientX : ev.clientX;
      const sx = ((cx - r.left) / r.width) * f.W;
      const target = x0 + ((sx - f.p.l) / (f.W - f.p.l - f.p.r)) * (x1 - x0);
      let bi = 0, bd = Infinity;
      pts.forEach((p, i) => { const dd = Math.abs(ym(p.d) - target); if (dd < bd) { bd = dd; bi = i; } });
      const p = pts[bi];
      cross.setAttribute("x1", X(p.d)); cross.setAttribute("x2", X(p.d)); cross.setAttribute("opacity", 0.9);
      dot.setAttribute("cx", X(p.d)); dot.setAttribute("cy", Y(p.v)); dot.setAttribute("opacity", 1);
      showTip(f, host, X(p.d), Y(p.v), `<b>${p.d}</b><div class="row"><span>Below peak</span><span>${usd(p.v)}</span></div>`);
    };
    const leave = () => { cross.setAttribute("opacity", 0); dot.setAttribute("opacity", 0); hideTip(f); };
    hit.addEventListener("mousemove", move);
    hit.addEventListener("touchmove", move, { passive: true });
    hit.addEventListener("mouseleave", leave);
    hit.addEventListener("touchend", leave);
  }

  /* ---------- trade-return histogram, split by exit reason ---------- */
  function histogram(hostId, trades) {
    const host = document.getElementById(hostId);
    const f = frame(host, 280, { l: 58, r: 20, t: 16, b: 42 });
    const g = el("g"); f.svg.appendChild(g);
    const step = 0.5, lo = -7, hi = 4;
    const bins = [];
    for (let b = lo; b < hi; b += step) bins.push({ lo: b, hi: b + step, rsi: 0, time: 0 });
    trades.forEach((t) => {
      const v = Math.max(lo + 1e-9, Math.min(hi - 1e-9, t.ret));
      const i = Math.min(bins.length - 1, Math.floor((v - lo) / step));
      if (t.r === "time_stop") bins[i].time++; else bins[i].rsi++;
    });
    const sc = niceScale(0, Math.max(...bins.map((b) => b.rsi + b.time)), 4);
    const y1 = sc.y1;
    const Y = (v) => f.p.t + (f.H - f.p.t - f.p.b) * (1 - v / y1);
    const X = (v) => f.p.l + (f.W - f.p.l - f.p.r) * ((v - lo) / (hi - lo));
    const bw = (f.W - f.p.l - f.p.r) / bins.length - 2;

    yAxis(f, g, sc, (v) => String(Math.round(v)));
    for (let v = lo; v <= hi; v += 1) {
      const t = el("text", { class: "tick", x: X(v + step / 2) - bw / 2 - 1, y: f.H - f.p.b + 17, "text-anchor": "middle" });
      t.textContent = (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v) + "%";
      g.appendChild(t);
    }
    const xl = el("text", { class: "tick", x: (f.p.l + f.W - f.p.r) / 2, y: f.H - 4, "text-anchor": "middle" });
    xl.textContent = "trade result, % of notional at entry";
    g.appendChild(xl);

    bins.forEach((b) => {
      const x = X(b.lo) + 1;
      let acc = 0;
      [["rsi", "--s1"], ["time", "--s2"]].forEach(([k, c]) => {
        if (!b[k]) return;
        const h = (Y(0) - Y(b[k]));
        const yTop = Y(acc + b[k]);
        const r = el("rect", { x: x, y: yTop, width: bw, height: Math.max(h - 2, 1), fill: css(c), rx: 2, style: "cursor:crosshair" });
        g.appendChild(r);
        acc += b[k];
        const enter = () => showTip(f, host, x + bw / 2, yTop, `<b>${b.lo.toFixed(1)}% to ${b.hi.toFixed(1)}%</b>
          <div class="row"><span><i style="background:${css("--s1")}"></i> RSI target</span><span>${b.rsi}</span></div>
          <div class="row"><span><i style="background:${css("--s2")}"></i> Time stop</span><span>${b.time}</span></div>`);
        r.addEventListener("mouseenter", enter);
        r.addEventListener("mousemove", enter);
        r.addEventListener("mouseleave", () => hideTip(f));
      });
    });
    g.appendChild(el("line", { class: "axisline", x1: f.p.l, x2: f.W - f.p.r, y1: Y(0), y2: Y(0) }));
    g.appendChild(el("line", { x1: X(0), x2: X(0), y1: f.p.t, y2: Y(0), stroke: css("--rule-strong"), "stroke-width": 1, "stroke-dasharray": "3 3" }));
  }


  /* ---------- India: cumulative % return, two markets ---------- */
  function pctLines(hostId, series) {
    const host = document.getElementById(hostId);
    const f = frame(host, 300, { l: 54, r: 74, t: 16, b: 30 });
    const g = el("g"); f.svg.appendChild(g);
    const all = series.flatMap((s) => s.pts);
    const x0 = Math.min(...all.map((p) => ym(p.d))), x1 = Math.max(...all.map((p) => ym(p.d)));
    const sc = niceScale(0, Math.max(...all.map((p) => p.v)), 5);
    const y0 = sc.y0, y1 = sc.y1;
    const X = (d) => f.p.l + (f.W - f.p.l - f.p.r) * ((ym(d) - x0) / (x1 - x0));
    const Y = (v) => f.p.t + (f.H - f.p.t - f.p.b) * (1 - (v - y0) / (y1 - y0));
    yAxis(f, g, sc, (v) => Math.round(v) + "%");
    for (let yr = 2008; yr <= 2026; yr += 3) {
      const t = el("text", { class: "tick", x: X(yr + "-01"), y: f.H - f.p.b + 17, "text-anchor": "middle" });
      t.textContent = yr; g.appendChild(t);
    }
    g.appendChild(el("line", { class: "axisline", x1: f.p.l, x2: f.W - f.p.r, y1: Y(0), y2: Y(0) }));
    series.forEach((s) => {
      const d = s.pts.map((p, i) => (i ? "L" : "M") + X(p.d).toFixed(1) + " " + Y(p.v).toFixed(1)).join(" ");
      g.appendChild(el("path", { d: d, fill: "none", stroke: css(s.color), "stroke-width": 2, "stroke-linejoin": "round" }));
      const last = s.pts[s.pts.length - 1];
      g.appendChild(el("circle", { cx: X(last.d), cy: Y(last.v), r: 4, fill: css(s.color), stroke: css("--surface"), "stroke-width": 2 }));
      const lb = el("text", { class: "dlabel", x: X(last.d) + 9, y: Y(last.v) + 4, fill: css(s.color) });
      lb.textContent = "+" + Math.round(last.v) + "%"; g.appendChild(lb);
    });
    const cross = el("line", { class: "axisline", y1: f.p.t, y2: f.H - f.p.b, opacity: 0 });
    g.appendChild(cross);
    const dots = series.map((s) => { const c = el("circle", { r: 4.5, fill: css(s.color), stroke: css("--surface"), "stroke-width": 2, opacity: 0 }); g.appendChild(c); return c; });
    const hit = el("rect", { x: f.p.l, y: f.p.t, width: f.W - f.p.l - f.p.r, height: f.H - f.p.t - f.p.b, fill: "transparent" });
    g.appendChild(hit);
    const move = (ev) => {
      const r = f.svg.getBoundingClientRect();
      const cx = ev.touches ? ev.touches[0].clientX : ev.clientX;
      const sx = ((cx - r.left) / r.width) * f.W;
      const target = x0 + ((sx - f.p.l) / (f.W - f.p.l - f.p.r)) * (x1 - x0);
      let rows = "", ty = Infinity, px = 0;
      series.forEach((s, i) => {
        let bi = 0, bd = Infinity;
        s.pts.forEach((p, j) => { const dd = Math.abs(ym(p.d) - target); if (dd < bd) { bd = dd; bi = j; } });
        const p = s.pts[bi];
        dots[i].setAttribute("cx", X(p.d)); dots[i].setAttribute("cy", Y(p.v)); dots[i].setAttribute("opacity", 1);
        ty = Math.min(ty, Y(p.v)); px = Math.max(px, X(p.d));
        rows += `<div class="row"><span><i style="background:${css(s.color)}"></i> ${s.name}</span><span>+${p.v.toFixed(1)}%</span></div>`;
      });
      cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("opacity", 0.9);
      const lbl = series[0].pts.reduce((a, b) => (Math.abs(ym(b.d) - target) < Math.abs(ym(a.d) - target) ? b : a));
      showTip(f, host, px, ty, `<b>${lbl.d}</b>${rows}`);
    };
    const leave = () => { cross.setAttribute("opacity", 0); dots.forEach((d) => d.setAttribute("opacity", 0)); hideTip(f); };
    hit.addEventListener("mousemove", move);
    hit.addEventListener("touchmove", move, { passive: true });
    hit.addEventListener("mouseleave", leave);
    hit.addEventListener("touchend", leave);
  }

  /* ---------- cost erosion, per trade ---------- */
  const COSTS = [
    { k: "India · gross price move", v: 0.341, c: "--s3", n: "before any cost" },
    { k: "India · after fees & slippage", v: 0.293, c: "--s3", n: "STT, exchange, stamp, brokerage" },
    { k: "India · after cost of carry", v: 0.193, c: "--neg", n: "long futures basis convergence" },
    { k: "US · gross price move", v: 0.423, c: "--s1", n: "before any cost" },
    { k: "US · after all costs", v: 0.409, c: "--s1", n: "$4 round turn + a tick a side" }
  ];
  function costBars(hostId) {
    const host = document.getElementById(hostId);
    const f = frame(host, 250, { l: 232, r: 96, t: 10, b: 34 });
    const g = el("g"); f.svg.appendChild(g);
    const x1v = 0.45;
    const X = (v) => f.p.l + (f.W - f.p.l - f.p.r) * (v / x1v);
    const rowH = (f.H - f.p.t - f.p.b) / COSTS.length;
    for (let v = 0; v <= x1v; v += 0.1) {
      g.appendChild(el("line", { class: "gridline", x1: X(v), x2: X(v), y1: f.p.t, y2: f.H - f.p.b }));
      const t = el("text", { class: "tick", x: X(v), y: f.H - f.p.b + 17, "text-anchor": "middle" });
      t.textContent = v.toFixed(1) + "%"; g.appendChild(t);
    }
    COSTS.forEach((d, i) => {
      const y = f.p.t + rowH * i + rowH / 2;
      const h = Math.min(rowH - 10, 20);
      const r = el("rect", { x: f.p.l, y: y - h / 2, width: Math.max(X(d.v) - f.p.l, 2), height: h, fill: css(d.c), rx: 3, style: "cursor:crosshair" });
      g.appendChild(r);
      const lb = el("text", { class: "tick", x: f.p.l - 10, y: y + 3.5, "text-anchor": "end", style: "font-size:11px" });
      lb.textContent = d.k; g.appendChild(lb);
      const vl = el("text", { class: "dlabel", x: X(d.v) + 9, y: y + 4, fill: css(d.c) });
      vl.textContent = "+" + d.v.toFixed(3) + "%"; g.appendChild(vl);
      const enter = () => showTip(f, host, X(d.v), y - h / 2, `<b>${d.k}</b><div class="row"><span>${d.n}</span><span>+${d.v.toFixed(3)}%</span></div>`);
      r.addEventListener("mouseenter", enter); r.addEventListener("mousemove", enter);
      r.addEventListener("mouseleave", () => hideTip(f));
    });
    g.appendChild(el("line", { class: "axisline", x1: f.p.l, x2: f.p.l, y1: f.p.t, y2: f.H - f.p.b }));
    const xl = el("text", { class: "tick", x: (f.p.l + f.W - f.p.r) / 2, y: f.H - 3, "text-anchor": "middle" });
    xl.textContent = "mean return per trade, % of notional"; g.appendChild(xl);
  }

  /* ---------- India yearly bars ---------- */
  function indiaYears(hostId, rows) {
    const host = document.getElementById(hostId);
    const f = frame(host, 230, { l: 54, r: 20, t: 16, b: 30 });
    const g = el("g"); f.svg.appendChild(g);
    const vals = rows.map((r) => r.net_pct);
    const sc = niceScale(Math.min(...vals), Math.max(...vals), 4);
    const y0 = sc.y0, y1 = sc.y1;
    const Y = (v) => f.p.t + (f.H - f.p.t - f.p.b) * (1 - (v - y0) / (y1 - y0));
    const iw = (f.W - f.p.l - f.p.r) / rows.length;
    const bw = Math.min(iw - 8, 34);
    yAxis(f, g, sc, (v) => v.toFixed(0) + "%");
    g.appendChild(el("line", { class: "axisline", x1: f.p.l, x2: f.W - f.p.r, y1: Y(0), y2: Y(0) }));
    rows.forEach((r, i) => {
      const cx = f.p.l + iw * (i + 0.5);
      const yv = Y(r.net_pct), yz = Y(0);
      const top = Math.min(yv, yz), h = Math.max(Math.abs(yv - yz), 1.5);
      const col = css(r.net_pct >= 0 ? "--s3" : "--neg");
      const rect = el("rect", { x: cx - bw / 2, y: top, width: bw, height: h, fill: col, rx: 3, style: "cursor:crosshair" });
      g.appendChild(rect);
      if (i % 2 === 0) {
        const t = el("text", { class: "tick", x: cx, y: f.H - f.p.b + 17, "text-anchor": "middle" });
        t.textContent = "'" + String(r.year).slice(2); g.appendChild(t);
      }
      const inr = (v) => (v < 0 ? "−₹" : "₹") + Math.round(Math.abs(v)).toLocaleString("en-IN");
      const enter = () => showTip(f, host, cx, top, `<b>${r.year}</b>
        <div class="row"><span>% of notional</span><span>${pct(r.net_pct)}</span></div>
        <div class="row"><span>Net, 1 lot each</span><span>${inr(r.net_ccy)}</span></div>
        <div class="row"><span>Trades</span><span>${r.trades}</span></div>
        <div class="row"><span>Win rate</span><span>${(r.win_rate * 100).toFixed(0)}%</span></div>`);
      rect.addEventListener("mouseenter", enter); rect.addEventListener("mousemove", enter);
      rect.addEventListener("mouseleave", () => hideTip(f));
    });
  }


  /* ---------- NSE: what the 0.545% is made of, vs what it costs ---------- */
  function nseDecomp(hostId, dc) {
    const host = document.getElementById(hostId);
    const f = frame(host, 236, { l: 176, r: 104, t: 22, b: 34 });
    const g = el("g"); f.svg.appendChild(g);
    const xmax = 0.6;
    const X = (v) => f.p.l + (f.W - f.p.l - f.p.r) * (v / xmax);
    const rows = [
      { k: "Gross, as reported", parts: [
          { v: dc.random_baseline, c: "--muted", n: "available from random entry" },
          { v: dc.timing_edge, c: "--s1", n: "added by the RSI(2) signal" }] },
      { k: "Cost · stock futures", parts: [{ v: dc.fno_cost, c: "--s2", n: "0.02% STT + fees + slippage" }] },
      { k: "Cost · delivery equity", parts: [{ v: dc.delivery_cost, c: "--neg", n: "0.1% STT each side + fees + slippage" }] }
    ];
    const rowH = (f.H - f.p.t - f.p.b) / rows.length;
    for (let v = 0; v <= xmax + 1e-9; v += 0.1) {
      g.appendChild(el("line", { class: "gridline", x1: X(v), x2: X(v), y1: f.p.t, y2: f.H - f.p.b }));
      const t = el("text", { class: "tick", x: X(v), y: f.H - f.p.b + 17, "text-anchor": "middle" });
      t.textContent = v.toFixed(1) + "%"; g.appendChild(t);
    }
    rows.forEach((r, i) => {
      const y = f.p.t + rowH * i + rowH / 2;
      const h = Math.min(rowH - 12, 22);
      let acc = 0;
      r.parts.forEach((p2) => {
        const x = X(acc), w = X(acc + p2.v) - X(acc);
        const rect = el("rect", { x: x + 1, y: y - h / 2, width: Math.max(w - 2, 1.5), height: h, fill: css(p2.c), rx: 3, style: "cursor:crosshair" });
        g.appendChild(rect);
        if (w > 44) {
          const inner = el("text", { class: "dlabel", x: x + w / 2, y: y + 4, fill: css("--surface"), "text-anchor": "middle", style: "font-size:11px" });
          inner.textContent = p2.v.toFixed(3) + "%"; g.appendChild(inner);
        }
        const px = x, pw = w, pv = p2.v, pn = p2.n;
        const enter = () => showTip(f, host, px + pw / 2, y - h / 2, `<b>${r.k}</b><div class="row"><span>${pn}</span><span>${pv.toFixed(3)}%</span></div>`);
        rect.addEventListener("mouseenter", enter); rect.addEventListener("mousemove", enter);
        rect.addEventListener("mouseleave", () => hideTip(f));
        acc += p2.v;
      });
      const lb = el("text", { class: "tick", x: f.p.l - 10, y: y + 3.5, "text-anchor": "end", style: "font-size:11px" });
      lb.textContent = r.k; g.appendChild(lb);
      const tot = el("text", { class: "dlabel", x: X(acc) + 9, y: y + 4, fill: css(r.parts[r.parts.length - 1].c) });
      tot.textContent = acc.toFixed(3) + "%"; g.appendChild(tot);
    });
    g.appendChild(el("line", { class: "axisline", x1: f.p.l, x2: f.p.l, y1: f.p.t, y2: f.H - f.p.b }));
    const lg = el("text", { class: "tick", x: f.p.l, y: 12, style: "font-size:10.5px" });
    lg.textContent = "grey = drift anyone gets · blue = the actual signal"; g.appendChild(lg);
    const xl = el("text", { class: "tick", x: (f.p.l + f.W - f.p.r) / 2, y: f.H - 3, "text-anchor": "middle" });
    xl.textContent = "per trade, % of position value"; g.appendChild(xl);
  }

  /* ---------- NSE: edge against round-trip cost ---------- */
  function nseCost(hostId, rows) {
    const host = document.getElementById(hostId);
    const f = frame(host, 230, { l: 56, r: 30, t: 16, b: 42 });
    const g = el("g"); f.svg.appendChild(g);
    const sc = niceScale(0, Math.max(...rows.map((r) => r.mean_net_pct)), 4);
    const xmax = Math.max(...rows.map((r) => r.cost_pct));
    const X = (v) => f.p.l + (f.W - f.p.l - f.p.r) * (v / xmax);
    const Y = (v) => f.p.t + (f.H - f.p.t - f.p.b) * (1 - (v - sc.y0) / (sc.y1 - sc.y0));
    yAxis(f, g, sc, (v) => v.toFixed(2) + "%");
    rows.forEach((r) => {
      const t = el("text", { class: "tick", x: X(r.cost_pct), y: f.H - f.p.b + 17, "text-anchor": "middle" });
      t.textContent = r.cost_pct.toFixed(3).replace(/0+$/, "").replace(/\.$/, "") + "%"; g.appendChild(t);
    });
    const d = rows.map((r, i) => (i ? "L" : "M") + X(r.cost_pct).toFixed(1) + " " + Y(r.mean_net_pct).toFixed(1)).join(" ");
    g.appendChild(el("path", { d: d, fill: "none", stroke: css("--s1"), "stroke-width": 2, "stroke-linejoin": "round" }));
    g.appendChild(el("line", { class: "axisline", x1: f.p.l, x2: f.W - f.p.r, y1: Y(0), y2: Y(0) }));
    rows.forEach((r) => {
      const live = Math.abs(r.cost_pct - 0.323) < 1e-6;
      const c = el("circle", { cx: X(r.cost_pct), cy: Y(r.mean_net_pct), r: live ? 6 : 4.5,
        fill: css(live ? "--neg" : "--s1"), stroke: css("--surface"), "stroke-width": 2, style: "cursor:crosshair" });
      g.appendChild(c);
      if (live) {
        const lb = el("text", { class: "dlabel", x: X(r.cost_pct), y: Y(r.mean_net_pct) - 14, fill: css("--neg"), "text-anchor": "middle" });
        lb.textContent = "delivery equity"; g.appendChild(lb);
      }
      const enter = () => showTip(f, host, X(r.cost_pct), Y(r.mean_net_pct), `<b>${r.cost_pct}% round trip</b>
        <div class="row"><span>Mean net / trade</span><span>${r.mean_net_pct.toFixed(3)}%</span></div>
        <div class="row"><span>Win rate</span><span>${(r.win_rate * 100).toFixed(1)}%</span></div>`);
      c.addEventListener("mouseenter", enter); c.addEventListener("mousemove", enter);
      c.addEventListener("mouseleave", () => hideTip(f));
    });
    const xl = el("text", { class: "tick", x: (f.p.l + f.W - f.p.r) / 2, y: f.H - 4, "text-anchor": "middle" });
    xl.textContent = "round-trip cost, % of position value"; g.appendChild(xl);
  }

  /* ---------- NSE: mean net return per trade, by year ---------- */
  function nseYears(hostId, rows) {
    const host = document.getElementById(hostId);
    const f = frame(host, 236, { l: 56, r: 20, t: 16, b: 30 });
    const g = el("g"); f.svg.appendChild(g);
    const vals = rows.map((r) => r.mean_net_pct);
    const sc = niceScale(Math.min(...vals), Math.max(...vals), 4);
    const Y = (v) => f.p.t + (f.H - f.p.t - f.p.b) * (1 - (v - sc.y0) / (sc.y1 - sc.y0));
    const iw = (f.W - f.p.l - f.p.r) / rows.length;
    const bw = Math.min(iw - 8, 32);
    yAxis(f, g, sc, (v) => v.toFixed(1) + "%");
    g.appendChild(el("line", { class: "axisline", x1: f.p.l, x2: f.W - f.p.r, y1: Y(0), y2: Y(0) }));
    const inr = (v) => (v < 0 ? "−₹" : "₹") + Math.round(Math.abs(v)).toLocaleString("en-IN");
    rows.forEach((r, i) => {
      const cx = f.p.l + iw * (i + 0.5);
      const yv = Y(r.mean_net_pct), yz = Y(0);
      const top = Math.min(yv, yz), h = Math.max(Math.abs(yv - yz), 1.5);
      const rect = el("rect", { x: cx - bw / 2, y: top, width: bw, height: h,
        fill: css(r.mean_net_pct >= 0 ? "--s1" : "--neg"), rx: 3, style: "cursor:crosshair" });
      g.appendChild(rect);
      if (i % 2 === 0) {
        const t = el("text", { class: "tick", x: cx, y: f.H - f.p.b + 17, "text-anchor": "middle" });
        t.textContent = "'" + String(r.year).slice(2); g.appendChild(t);
      }
      const enter = () => showTip(f, host, cx, top, `<b>${r.year}</b>
        <div class="row"><span>Mean net / trade</span><span>${pct(r.mean_net_pct)}</span></div>
        <div class="row"><span>Trades</span><span>${r.trades.toLocaleString()}</span></div>
        <div class="row"><span>Win rate</span><span>${(r.win_rate * 100).toFixed(0)}%</span></div>
        <div class="row"><span>P&amp;L at ₹1L each</span><span>${inr(r.pnl_inr)}</span></div>`);
      rect.addEventListener("mouseenter", enter); rect.addEventListener("mousemove", enter);
      rect.addEventListener("mouseleave", () => hideTip(f));
    });
  }

  /* ---------- tables ---------- */
  const ROBUST = [
    ["As stated", 298, .782, 2.35, 314790, -41683, true],
    ["Next-open entry", 296, .770, 2.11, 280145, -66003],
    ["Cutler's RSI, not Wilder's", 764, .724, 1.62, 361352, -59374],
    ["Entry RSI < 5", 167, .772, 2.30, 209840, -48033],
    ["Entry RSI < 15", 419, .754, 2.21, 383864, -41683],
    ["Exit RSI > 60", 303, .706, 2.23, 253070, -25378],
    ["Exit RSI > 80", 283, .756, 1.93, 305093, -78605],
    ["Max hold 5 sessions", 313, .693, 1.83, 242875, -47414],
    ["Max hold 20 sessions", 294, .782, 2.38, 312907, -54430],
    ["100-day SMA filter", 254, .783, 2.38, 247309, -30033],
    ["50-day SMA filter", 195, .785, 2.68, 189525, -18763]
  ];

  function tables(rows) {
    const rb = document.getElementById("tb-robust");
    ROBUST.forEach((r) => {
      const tr = document.createElement("tr");
      if (r[6]) tr.className = "total";
      tr.innerHTML = `<td>${r[0]}</td><td>${r[1]}</td><td>${(r[2] * 100).toFixed(1)}%</td>
        <td>${r[3].toFixed(2)}</td><td>${usd(r[4])}</td><td class="neg">${usd(r[5])}</td>`;
      rb.appendChild(tr);
    });

    const yb = document.getElementById("tb-years");
    let tot = 0, totT = 0;
    rows.forEach((r) => {
      tot += r.net_usd; totT += r.trades;
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.year}${r.year === 2026 ? " <span style=\"color:var(--muted)\">YTD</span>" : ""}</td>
        <td>${r.trades}</td><td>${(r.win_rate * 100).toFixed(0)}%</td>
        <td class="${r.net_usd >= 0 ? "pos" : "neg"}">${usd(r.net_usd)}</td>
        <td class="${r.sum_ret_pct >= 0 ? "pos" : "neg"}">${pct(r.sum_ret_pct)}</td>
        <td>${usdK(r.mean_notional)}</td>`;
      yb.appendChild(tr);
    });
    const tr = document.createElement("tr");
    tr.className = "total";
    tr.innerHTML = `<td>2009&ndash;2026</td><td>${totT}</td><td>78%</td>
      <td class="pos">${usd(tot)}</td><td class="pos">+130.4%</td><td>&mdash;</td>`;
    yb.appendChild(tr);
  }

  function draw() {
    lineChart("c-equity", [
      { name: "Dip Buy strategy", color: "--s1", pts: DATA.equity },
      { name: "Buy and hold", color: "--s2", pts: DATA.buy_hold }
    ]);
    barChart("c-yeardollars", DATA.per_year, "net_usd", (v) => (v === 0 ? "$0" : usdK(v)), "Net P&L, dollars per 1 ES + 1 NQ", 220);
    barChart("c-yearpct", DATA.per_year, "sum_ret_pct", (v) => v.toFixed(0) + "%", "Same years, as % of notional risked", 220);
    underwater("c-underwater", DATA.underwater);
    histogram("c-hist", DATA.trades);
    pctLines("c-intl", [
      { name: "US · ES + NQ", color: "--s1", pts: INDIA.curve_us },
      { name: "India · Nifty + Bank Nifty", color: "--s3", pts: INDIA.curve_india }
    ]);
    costBars("c-costs");
    indiaYears("c-indiayear", INDIA.year_india);
    nseDecomp("c-nsedecomp", NSE.decomposition);
    nseCost("c-nsecost", NSE.cost_sensitivity);
    nseYears("c-nseyear", NSE.per_year);
  }

  document.addEventListener("DOMContentLoaded", () => { tables(DATA.per_year); draw(); });
  let t;
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const redraw = () => { clearTimeout(t); t = setTimeout(draw, 60); };
  mq.addEventListener("change", redraw);
  new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
})();
