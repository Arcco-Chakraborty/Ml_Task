// Draws the "next 24 hours" chart: temperature line + rain-probability bars.
(function () {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const HEIGHT = 190;
  const PAD = { top: 26, bottom: 44, left: 8, right: 8 };

  function el(name, attrs, text) {
    const node = document.createElementNS(SVG_NS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function draw(container, hours, unit) {
    container.innerHTML = "";
    if (!hours.length) return;
    const width = container.clientWidth;
    const svg = el("svg", { width, height: HEIGHT, viewBox: `0 0 ${width} ${HEIGHT}` });

    const temps = hours.map((h) => h.temperature);
    const min = Math.min(...temps);
    const max = Math.max(...temps);
    const span = Math.max(max - min, 1);
    const plotH = HEIGHT - PAD.top - PAD.bottom;
    const step = (width - PAD.left - PAD.right) / hours.length;
    const x = (i) => PAD.left + step * i + step / 2;
    const y = (t) => PAD.top + plotH - ((t - min) / span) * plotH;

    // rain probability bars (full plot height = 100%)
    hours.forEach((h, i) => {
      const p = h.precip_probability || 0;
      const bh = (p / 100) * plotH;
      svg.appendChild(el("rect", {
        class: "rain-bar", x: x(i) - step * 0.35, y: PAD.top + plotH - bh, width: step * 0.7, height: bh,
      }));
    });

    const points = hours.map((h, i) => `${x(i)},${y(h.temperature)}`).join(" ");
    svg.appendChild(el("polyline", { class: "temp-line", points }));

    hours.forEach((h, i) => {
      svg.appendChild(el("circle", { class: "temp-dot", cx: x(i), cy: y(h.temperature), r: 3 }));
      svg.appendChild(el("text", { class: "temp-label", x: x(i), y: y(h.temperature) - 9, "text-anchor": "middle" },
        `${h.temperature}°`));
      svg.appendChild(el("text", { x: x(i), y: HEIGHT - 24, "text-anchor": "middle" }, h.time));
      svg.appendChild(el("text", { x: x(i), y: HEIGHT - 8, "text-anchor": "middle" },
        h.precip_probability ? `${h.precip_probability}%` : ""));
    });

    const title = el("title", {}, `Hourly temperature (${unit}) and chance of rain`);
    svg.prepend(title);
    container.appendChild(svg);
  }

  let last = null;
  window.addEventListener("resize", () => {
    if (last) draw(...last);
  });

  window.HourlyChart = {
    render(container, hours, unit) {
      last = [container, hours, unit];
      draw(container, hours, unit);
    },
  };
})();
