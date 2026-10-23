// Main weather page.
(function () {
  const DEFAULT_PLACE = { name: "Pilani", label: "Pilani, Rajasthan, India", lat: 28.367, lon: 75.588 };
  const $ = (id) => document.getElementById(id);

  const store = {
    get(key, fallback) {
      try {
        const v = localStorage.getItem(key);
        return v === null ? fallback : JSON.parse(v);
      } catch (e) {
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch (e) { /* storage unavailable */ }
    },
  };

  const state = {
    units: store.get("cirrus.units", "metric"),
    place: store.get("cirrus.lastPlace", DEFAULT_PLACE),
    saved: store.get("cirrus.saved", []),
  };

  // ---------------------------------------------------------------- helpers
  function toast(msg) {
    const t = $("toast");
    t.textContent = msg;
    t.classList.add("on");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => t.classList.remove("on"), 3000);
  }

  function showLoading(on) {
    $("loading").classList.toggle("on", on);
  }

  function sameSpot(a, b) {
    return Math.abs(a.lat - b.lat) < 0.01 && Math.abs(a.lon - b.lon) < 0.01;
  }

  function aqiClass(value) {
    if (value <= 50) return "aqi-good";
    if (value <= 100) return "aqi-moderate";
    return "aqi-bad";
  }

  // ---------------------------------------------------------------- rendering
  function render(data, place) {
    const u = data.units;
    const c = data.current;
    const today = data.daily[0];

    $("place-name").textContent = place.name;
    $("place-sub").textContent = `${place.label} · updated ${c.time.slice(11, 16)} local time`;
    $("now-icon").textContent = c.icon;
    $("now-temp").textContent = `${c.temperature}°`;
    $("now-cond").textContent = c.text;
    $("now-feels").textContent = `Feels like ${c.feels_like}°`;
    $("now-hilo").textContent = `H ${today.high}° · L ${today.low}°`;

    $("d-rain").textContent = `${c.precip_probability ?? 0}%`;
    $("d-humidity").textContent = `${c.humidity}%`;
    // arrow points where the wind is blowing TO; the label says where it comes FROM
    $("d-wind").innerHTML =
      `<span class="wind-arrow" style="transform: rotate(${(c.wind_direction + 180) % 360}deg)">↑</span> ` +
      `${c.wind_speed} ${u.wind} <small>${c.wind_from}</small>`;
    $("d-pressure").textContent = `${c.pressure} ${u.pressure}`;
    $("d-uv").textContent = c.uv_index ?? "--";

    const aqi = data.air_quality;
    $("d-aqi").innerHTML = aqi.value == null
      ? "--"
      : `${aqi.value}<span class="aqi-badge ${aqiClass(aqi.value)}">${aqi.category}</span>`;

    $("sunrise").textContent = today.sunrise;
    $("sunset").textContent = today.sunset;

    $("daily").innerHTML = data.daily.map((d) => `
      <li>
        <span class="day">${d.day}</span>
        <span class="ico">${d.icon}</span>
        <span class="cond">${d.text}</span>
        <span class="rain">${d.precip_probability ? `💧${d.precip_probability}%` : ""}</span>
        <span class="range">${d.high}°<span class="lo">${d.low}°</span></span>
      </li>`).join("");

    HourlyChart.render($("hourly-chart"), data.hourly, u.temperature);
    Radar.show(place.lat, place.lon, place.name);
    renderSaved();
  }

  function renderSaved() {
    const box = $("saved");
    const isSaved = state.saved.some((p) => sameSpot(p, state.place));
    $("save-place").textContent = isSaved ? "★" : "☆";
    $("save-place").classList.toggle("saved", isSaved);

    if (!state.saved.length) {
      box.innerHTML = `<span class="hint">Tap ☆ to save a location here.</span>`;
      return;
    }
    box.innerHTML = "";
    state.saved.forEach((p, i) => {
      const chip = document.createElement("span");
      chip.className = "chip" + (sameSpot(p, state.place) ? " active" : "");
      const name = document.createElement("a");
      name.href = "#";
      name.textContent = p.name;
      name.onclick = (e) => {
        e.preventDefault();
        loadWeather(p);
      };
      const del = document.createElement("button");
      del.title = `Remove ${p.name}`;
      del.setAttribute("aria-label", `Remove ${p.name}`);
      del.textContent = "×";
      del.onclick = () => {
        state.saved.splice(i, 1);
        store.set("cirrus.saved", state.saved);
        renderSaved();
      };
      chip.append(name, del);
      box.appendChild(chip);
    });
  }

  // ---------------------------------------------------------------- data
  function loadWeather(place) {
    state.place = place;
    store.set("cirrus.lastPlace", place);
    showLoading(true);
    const qs = new URLSearchParams({ lat: place.lat, lon: place.lon, units: state.units });
    fetch(`/api/weather?${qs}`)
      .then((r) => r.json())
      .then((data) => {
        render(data, place);
        showLoading(false);
      });
  }

  function locateMe() {
    if (!navigator.geolocation) {
      toast("Location is not available in this browser.");
      return;
    }
    navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        fetch(`/api/reverse?lat=${latitude}&lon=${longitude}`)
          .then((r) => r.json())
          .then((p) => loadWeather({ name: p.name, label: p.label, lat: latitude, lon: longitude }));
      },
      () => toast("Couldn't get your location. Check the location permission."),
      { enableHighAccuracy: true, maximumAge: 0 }
    );
  }

  // ---------------------------------------------------------------- search
  function setupSearch() {
    const input = $("search");
    const list = $("search-results");
    let timer = null;
    let results = [];

    function close() {
      list.classList.remove("open");
      list.innerHTML = "";
    }

    function choose(r) {
      input.value = "";
      close();
      loadWeather({ name: r.name, label: r.label, lat: r.lat, lon: r.lon });
    }

    input.addEventListener("input", () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) return close();
      timer = setTimeout(() => {
        fetch(`/api/search?q=${encodeURIComponent(q)}`)
          .then((r) => r.json())
          .then((data) => {
            results = data.results || [];
            if (!results.length) {
              list.innerHTML = `<li aria-disabled="true">No places found</li>`;
            } else {
              list.innerHTML = "";
              results.forEach((r) => {
                const li = document.createElement("li");
                li.textContent = r.label;
                li.onclick = () => choose(r);
                list.appendChild(li);
              });
            }
            list.classList.add("open");
          })
          .catch(() => close());
      }, 250);
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && results.length) choose(results[0]);
      if (e.key === "Escape") close();
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".search")) close();
    });
  }

  // ---------------------------------------------------------------- units, saving
  function setupControls() {
    document.querySelectorAll(".unit-toggle button").forEach((b) => {
      b.classList.toggle("on", b.dataset.units === state.units);
      b.onclick = () => {
        if (state.units === b.dataset.units) return;
        state.units = b.dataset.units;
        store.set("cirrus.units", state.units);
        document.querySelectorAll(".unit-toggle button").forEach((x) =>
          x.classList.toggle("on", x.dataset.units === state.units));
        loadWeather(state.place);
      };
    });

    $("save-place").onclick = () => {
      const i = state.saved.findIndex((p) => sameSpot(p, state.place));
      if (i >= 0) state.saved.splice(i, 1);
      else state.saved.push(state.place);
      store.set("cirrus.saved", state.saved);
      renderSaved();
    };

    $("locate").onclick = locateMe;

    document.querySelectorAll(".bottom-nav a[href^='#']").forEach((a) => {
      a.addEventListener("click", () => {
        document.querySelectorAll(".bottom-nav a").forEach((x) => x.classList.remove("active"));
        a.classList.add("active");
      });
    });
  }

  setupSearch();
  setupControls();
  loadWeather(state.place);
})();
