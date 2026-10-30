/* 首页：首屏胶片墙、四卷作品、放映窗、竖屏长条、《拾星》对照。 */
(function () {
  "use strict";
  var S = window.Site;
  var M = window.Motion;
  var el = S.el;

  S.load().then(render).catch(function (err) {
    document.getElementById("works").appendChild(el("p", { class: "noscript", text: "作品清单没有读出来：" + err.message + "。请用 python -m http.server 在仓库根目录打开，而不是直接双击 index.html。" }));
    M.ready();
  });

  function render(data) {
    var shown = data.works.filter(function (w) { return !S.isSoon(w); });
    document.querySelector("[data-count-works]").textContent = S.pad(shown.length);
    document.querySelector("[data-count-series]").textContent = S.pad(data.sections.length);
    wall(shown);
    var main = document.getElementById("works");
    data.sections.forEach(function (sec, i) {
      var works = data.works.filter(function (w) { return S.inSection(w, sec.id); });
      main.appendChild(chapter(sec, works, i));
    });
    M.ready();
  }

  /* ---------- 首屏：三条胶片缓慢横走，几格是真视频 ---------- */

  function wall(shown) {
    var box = document.querySelector(".hero-wall");
    var withVideo = shown.filter(S.hasVideo);
    var lively = !S.reduced.matches && !S.touch.matches && !(navigator.connection && navigator.connection.saveData) && window.innerWidth > 720;
    var rows = 3;
    var perRow = Math.ceil(shown.length / rows) + 2;
    var videos = [];
    for (var r = 0; r < rows; r++) {
      var list = [];
      for (var k = 0; k < perRow; k++) list.push(shown[(r * 7 + k * 2 + r) % shown.length]);
      var liveAt = lively && r !== 1 ? (r === 0 ? 2 : 4) : -1;
      var frames = list.map(function (w, k) {
        var live = k === liveAt && S.hasVideo(w) ? w : (k === liveAt ? withVideo[(r * 3) % withVideo.length] : null);
        var shownWork = live || w;
        var frame = el("div", { class: "reel-frame", style: "aspect-ratio:" + (S.isTall(shownWork) ? "9/16" : (shownWork.group && !S.hasVideo(shownWork) ? "16/10" : "16/9")) }, [
          el("img", { src: S.cover(shownWork), alt: "", decoding: "async", loading: r === 1 ? "eager" : "lazy" }),
          el("span", { class: "tag", text: "F" + S.pad(r * perRow + k + 1, 3) + "  " + S.ratioLabel(shownWork) })
        ]);
        if (live) {
          var v = el("video", { muted: true, loop: true, playsinline: true, preload: "none" });
          v.muted = true;
          v.addEventListener("error", function () { v.remove(); });
          v.dataset.src = S.film(live);
          v.dataset.start = String(3 + r * 5);
          frame.appendChild(v);
          videos.push(v);
        }
        return frame;
      });
      // 复制一遍，动画走到一半正好接上
      var track = el("div", { class: "reel-track", style: "--dur:" + (110 + r * 30) + "s" }, frames.concat(frames.map(function (f) {
        var c = f.cloneNode(true);
        [].forEach.call(c.querySelectorAll("video"), function (v) { v.remove(); });
        return c;
      })));
      box.appendChild(el("div", { class: "reel-row" }, [track]));
    }
    if (!videos.length) return;
    new IntersectionObserver(function (entries) {
      videos.forEach(function (v) {
        if (entries[0].isIntersecting) {
          if (!v.getAttribute("src")) {
            v.src = v.dataset.src;
            v.addEventListener("loadedmetadata", function () { v.currentTime = Math.min(+v.dataset.start, (v.duration || 10) - 1); }, { once: true });
          }
          var p = v.play(); if (p && p.catch) p.catch(function () {});
        } else v.pause();
      });
    }).observe(document.querySelector(".hero"));
  }

  /* ---------- 卷 ---------- */

  var RATIO = { "16:9": "16:9 横屏", "9:16": "9:16 竖屏", mixed: "横竖混合" };

  function chapter(sec, works, i) {
    var no = S.pad(i + 1);
    var count = works.filter(function (w) { return !S.isSoon(w); }).length;
    var bandBits = [];
    for (var k = 0; k < 4; k++) bandBits.push(el("span", { text: sec.name }), el("em", { text: sec.brand }));

    var node = el("section", { class: "chapter" + (sec.id === "anatomy" ? " lightbox" : ""), id: sec.id, "aria-labelledby": sec.id + "-h" }, [
      el("div", { class: "chapter-meta", "aria-hidden": "true" }, [
        el("b", { text: "卷 " + no }),
        el("span", { text: RATIO[sec.ratio] }),
        el("span", { text: count + " 部" }),
        el("i", { class: "grow" }),
        el("span", { text: sec.brand })
      ]),
      el("div", { class: "band", "aria-hidden": "true" }, [el("div", { class: "band-track" }, bandBits)]),
      el("div", { class: "chapter-intro" }, [
        el("p", { class: "chapter-no", "aria-hidden": "true", text: no }),
        el("div", { class: "stack rv-fade" }, [
          el("h2", { id: sec.id + "-h", text: sec.title }),
          el("p", { text: sec.desc })
        ])
      ])
    ]);

    var opts = { onPlay: openViewer };
    if (sec.id === "manimgx") groups(node, sec, works, opts);
    else if (sec.id === "anatomy") anatomy(node, works);
    else if (sec.id === "opuscar") opus(node, works);
    else doodle(node, works);
    return node;
  }

  function numbered(list) {
    return function (w) { return S.pad(list.indexOf(w) + 1) + "/" + S.pad(list.length); };
  }

  // 01 讲解：学科做左栏，第一部横排放大，其余按数量分栏
  function groups(node, sec, works, opts) {
    var no = numbered(works);
    sec.groups.forEach(function (g) {
      var list = works.filter(function (w) { return w[sec.groupBy] === g.id; });
      if (!list.length) return;
      var rest = list.length - 1;
      var span = rest === 1 ? 6 : rest === 2 ? 3 : 2;
      node.appendChild(el("div", { class: "group" }, [
        el("div", { class: "group-label" }, [el("h3", { text: g.title }), el("span", { text: S.pad(list.length) + " 部" })]),
        el("div", { class: "grid" }, list.map(function (w, j) {
          var c = S.card(w, { onPlay: opts.onPlay, no: no(w), feature: j === 0 });
          c.classList.add("rv");
          if (j) c.style.setProperty("--span", span);
          c.style.setProperty("--n", j % 3);
          return c;
        }))
      ]));
    });
  }

  // 02 拆解：有视频的错位排；只有交互图的做成索引，悬停时封面跟着光标
  function anatomy(node, works) {
    var films = works.filter(S.hasVideo);
    var figs = works.filter(function (w) { return !S.hasVideo(w) && w.figure; });
    var no = numbered(films);
    node.appendChild(el("div", { class: "films" }, films.map(function (w, j) {
      var c = S.card(w, { onPlay: openViewer, anatomy: true, groupTag: true, no: no(w) });
      c.classList.add("rv");
      c.style.setProperty("--n", j % 2);
      return c;
    })));
    if (!figs.length) return;

    var peek = el("div", { class: "peek", "aria-hidden": "true" }, [el("img", { alt: "" })]);
    var peekImg = peek.firstChild;
    var rows = figs.map(function (w, j) {
      return el("li", {}, [el("a", { class: "index-row", href: S.page(w, true), "data-cursor": "动手玩", "data-cover": S.cover(w) }, [
        el("span", { class: "no", text: S.pad(j + 1) }),
        el("img", { src: S.cover(w), alt: "", loading: "lazy", decoding: "async" }),
        el("h4", { text: w.title }),
        el("span", { class: "grp", text: w.group === "textbook" ? "课本系列" : "生活系列" }),
        el("p", { text: w.blurb }),
        el("span", { class: "go", text: "动手玩" })
      ])]);
    });
    var index = el("div", { class: "index" }, [
      el("div", { class: "index-head rv-fade" }, [
        el("h3", { text: "只做了交互图的 " + figs.length + " 张" }),
        el("p", { text: "没有视频，打开就能拖、能按，看机器自己动起来。" })
      ]),
      el("ul", { class: "index-list" }, rows),
      peek
    ]);
    node.appendChild(index);

    if (!S.finePointer.matches || S.reduced.matches) return;
    var px = 0, py = 0, tx = 0, ty = 0, on = false, raf = 0;
    function follow() {
      px += (tx - px) * 0.18; py += (ty - py) * 0.18;
      peek.style.transform = "translate3d(" + (px + 40) + "px," + (py - 100) + "px,0)";
      raf = on ? requestAnimationFrame(follow) : 0;
    }
    index.addEventListener("pointermove", function (e) {
      tx = e.clientX; ty = e.clientY;
      var row = e.target.closest(".index-row");
      if (row) {
        if (peekImg.getAttribute("src") !== row.dataset.cover) peekImg.src = row.dataset.cover;
        if (!on) { on = true; px = tx; py = ty; peek.classList.add("is-on"); raf = raf || requestAnimationFrame(follow); }
      } else if (on) { on = false; peek.classList.remove("is-on"); }
    });
    index.addEventListener("pointerleave", function () { on = false; peek.classList.remove("is-on"); });
  }

  // 03 短片：横屏放左栏，竖屏在右边长条里上下滑
  function opus(node, works) {
    var wide = works.filter(function (w) { return !S.isTall(w); });
    var tall = works.filter(S.isTall);
    var no = numbered(works);
    node.appendChild(el("div", { class: "opus" }, [
      el("div", { class: "opus-wide" }, wide.map(function (w, j) {
        var c = S.card(w, { onPlay: openViewer, no: no(w) });
        c.classList.add("rv");
        return c;
      })),
      strip(tall)
    ]));
  }

  // 04 动画：两支竖屏错开放，下面是《拾星》对照
  function doodle(node, works) {
    var solo = works.filter(function (w) { return !w.pair; });
    var pairs = works.filter(function (w) { return w.pair; });
    var no = numbered(works);
    node.appendChild(el("div", { class: "doodle" }, solo.map(function (w, j) {
      var c = S.card(w, { onPlay: openViewer, no: no(w) });
      c.classList.add("rv");
      c.style.setProperty("--n", j);
      return c;
    }).concat(pairs.length === 2 ? [duel(pairs)] : [])));
  }

  /* ---------- 竖屏长条：上下滑，停在哪支就静音放哪支 ---------- */

  function strip(list) {
    var counter = el("b", { text: "01 / " + S.pad(list.length) });
    var box = el("div", { class: "strip", tabindex: "0", "data-lenis-prevent": "", "aria-label": "竖屏短片，滑动切换" }, list.map(function (w) {
      var soon = S.isSoon(w);
      var media = el(soon ? "div" : "button", {
        class: "media t", type: soon ? null : "button", "data-cursor": soon ? null : "播放",
        "aria-label": soon ? null : "播放《" + w.title + "》"
      }, [
        el("span", { class: "media-clip" }, [soon ? null : el("img", { src: S.cover(w), alt: "", loading: "lazy", decoding: "async" })]),
        soon ? el("span", { class: "badge-soon" }, [el("span", { text: "待出片" })]) : null,
        el("span", { class: "tag tl", "aria-hidden": "true", text: "9:16" }),
        w.duration ? el("span", { class: "tag tr", "aria-hidden": "true", text: S.duration(w.duration) }) : null,
        soon ? null : el("span", { class: "tag br live", "aria-hidden": "true", text: "● 预览" }),
        S.marks()
      ]);
      if (!soon) media.addEventListener("click", function () { S.stopPreview(media); openViewer(w); });
      return el("div", { class: "strip-item", "data-film": soon ? "" : S.film(w) }, [
        media,
        el("div", { class: "strip-cap" }, [
          el("h4", { text: w.title }),
          soon ? el("p", { text: "还在做，做好就放上来。" }) : (w.blurb ? el("p", { text: w.blurb.length > 40 ? w.blurb.slice(0, 39) + "…" : w.blurb }) : null)
        ])
      ]);
    }));

    var hint = el("p", { class: "strip-hint" });
    var wrap = el("div", { class: "strip-wrap rv-fade" }, [
      el("div", { class: "strip-label" }, [el("span", { text: "竖屏 9:16" }), counter]),
      box,
      hint
    ]);

    // 桌面上是竖着滑，手机上（≤640）CSS 把它改成横着滑，提示和方向键跟着换
    function horizontal() { return box.scrollWidth > box.clientWidth + 1; }
    function syncHint() {
      if (list.length < 2) hint.textContent = "点开带声音看。";
      else if (horizontal()) hint.textContent = "左右滑，换下一支。点开带声音看。";
      else hint.textContent = "在框里上下滑，换下一支。点开带声音看。";
    }
    requestAnimationFrame(syncHint);
    var narrow = window.matchMedia("(max-width: 640px)");
    if (narrow.addEventListener) narrow.addEventListener("change", function () { requestAnimationFrame(syncHint); });

    var items = [].slice.call(box.children);
    var current = null;
    var visible = false;
    function playCurrent() {
      items.forEach(function (it) {
        var media = it.querySelector(".media");
        if (it === current && visible && it.dataset.film) S.startPreview(media, it.dataset.film);
        else S.stopPreview(media);
      });
    }
    var inner = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          current = e.target;
          counter.textContent = S.pad(items.indexOf(current) + 1) + " / " + S.pad(items.length);
        }
      });
      playCurrent();
    }, { root: box, threshold: 0.6 });
    items.forEach(function (it) { inner.observe(it); });
    new IntersectionObserver(function (entries) {
      visible = entries[0].isIntersecting;
      playCurrent();
    }, { threshold: 0.5 }).observe(box);

    box.addEventListener("keydown", function (e) {
      var back = e.key === "ArrowUp" || e.key === "ArrowLeft";
      var fwd = e.key === "ArrowDown" || e.key === "ArrowRight";
      if (!back && !fwd) return;
      e.preventDefault();
      var across = horizontal();
      var step = (back ? -1 : 1) * (across ? box.clientWidth : box.clientHeight);
      var to = { behavior: S.reduced.matches ? "auto" : "smooth" };
      if (across) to.left = step; else to.top = step;
      box.scrollBy(to);
    });
    return wrap;
  }

  /* ---------- 《拾星》：同一提示词，两个 AI，并排同步放 ---------- */

  function duel(pair) {
    var sides = pair.map(function (w) {
      var video = el("video", { playsinline: true, muted: true, preload: "none", poster: S.cover(w), "aria-label": w.title });
      video.muted = true;
      var media = el("div", { class: "media t" }, [
        el("span", { class: "media-clip" }, [video]),
        el("span", { class: "tag tl", "aria-hidden": "true", text: "9:16" }),
        el("span", { class: "tag tr", "aria-hidden": "true", text: S.duration(w.duration) }),
        el("span", { class: "tag bl", "aria-hidden": "true", text: w.maker }),
        S.marks()
      ]);
      video.style.clipPath = "none";
      return {
        work: w, video: video, media: media,
        node: el("div", { class: "duel-side rv" }, [
          media,
          el("div", { class: "duel-maker" }, [el("b", { text: w.maker }), el("a", { href: S.page(w), text: "单独看这一版" })])
        ])
      };
    });

    var tc = el("p", { class: "duel-tc", "aria-hidden": "true", text: "00:00:00" });
    var head = el("i");
    var bar = el("div", { class: "duel-bar", role: "slider", tabindex: "0", "aria-label": "两版一起跳到", "aria-valuemin": "0", "aria-valuemax": String(pair[0].duration), "aria-valuenow": "0" }, [head]);
    var playBoth = el("button", { class: "btn primary magnetic", type: "button" }, [S.icon("play"), el("span", { text: "两版一起放" })]);
    var listen = sides.map(function (s) {
      return el("button", { class: "btn magnetic", type: "button", "aria-pressed": "false" }, [S.icon("sound"), "听 " + s.work.maker + " 版"]);
    });

    function ensureSrc(s) { if (!s.video.getAttribute("src")) s.video.src = S.film(s.work); }
    function playing() { return sides.some(function (s) { return !s.video.paused; }); }
    function setPlayLabel() {
      var on = playing();
      playBoth.replaceChild(S.icon(on ? "pause" : "play"), playBoth.firstChild);
      playBoth.lastChild.textContent = on ? "两版一起停" : "两版一起放";
    }
    function startBoth(fromZero) {
      sides.forEach(function (s) { ensureSrc(s); if (fromZero) s.video.currentTime = 0; });
      sides.forEach(function (s) { var p = s.video.play(); if (p && p.catch) p.catch(function () {}); });
    }
    function setLoud(index) {
      sides.forEach(function (s, i) {
        s.video.muted = i !== index;
        s.media.classList.toggle("is-loud", i === index);
        listen[i].setAttribute("aria-pressed", i === index ? "true" : "false");
      });
    }
    function seek(ratio) {
      sides.forEach(function (s) {
        ensureSrc(s);
        var d = s.video.duration || s.work.duration;
        s.video.currentTime = Math.max(0, Math.min(d - 0.05, ratio * d));
      });
    }

    playBoth.addEventListener("click", function () {
      if (playing()) sides.forEach(function (s) { s.video.pause(); });
      else startBoth(sides[0].video.ended || !sides[0].video.currentTime);
    });
    listen.forEach(function (btn, i) {
      btn.addEventListener("click", function () {
        var already = btn.getAttribute("aria-pressed") === "true";
        setLoud(already ? -1 : i);
        if (!already && !playing()) startBoth(true);
      });
    });
    bar.addEventListener("click", function (e) {
      var r = bar.getBoundingClientRect();
      seek((e.clientX - r.left) / r.width);
    });
    bar.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      var v = sides[0].video;
      seek(((v.currentTime || 0) + (e.key === "ArrowRight" ? 2 : -2)) / (v.duration || pair[0].duration));
    });
    sides.forEach(function (s) {
      s.video.addEventListener("play", setPlayLabel);
      s.video.addEventListener("pause", setPlayLabel);
      s.video.addEventListener("error", function () { s.video.removeAttribute("src"); });
    });
    sides[0].video.addEventListener("timeupdate", function () {
      var v = sides[0].video;
      var d = v.duration || pair[0].duration;
      tc.textContent = S.timecode(v.currentTime);
      bar.style.setProperty("--x", (v.currentTime / d * bar.clientWidth) + "px");
      bar.setAttribute("aria-valuenow", String(Math.round(v.currentTime)));
    });

    return el("div", { class: "duel", id: "duel" }, [
      el("div", { class: "duel-head" }, [
        el("h3", { text: "《" + pair[0].pair + "》两个版本" }),
        el("p", { text: "同一段提示词，分别交给 " + pair.map(function (w) { return w.maker; }).join(" 和 ") + "。两版同时放，声音一次听一边。" })
      ]),
      sides[0].node,
      el("div", { class: "duel-mid" }, [tc, bar, playBoth].concat(listen, [el("p", { class: "duel-note", text: "拖动或点刻度条，两版一起跳。" })])),
      sides[1].node
    ]);
  }

  /* ---------- 放映窗：点卡片，带声音放 ---------- */

  var viewer = document.getElementById("viewer");
  var vStage = viewer.querySelector(".viewer-stage");
  var vVideo = viewer.querySelector("video");
  var vTitle = viewer.querySelector(".viewer-top h3");
  var vTc = viewer.querySelector("[data-viewer-tc]");
  var vActions = viewer.querySelector(".viewer-actions");
  var lastFocus = null;

  vVideo.addEventListener("error", function () { if (vVideo.getAttribute("src")) vStage.classList.add("is-missing"); });
  vVideo.addEventListener("timeupdate", function () { vTc.textContent = S.timecode(vVideo.currentTime); });

  function openViewer(work) {
    lastFocus = document.activeElement;
    vStage.classList.remove("is-missing");
    vTitle.textContent = work.title;
    vTc.textContent = "00:00:00";
    vActions.innerHTML = "";
    vActions.appendChild(el("a", { class: "btn", href: S.page(work) }, ["作品页"]));
    if (work.figure) vActions.appendChild(el("a", { class: "btn", href: S.page(work, true) }, [S.icon("hand"), "动手玩"]));
    vActions.appendChild(el("a", { class: "btn primary", href: S.fullFilm(work), download: true }, [S.icon("down"), "下载完整版"]));
    viewer.querySelector(".viewer-msg span").textContent = "这支片子的预览还没放进 films/ 文件夹。可以先下载完整版。";
    vVideo.poster = S.cover(work);
    vVideo.src = S.film(work);
    vVideo.muted = false;
    M.lock();
    if (typeof viewer.showModal === "function") viewer.showModal(); else viewer.setAttribute("open", "");
    var p = vVideo.play();
    if (p && p.catch) p.catch(function () {});
  }

  function closeViewer() {
    if (viewer.open && typeof viewer.close === "function") viewer.close();
    else { viewer.removeAttribute("open"); onClose(); }
  }
  function onClose() {
    vVideo.pause();
    vVideo.removeAttribute("src");
    vVideo.load();
    M.unlock();
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }

  viewer.addEventListener("close", onClose);
  viewer.querySelector(".viewer-close").addEventListener("click", closeViewer);
  viewer.addEventListener("click", function (e) { if (e.target === viewer) closeViewer(); });
})();
