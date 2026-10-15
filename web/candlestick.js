// 手刻 Canvas K 線圖元件,不依賴任何第三方圖表庫。
// 用法:
//   const chart = new CandleChart(container, { dates, o, h, l, c, v }, { onHover });
//   chart.jumpTo("2024-02-08");   // 跳到某個日期並置中、短暫高亮
//   chart.resize();               // 容器尺寸改變後(例如從 display:none 變成顯示)要手動呼叫一次
//
// 互動:滑鼠滾輪縮放(以游標位置為中心)、按住拖曳平移、移動滑鼠顯示十字線與當天 OHLC + 成交量。
// 十字線完全照滑鼠的實際像素位置畫(不是卡在K棒中心),並把瀏覽器原生游標藏起來,
// 避免「原生游標圖示」跟「自己畫的虛線」兩套十字對不齊的狀況。
// 下方附一條成交量子圖(單位:張,= 股數 / 1000)。

class CandleChart {
  constructor(container, data, opts = {}) {
    this.container = container;
    this.dates = data.dates;
    this.o = data.o;
    this.h = data.h;
    this.l = data.l;
    this.c = data.c;
    this.v = data.v || data.dates.map(() => 0);
    this.n = this.dates.length;
    this.onHover = opts.onHover || null;

    this.visibleCount = Math.min(120, this.n);
    this.startIndex = Math.max(0, this.n - this.visibleCount);
    this.highlightIndex = null;
    this.highlightUntil = 0;
    this.hoverIndex = null;
    this.mouseX = null;
    this.mouseY = null;

    this.canvas = document.createElement("canvas");
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    this.canvas.style.display = "block";
    this.canvas.style.cursor = "crosshair";
    container.innerHTML = "";
    container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext("2d");

    this._bindEvents();
    this.resize();
    this._resizeHandler = () => this.resize();
    window.addEventListener("resize", this._resizeHandler);
    this._raf = requestAnimationFrame(() => this._loop());
  }

  destroy() {
    cancelAnimationFrame(this._raf);
    window.removeEventListener("resize", this._resizeHandler);
  }

  jumpTo(dateStr) {
    let idx = this.dates.indexOf(dateStr);
    if (idx === -1) {
      idx = this.dates.findIndex(d => d >= dateStr);
      if (idx === -1) idx = this.n - 1;
    }
    this.visibleCount = Math.min(60, this.n);
    this.startIndex = Math.max(0, Math.min(this.n - this.visibleCount, idx - Math.floor(this.visibleCount / 2)));
    this.highlightIndex = idx;
    this.highlightUntil = performance.now() + 2200;
    this._draw();
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.container.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return; // 容器還是 display:none,先不畫
    this.canvas.width = Math.max(1, rect.width * dpr);
    this.canvas.height = Math.max(1, rect.height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.cssW = rect.width;
    this.cssH = rect.height;
    this._draw();
  }

  _bindEvents() {
    const cv = this.canvas;

    cv.addEventListener("wheel", (e) => {
      e.preventDefault();
      const rect = cv.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const ratio = mouseX / this.cssW;
      const focusIdx = this.startIndex + ratio * this.visibleCount;

      const factor = e.deltaY > 0 ? 1.15 : 1 / 1.15;
      let newCount = Math.round(this.visibleCount * factor);
      newCount = Math.max(15, Math.min(this.n, newCount));

      this.startIndex = Math.round(focusIdx - ratio * newCount);
      this.startIndex = Math.max(0, Math.min(this.n - newCount, this.startIndex));
      this.visibleCount = newCount;
      this._draw();
    }, { passive: false });

    let dragging = false, dragStartX = 0, dragStartIdx = 0;
    cv.addEventListener("mousedown", (e) => {
      dragging = true;
      dragStartX = e.clientX;
      dragStartIdx = this.startIndex;
    });
    window.addEventListener("mouseup", () => { dragging = false; });
    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      const dx = e.clientX - dragStartX;
      const barW = this.cssW / this.visibleCount;
      const shift = Math.round(-dx / barW);
      this.startIndex = Math.max(0, Math.min(this.n - this.visibleCount, dragStartIdx + shift));
      this._draw();
    });

