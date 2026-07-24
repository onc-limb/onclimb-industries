(function () {
  "use strict";

  var params = new URLSearchParams(location.search);
  var currentPath = params.get("path");

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

  // ---- 新規ノート作成フォーム（サイドバー）----
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

  // ---- ファイルツリー: 現在のノートをハイライトして展開 ----
  if (currentPath) {
    var links = document.querySelectorAll(".tree a[data-path]");
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

  function paletteMatches(q) {
    if (!paletteNotes) return [];
    if (!q) return paletteNotes.slice(0, 12);
    var lq = q.toLowerCase();
    var scored = [];
    for (var i = 0; i < paletteNotes.length; i++) {
      var p = paletteNotes[i];
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
    return scored.slice(0, 12).map(function (s) { return s[1]; });
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
    if (mod && e.key === "e" && currentPath) {
      e.preventDefault();
      var toEdit = location.pathname === "/note";
      location.href = (toEdit ? "/edit" : "/note") + "?path=" + encodeURIComponent(currentPath);
    }
  });

  // ---- 閲覧ページ: 外部変更の自動リロード（スクロール位置維持）----
  var watch = document.querySelector("[data-watch-path]");
  var contentEl = document.querySelector(".content");
  if (watch && contentEl) {
    var scrollKey = "scroll:" + location.pathname + location.search;
    var savedScroll = sessionStorage.getItem(scrollKey);
    if (savedScroll !== null) {
      contentEl.scrollTop = parseInt(savedScroll, 10);
      sessionStorage.removeItem(scrollKey);
    }
    var watchBase = parseInt(watch.dataset.mtime, 10) || 0;
    var checkExternal = function () {
      fetch("/api/mtime?path=" + encodeURIComponent(watch.dataset.watchPath))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.mtime && watchBase && d.mtime > watchBase) {
            sessionStorage.setItem(scrollKey, contentEl.scrollTop);
            location.reload();
          }
        })
        .catch(function () {});
    };
    // タブが見えているときだけポーリングする（常駐サーバーの負荷をゼロに近づける）
    setInterval(function () {
      if (document.hidden) return;
      checkExternal();
    }, 3000);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) checkExternal();
    });
  }

  // ---- エディタ ----
  var ta = document.getElementById("editor");
  if (!ta) return;
  var preview = document.getElementById("preview");
  var status = document.getElementById("save-status");
  var conflictBanner = document.getElementById("conflict-banner");
  var conflictMsg = document.getElementById("conflict-msg");
  var path = ta.dataset.path;
  var noteDir = ta.dataset.dir;
  var baseMtime = parseInt(ta.dataset.mtime, 10) || 0;
  var dirty = false;
  var saving = false;
  var queued = false;
  var timer = null;

  // 新規デイリーノートには daily テンプレートを自動で敷く（保存はユーザーが書き始めてから）
  var dailyDir = ta.dataset.dailyDir;
  if (ta.dataset.new === "1" && !ta.value && dailyDir && path.indexOf(dailyDir + "/") === 0) {
    fetch("/api/template?name=daily")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!ta.value && d.content) {
          ta.value = fillPlaceholders(d.content);
          ta.focus();
          ta.setSelectionRange(ta.value.length, ta.value.length);
        }
      })
      .catch(function () {});
  } else {
    ta.focus();
  }

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
          if (preview && typeof data.html === "string") {
            preview.innerHTML = data.html;
            renderExtras(preview);
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

  document.addEventListener("keydown", function (e) {
    var mod = e.metaKey || e.ctrlKey;
    if (mod && e.key === "s") {
      e.preventDefault();
      clearTimeout(timer);
      save(false);
    }
    // ⌘; で現在時刻を挿入（MTG 中の発言メモ用。⌘T はブラウザに取られるため）
    if (mod && e.key === ";") {
      e.preventDefault();
      var d = new Date();
      insertAtCursor(pad(d.getHours()) + ":" + pad(d.getMinutes()) + " ");
    }
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

  // Tab キーでスペース 2 個を挿入
  ta.addEventListener("keydown", function (e) {
    if (e.key === "Tab") {
      e.preventDefault();
      insertAtCursor("  ");
    }
  });

  // ---- テンプレート挿入 ----
  var tplSelect = document.getElementById("tpl-select");
  var tplInsert = document.getElementById("tpl-insert");
  if (tplInsert && tplSelect) {
    tplInsert.addEventListener("click", function () {
      fetch("/api/template?name=" + encodeURIComponent(tplSelect.value))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.content) insertAtCursor(fillPlaceholders(d.content));
        })
        .catch(function () {});
    });
  }

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

  // ---- 編集中の外部変更を早期警告（保存前に気づけるように）----
  // タブ非表示中はポーリングしない
  setInterval(function () {
    if (document.hidden || saving) return;
    fetch("/api/mtime?path=" + encodeURIComponent(path))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.mtime && baseMtime && d.mtime > baseMtime && conflictBanner && conflictBanner.hidden) {
          showConflict("他のプロセスがこのファイルを変更しました（保存すると競合します）。");
        }
      })
      .catch(function () {});
  }, 5000);
})();
