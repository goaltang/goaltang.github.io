/* 作品页：work.html?id=<作品 id>，带 #play 时直接打开交互图。 */
(function () {
  "use strict";
  var S = window.Site;
  var M = window.Motion;
  var el = S.el;
  var main = document.getElementById("work");
  var id = new URLSearchParams(location.search).get("id");

  S.load().then(function (data) {
    var work = data.works.filter(function (w) { return w.id === id; })[0];
    if (!work) missing(); else render(data, work);
    M.ready();
  }).catch(function (err) {
    main.appendChild(el("p", { text: "作品清单没有读出来：" + err.message + "。" }));
    M.ready();
  });

  function setMeta(selector, attribute, value) {
    var node = document.querySelector(selector);
    if (node) node.setAttribute(attribute, value);
  }

  function missing() {
    document.title = "找不到这部作品 · TaopleOne";
    main.appendChild(el("h1", { class: "work-title", text: "找不到这部作品" }));
    main.appendChild(el("p", { class: "work-blurb" }, ["链接里的作品编号不在清单里，可能已经改名。", el("a", { href: "./", text: "回首页看全部作品" }), "。"]));
  }

  function render(data, work) {
    var secIndex = 0;
    var sec = data.sections.filter(function (s, i) { if (s.id === work.series) { secIndex = i; return true; } return false; })[0];
    var secNo = S.pad(secIndex + 1);
    var siblings = data.works.filter(function (w) { return S.inSection(w, sec.id); });
    var workNo = S.pad(siblings.indexOf(work) + 1) + "/" + S.pad(siblings.length);
    document.title = work.title + " · TaopleOne";
    if (work.blurb) document.querySelector('meta[name="description"]').setAttribute("content", work.blurb);
    // 分享卡片和 canonical 指向 build.py 生成的静态页 work/<id>.html（爬虫不用跑 JS 就能拿到这些值）
    var base = (data.site && data.site.url) || "";
    if (base) {
      var canonical = base + "work/" + work.id + ".html";
      var cover = base + "covers/" + work.id + ".jpg";
      var title = work.title + " · TaopleOne";
      setMeta('link[rel="canonical"]', "href", canonical);
      setMeta('meta[property="og:url"]', "content", canonical);
      setMeta('meta[property="og:title"]', "content", title);
      setMeta('meta[name="twitter:title"]', "content", title);
      setMeta('meta[property="og:image"]', "content", cover);
      setMeta('meta[name="twitter:image"]', "content", cover);
      if (work.blurb) {
        setMeta('meta[property="og:description"]', "content", work.blurb);
        setMeta('meta[name="twitter:description"]', "content", work.blurb);
      }
    }

    main.appendChild(el("a", { class: "work-back magnetic", href: "./#" + sec.id }, [el("b", { text: "卷 " + secNo }), "回到" + sec.name + "（" + sec.brand + "）"]));
    main.appendChild(el("h1", { class: "work-title", text: work.title }));

    var video = S.hasVideo(work);
    var figure = work.figure ? "figures/" + work.figure + ".html" : null;
    var stage = el("div", { class: "stage" });
    var tc = el("b", { text: "00:00:00" });
    var mode = el("span");
    var chrome = el("div", { class: "stage-chrome", "aria-hidden": "true" }, [
      el("span", {}, [mode]),
      el("span", { text: workNo }),
      el("span", {}, ["TC ", tc])
    ]);
    var tabs = null;

    if (video && figure) {
      tabs = el("div", { class: "tabs", role: "tablist", "aria-label": "看视频或动手玩" }, [
        el("button", { type: "button", role: "tab", "data-tab": "video", text: "看视频" }),
        el("button", { type: "button", role: "tab", "data-tab": "figure", text: "动手玩" })
      ]);
      tabs.addEventListener("click", function (e) {
        var t = e.target.closest("[data-tab]");
        if (t) show(t.dataset.tab, true);
      });
      main.appendChild(tabs);
    }
    main.appendChild(el("div", { class: "stage-wrap rv-fade" }, [chrome, stage]));

    var player = null;
    function show(which, byUser) {
      if (tabs) [].forEach.call(tabs.children, function (b) { b.setAttribute("aria-selected", b.dataset.tab === which ? "true" : "false"); });
      if (player) player.pause();
      stage.innerHTML = "";
      if (which === "figure") {
        stage.className = "stage fig";
        mode.textContent = "交互图  拖动、点击都可以";
        tc.textContent = "实时";
        stage.appendChild(el("iframe", { src: figure, title: work.title + "（可交互）", loading: "lazy", allow: "fullscreen" }));
        if (byUser) history.replaceState(null, "", "#play");
      } else {
        stage.className = "stage " + (S.isTall(work) ? "t" : "w");
        mode.textContent = S.ratioLabel(work) + "  " + (S.isTall(work) ? "竖屏" : "横屏");
        tc.textContent = S.timecode(player ? player.currentTime : 0);
        player = player || makePlayer();
        stage.appendChild(player);
        if (byUser) {
          history.replaceState(null, "", location.pathname + location.search);
          var p = player.play();
          if (p && p.catch) p.catch(function () {});
        }
      }
      stage.appendChild(S.marks());
    }

    function makePlayer() {
      var v = el("video", { controls: true, playsinline: true, preload: "metadata", poster: S.cover(work) });
      v.addEventListener("error", function () {
        stage.appendChild(el("div", { class: "stage-msg" }, [el("span", { text: "这支片子的预览还没放进 films/ 文件夹。可以先下载完整版。" })]));
      });
      v.addEventListener("timeupdate", function () { tc.textContent = S.timecode(v.currentTime); });
      v.src = S.film(work);
      return v;
    }

    if (S.isSoon(work)) {
      stage.className = "stage " + (S.isTall(work) ? "t" : "w");
      mode.textContent = "待出片";
      stage.appendChild(el("div", { class: "stage-msg" }, [el("span", { text: "还在做，做好就放上来。" })]));
    } else if (figure && (!video || location.hash === "#play")) {
      show("figure");
    } else {
      show("video");
      // 从首页点进来时试着直接带声音放；浏览器不允许就停在封面，按播放即可
      var p = player.play();
      if (p && p.catch) p.catch(function () {});
    }

    // 场记板
    var slate = [["卷", secNo + "  " + sec.name], ["编号", workNo]];
    slate.push(["时长", work.duration ? S.duration(work.duration) : (video ? "—" : "交互图")]);
    slate.push(["画幅", S.ratioLabel(work) + (S.isTall(work) ? " 竖屏" : " 横屏")]);
    if (work.level) slate.push(["适合", work.level]);
    if (work.group) slate.push(["系列", work.group === "textbook" ? "课本系列" : "生活系列"]);
    if (work.maker) slate.push(["制作", work.maker]);
    if (slate.length % 2) slate.push(["制作人", "TaopleOne"]);

    var actions = [];
    if (video) actions.push(el("a", { class: "btn primary magnetic", href: S.fullFilm(work), download: true }, [S.icon("down"), "下载完整版"]));
    if (work.bilibili) actions.push(el("a", { class: "btn magnetic", href: work.bilibili, rel: "noopener" }, [S.icon("out"), "在 B 站看"]));
    if (figure) actions.push(el("a", { class: "btn magnetic", href: figure, target: "_blank", rel: "noopener" }, [S.icon("out"), "全屏打开交互图"]));

    main.appendChild(el("div", { class: "work-info" }, [
      el("dl", { class: "slate rv-fade" }, slate.map(function (row) {
        return el("div", {}, [el("dt", { text: row[0] }), el("dd", { text: row[1] })]);
      })),
      el("div", { class: "work-text rv-fade" }, [
        work.blurb || S.isSoon(work) ? el("p", { class: "work-blurb", text: work.blurb || "还在做，简介之后补上。" }) : null,
        actions.length ? el("div", { class: "work-actions" }, actions) : null
      ])
    ]));

    var more = siblings.filter(function (w) { return w.id !== work.id && !S.isSoon(w); });
    if (more.length) {
      var tall = sec.ratio === "9:16";
      var list = more.slice(0, tall ? 4 : 3);
      main.appendChild(el("section", { class: "work-more", "aria-labelledby": "more-h" }, [
        el("div", { class: "work-more-head" }, [
          el("h2", { id: "more-h", text: "同一卷里的其他作品" }),
          el("span", { text: "卷 " + secNo + "  " + sec.brand })
        ]),
        el("div", { class: "grid " + (tall ? "tall" : "wide") }, list.map(function (w, j) {
          var c = S.card(w, { anatomy: sec.id === "anatomy", no: S.pad(siblings.indexOf(w) + 1) + "/" + S.pad(siblings.length) });
          c.classList.add("rv");
          c.style.setProperty("--n", j);
          return c;
        }))
      ]));
    }
  }
})();
