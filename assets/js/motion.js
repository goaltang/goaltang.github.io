/* 两页共用的动效：平滑滚动（Lenis）、滚动联动（GSAP ScrollTrigger）、时间码、自定义光标、磁吸按钮、换页快门。
   减少动效时：不开 Lenis 和联动，光标不跟随延迟，磁吸和快门都关掉。 */
(function () {
  "use strict";
  var S = window.Site;
  var root = document.documentElement;
  var reduced = S.reduced.matches;
  var fine = S.finePointer.matches;
  var touch = S.touch.matches;
  var gsap = window.gsap;
  var ST = window.ScrollTrigger;
  var lenis = null;

  if (gsap && ST) gsap.registerPlugin(ST);

  /* ---------- 平滑滚动（触屏上交给系统，少一层惯性接管） ---------- */

  if (!reduced && !touch && window.Lenis) {
    lenis = new window.Lenis({ lerp: 0.1, smoothWheel: true });
    if (gsap && ST) {
      lenis.on("scroll", ST.update);
      gsap.ticker.add(function (t) { lenis.raf(t * 1000); });
      gsap.ticker.lagSmoothing(0);
    } else {
      (function raf(t) { lenis.raf(t); requestAnimationFrame(raf); })(performance.now());
    }
  }

  function scrollToTarget(target) {
    if (lenis) lenis.scrollTo(target, { offset: -64, duration: 1.4 });
    else target.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  }

  // 顶栏：往下滚时收起，往上滚时出来；过了首屏给顶栏一块实底，
  // 米白的拆解卷上字标和「菜单」也看得清（窄屏 CSS 才用这块底色）
  var lastY = window.scrollY;
  var heroBox = document.querySelector(".hero");
  function syncTopBar() {
    root.classList.toggle("is-past-hero", !heroBox || window.scrollY > heroBox.offsetHeight - 72);
  }
  syncTopBar();
  window.addEventListener("scroll", function () {
    var y = window.scrollY;
    root.classList.toggle("is-scrolled-down", y > lastY && y > 240);
    syncTopBar();
    lastY = y;
  }, { passive: true });
  window.addEventListener("resize", syncTopBar);

  /* ---------- 手机菜单 ---------- */

  var menuBtn = document.querySelector(".menu-btn");
  var topNav = document.querySelector(".top-nav");
  if (menuBtn && topNav) {
    var menuLabel = menuBtn.querySelector(".menu-label");
    var setMenu = function (open) {
      root.classList.toggle("is-menu-open", open);
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
      if (menuLabel) menuLabel.textContent = open ? "关闭" : "菜单";
    };
    menuBtn.addEventListener("click", function () {
      setMenu(!root.classList.contains("is-menu-open"));
    });
    topNav.addEventListener("click", function (e) { if (e.target.closest("a")) setMenu(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape" || !root.classList.contains("is-menu-open")) return;
      setMenu(false);
      menuBtn.focus();
    });
    var wide = window.matchMedia("(min-width: 641px)");
    var closeOnWide = function () { if (wide.matches) setMenu(false); };
    if (wide.addEventListener) wide.addEventListener("change", closeOnWide); else wide.addListener(closeOnWide);
  }

  /* ---------- 时间码与帧计数 ---------- */

  var t0 = performance.now();
  var tcNodes = [].slice.call(document.querySelectorAll("[data-tc]"));
  var frameNodes = [].slice.call(document.querySelectorAll("[data-frame]"));
  var lastFrame = -1;
  var lastBucket = -1;
  function tick() {
    var sec = (performance.now() - t0) / 1000;
    var frame = Math.floor(sec * 24);
    if (reduced) frame = Math.floor(sec) * 24;
    // 触屏上时间码一秒跳一次就够，别每帧写 DOM
    var bucket = touch ? Math.floor(sec) : frame;
    if (frame !== lastFrame && bucket !== lastBucket) {
      lastFrame = frame;
      lastBucket = bucket;
      var tc = S.pad(sec / 3600) + ":" + S.pad((sec / 60) % 60) + ":" + S.pad(sec % 60) + ":" + S.pad(reduced ? 0 : frame % 24);
      tcNodes.forEach(function (n) { n.textContent = tc; });
      frameNodes.forEach(function (n) { n.textContent = S.pad(frame, 6); });
    }
    if (!document.hidden) requestAnimationFrame(tick);
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) requestAnimationFrame(tick); });
  requestAnimationFrame(tick);

  /* ---------- 自定义光标：悬停在视频上变成「播放」圆标 ---------- */

  var cursor = document.querySelector(".cursor");
  if (cursor && fine && !touch) {
    root.classList.add("has-cursor");
    var dot = cursor.querySelector(".cursor-dot");
    var ring = cursor.querySelector(".cursor-ring");
    var label = ring.querySelector("b");
    var mx = -100, my = -100, rx = -100, ry = -100, running = false;
    function loop() {
      rx += (mx - rx) * (reduced ? 1 : 0.2);
      ry += (my - ry) * (reduced ? 1 : 0.2);
      ring.style.transform = "translate3d(" + rx + "px," + ry + "px,0)";
      if (Math.abs(mx - rx) > 0.1 || Math.abs(my - ry) > 0.1) requestAnimationFrame(loop);
      else running = false;
    }
    document.addEventListener("pointermove", function (e) {
      if (e.pointerType !== "mouse") return;
      mx = e.clientX; my = e.clientY;
      dot.style.transform = "translate3d(" + mx + "px," + my + "px,0)";
      cursor.classList.remove("is-hidden");
      if (!running) { running = true; requestAnimationFrame(loop); }
    }, { passive: true });
    document.addEventListener("pointerover", function (e) {
      var t = e.target.closest && e.target.closest("[data-cursor]");
      if (t) label.textContent = t.getAttribute("data-cursor");
      cursor.classList.toggle("is-label", !!t);
      // 交互图 iframe 里收不到事件，先藏起来
      cursor.classList.toggle("is-hidden", e.target.tagName === "IFRAME");
    });
    document.documentElement.addEventListener("pointerleave", function () { cursor.classList.add("is-hidden"); });
  }

  /* ---------- 磁吸按钮 ---------- */

  function magnetize(scope) {
    if (reduced || touch || !fine) return;
    [].forEach.call((scope || document).querySelectorAll(".magnetic:not([data-mag])"), function (node) {
      node.setAttribute("data-mag", "");
      var strength = node.classList.contains("hero-cue") ? 0.45 : 0.3;
      var move = gsap
        ? { x: gsap.quickTo(node, "x", { duration: 0.6, ease: "power3" }), y: gsap.quickTo(node, "y", { duration: 0.6, ease: "power3" }) }
        : null;
      function set(x, y) {
        if (move) { move.x(x); move.y(y); }
        else node.style.transform = "translate(" + x + "px," + y + "px)";
      }
      node.addEventListener("pointermove", function (e) {
        var r = node.getBoundingClientRect();
        set((e.clientX - r.left - r.width / 2) * strength, (e.clientY - r.top - r.height / 2) * strength);
      });
      node.addEventListener("pointerleave", function () { set(0, 0); });
    });
  }

  /* ---------- 换页快门 ---------- */

  if (root.classList.contains("is-cut-in")) {
    sessionStorage.removeItem("cut");
    setTimeout(function () { root.classList.remove("is-cut-in"); }, 1300);
  }
  window.addEventListener("pageshow", function (e) {
    if (e.persisted) root.classList.remove("is-leaving", "is-cut-in");
  });

  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a || a.target === "_blank" || a.hasAttribute("download")) return;
    var url = new URL(a.href, location.href);
    if (url.origin !== location.origin) return;

    // 同一页里的锚点：交给平滑滚动
    if (url.pathname === location.pathname && url.search === location.search && url.hash) {
      var target = document.getElementById(decodeURIComponent(url.hash.slice(1)));
      if (target) { e.preventDefault(); scrollToTarget(target); history.replaceState(null, "", url.hash); }
      return;
    }
    if (!/\.html$|\/$/.test(url.pathname)) return;
    if (reduced || touch) return;
    e.preventDefault();
    sessionStorage.setItem("cut", "1");
    root.classList.add("is-leaving");
    setTimeout(function () { location.href = url.href; }, 520);
  });

  /* ---------- 滚动显露与联动 ---------- */

  var io = ("IntersectionObserver" in window && !reduced) ? new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); }
    });
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.01 }) : null;

  function reveal(scope) {
    [].forEach.call((scope || document).querySelectorAll(".rv, .rv-fade"), function (n) {
      if (io) io.observe(n); else n.classList.add("is-in");
    });
  }

  function scrub(scope) {
    if (reduced || touch || !gsap || !ST) return;
    scope = scope || document;
    // 分区跨栏大标题：滚动时横向位移，单双卷方向相反
    [].forEach.call(scope.querySelectorAll(".band-track"), function (track, i) {
      var left = i % 2 === 0;
      gsap.fromTo(track, { xPercent: left ? 0 : -28 }, {
        xPercent: left ? -28 : 0, ease: "none",
        scrollTrigger: { trigger: track.parentNode, start: "top bottom", end: "bottom top", scrub: 0.6 }
      });
    });
    [].forEach.call(scope.querySelectorAll(".chapter-intro .chapter-no"), function (no) {
      gsap.fromTo(no, { yPercent: 30 }, { yPercent: -10, ease: "none", scrollTrigger: { trigger: no, start: "top bottom", end: "bottom 40%", scrub: true } });
    });
  }

  function hero() {
    if (reduced || touch || !gsap || !ST || !document.querySelector(".hero")) return;
    var tl = gsap.timeline({ scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });
    tl.to(".wordmark", { yPercent: -38, ease: "none" }, 0)
      .to(".hero-wall", { yPercent: 14, scale: 1.08, ease: "none" }, 0)
      .to(".hero-copy", { yPercent: -60, opacity: 0, ease: "none" }, 0);
  }

  // 字标撑满一行：按实际字宽算字号
  function fitWordmark() {
    var wm = document.querySelector(".wordmark");
    if (!wm) return;
    var cs = getComputedStyle(wm);
    var avail = wm.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    wm.style.setProperty("--wm", "100px");
    var used = 0;
    [].forEach.call(wm.children, function (c) { used += c.getBoundingClientRect().width; });
    if (used > 0) wm.style.setProperty("--wm", Math.floor(100 * avail / used * 0.985) + "px");
  }
  if (document.querySelector(".wordmark")) {
    fitWordmark();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { fitWordmark(); if (ST) ST.refresh(); });
    var rt;
    window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(fitWordmark, 120); });
  }

  // 当前所在分区，在顶栏标出来
  function navSpy() {
    var links = [].slice.call(document.querySelectorAll('.top-nav a[href^="#"]'));
    if (!links.length || !("IntersectionObserver" in window)) return;
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        links.forEach(function (l) { l.classList.toggle("is-here", l.getAttribute("href") === "#" + en.target.id); });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    links.forEach(function (l) { var t = document.querySelector(l.getAttribute("href")); if (t) spy.observe(t); });
  }

  // 页面内容渲染完后调用
  function ready(scope) {
    magnetize(scope);
    reveal(scope);
    scrub(scope);
    if (!scope) { hero(); navSpy(); }
    if (ST) ST.refresh();
    requestAnimationFrame(function () { root.classList.add("is-ready"); });
    if (location.hash && !scope) {
      var target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (target) setTimeout(function () { scrollToTarget(target); }, 60);
    }
  }

  window.Motion = {
    ready: ready,
    lock: function () { if (lenis) lenis.stop(); },
    unlock: function () { if (lenis) lenis.start(); },
    scrollTo: scrollToTarget,
    refresh: function () { if (ST) ST.refresh(); }
  };
})();