    cv.addEventListener("mousemove", (e) => {
      const rect = cv.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      this.mouseX = x;
      this.mouseY = y;
      if (dragging) { this._draw(); return; }
      const idx = Math.floor(this.startIndex + (x / this.cssW) * this.visibleCount);
      this.hoverIndex = (idx >= 0 && idx < this.n) ? idx : null;
      if (this.onHover) {
        if (this.hoverIndex !== null) {
          const i = this.hoverIndex;
          this.onHover({ date: this.dates[i], o: this.o[i], h: this.h[i], l: this.l[i], c: this.c[i], lots: Math.round(this.v[i] / 1000) });
        } else {
          this.onHover(null);
        }
      }
      this._draw();
    });
    cv.addEventListener("mouseleave", () => {
      this.hoverIndex = null; this.mouseX = null; this.mouseY = null;
      if (this.onHover) this.onHover(null);
      this._draw();
    });
  }

  _loop() {
    if (this.highlightIndex !== null && performance.now() < this.highlightUntil) {
      this._draw();
    }
    this._raf = requestAnimationFrame(() => this._loop());
  }

  _draw() {
    const ctx = this.ctx;
    const W = this.cssW, H = this.cssH;
    if (!W || !H) return;
    ctx.clearRect(0, 0, W, H);

    const padL = 8, padR = 56, padT = 10, padB = 24;
    const gapPV = 6;                 // 價格圖與成交量圖中間的間距
    const volH = Math.max(40, H * 0.2);
    const priceH = H - padT - padB - gapPV - volH;
    const plotW = W - padL - padR;

    const s = this.startIndex;
    const e = Math.min(this.n, s + this.visibleCount);
    if (e <= s) return;

    let hi = -Infinity, lo = Infinity, volMax = 0;
    for (let i = s; i < e; i++) {
      if (this.h[i] > hi) hi = this.h[i];
      if (this.l[i] < lo) lo = this.l[i];
      const lots = this.v[i] / 1000;
      if (lots > volMax) volMax = lots;
    }
    const pad = (hi - lo) * 0.08 || 1;
    hi += pad; lo -= pad;
    volMax = volMax || 1;

    const yOf = (price) => padT + priceH * (1 - (price - lo) / (hi - lo));
    const volTop = padT + priceH + gapPV;
    const yOfVol = (lots) => volTop + volH * (1 - lots / volMax);

    const count = e - s;
    const barW = plotW / count;
    const xOf = (i) => padL + (i - s) * barW + barW / 2;

    ctx.font = "11px sans-serif";
    ctx.lineWidth = 1;

    // ---- 價格區網格 + 右側刻度 ----
    ctx.strokeStyle = "#242936";
    ctx.fillStyle = "#868c99";
    const gridLines = 5;
    for (let g = 0; g <= gridLines; g++) {
      const price = lo + (hi - lo) * (g / gridLines);
      const y = yOf(price);
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(W - padR, y);
      ctx.stroke();
      ctx.textAlign = "left";
      ctx.fillText(price.toFixed(1), W - padR + 6, y + 3);
    }

    // ---- K 棒 ----
    const up = "#ef4452", down = "#1fae6a"; // 台股慣例:紅漲綠跌
    for (let i = s; i < e; i++) {
      const x = xOf(i);
      const isUp = this.c[i] >= this.o[i];
      ctx.strokeStyle = ctx.fillStyle = isUp ? up : down;
      ctx.beginPath();
      ctx.moveTo(x, yOf(this.h[i]));
      ctx.lineTo(x, yOf(this.l[i]));
      ctx.stroke();
      const bw = Math.max(1, barW * 0.6);
      const yOpen = yOf(this.o[i]), yClose = yOf(this.c[i]);
      const top = Math.min(yOpen, yClose);
      const bh = Math.max(1, Math.abs(yClose - yOpen));
      ctx.fillRect(x - bw / 2, top, bw, bh);
    }

    // ---- 成交量子圖(張 = 股數 / 1000)----
    ctx.strokeStyle = "#1c2029";
    ctx.beginPath();
    ctx.moveTo(padL, volTop - gapPV / 2);
    ctx.lineTo(W - padR, volTop - gapPV / 2);
    ctx.stroke();
    ctx.fillStyle = "#868c99";
    ctx.textAlign = "left";
    ctx.fillText(Math.round(volMax).toLocaleString() + " 張", W - padR + 6, volTop + 8);
    for (let i = s; i < e; i++) {
      const x = xOf(i);
      const lots = this.v[i] / 1000;
      const isUp = this.c[i] >= this.o[i];
      ctx.fillStyle = (isUp ? up : down) + "99";
      const bw = Math.max(1, barW * 0.6);
      const y = yOfVol(lots);
      ctx.fillRect(x - bw / 2, y, bw, (volTop + volH) - y);
    }

    // ---- 高亮直線(跳轉定位用,卡在K棒中心)----
    // 剛跳轉過來的幾秒會閃爍吸引注意,之後轉成常駐的淡色線,只要還停留在這個頁面就不會消失,
    // 直到使用者點了別的明細(重新呼叫 jumpTo)才會換到新的位置。
    if (this.highlightIndex !== null && this.highlightIndex >= s && this.highlightIndex < e) {
      const remain = this.highlightUntil - performance.now();
      const x = xOf(this.highlightIndex);
      const alpha = remain > 0 ? (0.35 + 0.35 * Math.abs(Math.sin(performance.now() / 180))) : 0.4;
      ctx.strokeStyle = `rgba(91,141,239,${alpha})`;
      ctx.lineWidth = remain > 0 ? 2 : 1.5;
      ctx.beginPath();
      ctx.moveTo(x, padT);
      ctx.lineTo(x, volTop + volH);
      ctx.stroke();
      ctx.lineWidth = 1;
    }

    // ---- X 軸日期標籤(避免兩端被裁切)----
    ctx.fillStyle = "#868c99";
    const bottomY = volTop + volH + 15;
    const labelEvery = Math.max(1, Math.ceil(count / 8));
    const labelIdxs = [];
    for (let i = s; i < e; i += labelEvery) labelIdxs.push(i);
    if (labelIdxs[labelIdxs.length - 1] !== e - 1) labelIdxs.push(e - 1);
    labelIdxs.forEach((i, k) => {
      if (k === 0) { ctx.textAlign = "left"; ctx.fillText(this.dates[i], Math.max(padL, xOf(i) - barW), bottomY); }
      else if (k === labelIdxs.length - 1) { ctx.textAlign = "right"; ctx.fillText(this.dates[i], Math.min(W - padR, xOf(i) + barW), bottomY); }
      else { ctx.textAlign = "center"; ctx.fillText(this.dates[i], xOf(i), bottomY); }
    });

    // ---- 十字線:卡在滑鼠所在那根 K 棒的「中心 x」+「收盤價 y」,不是滑鼠原始像素位置 ----
    // 這樣線永遠精準對齊某一根 K 棒的收盤價,滑鼠游標本身維持瀏覽器原生的十字圖示(見 cursor:crosshair)。
    if (this.hoverIndex !== null && this.hoverIndex >= s && this.hoverIndex < e) {
      const i = this.hoverIndex;
      const x = xOf(i);
      const yClose = yOf(this.c[i]);

      ctx.strokeStyle = "#5b8def90";
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x, padT);
      ctx.lineTo(x, volTop + volH);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(padL, yClose);
      ctx.lineTo(W - padR, yClose);
      ctx.stroke();
      ctx.setLineDash([]);

      // 價格標籤:貼在右軸、水平線的右端點,顯示這根 K 棒的實際收盤價
      ctx.font = "11px sans-serif";
      const priceText = this.c[i].toFixed(2);
      const ptw = ctx.measureText(priceText).width + 10;
      ctx.fillStyle = "#5b8def";
      ctx.fillRect(W - padR, yClose - 9, ptw, 18);
      ctx.fillStyle = "#fff";
      ctx.textAlign = "left";
      ctx.fillText(priceText, W - padR + 5, yClose + 4);

      // 日期標籤:貼在垂直線的底端點
      const dateText = this.dates[i];
      const dtw = ctx.measureText(dateText).width + 10;
      let dtx = Math.max(padL, Math.min(W - padR - dtw, x - dtw / 2));
      ctx.fillStyle = "#5b8def";
      ctx.fillRect(dtx, volTop + volH + 3, dtw, 16);
      ctx.fillStyle = "#fff";
      ctx.textAlign = "left";
      ctx.fillText(dateText, dtx + 5, volTop + volH + 14);
    }
  }
}