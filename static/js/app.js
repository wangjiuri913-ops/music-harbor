(() => {
  "use strict";

  const els = {
    audio: document.getElementById("audio"),
    form: document.getElementById("search-form"),
    input: document.getElementById("search-input"),
    searchBtn: document.getElementById("search-btn"),
    tabs: Array.from(document.querySelectorAll(".tab")),
    chips: Array.from(document.querySelectorAll(".chip")),
    results: document.getElementById("results"),
    count: document.getElementById("result-count"),
    playBtn: document.getElementById("play-btn"),
    iconPlay: document.getElementById("icon-play"),
    iconPause: document.getElementById("icon-pause"),
    prevBtn: document.getElementById("prev-btn"),
    nextBtn: document.getElementById("next-btn"),
    progress: document.getElementById("progress"),
    timeCurrent: document.getElementById("time-current"),
    timeTotal: document.getElementById("time-total"),
    volume: document.getElementById("volume"),
    npCover: document.getElementById("np-cover"),
    npTitle: document.getElementById("np-title"),
    npArtist: document.getElementById("np-artist"),
    download: document.getElementById("download-current"),
  };

  const state = {
    tracks: [],
    current: -1,
    source: "all",
    query: "",
    loading: false,
    seeking: false,
  };

  const SOURCE_LABELS = {
    audius: "Audius",
    itunes: "iTunes",
  };

  const ICON_PLAY =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 4.5v15l12-7.5z" fill="currentColor"></path></svg>';

  const escapeHtml = (value = "") =>
    String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char]));

  const formatTime = (seconds) => {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    if (hours) {
      return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    }
    return `${minutes}:${String(secs).padStart(2, "0")}`;
  };

  const sourceLabel = (source) => SOURCE_LABELS[source] || source;

  const firstChar = (text) => (String(text || "♪").trim()[0] || "♪").toUpperCase();

  function paintRange(input) {
    const min = Number(input.min || 0);
    const max = Number(input.max || 100);
    const value = Number(input.value || 0);
    const pct = max > min ? ((value - min) / (max - min)) * 100 : 0;
    input.style.setProperty("--pct", `${pct}%`);
  }

  let toastTimer = 0;
  function toast(message) {
    let node = document.querySelector(".toast");
    if (!node) {
      node = document.createElement("div");
      node.className = "toast";
      node.setAttribute("role", "status");
      node.setAttribute("aria-live", "polite");
      document.body.appendChild(node);
    }
    node.textContent = message;
    node.classList.add("show");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => node.classList.remove("show"), 3200);
  }

  function setPlayingUI(isPlaying) {
    els.iconPlay.hidden = isPlaying;
    els.iconPause.hidden = !isPlaying;
    els.playBtn.setAttribute("aria-label", isPlaying ? "暂停" : "播放");
  }

  function setDownload(track) {
    if (!track) {
      els.download.setAttribute("aria-disabled", "true");
      els.download.href = "#";
      els.download.removeAttribute("download");
      return;
    }
    els.download.href = track.download_url;
    els.download.setAttribute("download", `${track.artist} - ${track.title}`);
    els.download.removeAttribute("aria-disabled");
  }

  function setNowPlaying(track) {
    if (!track) {
      els.npTitle.textContent = "未在播放";
      els.npArtist.textContent = "选择一首歌开始";
      els.npCover.style.backgroundImage = "";
      els.npCover.classList.remove("has-cover");
      return;
    }
    els.npTitle.textContent = track.title;
    els.npArtist.textContent = track.album
      ? `${track.artist} · ${track.album}`
      : track.artist;
    if (track.cover) {
      els.npCover.style.backgroundImage = `url("${track.cover}")`;
      els.npCover.classList.add("has-cover");
    } else {
      els.npCover.style.backgroundImage = "";
      els.npCover.classList.remove("has-cover");
    }
  }

  function highlightCurrent() {
    Array.from(els.results.querySelectorAll(".track")).forEach((card) => {
      card.classList.toggle("is-current", Number(card.dataset.index) === state.current);
    });
  }

  function playTrack(index) {
    const track = state.tracks[index];
    if (!track) return;

    if (index === state.current) {
      togglePlay();
      return;
    }

    state.current = index;
    els.audio.src = track.stream_url;
    els.audio.volume = Number(els.volume.value) / 100;
    setNowPlaying(track);
    setDownload(track);
    highlightCurrent();
    els.timeCurrent.textContent = "0:00";
    els.timeTotal.textContent = track.duration_text || "0:00";
    els.progress.value = "0";
    paintRange(els.progress);

    const playPromise = els.audio.play();
    if (playPromise && typeof playPromise.catch === "function") {
      playPromise.catch((error) => {
        if (error && error.name === "NotAllowedError") return;
        toast("播放失败，换一首试试");
      });
    }
  }

  function togglePlay() {
    if (state.current < 0) {
      if (state.tracks.length) playTrack(0);
      return;
    }
    if (els.audio.paused) {
      const playPromise = els.audio.play();
      if (playPromise && typeof playPromise.catch === "function") {
        playPromise.catch(() => toast("播放失败，换一首试试"));
      }
    } else {
      els.audio.pause();
    }
  }

  function step(direction) {
    if (!state.tracks.length) return;
    let next = state.current + direction;
    if (next < 0) next = state.tracks.length - 1;
    if (next >= state.tracks.length) next = 0;
    playTrack(next);
  }

  function stopPlayback() {
    els.audio.pause();
    els.audio.removeAttribute("src");
    els.audio.load();
    state.current = -1;
    els.progress.value = "0";
    paintRange(els.progress);
    els.timeCurrent.textContent = "0:00";
    els.timeTotal.textContent = "0:00";
    setNowPlaying(null);
    setDownload(null);
    setPlayingUI(false);
  }

  function buildCard(track, index) {
    const card = document.createElement("article");
    card.className = "track";
    card.dataset.index = String(index);
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `播放 ${track.title}`);

    const cover = track.cover
      ? `<img src="${escapeHtml(track.cover)}" alt="${escapeHtml(track.title)}" loading="lazy" referrerpolicy="no-referrer">`
      : `<div class="cover-fallback">${escapeHtml(firstChar(track.title))}</div>`;

    card.innerHTML = `
      <div class="track-cover">
        ${cover}
        <span class="track-badge">${track.preview_only ? "试听 30s" : "完整曲目"}</span>
        <button class="cover-play" type="button" aria-label="播放 ${escapeHtml(track.title)}">${ICON_PLAY}</button>
      </div>
      <div class="track-body">
        <h3 class="track-title" title="${escapeHtml(track.title)}">${escapeHtml(track.title)}</h3>
        <p class="track-artist" title="${escapeHtml(track.artist)}">${escapeHtml(track.artist)}</p>
        <div class="track-meta">
          <span class="track-source src-${escapeHtml(track.source)}">${escapeHtml(sourceLabel(track.source))}</span>
          <span>${escapeHtml(track.duration_text || "—")}</span>
        </div>
      </div>
    `;

    const img = card.querySelector("img");
    if (img) {
      img.addEventListener("error", () => {
        const fallback = document.createElement("div");
        fallback.className = "cover-fallback";
        fallback.textContent = firstChar(track.title);
        img.replaceWith(fallback);
      });
    }

    card.querySelector(".cover-play").addEventListener("click", (event) => {
      event.stopPropagation();
      playTrack(index);
    });

    card.addEventListener("click", () => playTrack(index));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        playTrack(index);
      }
    });

    return card;
  }

  function renderResults() {
    els.results.innerHTML = "";
    if (!state.tracks.length) {
      showEmpty("没有找到相关曲目", "换个关键词试试，或切换到“全部音源”。");
      els.count.textContent = "0";
      return;
    }
    const fragment = document.createDocumentFragment();
    state.tracks.forEach((track, index) => fragment.appendChild(buildCard(track, index)));
    els.results.appendChild(fragment);
    els.count.textContent = String(state.tracks.length);
    highlightCurrent();
  }

  function showEmpty(title, desc, icon = "♪") {
    els.results.innerHTML = `
      <div class="empty">
        <div class="empty-icon">${escapeHtml(icon)}</div>
        <p class="empty-title">${escapeHtml(title)}</p>
        <p class="empty-desc">${escapeHtml(desc)}</p>
      </div>
    `;
  }

  function renderSkeletons(count = 8) {
    els.results.innerHTML = "";
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < count; i += 1) {
      const skeleton = document.createElement("div");
      skeleton.className = "skeleton";
      skeleton.innerHTML =
        '<div class="skeleton-cover"></div><div class="skeleton-body">' +
        '<div class="skeleton-line"></div><div class="skeleton-line short"></div></div>';
      fragment.appendChild(skeleton);
    }
    els.results.appendChild(fragment);
    els.count.textContent = "…";
  }

  function setLoading(loading) {
    state.loading = loading;
    els.searchBtn.disabled = loading;
    els.searchBtn.textContent = loading ? "搜索中…" : "搜索";
  }

  async function runSearch(rawQuery) {
    if (state.loading) return;

    const query = String(rawQuery ?? els.input.value).trim();
    if (!query) {
      els.input.focus();
      return;
    }

    state.query = query;
    els.input.value = query;
    els.input.blur();
    setLoading(true);
    stopPlayback();
    renderSkeletons();

    const limit = state.source === "all" ? 10 : 18;

    try {
      const response = await fetch(
        `/api/search?q=${encodeURIComponent(query)}&source=${encodeURIComponent(state.source)}&limit=${limit}`
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || `请求失败（${response.status}）`);
      }
      state.tracks = Array.isArray(data.results) ? data.results : [];
      renderResults();
    } catch (error) {
      state.tracks = [];
      showEmpty("搜索失败", error.message || "网络异常，请稍后再试。", "!");
      els.count.textContent = "—";
      toast(error.message || "搜索失败");
    } finally {
      setLoading(false);
    }
  }

  /* ---------- 事件绑定 ---------- */
  els.form.addEventListener("submit", (event) => {
    event.preventDefault();
    runSearch(els.input.value);
  });

  els.chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const query = chip.dataset.q || "";
      els.input.value = query;
      runSearch(query);
    });
  });

  els.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const source = tab.dataset.source;
      if (!source || source === state.source) return;
      state.source = source;
      els.tabs.forEach((item) => item.classList.toggle("is-active", item === tab));
      if (state.query) runSearch(state.query);
    });
  });

  els.playBtn.addEventListener("click", togglePlay);
  els.prevBtn.addEventListener("click", () => step(-1));
  els.nextBtn.addEventListener("click", () => step(1));

  els.progress.addEventListener("pointerdown", () => {
    state.seeking = true;
  });

  els.progress.addEventListener("input", () => {
    const duration = els.audio.duration;
    paintRange(els.progress);
    if (Number.isFinite(duration) && duration > 0) {
      els.timeCurrent.textContent = formatTime((Number(els.progress.value) / 1000) * duration);
    }
  });

  window.addEventListener("pointerup", () => {
    if (!state.seeking) return;
    state.seeking = false;
    const duration = els.audio.duration;
    if (Number.isFinite(duration) && duration > 0) {
      els.audio.currentTime = (Number(els.progress.value) / 1000) * duration;
    }
  });

  els.volume.addEventListener("input", () => {
    const volume = Number(els.volume.value) / 100;
    els.audio.volume = volume;
    paintRange(els.volume);
    try {
      window.localStorage.setItem("mh-volume", String(volume));
    } catch (_error) {
      /* 隐私模式下忽略 */
    }
  });

  els.audio.addEventListener("play", () => setPlayingUI(true));
  els.audio.addEventListener("pause", () => setPlayingUI(false));

  els.audio.addEventListener("loadedmetadata", () => {
    const duration = els.audio.duration;
    if (Number.isFinite(duration)) {
      els.timeTotal.textContent = formatTime(duration);
    }
  });

  els.audio.addEventListener("timeupdate", () => {
    const duration = els.audio.duration;
    if (!Number.isFinite(duration) || duration <= 0) return;
    if (!state.seeking) {
      els.progress.value = String(Math.round((els.audio.currentTime / duration) * 1000));
      paintRange(els.progress);
    }
    els.timeCurrent.textContent = formatTime(els.audio.currentTime);
  });

  els.audio.addEventListener("ended", () => step(1));

  els.audio.addEventListener("error", () => {
    if (!els.audio.getAttribute("src")) return;
    toast("音频加载失败，可能已下架，换一首试试");
  });

  /* ---------- 初始化 ---------- */
  try {
    const savedVolume = Number(window.localStorage.getItem("mh-volume"));
    if (savedVolume >= 0 && savedVolume <= 1) {
      els.volume.value = String(Math.round(savedVolume * 100));
    }
  } catch (_error) {
    /* 忽略 */
  }

  els.audio.volume = Number(els.volume.value) / 100;
  paintRange(els.volume);
  paintRange(els.progress);
  setPlayingUI(false);
})();
