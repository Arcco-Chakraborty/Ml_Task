// Rain radar: OpenStreetMap base layer + latest RainViewer radar frame.
(function () {
  const RAINVIEWER = "https://api.rainviewer.com/public/weather-maps.json";
  let map = null;
  let marker = null;
  let radarLayer = null;

  function init() {
    map = L.map("radar-map", { zoomControl: true, attributionControl: true }).setView([28.37, 75.59], 6);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 12,
      attribution: "© OpenStreetMap contributors",
    }).addTo(map);
    loadRadar();
    setInterval(loadRadar, 10 * 60 * 1000);
  }

  function loadRadar() {
    fetch(RAINVIEWER)
      .then((r) => r.json())
      .then((data) => {
        const frames = data.radar && data.radar.past;
        if (!frames || !frames.length) return;
        const frame = frames[frames.length - 1];
        const url = `${data.host}${frame.path}/256/{z}/{y}/{x}/2/1_1.png`;
        if (radarLayer) map.removeLayer(radarLayer);
        radarLayer = L.tileLayer(url, { opacity: 0.7, maxNativeZoom: 7, maxZoom: 12, attribution: "RainViewer" });
        radarLayer.addTo(map);
        const when = new Date(frame.time * 1000);
        document.getElementById("radar-meta").textContent =
          `Radar image from ${when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
      })
      .catch(() => {
        document.getElementById("radar-meta").textContent = "Radar is temporarily unavailable.";
      });
  }

  window.Radar = {
    show(lat, lon, label) {
      if (!map) init();
      map.setView([lat, lon], 7);
      if (marker) marker.remove();
      marker = L.marker([lat, lon]).addTo(map).bindTooltip(label);
    },
  };
})();
