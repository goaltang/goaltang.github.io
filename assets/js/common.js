/* 首页和作品页共用：读 works.json、拼卡片、悬停静音预览前 3 秒。 */
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
  var touchPointer = window.matchMedia("(hover: none), (pointer: coarse)");
  var PREVIEW_SECONDS = 3;
  var FPS = 24;

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        var value = attrs[key];
        if (value === null || value === undefined || value === false) return;
        if (key === "class") node.className = value;
        else if (key === "text") node.textContent = value;
        else if (key === "html") node.innerHTML = value;
        else if (key === "style") node.setAttribute("style", value);
        else node.setAttribute(key, value === true ? "" : value);
      });
    }
    (children || []).forEach(function (child) {
      if (child === null || child === undefined || child === false) return;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return node;
  }

  function marks() {
    return el("span", { class: "marks", "aria-hidden": "true" }, [el("i"), el("i"), el("i"), el("i")]);
  }

  function pad(n, len) { n = String(Math.floor(n)); while (n.length < (len || 2)) n = "0" + n; return n; }

  function duration(seconds) {
    if (!seconds) return "";
    return pad(seconds / 60) + ":" + pad(Math.round(seconds % 60));
  }

  function durationWords(seconds) {
    if (!seconds) return "";
    var m = Math.floor(seconds / 60);
    var s = Math.round(seconds % 60);
    return (m ? m + " 分 " : "") + (s ? s + " 秒" : "");
  }

  // 时间码 mm:ss:ff（24 帧）
  function timecode(seconds) {
    seconds = Math.max(0, seconds || 0);
    return pad(seconds / 60) + ":" + pad(seconds % 60) + ":" + pad((seconds % 1) * FPS);
  }

  var state = { data: null };

  function load() {
    return fetch("data/works.json", { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("data/works.json 读取失败（" + r.status + "）");
        return r.json();
      })
      .then(function (data) {
        state.data = data;
        return data;
      });
  }

  function isTall(work) { return work.ratio === "9:16"; }
  function isSoon(work) { return work.status === "soon"; }
  function hasVideo(work) { return work.video !== false && !isSoon(work); }
  function cover(work) { return "covers/" + work.id + ".jpg"; }
  function film(work) { return state.data.site.films + work.id + ".mp4"; }
  function fullFilm(work) { return state.data.site.fullBase + work.id + ".mp4"; }
  function page(work, play) { return "work.html?id=" + encodeURIComponent(work.id) + (play ? "#play" : ""); }
  function ratioLabel(work) { return isTall(work) ? "9:16" : "16:9"; }
  function inSection(work, id) { return work.series === id || (work.also || []).indexOf(id) >= 0; }

  /* ---------- 预览：鼠标悬停静音放前 3 秒；触屏第一次点静音放，再点才真打开 ---------- */

  var LIVE_TAG = "● 预览";
  var ARMED_TAG = "▶ 再点打开";
  var armedMedia = null;

  function liveTag(media, text) {
    var tag = media.querySelector(".tag.live");
    if (tag) tag.textContent = text;
  }

  function startPreview(media, src) {
    if (reduced.matches || !src) return;
    var clip = media.querySelector(".media-clip");
    var video = clip.querySelector("video");
    if (!video) {
      video = el("video", { muted: true, playsinline: true, preload: "auto", "aria-hidden": "true" });
      video.muted = true;
      video.playsInline = true;
      video.addEventListener("timeupdate", function () {
        if (video.currentTime >= PREVIEW_SECONDS) video.currentTime = 0;
      });
      // 播不了就当没预览过，别让第一下点击白吞掉
      video.addEventListener("error", function () {
        media._previewOn = false;
        video.remove();
        media.classList.remove("is-previewing");
        liveTag(media, LIVE_TAG);
      });
      video.src = src;
      clip.appendChild(video);
    }
    media._previewOn = true;
    clearTimeout(media._previewTimer);
    var p = video.play();
    if (p && p.then) {
      p.then(function () {
        if (!media._previewOn) return;
        video.classList.add("is-on");
        media.classList.add("is-previewing");
      }).catch(function () {});
    }
  }

  function stopPreview(media) {
    media._previewOn = false;
    if (armedMedia === media) armedMedia = null;
    media.classList.remove("is-previewing");
    liveTag(media, LIVE_TAG);
    var video = media.querySelector(".media-clip video");
    if (!video) return;
    video.classList.remove("is-on");
    clearTimeout(media._previewTimer);
    media._previewTimer = setTimeout(function () {
      if (media._previewOn) return;
      video.pause();
      video.removeAttribute("src");
      video.load();
      video.remove();
    }, 700);
  }

  // 触屏：第一下只预览（拦在卡片自己的「打开」之前），第二下才放行。
  // 监听必须先于卡片的 click 注册，同元素上按注册顺序触发。
  function tapPreview(media, src) {
    media.addEventListener("click", function (e) {
      if (!touchPointer.matches || reduced.matches) return;
      if (media._previewOn) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      if (armedMedia && armedMedia !== media) stopPreview(armedMedia);
      armedMedia = media;
      startPreview(media, src);
      if (media._previewOn) liveTag(media, ARMED_TAG);
    });
  }

  function hoverPreview(media, src) {
    media.addEventListener("pointerenter", function () { if (finePointer.matches) startPreview(media, src); });
    media.addEventListener("pointerleave", function () { if (finePointer.matches) stopPreview(media); });
    media.addEventListener("focus", function () { if (finePointer.matches) startPreview(media, src); });
    media.addEventListener("blur", function () { if (finePointer.matches) stopPreview(media); });
  }

  function attachPreview(media, src) {
    tapPreview(media, src);
    hoverPreview(media, src);
  }

  /* ---------- 卡片 ---------- */

  // 画面四角：左上比例，右上时长，左下编号，右下悬停时亮「预览」。
  function mediaTags(work, no) {
    return [
      el("span", { class: "tag tl", "aria-hidden": "true", text: ratioLabel(work) }),
      work.duration ? el("span", { class: "tag tr", "aria-hidden": "true", text: duration(work.duration) }) : null,
      no ? el("span", { class: "tag bl", "aria-hidden": "true", text: no }) : null,
      el("span", { class: "tag br live", "aria-hidden": "true", text: "● 预览" })
    ];
  }

  // opts.onPlay(work)：首页传入，点画面直接在放映窗里带声音放；作品页不传，点画面就进作品页。
  // opts.no：左下角编号；opts.feature：横排大卡；opts.groupTag：显示课本/生活系列。
  function card(work, opts) {
    opts = opts || {};
    var video = hasVideo(work);
    var soon = isSoon(work);
    var playable = video && opts.onPlay;
    var href = page(work, !video && work.figure);

    var media = el(playable ? "button" : (soon ? "div" : "a"), {
      class: "media" + (isTall(work) ? " t" : ""),
      type: playable ? "button" : null,
      href: playable || soon ? null : href,
      "data-cursor": soon ? null : (playable ? "播放" : video ? "打开" : "动手玩"),
      "aria-label": soon ? null : (playable ? "播放《" : video ? "打开《" : "动手玩《") + work.title + "》"
    }, [
      el("span", { class: "media-clip" }, [
        soon ? null : el("img", { src: cover(work), alt: "", loading: opts.eager ? "eager" : "lazy", decoding: "async" })
      ]),
      soon ? el("span", { class: "badge-soon" }, [el("span", { text: "待出片" })]) : null
    ].concat(soon ? [el("span", { class: "tag tl", "aria-hidden": "true", text: ratioLabel(work) })] : mediaTags(work, opts.no), [marks()]));
    // 预览的监听要先挂，触屏第一下才能在「打开」之前被拦下
    if (video) attachPreview(media, film(work));
    if (playable) {
      media.addEventListener("click", function () { stopPreview(media); opts.onPlay(work); });
    }

    var foot = [];
    if (work.level) foot.push(el("span", { class: "level", "data-level": work.level, text: "适合" + work.level }));
    if (opts.groupTag && work.group) foot.push(el("span", { class: "level", text: work.group === "textbook" ? "课本系列" : "生活系列" }));
    if (work.figure && opts.anatomy) {
      if (video) {
        foot.push(opts.onPlay
          ? el("button", { class: "btn magnetic", type: "button", "data-act": "watch" }, [icon("play"), "看视频"])
          : el("a", { class: "btn magnetic", href: page(work) }, [icon("play"), "看视频"]));
      }
      foot.push(el("a", { class: "btn magnetic", href: page(work, true) }, [icon("hand"), "动手玩"]));
    }

    var body = el("div", { class: "card-body" }, [
      el("h4", { class: "card-title" }, [soon ? work.title : el("a", { href: href, text: work.title })]),
      soon ? el("p", { class: "card-blurb", text: "还在做，做好就放上来。" }) : (work.blurb ? el("p", { class: "card-blurb", text: work.blurb }) : null),
      foot.length ? el("div", { class: "card-foot" }, foot) : null
    ]);

    var node = el("article", { class: "card" + (opts.feature ? " feature" : ""), "data-id": work.id }, [media, body]);
    var watch = node.querySelector('[data-act="watch"]');
    if (watch) watch.addEventListener("click", function () { opts.onPlay(work); });
    return node;
  }

  function icon(name) {
    var paths = {
      play: '<path d="M4 2.5v11l9-5.5z" fill="currentColor"/>',
      pause: '<path d="M4 2.5h3v11H4zM9 2.5h3v11H9z" fill="currentColor"/>',
      hand: '<path d="M6 8V3a1 1 0 0 1 2 0v4.5M8 7V2a1 1 0 0 1 2 0v5M10 7.5V3.5a1 1 0 0 1 2 0V10c0 2.5-1.8 4.5-4.3 4.5S4 13 3.2 11.4L1.8 8.6a1 1 0 0 1 1.7-1L6 10" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>',
      down: '<path d="M8 2v9M4 7.5 8 11.5l4-4M3 14h10" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
      out: '<path d="M9 2h5v5M14 2 7.5 8.5M12 9.5V14H2V4h4.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>',
      sound: '<path d="M2 6h3l4-3v10l-4-3H2zM11.5 5.5a3.5 3.5 0 0 1 0 5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/>'
    };
    var span = el("span", { "aria-hidden": "true", style: "display:inline-flex" });
    span.innerHTML = '<svg viewBox="0 0 16 16">' + paths[name] + "</svg>";
    return span;
  }

  window.Site = {
    el: el, marks: marks, icon: icon, load: load, state: state, card: card,
    pad: pad, duration: duration, durationWords: durationWords, timecode: timecode,
    isTall: isTall, isSoon: isSoon, hasVideo: hasVideo, inSection: inSection, ratioLabel: ratioLabel,
    cover: cover, film: film, fullFilm: fullFilm, page: page,
    startPreview: startPreview, stopPreview: stopPreview, attachPreview: attachPreview,
    reduced: reduced, finePointer: finePointer, touch: touchPointer
  };
})();
