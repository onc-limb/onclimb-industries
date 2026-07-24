(function () {
  "use strict";

  var params = new URLSearchParams(location.search);
  var currentPath = params.get("path");
  var contentEl = document.querySelector(".content");

  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function fillPlaceholders(text) {
    var d = new Date();
    var date = d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
    var time = pad(d.getHours()) + ":" + pad(d.getMinutes());
    return text
      .replace(/\{\{date\}\}/g, date)
      .replace(/\{\{time\}\}/g, time)
      .replace(/\{\{datetime\}\}/g, date + " " + time);
  }

  function isTyping() {
    var el = document.activeElement;
    return (
      el &&
      (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT")
    );
  }

  // ---- mermaid / highlight.js のレンダリング（vendored、無ければ何もしない）----
  if (window.mermaid) {
    mermaid.initialize({
      startOnLoad: false,
      theme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default",
    });
  }
  function renderExtras(root) {
    if (window.hljs) {
      root.querySelectorAll("pre code").forEach(function (el) {
        if (!el.dataset.hl) {
          try { hljs.highlightElement(el); } catch (e) {}
          el.dataset.hl = "1";
        }
      });
    }
    if (window.mermaid) {
      var nodes = root.querySelectorAll(".mermaid:not([data-processed])");
      if (nodes.length) {
        try { mermaid.run({ nodes: nodes }); } catch (e) {}
      }
    }
  }
  renderExtras(document);

  // ---- パスを開く・新規作成（サイドバー）----
  var newForm = document.getElementById("newnote-form");
  if (newForm) {
    newForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var input = document.getElementById("newnote-path");
      var p = input.value.trim().replace(/^\/+/, "");
      if (!p) return;
      if (!/\.md$/i.test(p)) p += ".md";
      location.href = "/edit?path=" + encodeURIComponent(p);
    });
  }

  // ---- ツリー表示フォルダの追加・削除 ----
  var rootMsg = document.getElementById("root-msg");
  function rootsRequest(bodyObj) {
    fetch("/api/roots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bodyObj),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) {
          location.reload();
        } else if (rootMsg) {
          rootMsg.textContent = d.error || "変更に失敗しました";
        }
      })
      .catch(function (err) {
        if (rootMsg) rootMsg.textContent = "変更に失敗しました: " + err;
      });
  }
  var addRootForm = document.getElementById("addroot-form");
  if (addRootForm) {
    addRootForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var input = document.getElementById("addroot-path");
      var p = input.value.trim();
      if (!p) return;
      rootsRequest({ add: p });
    });
  }
  document.querySelectorAll(".root-remove").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      rootsRequest({ remove: btn.dataset.root });
    });
  });

  // ---- ファイルツリー/ピン留め: 現在のノートをハイライトして展開 ----
  if (currentPath) {
    var links = document.querySelectorAll(".tree a[data-path], .pins a[data-path]");
    for (var i = 0; i < links.length; i++) {
      if (links[i].dataset.path === currentPath) {
        links[i].classList.add("active");
        var d = links[i].closest("details");
        while (d) {
          d.open = true;
          d = d.parentElement ? d.parentElement.closest("details") : null;
        }
        links[i].scrollIntoView({ block: "nearest" });
        break;
      }
    }
  }

  // ---- クイックスイッチャー（⌘K）----
  var overlay = document.getElementById("palette-overlay");
  var paletteInput = document.getElementById("palette-input");
  var paletteList = document.getElementById("palette-list");
  var paletteNotes = null;
  var paletteSel = 0;

  function paletteOpen() {
    overlay.hidden = false;
    paletteInput.value = "";
    paletteSel = 0;
    paletteInput.focus();
    if (paletteNotes === null) {
      fetch("/api/notes")
        .then(function (r) { return r.json(); })
        .then(function (list) { paletteNotes = list; paletteRender(); });
    } else {
      paletteRender();
    }
  }
  function paletteClose() { overlay.hidden = true; }

  function fuzzyMatches(list, q) {
    if (!list) return [];
    if (!q) return list.slice(0, 12);
    var lq = q.toLowerCase();
    var scored = [];
    for (var i = 0; i < list.length; i++) {
      var p = list[i];
      var lp = p.toLowerCase();
      var idx = lp.indexOf(lq);
      var score;
      if (idx >= 0) {
        // ファイル名部分での一致を優先
        var nameIdx = lp.lastIndexOf("/") + 1;
        score = (idx >= nameIdx ? 0 : 1000) + idx;
      } else {
        // サブシーケンス一致
        var qi = 0;
        for (var ci = 0; ci < lp.length && qi < lq.length; ci++) {
          if (lp[ci] === lq[qi]) qi++;
        }
        if (qi < lq.length) continue;
        score = 5000 + lp.length;
      }
      scored.push([score, p]);
    }
    scored.sort(function (a, b) { return a[0] - b[0] || (a[1] < b[1] ? -1 : 1); });
    return scored.map(function (s) { return s[1]; });
  }

  function paletteMatches(q) {
    return fuzzyMatches(paletteNotes, q).slice(0, 12);
  }

  function paletteRender() {
    var items = paletteMatches(paletteInput.value.trim());
    if (paletteSel >= items.length) paletteSel = Math.max(0, items.length - 1);
    paletteList.innerHTML = "";
    items.forEach(function (p, i) {
      var div = document.createElement("div");
      div.className = "palette-item" + (i === paletteSel ? " selected" : "");
      div.textContent = p;
      div.addEventListener("click", function () {
        location.href = "/note?path=" + encodeURIComponent(p);
      });
      paletteList.appendChild(div);
    });
  }

  if (paletteInput) {
    paletteInput.addEventListener("input", function () { paletteSel = 0; paletteRender(); });
    paletteInput.addEventListener("keydown", function (e) {
      var items = paletteList.querySelectorAll(".palette-item");
      if (e.key === "ArrowDown") {
        e.preventDefault();
        paletteSel = Math.min(paletteSel + 1, items.length - 1);
        paletteRender();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        paletteSel = Math.max(paletteSel - 1, 0);
        paletteRender();
      } else if (e.key === "Enter") {
        e.preventDefault();
        var sel = items[paletteSel];
        if (!sel) return;
        var page = e.metaKey || e.ctrlKey ? "/edit" : "/note";
        location.href = page + "?path=" + encodeURIComponent(sel.textContent);
      } else if (e.key === "Escape") {
        paletteClose();
      }
    });
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) paletteClose();
    });
  }

  // ---- グローバルショートカット ----
  document.addEventListener("keydown", function (e) {
    var mod = e.metaKey || e.ctrlKey;
    if (mod && e.key === "k") {
      e.preventDefault();
      if (overlay.hidden) paletteOpen();
      else paletteClose();
      return;
    }
    if (mod && e.key === "e" && window.__toggleMode) {
      e.preventDefault();
      window.__toggleMode();
    }
  });

  // ---- ノートページ（vim 風モーダル編集）----
  var ta = document.getElementById("editor");
  if (!ta) return;
  var notePage = document.getElementById("note-page");
  var viewEl = document.getElementById("view");
  var modeBadge = document.getElementById("mode-badge");
  var status = document.getElementById("save-status");
  var conflictBanner = document.getElementById("conflict-banner");
  var conflictMsg = document.getElementById("conflict-msg");
  var path = ta.dataset.path;
  var noteDir = ta.dataset.dir;
  var baseMtime = parseInt(ta.dataset.mtime, 10) || 0;
  var mode = "normal";
  var lastCursor = 0;
  var pendingHtml = null; // INSERT 中に届いた最新レンダリング（Esc で反映）
  var dirty = false;
  var saving = false;
  var queued = false;
  var timer = null;
  var pendingG = 0;

  function setStatus(text, cls) {
    if (!status) return;
    status.textContent = text;
    status.className = "status " + (cls || "");
  }

  function showConflict(msg) {
    if (conflictMsg && msg) conflictMsg.textContent = msg;
    if (conflictBanner) conflictBanner.hidden = false;
  }
  function hideConflict() {
    if (conflictBanner) conflictBanner.hidden = true;
  }

  function setMode(m) {
    mode = m;
    var insert = m === "insert";
    notePage.classList.toggle("mode-insert", insert);
    ta.hidden = !insert;
    if (modeBadge) {
      modeBadge.textContent = insert ? "INSERT" : "NORMAL";
      modeBadge.classList.toggle("insert", insert);
    }
  }

  function enterInsert(pos) {
    setMode("insert");
    ta.focus();
    var p = typeof pos === "number" ? pos : lastCursor;
    p = Math.min(p, ta.value.length);
    ta.setSelectionRange(p, p);
  }

  function exitInsert() {
    lastCursor = ta.selectionStart;
    setMode("normal");
    if (pendingHtml !== null) {
      viewEl.innerHTML = pendingHtml;
      renderExtras(viewEl);
      pendingHtml = null;
    }
    if (dirty) {
      clearTimeout(timer);
      save(false);
    }
    ta.blur();
  }

  window.__toggleMode = function () {
    if (mode === "normal") enterInsert();
    else exitInsert();
  };

  function save(force) {
    if (saving) {
      queued = true;
      return;
    }
    saving = true;
    setStatus("保存中…", "saving");
    fetch("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path: path,
        content: ta.value,
        base_mtime: force || !baseMtime ? null : baseMtime,
      }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.ok) {
          dirty = false;
          hideConflict();
          if (data.mtime) baseMtime = data.mtime;
          if (typeof data.html === "string") {
            if (mode === "normal") {
              viewEl.innerHTML = data.html;
              renderExtras(viewEl);
              pendingHtml = null;
            } else {
              pendingHtml = data.html;
            }
          }
          setStatus("保存済み " + new Date().toLocaleTimeString(), "saved");
        } else if (data.conflict) {
          setStatus("競合検知", "error");
          showConflict("ファイルが外部で変更されています。どちらを残すか選んでください。");
        } else {
          setStatus("保存失敗: " + (data.error || "不明なエラー"), "error");
        }
      })
      .catch(function (err) {
        setStatus("保存失敗: " + err, "error");
      })
      .finally(function () {
        saving = false;
        if (queued) {
          queued = false;
          save(false);
        }
      });
  }

  var btnReload = document.getElementById("btn-conflict-reload");
  var btnForce = document.getElementById("btn-conflict-force");
  if (btnReload) btnReload.addEventListener("click", function () { location.reload(); });
  if (btnForce) btnForce.addEventListener("click", function () { hideConflict(); save(true); });

  ta.addEventListener("input", function () {
    dirty = true;
    setStatus("未保存", "dirty");
    clearTimeout(timer);
    timer = setTimeout(function () { save(false); }, 700);
  });

  window.addEventListener("beforeunload", function (e) {
    if (dirty) e.preventDefault();
  });

  function insertAtCursor(text) {
    var s = ta.selectionStart;
    var epos = ta.selectionEnd;
    ta.setRangeText(text, s, epos, "end");
    ta.focus();
    ta.dispatchEvent(new Event("input"));
  }

  // ---- INSERT モード内のキー操作 ----
  ta.addEventListener("keydown", function (e) {
    if (e.key === "Tab") {
      // wikilink サジェスト表示中の Tab は選択に使う（後段のハンドラに任せる）
      if (typeof wlBox !== "undefined" && wlBox && !wlBox.hidden) return;
      e.preventDefault();
      insertAtCursor("  ");
    }
  });

  // Esc はドキュメントレベルで拾う（テンプレボタン等にフォーカスが移っていても効くように）。
  // IME 変換中の Esc は変換キャンセルなのでモードは変えない。
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" || mode !== "insert") return;
    if (e.isComposing || e.keyCode === 229) return;
    if (e.target === paletteInput || !overlay.hidden) return; // パレットの Esc は閉じる操作
    e.preventDefault();
    exitInsert();
  });

  document.addEventListener("keydown", function (e) {
    var mod = e.metaKey || e.ctrlKey;
    if (mod && e.key === "s") {
      e.preventDefault();
      clearTimeout(timer);
      save(false);
      return;
    }
    // ⌘; で現在時刻を挿入（MTG 中の発言メモ用。⌘T はブラウザに取られるため）
    if (mod && e.key === ";" && mode === "insert") {
      e.preventDefault();
      var d = new Date();
      insertAtCursor(pad(d.getHours()) + ":" + pad(d.getMinutes()) + " ");
    }
  });

  // ---- NORMAL モードの vim 風キーバインド ----
  var SCROLL_STEP = 70;
  document.addEventListener("keydown", function (e) {
    if (mode !== "normal") return;
    if (!overlay.hidden) return; // パレット表示中
    if (isTyping()) return; // サイドバーの入力欄など
    if (e.ctrlKey && !e.metaKey && !e.altKey) {
      if (e.key === "d" || e.key === "u") {
        e.preventDefault();
        var half = contentEl.clientHeight / 2;
        contentEl.scrollBy({ top: e.key === "d" ? half : -half });
      }
      return;
    }
    if (e.metaKey || e.altKey) return;
    switch (e.key) {
      case "i":
      case "a":
        e.preventDefault();
        enterInsert();
        break;
      case "A":
        e.preventDefault();
        enterInsert(ta.value.length);
        break;
      case "o":
        e.preventDefault();
        enterInsert(ta.value.length);
        if (ta.value.length && !ta.value.endsWith("\n")) {
          insertAtCursor("\n");
        }
        break;
      case "j":
        e.preventDefault();
        contentEl.scrollBy({ top: SCROLL_STEP });
        break;
      case "k":
        e.preventDefault();
        contentEl.scrollBy({ top: -SCROLL_STEP });
        break;
      case "G":
        e.preventDefault();
        contentEl.scrollTo({ top: contentEl.scrollHeight });
        break;
      case "g":
        if (pendingG && Date.now() - pendingG < 600) {
          e.preventDefault();
          contentEl.scrollTo({ top: 0 });
          pendingG = 0;
        } else {
          pendingG = Date.now();
        }
        break;
      case "/": {
        e.preventDefault();
        var search = document.querySelector(".search input");
        if (search) search.focus();
        break;
      }
    }
    if (e.key !== "g") pendingG = 0;
  });

  // ---- 初期モード / 新規デイリーノートのテンプレート展開 ----
  var dailyDir = ta.dataset.dailyDir;
  var startInsert = ta.dataset.startMode === "insert";
  if (startInsert) setMode("insert");
  if (ta.dataset.new === "1" && !ta.value && dailyDir && path.indexOf(dailyDir + "/") === 0) {
    fetch("/api/template?name=daily")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!ta.value && d.content) {
          ta.value = fillPlaceholders(d.content);
          if (mode === "insert") {
            ta.focus();
            ta.setSelectionRange(ta.value.length, ta.value.length);
          }
        }
      })
      .catch(function () {});
  } else if (startInsert) {
    ta.focus();
    ta.setSelectionRange(ta.value.length, ta.value.length);
  }

  // ---- テンプレート挿入・編集 ----
  var tplSelect = document.getElementById("tpl-select");
  var tplInsert = document.getElementById("tpl-insert");
  var tplEdit = document.getElementById("tpl-edit");
  if (tplInsert && tplSelect) {
    tplInsert.addEventListener("click", function () {
      fetch("/api/template?name=" + encodeURIComponent(tplSelect.value))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d.content) return;
          if (mode === "normal") enterInsert(ta.value.length);
          insertAtCursor(fillPlaceholders(d.content));
        })
        .catch(function () {});
    });
  }
  if (tplEdit && tplSelect) {
    tplEdit.addEventListener("click", function () {
      var dir = tplEdit.dataset.templatesDir;
      location.href =
        "/edit?path=" + encodeURIComponent(dir + "/" + tplSelect.value + ".md");
    });
  }

  // ---- ノート操作メニュー（ピン留め・リネーム/移動・削除） ----
  var noteMenu = document.getElementById("note-menu");
  function closeMenu() {
    if (noteMenu) noteMenu.removeAttribute("open");
  }
  var btnPin = document.getElementById("btn-pin");
  if (btnPin) {
    btnPin.addEventListener("click", function () {
      closeMenu();
      fetch("/api/pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path, pinned: btnPin.dataset.pinned !== "1" }),
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.ok) location.reload();
          else setStatus(d.error || "ピン留めに失敗しました", "error");
        })
        .catch(function (err) { setStatus("ピン留めに失敗: " + err, "error"); });
    });
  }

  var renameBanner = document.getElementById("rename-banner");
  var renameInput = document.getElementById("rename-input");
  var btnRename = document.getElementById("btn-rename");
  if (btnRename && renameBanner && renameInput) {
    btnRename.addEventListener("click", function () {
      closeMenu();
      renameBanner.hidden = false;
      renameInput.focus();
      renameInput.setSelectionRange(0, renameInput.value.length);
    });
    function doRename() {
      var to = renameInput.value.trim();
      if (!to || to === path) {
        renameBanner.hidden = true;
        return;
      }
      fetch("/api/rename", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ from: path, to: to }),
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.ok && d.to) {
            location.href = "/note?path=" + encodeURIComponent(d.to);
          } else {
            setStatus(d.error || "変更に失敗しました", "error");
          }
        })
        .catch(function (err) { setStatus("変更に失敗: " + err, "error"); });
    }
    document.getElementById("btn-rename-do").addEventListener("click", doRename);
    document.getElementById("btn-rename-cancel").addEventListener("click", function () {
      renameBanner.hidden = true;
    });
    renameInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); doRename(); }
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        renameBanner.hidden = true;
      }
    });
  }

  var deleteBanner = document.getElementById("delete-banner");
  var btnDelete = document.getElementById("btn-delete");
  if (btnDelete && deleteBanner) {
    btnDelete.addEventListener("click", function () {
      closeMenu();
      deleteBanner.hidden = false;
    });
    document.getElementById("btn-delete-do").addEventListener("click", function () {
      fetch("/api/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path }),
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.ok) {
            dirty = false;
            location.href = "/";
          } else {
            setStatus(d.error || "削除に失敗しました", "error");
          }
        })
        .catch(function (err) { setStatus("削除に失敗: " + err, "error"); });
    });
    document.getElementById("btn-delete-cancel").addEventListener("click", function () {
      deleteBanner.hidden = true;
    });
  }

  // ---- wikilink 補完（INSERT 中に [[ でサジェスト） ----
  var wlBox = document.createElement("div");
  wlBox.id = "wl-suggest";
  wlBox.hidden = true;
  document.body.appendChild(wlBox);
  var wlItems = [];
  var wlSel = 0;
  var wlStart = -1; // "[[" の直後のカーソル位置

  function wlClose() {
    wlBox.hidden = true;
    wlItems = [];
    wlStart = -1;
  }

  function wlStemCounts() {
    var counts = {};
    (paletteNotes || []).forEach(function (p) {
      var stem = p.replace(/\.md$/i, "").split("/").pop().toLowerCase();
      counts[stem] = (counts[stem] || 0) + 1;
    });
    return counts;
  }

  function wlPick(item) {
    if (wlStart < 0) return;
    var noExt = item.replace(/\.md$/i, "");
    var stem = noExt.split("/").pop();
    var counts = wlStemCounts();
    // stem が一意ならファイル名だけ、重複するならパスで挿入する
    var text = counts[stem.toLowerCase()] === 1 ? stem : noExt;
    var end = ta.selectionStart;
    ta.setRangeText(text + "]]", wlStart, end, "end");
    ta.focus();
    ta.dispatchEvent(new Event("input"));
    wlClose();
  }

  function caretPosition() {
    // ミラー要素でキャレットの画面座標を測る
    var mirror = document.createElement("div");
    var style = getComputedStyle(ta);
    [
      "fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing",
      "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
      "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth",
      "boxSizing",
    ].forEach(function (prop) { mirror.style[prop] = style[prop]; });
    mirror.style.position = "fixed";
    mirror.style.visibility = "hidden";
    mirror.style.whiteSpace = "pre-wrap";
    mirror.style.wordBreak = "break-word";
    mirror.style.overflow = "hidden";
    mirror.style.width = ta.clientWidth + "px";
    mirror.textContent = ta.value.slice(0, ta.selectionStart);
    var marker = document.createElement("span");
    marker.textContent = "|";
    mirror.appendChild(marker);
    document.body.appendChild(mirror);
    var rect = ta.getBoundingClientRect();
    var lineHeight = parseFloat(style.lineHeight) || 20;
    var x = rect.left + marker.offsetLeft - ta.scrollLeft;
    var y = rect.top + marker.offsetTop - ta.scrollTop + lineHeight;
    document.body.removeChild(mirror);
    return { x: x, y: y };
  }

  function wlRender(query) {
    var matches = fuzzyMatches(paletteNotes, query).slice(0, 8);
    wlItems = matches;
    if (!matches.length) {
      wlClose();
      return;
    }
    if (wlSel >= matches.length) wlSel = matches.length - 1;
    wlBox.innerHTML = "";
    matches.forEach(function (p, i) {
      var div = document.createElement("div");
      div.className = "wl-item" + (i === wlSel ? " selected" : "");
      div.textContent = p;
      div.addEventListener("mousedown", function (e) {
        e.preventDefault();
        wlPick(p);
      });
      wlBox.appendChild(div);
    });
    var pos = caretPosition();
    wlBox.hidden = false;
    var maxX = window.innerWidth - wlBox.offsetWidth - 8;
    var maxY = window.innerHeight - wlBox.offsetHeight - 8;
    wlBox.style.left = Math.max(8, Math.min(pos.x, maxX)) + "px";
    wlBox.style.top = Math.min(pos.y + 4, maxY) + "px";
  }

  function wlCheck() {
    if (mode !== "insert") {
      wlClose();
      return;
    }
    var pos = ta.selectionStart;
    var before = ta.value.slice(0, pos);
    var open = before.lastIndexOf("[[");
    if (open < 0) {
      wlClose();
      return;
    }
    var frag = before.slice(open + 2);
    if (frag.length > 60 || frag.indexOf("]") >= 0 || frag.indexOf("\n") >= 0) {
      wlClose();
      return;
    }
    wlStart = open + 2;
    if (paletteNotes === null) {
      fetch("/api/notes")
        .then(function (r) { return r.json(); })
        .then(function (list) {
          paletteNotes = list;
          wlRender(frag);
        })
        .catch(function () {});
    } else {
      wlRender(frag);
    }
  }

  ta.addEventListener("input", wlCheck);
  ta.addEventListener("click", wlCheck);
  ta.addEventListener("keydown", function (e) {
    if (wlBox.hidden) return;
    if (e.isComposing || e.keyCode === 229) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      wlSel = Math.min(wlSel + 1, wlItems.length - 1);
      wlRender(ta.value.slice(wlStart, ta.selectionStart));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      wlSel = Math.max(wlSel - 1, 0);
      wlRender(ta.value.slice(wlStart, ta.selectionStart));
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      var item = wlItems[wlSel];
      if (item) wlPick(item);
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation(); // INSERT モードは抜けず、サジェストだけ閉じる
      wlClose();
    }
  });

  // ---- クリップボード画像貼り付け ----
  ta.addEventListener("paste", function (e) {
    var items = (e.clipboardData || {}).items || [];
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      if (item.kind !== "file" || item.type.indexOf("image/") !== 0) continue;
      e.preventDefault();
      var file = item.getAsFile();
      var ext = (item.type.split("/")[1] || "png").replace("jpeg", "jpg");
      setStatus("画像アップロード中…", "saving");
      fetch("/api/upload?dir=" + encodeURIComponent(noteDir) + "&ext=" + encodeURIComponent(ext), {
        method: "POST",
        body: file,
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.ok && d.insert) {
            insertAtCursor("![](" + d.insert + ")");
          } else {
            setStatus("画像アップロード失敗: " + (d.error || ""), "error");
          }
        })
        .catch(function (err) { setStatus("画像アップロード失敗: " + err, "error"); });
      return;
    }
  });

  // ---- 外部変更の監視（タブ表示中のみ 3 秒ごと）----
  // NORMAL かつ未編集なら自動リロード（スクロール位置維持）、編集中なら競合警告。
  var scrollKey = "scroll:" + location.pathname + location.search;
  var savedScroll = sessionStorage.getItem(scrollKey);
  if (savedScroll !== null && contentEl) {
    contentEl.scrollTop = parseInt(savedScroll, 10);
    sessionStorage.removeItem(scrollKey);
  }
  function checkExternal() {
    if (saving) return;
    fetch("/api/mtime?path=" + encodeURIComponent(path))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.mtime || !baseMtime || d.mtime <= baseMtime) return;
        if (mode === "normal" && !dirty) {
          sessionStorage.setItem(scrollKey, contentEl ? contentEl.scrollTop : 0);
          location.reload();
        } else if (conflictBanner && conflictBanner.hidden) {
          showConflict("他のプロセスがこのファイルを変更しました（保存すると競合します）。");
        }
      })
      .catch(function () {});
  }
  setInterval(function () {
    if (document.hidden) return;
    checkExternal();
  }, 3000);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) checkExternal();
  });
})();
